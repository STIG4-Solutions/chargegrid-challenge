"""Gateways de pagamento atras de uma interface unica.

O desafio deixa a escolha do gateway em aberto. O acoplamento fica aqui: trocar
Pix por Stripe (ou somar os dois) e escrever uma classe, nao mexer no dominio.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal

import httpx

from app.core.config import settings
from app.core.errors import PaymentError
from app.models.enums import PaymentMethodKind, PaymentStatus

# Token OAuth do Pix por (base_url, client_id). De modulo, e nao da instancia,
# porque `get_provider` monta um provedor novo a cada cobranca - ver `_token`.
_TOKENS_PIX: dict[tuple[str, str], tuple[str, float]] = {}

# Os estados que a API Pix usa para uma cobranca imediata.
_ESTADO_DA_COBRANCA = {
    "ATIVA": PaymentStatus.PENDING,
    "CONCLUIDA": PaymentStatus.CAPTURED,
    "REMOVIDA_PELO_USUARIO_RECEBEDOR": PaymentStatus.FAILED,
    "REMOVIDA_PELO_PSP": PaymentStatus.FAILED,
}
_ESTADOS_VIVOS = {"ATIVA", "CONCLUIDA"}


def _detalhe_do_erro(resposta: httpx.Response) -> str:
    """Mensagem do PSP, quando ha uma, sem despejar o corpo inteiro no log.

    A API Pix erra em RFC 7807 (`title`/`detail`). Quando nao for isso, corta-se
    o corpo: resposta de erro pode conter o que foi enviado, e o que foi enviado
    inclui dados do pagador.
    """
    try:
        dados = resposta.json()
    except ValueError:
        return f"HTTP {resposta.status_code}"
    if isinstance(dados, dict):
        detalhe = dados.get("detail") or dados.get("title") or dados.get("mensagem")
        if detalhe:
            violacoes = dados.get("violacoes") or []
            if violacoes:
                razoes = "; ".join(
                    str(v.get("razao", v)) for v in violacoes if isinstance(v, dict) or v
                )
                return f"{detalhe} ({razoes})"
            return str(detalhe)
    return f"HTTP {resposta.status_code}"


def _resumo_da_cobranca(dados: dict) -> dict:
    """O que vale a pena guardar em `Payment.raw_response`.

    A resposta inteira vai para o banco e fica la'. `devedor` traz CPF e nome do
    pagador, que ja estao em `users` - repetir dado pessoal numa coluna JSON que
    ninguem indexa nem expira e' guardar risco sem ganho.
    """
    return {
        "txid": dados.get("txid"),
        "status": dados.get("status"),
        "valor": (dados.get("valor") or {}).get("original"),
        "expiracao": (dados.get("calendario") or {}).get("expiracao"),
        "revisao": dados.get("revisao"),
    }


@dataclass(slots=True)
class ChargeRequest:
    amount: Decimal
    currency: str
    method: PaymentMethodKind
    reference: str
    description: str
    payer_document: str | None = None
    payer_email: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class ChargeResponse:
    status: PaymentStatus
    provider_ref: str
    qr_code: str | None = None
    failure_reason: str | None = None
    raw: dict = field(default_factory=dict)


class PaymentProvider(ABC):
    name = "abstract"

    @abstractmethod
    async def create_charge(self, request: ChargeRequest) -> ChargeResponse: ...

    @abstractmethod
    async def capture(self, provider_ref: str, amount: Decimal) -> ChargeResponse: ...

    @abstractmethod
    async def refund(self, provider_ref: str, amount: Decimal) -> ChargeResponse: ...

    def __init__(self, config: dict | None = None):
        # Config do estabelecimento (SitePaymentMethod.provider_config). Fica na
        # instancia, nao na classe: um dict como atributo de classe seria o mesmo
        # objeto para todos os provedores de todos os sites.
        self.config = config or {}

    @property
    def webhook_secret(self) -> str:
        return self.config.get("webhook_secret") or settings.payment_webhook_secret

    def traduzir_webhook(self, corpo: dict) -> list[dict]:
        """Converte o corpo do PSP nos eventos que `handle_webhook` entende.

        Um evento por padrao, porque e' o que a maioria dos PSPs manda. O Pix
        manda uma LISTA - dai o metodo existir em vez de a rota supor a forma.
        """
        return [corpo]

    def verify_webhook(self, body: bytes, signature: str | None) -> bool:
        """HMAC do corpo cru: sem isso qualquer um marca fatura como paga.

        O segredo sai de `webhook_secret`, nao mais direto das settings. Antes,
        `provedor_do_evento` descobria de qual estabelecimento era o evento e
        montava o provedor com a config dele - e a verificacao ignorava tudo
        isso, usando sempre o segredo global. Com dois sites em PSPs diferentes,
        so um funcionava: os webhooks legitimos do outro tomavam 401.
        """
        if not signature:
            return False
        expected = hmac.new(self.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


class MockProvider(PaymentProvider):
    """Provedor de desenvolvimento: aprova na hora e devolve um Pix ficticio."""

    name = "mock"

    async def create_charge(self, request: ChargeRequest) -> ChargeResponse:
        ref = f"mock_{uuid.uuid4().hex[:16]}"
        if request.method == PaymentMethodKind.PIX:
            return ChargeResponse(
                status=PaymentStatus.PENDING,
                provider_ref=ref,
                qr_code=(
                    f"00020126580014BR.GOV.BCB.PIX0136{uuid.uuid4()}"
                    f"5204000053039865802BR5913CHARGEGRID6009SAO PAULO62070503***6304"
                ),
                raw={"simulated": True, "amount": float(request.amount)},
            )
        if request.method == PaymentMethodKind.WALLET:
            return ChargeResponse(status=PaymentStatus.CAPTURED, provider_ref=ref)
        return ChargeResponse(status=PaymentStatus.AUTHORIZED, provider_ref=ref)

    async def capture(self, provider_ref: str, amount: Decimal) -> ChargeResponse:
        return ChargeResponse(status=PaymentStatus.CAPTURED, provider_ref=provider_ref)

    async def refund(self, provider_ref: str, amount: Decimal) -> ChargeResponse:
        return ChargeResponse(status=PaymentStatus.REFUNDED, provider_ref=provider_ref)


class PixProvider(PaymentProvider):
    """PSP Pix pela API do BACEN: cobranca imediata e liquidacao por webhook.

    As credenciais e a URL vem de `SitePaymentMethod.provider_config`, para cada
    estabelecimento usar a propria conta - o dinheiro cai direto no lojista, e
    nao numa conta da rede que depois teria de repassar.

    O QUE ESTA E O QUE NAO ESTA EXERCITADO. O codigo abaixo fala a API Pix como
    ela e' especificada, e os testes o exercitam contra um PSP de mentira
    (`httpx.MockTransport`) - chamadas, cabecalhos, corpos, codigos de erro e
    renovacao de token. O que NAO existe e' uma unica execucao contra um PSP de
    verdade: nao ha conta contratada. Entao trate isto como integracao
    **escrita e testada, nao homologada** - o primeiro contato com um PSP real
    vai encontrar divergencias de detalhe, porque sempre encontra.

    ONDE A ESPECIFICACAO E' MAIS APERTADA DO QUE PARECE:

      - `txid` aceita `[a-zA-Z0-9]{26,35}` e mais nada. `INV-1042` tem hifen e
        oito caracteres: usar o codigo da fatura direto e' recusado pelo PSP.
      - `PUT /v2/cob/{txid}` e' idempotente POR CONSTRUCAO, e e' por isso que
        se usa PUT com txid proprio em vez de `POST /v2/cob` com txid do PSP:
        o retry de uma resposta perdida na rede reaproveita a mesma cobranca em
        vez de criar a segunda.
      - o valor vai como STRING com duas casas (`"10.00"`). Mandar numero e' o
        erro classico: 10.1 vira "10.1" e o PSP recusa.
      - a autenticacao e' OAuth2 client_credentials SOBRE mTLS. O certificado
        nao e' opcional nem detalhe de infra: sem ele o PSP recusa o handshake
        antes de olhar o `client_secret`.
    """

    name = "pix"

    # Renova o token antes do fim. Trinta segundos cobrem a latencia da chamada
    # seguinte sem desperdicar token valido.
    FOLGA_DO_TOKEN = 30

    # Quanto tempo a cobranca fica em pe'. Uma hora e' o costume do mercado para
    # pagamento presencial; abaixo disso o motorista que sai do carro para
    # buscar o celular perde a cobranca.
    EXPIRACAO_PADRAO = 3600

    TEMPO_LIMITE = 20.0

    def _exigir(self, chave: str) -> str:
        valor = self.config.get(chave)
        if not valor:
            raise PaymentError(
                f"configuração do Pix incompleta: falta '{chave}' em provider_config"
            )
        return str(valor)

    @property
    def base_url(self) -> str:
        return self._exigir("base_url").rstrip("/")

    def _cliente(self) -> httpx.AsyncClient:
        """Cliente HTTP com o certificado do estabelecimento.

        `cert` e' o que faz o mTLS acontecer. Sem ele o PSP encerra a conexao no
        handshake, e o erro que chega aqui fala de TLS, nao de credencial - o
        que manda quem esta depurando para o lado errado. Dai a mensagem
        explicita em `_exigir`.
        """
        certificado = self.config.get("certificado")
        chave = self.config.get("chave_privada")
        cert = None
        if certificado and chave:
            cert = (certificado, chave)
        elif certificado:
            cert = certificado

        # Costura para o teste trocar a rede por um PSP de mentira
        # (`httpx.MockTransport`). Nada em producao escreve esta chave, e o
        # nome com underscore diz isso a quem ler um `provider_config` real.
        # A alternativa - subclasse so' para teste - faria os testes exercitarem
        # uma classe que nao e' a que roda.
        transporte = self.config.get("_transporte_de_teste")
        return httpx.AsyncClient(
            base_url=self.base_url,
            cert=cert,
            verify=self.config.get("verify", True),
            timeout=self.TEMPO_LIMITE,
            transport=transporte,
        )

    async def _token(self, cliente: httpx.AsyncClient) -> str:
        """Token OAuth2, reaproveitado enquanto valer.

        O cache e' de MODULO, e nao da instancia, porque `get_provider` monta um
        provedor novo a cada cobranca: um cache de instancia nasceria vazio toda
        vez e cada pagamento gastaria duas viagens ate o PSP em vez de uma.

        A chave inclui o `client_id` para nao misturar estabelecimentos - dois
        sites no mesmo PSP tem credenciais diferentes, e um token vazado de um
        para o outro seria cobranca emitida na conta errada.

        Duas corrotinas podem buscar token ao mesmo tempo e uma sobrescrever a
        outra. E' inofensivo: os dois tokens sao validos, e o perdedor so'
        desperdicou uma chamada. Um lock custaria mais do que resolve.
        """
        client_id = self._exigir("client_id")
        chave_cache = (self.base_url, client_id)
        agora = time.monotonic()
        cacheado = _TOKENS_PIX.get(chave_cache)
        if cacheado and cacheado[1] > agora:
            return cacheado[0]

        resposta = await cliente.post(
            "/oauth/token",
            data={"grant_type": "client_credentials"},
            auth=(client_id, self._exigir("client_secret")),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resposta.status_code >= 400:
            # Sem eco do corpo: resposta de erro de autenticacao costuma repetir
            # o que foi enviado, e o que foi enviado e' o segredo.
            raise PaymentError(
                f"PSP recusou as credenciais do Pix (HTTP {resposta.status_code})"
            )
        dados = resposta.json()
        token = dados.get("access_token")
        if not token:
            raise PaymentError("PSP não devolveu access_token")
        validade = int(dados.get("expires_in", 600))
        _TOKENS_PIX[chave_cache] = (token, agora + max(validade - self.FOLGA_DO_TOKEN, 0))
        return token

    @staticmethod
    def _txid(referencia: str) -> str:
        """Identificador da cobranca no PSP: `[a-zA-Z0-9]{26,35}`.

        DETERMINISTICO a partir da referencia, e e' isso que torna o retry
        seguro: `PUT /v2/cob/{txid}` com o mesmo txid reaproveita a cobranca em
        vez de abrir outra. Sorteado, cada tentativa perdida na rede deixaria uma
        cobranca orfa esperando pagamento.

        O codigo da fatura entra no comeco para a conciliacao manual continuar
        possivel - quem olha o extrato do PSP reconhece `INV1042...`. O resto e'
        hash, que garante o comprimento e evita colisao entre referencias
        parecidas depois de tirar os caracteres proibidos.
        """
        base = "".join(c for c in referencia if c.isalnum())
        digest = hashlib.sha256(referencia.encode()).hexdigest()
        return (base + digest)[:32]

    @staticmethod
    def _valor(quantia: Decimal) -> str:
        """Duas casas, sempre, como string.

        `str(Decimal("10.1"))` e' "10.1" e o PSP recusa; `float` chega a
        "10.100000000000001". A quantizacao aqui e' o que impede os dois.
        """
        return str(quantia.quantize(Decimal("0.01")))

    async def _pedir(
        self, cliente: httpx.AsyncClient, metodo: str, caminho: str, corpo: dict | None = None
    ) -> dict:
        token = await self._token(cliente)
        resposta = await cliente.request(
            metodo,
            caminho,
            json=corpo,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        if resposta.status_code == 401:
            # Token revogado antes da hora: derruba o cache e tenta uma vez.
            # Sem isto, um token invalidado cedo pelo PSP derrubaria toda
            # cobranca ate o cache expirar sozinho.
            _TOKENS_PIX.pop((self.base_url, self.config.get("client_id")), None)
            token = await self._token(cliente)
            resposta = await cliente.request(
                metodo,
                caminho,
                json=corpo,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
        if resposta.status_code >= 400:
            raise PaymentError(f"PSP recusou {metodo} {caminho}: {_detalhe_do_erro(resposta)}")
        return resposta.json()

    async def create_charge(self, request: ChargeRequest) -> ChargeResponse:
        if request.method != PaymentMethodKind.PIX:
            # Recusa explicita em vez de emitir um Pix para quem pediu cartao.
            # Silencio aqui cobraria o cliente pelo meio errado.
            raise PaymentError(f"provedor Pix não atende o método {request.method}")

        txid = self._txid(request.reference)
        corpo = {
            "calendario": {
                "expiracao": int(self.config.get("expiracao_segundos", self.EXPIRACAO_PADRAO))
            },
            "valor": {"original": self._valor(request.amount)},
            "chave": self._exigir("chave_pix"),
            "solicitacaoPagador": request.description[:140],
        }
        if request.payer_document:
            documento = "".join(c for c in request.payer_document if c.isdigit())
            # O PSP valida o tamanho: 11 vira CPF, 14 vira CNPJ, o resto seria
            # recusa da cobranca inteira por um campo que e' OPCIONAL.
            if len(documento) in (11, 14):
                campo = "cpf" if len(documento) == 11 else "cnpj"
                nome = request.metadata.get("payer_name", "")
                corpo["devedor"] = {campo: documento, "nome": nome}
                if not corpo["devedor"]["nome"]:
                    corpo["devedor"].pop("nome")

        async with self._cliente() as cliente:
            dados = await self._pedir(cliente, "PUT", f"/v2/cob/{txid}", corpo)

        copia_e_cola = dados.get("pixCopiaECola")
        return ChargeResponse(
            status=_ESTADO_DA_COBRANCA.get(dados.get("status", ""), PaymentStatus.PENDING),
            # O txid do PSP manda, nao o nosso: alguns devolvem normalizado, e
            # gravar o nosso faria o webhook nao encontrar o pagamento.
            provider_ref=dados.get("txid", txid),
            qr_code=copia_e_cola,
            raw=_resumo_da_cobranca(dados),
        )

    async def consultar(self, txid: str) -> dict:
        async with self._cliente() as cliente:
            return await self._pedir(cliente, "GET", f"/v2/cob/{txid}")

    async def capture(self, provider_ref: str, amount: Decimal) -> ChargeResponse:
        """Pix nao tem captura em duas fases - isto CONSULTA e relata.

        A versao anterior devolvia CAPTURED sem perguntar nada a ninguem. Num
        fluxo que nunca chamava `capture` isso passava despercebido; no dia em
        que alguem chamasse, a fatura viraria paga sem dinheiro ter entrado.
        """
        dados = await self.consultar(provider_ref)
        estado = dados.get("status", "")
        return ChargeResponse(
            status=_ESTADO_DA_COBRANCA.get(estado, PaymentStatus.PENDING),
            provider_ref=provider_ref,
            failure_reason=None if estado in _ESTADOS_VIVOS else estado,
            raw=_resumo_da_cobranca(dados),
        )

    async def refund(self, provider_ref: str, amount: Decimal) -> ChargeResponse:
        """Devolucao: `PUT /v2/pix/{e2eid}/devolucao/{id}`.

        O e2eid nao e' o txid - e' o identificador do Pix RECEBIDO, e so' existe
        depois que alguem pagou. Por isso a consulta antes: devolver sem ela
        exigiria guardar um campo que a cobranca nao tem enquanto esta ATIVA.
        """
        dados = await self.consultar(provider_ref)
        recebidos = dados.get("pix") or []
        if not recebidos:
            raise PaymentError("cobrança Pix ainda não foi paga: não há o que devolver")
        e2eid = recebidos[0].get("endToEndId")
        if not e2eid:
            raise PaymentError("PSP não informou endToEndId do Pix recebido")

        # Id da devolucao tambem deterministico: repetir a chamada nao devolve
        # duas vezes. E' a mesma protecao do txid, no sentido inverso.
        semente = f"{provider_ref}:{self._valor(amount)}".encode()
        devolucao = hashlib.sha256(semente).hexdigest()[:32]
        async with self._cliente() as cliente:
            resultado = await self._pedir(
                cliente,
                "PUT",
                f"/v2/pix/{e2eid}/devolucao/{devolucao}",
                {"valor": self._valor(amount)},
            )
        estado = resultado.get("status", "")
        return ChargeResponse(
            status=(
                PaymentStatus.REFUNDED
                if estado in ("DEVOLVIDO", "EM_PROCESSAMENTO")
                else PaymentStatus.FAILED
            ),
            provider_ref=provider_ref,
            failure_reason=None if estado in ("DEVOLVIDO", "EM_PROCESSAMENTO") else estado,
            raw={"devolucao": devolucao, "status": estado},
        )

    def traduzir_webhook(self, corpo: dict) -> list[dict]:
        """O corpo do PSP Pix nao tem a forma que `handle_webhook` espera.

        O PSP manda `{"pix": [{endToEndId, txid, valor, horario}, ...]}` - uma
        LISTA, sem campo de status, porque a notificacao so' existe quando o
        pagamento aconteceu. `handle_webhook` espera `provider_ref` e `status`
        no topo.

        Sem esta traducao a integracao fica pela metade: a cobranca e' criada e
        o pagamento nunca liquida, que e' o pior dos dois mundos - o motorista
        paga e a fatura continua aberta.
        """
        recebidos = corpo.get("pix")
        if not isinstance(recebidos, list):
            return [corpo]
        return [
            {
                "provider_ref": p.get("txid"),
                "status": "CONCLUIDA",
                "endToEndId": p.get("endToEndId"),
                "valor": p.get("valor"),
                "horario": p.get("horario"),
            }
            for p in recebidos
            if p.get("txid")
        ]


PROVIDERS: dict[str, type[PaymentProvider]] = {"mock": MockProvider, "pix": PixProvider}


def get_provider(name: str | None = None, config: dict | None = None) -> PaymentProvider:
    """Resolve o provedor pelo nome, recusando o que nao conhece.

    O fallback silencioso para MockProvider era perigoso: `payment_provider`
    aceita "stripe" no Literal da config, mas PROVIDERS so registra mock e pix.
    PAYMENT_PROVIDER=stripe passava na validacao e caia no simulador, que
    aprova na hora e devolve uma referencia inventada - a fatura virava paga
    sem dinheiro nenhum ter entrado. O mesmo valia para qualquer erro de
    digitacao no campo livre SitePaymentMethod.provider.

    Um nome desconhecido tem de estourar. Aprovar por engano e' pior do que
    ficar fora do ar.
    """
    escolhido = name or settings.payment_provider
    provider_cls = PROVIDERS.get(escolhido)
    if provider_cls is None:
        raise PaymentError(
            f"provedor de pagamento desconhecido: {escolhido!r} "
            f"(disponíveis: {', '.join(sorted(PROVIDERS))})"
        )
    # A config vai para qualquer provedor, nao so o Pix. Como
    # SitePaymentMethod.provider tem "mock" por padrao, tratar so o Pix
    # descartava a config no caso mais comum - e o segredo de webhook do
    # estabelecimento voltava a ser ignorado, que era o defeito a corrigir.
    return provider_cls(config)
