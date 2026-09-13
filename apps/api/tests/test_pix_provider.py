"""O provedor Pix, contra um PSP de mentira.

NAO HA CONTA CONTRATADA em PSP nenhum, e isso define o que estes testes podem e
nao podem afirmar. Eles exercitam o que o codigo ENVIA e como ele interpreta o
que VOLTA - caminho, cabecalho, corpo, renovacao de token, erro em RFC 7807. O
que nenhum deles prova e' que um PSP real aceita exatamente isso.

E' uma distincao que vale escrever em vez de deixar implicita: a integracao esta
**escrita e testada, nao homologada**. O primeiro contato com um PSP de verdade
vai achar divergencia de detalhe, porque sempre acha.

O PSP de mentira e' `httpx.MockTransport`, entao nao ha rede, nem porta, nem
espera. O provedor recebe o transporte por `provider_config`, que e' a mesma
porta por onde ele recebe URL e credencial em producao.
"""

from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.core.errors import PaymentError
from app.models.enums import PaymentMethodKind, PaymentStatus
from app.services import payment_providers
from app.services.payment_providers import ChargeRequest, PixProvider

TXID_VALIDO = r"^[a-zA-Z0-9]{26,35}$"


@pytest.fixture(autouse=True)
def _sem_token_vazando():
    """O cache de token e' de modulo, entao um teste sujaria o seguinte."""
    payment_providers._TOKENS_PIX.clear()
    yield
    payment_providers._TOKENS_PIX.clear()


class PspFalso:
    """Um PSP Pix que responde o que a especificacao manda, e anota o que ouviu.

    Guardar as requisicoes e' o ponto: metade do que importa numa integracao de
    pagamento nao esta na resposta, esta no que foi ENVIADO - o valor com duas
    casas, o txid no caminho, o Bearer no cabecalho.
    """

    def __init__(self, cobrancas: dict | None = None, token_expira_em: int = 600):
        self.pedidos: list[httpx.Request] = []
        self.tokens_emitidos = 0
        self.cobrancas = cobrancas or {}
        self.token_expira_em = token_expira_em
        self.recusar_token_uma_vez = False
        self.erro_da_cobranca: tuple[int, dict] | None = None

    def transporte(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._responder)

    def _responder(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        caminho = pedido.url.path

        if caminho == "/oauth/token":
            self.tokens_emitidos += 1
            return httpx.Response(
                200,
                json={
                    "access_token": f"tok-{self.tokens_emitidos}",
                    "expires_in": self.token_expira_em,
                    "token_type": "Bearer",
                },
            )

        if self.recusar_token_uma_vez:
            self.recusar_token_uma_vez = False
            return httpx.Response(401, json={"detail": "token expirado"})

        if caminho.startswith("/v2/cob/"):
            txid = caminho.rsplit("/", 1)[-1]
            if pedido.method == "PUT":
                if self.erro_da_cobranca:
                    codigo, corpo = self.erro_da_cobranca
                    return httpx.Response(codigo, json=corpo)
                enviado = json.loads(pedido.content)
                cob = {
                    "txid": txid,
                    "status": "ATIVA",
                    "revisao": 0,
                    "calendario": enviado["calendario"],
                    "valor": enviado["valor"],
                    "chave": enviado["chave"],
                    "pixCopiaECola": f"00020126580014BR.GOV.BCB.PIX...{txid}6304ABCD",
                }
                if "devedor" in enviado:
                    cob["devedor"] = enviado["devedor"]
                self.cobrancas[txid] = cob
                return httpx.Response(201, json=cob)
            return httpx.Response(200, json=self.cobrancas.get(txid, {"status": "ATIVA"}))

        if "/devolucao/" in caminho:
            devolucao = caminho.rsplit("/", 1)[-1]
            return httpx.Response(201, json={"id": devolucao, "status": "DEVOLVIDO"})

        return httpx.Response(404, json={"detail": "rota nao prevista no PSP falso"})


def _provedor(psp: PspFalso, **extra) -> PixProvider:
    config = {
        "base_url": "https://pix.psp-de-mentira.com.br",
        "client_id": "cliente-123",
        "client_secret": "segredo-que-nao-pode-vazar",
        "chave_pix": "recebedor@chargegrid.com.br",
        "_transporte_de_teste": psp.transporte(),
    }
    config.update(extra)
    return PixProvider(config)


def _cobranca(valor="10.00", referencia="INV-1042", **extra) -> ChargeRequest:
    base = {
        "amount": Decimal(valor),
        "currency": "BRL",
        "method": PaymentMethodKind.PIX,
        "reference": referencia,
        "description": "Recarga EV",
    }
    base.update(extra)
    return ChargeRequest(**base)


# --------------------------------------------------------------------- txid


def test_txid_respeita_o_formato_do_bacen():
    """`INV-1042` tem hifen e oito caracteres - o PSP recusaria."""
    import re

    assert re.match(TXID_VALIDO, PixProvider._txid("INV-1042"))
    assert re.match(TXID_VALIDO, PixProvider._txid("X"))
    assert re.match(TXID_VALIDO, PixProvider._txid("INV-" + "9" * 60))


def test_txid_e_deterministico():
    """E' o que faz o retry reaproveitar a cobranca em vez de abrir outra."""
    assert PixProvider._txid("INV-1042") == PixProvider._txid("INV-1042")
    assert PixProvider._txid("INV-1042") != PixProvider._txid("INV-1043")


def test_txid_comeca_pelo_codigo_da_fatura():
    """Para a conciliacao manual no extrato do PSP continuar possivel."""
    assert PixProvider._txid("INV-1042").startswith("INV1042")


# ------------------------------------------------------------------- valor


@pytest.mark.parametrize(
    "entrada,esperado",
    [("10", "10.00"), ("10.1", "10.10"), ("10.005", "10.00"), ("0.5", "0.50")],
)
def test_valor_vai_com_duas_casas(entrada, esperado):
    """`str(Decimal("10.1"))` e' "10.1", e o PSP recusa."""
    assert PixProvider._valor(Decimal(entrada)) == esperado


# --------------------------------------------------------------- cobranca


async def test_cobranca_vai_para_o_caminho_certo():
    psp = PspFalso()
    resposta = await _provedor(psp).create_charge(_cobranca())

    cob = [p for p in psp.pedidos if p.url.path.startswith("/v2/cob/")][0]
    assert cob.method == "PUT", "POST /cob deixaria o txid a cargo do PSP e perderia a idempotencia"
    assert cob.url.path == f"/v2/cob/{PixProvider._txid('INV-1042')}"
    assert cob.headers["Authorization"] == "Bearer tok-1"
    assert resposta.status == PaymentStatus.PENDING
    assert resposta.qr_code.startswith("00020126")


async def test_corpo_da_cobranca_segue_a_especificacao():
    psp = PspFalso()
    await _provedor(psp).create_charge(_cobranca(valor="10.1"))

    enviado = json.loads([p for p in psp.pedidos if p.url.path.startswith("/v2/cob/")][0].content)
    assert enviado["valor"]["original"] == "10.10", "valor tem de ser string com duas casas"
    assert enviado["chave"] == "recebedor@chargegrid.com.br"
    assert enviado["calendario"]["expiracao"] == PixProvider.EXPIRACAO_PADRAO
    assert enviado["solicitacaoPagador"] == "Recarga EV"


async def test_descricao_longa_e_truncada():
    """O campo tem teto no PSP, e estourar derruba a cobranca inteira."""
    psp = PspFalso()
    await _provedor(psp).create_charge(_cobranca(description="x" * 500))
    enviado = json.loads([p for p in psp.pedidos if "/v2/cob/" in p.url.path][0].content)
    assert len(enviado["solicitacaoPagador"]) == 140


async def test_documento_valido_vira_devedor():
    psp = PspFalso()
    await _provedor(psp).create_charge(_cobranca(payer_document="123.456.789-09"))
    enviado = json.loads([p for p in psp.pedidos if "/v2/cob/" in p.url.path][0].content)
    assert enviado["devedor"]["cpf"] == "12345678909"


async def test_documento_invalido_nao_derruba_a_cobranca():
    """`devedor` e' OPCIONAL. Mandar um CPF com 9 digitos trocaria uma cobranca
    que funcionaria por uma recusa, por causa de um campo que podia ficar fora."""
    psp = PspFalso()
    resposta = await _provedor(psp).create_charge(_cobranca(payer_document="123456789"))
    enviado = json.loads([p for p in psp.pedidos if "/v2/cob/" in p.url.path][0].content)
    assert "devedor" not in enviado
    assert resposta.status == PaymentStatus.PENDING


async def test_provider_ref_vem_do_psp():
    """Alguns normalizam o txid. Gravar o nosso faria o webhook nao achar o pagamento."""
    psp = PspFalso()
    psp.erro_da_cobranca = None

    class Normalizador(PspFalso):
        def _responder(self, pedido):
            if pedido.url.path.startswith("/v2/cob/") and pedido.method == "PUT":
                self.pedidos.append(pedido)
                return httpx.Response(
                    201, json={"txid": "TXIDNORMALIZADOPELOPSP123456", "status": "ATIVA"}
                )
            return super()._responder(pedido)

    outro = Normalizador()
    resposta = await _provedor(outro).create_charge(_cobranca())
    assert resposta.provider_ref == "TXIDNORMALIZADOPELOPSP123456"


async def test_metodo_que_nao_e_pix_e_recusado():
    """Emitir um Pix para quem pediu cartao cobraria pelo meio errado."""
    psp = PspFalso()
    with pytest.raises(PaymentError, match="não atende o método"):
        await _provedor(psp).create_charge(_cobranca(method=PaymentMethodKind.CREDIT_CARD))


async def test_configuracao_incompleta_diz_o_que_falta():
    psp = PspFalso()
    provedor = _provedor(psp)
    del provedor.config["chave_pix"]
    with pytest.raises(PaymentError, match="chave_pix"):
        await provedor.create_charge(_cobranca())


# --------------------------------------------------------------------- token


async def test_token_e_reaproveitado_entre_cobrancas():
    """Sem cache, cada pagamento gastaria duas viagens ate o PSP em vez de uma."""
    psp = PspFalso()
    await _provedor(psp).create_charge(_cobranca(referencia="INV-1"))
    await _provedor(psp).create_charge(_cobranca(referencia="INV-2"))
    assert psp.tokens_emitidos == 1, (
        "o cache e' de modulo justamente porque o provedor e' novo a cada cobranca"
    )


async def test_token_vencido_e_renovado():
    psp = PspFalso(token_expira_em=0)
    await _provedor(psp).create_charge(_cobranca(referencia="INV-1"))
    await _provedor(psp).create_charge(_cobranca(referencia="INV-2"))
    assert psp.tokens_emitidos == 2


async def test_clientes_diferentes_nao_compartilham_token():
    """Token de um estabelecimento no outro seria cobranca na conta errada."""
    psp = PspFalso()
    await _provedor(psp).create_charge(_cobranca(referencia="INV-1"))
    await _provedor(psp, client_id="outro-cliente").create_charge(_cobranca(referencia="INV-2"))
    assert psp.tokens_emitidos == 2


async def test_401_no_meio_do_caminho_renova_e_tenta_de_novo():
    """Token revogado antes da hora derrubaria toda cobranca ate o cache expirar."""
    psp = PspFalso()
    psp.recusar_token_uma_vez = True
    resposta = await _provedor(psp).create_charge(_cobranca())
    assert resposta.status == PaymentStatus.PENDING
    assert psp.tokens_emitidos == 2


async def test_credencial_recusada_nao_ecoa_o_segredo():
    """Resposta de erro de autenticacao costuma repetir o que foi enviado."""

    class SemCredencial(PspFalso):
        def _responder(self, pedido):
            self.pedidos.append(pedido)
            return httpx.Response(
                401, json={"detail": "client_secret invalido: segredo-que-nao-pode-vazar"}
            )

    with pytest.raises(PaymentError) as erro:
        await _provedor(SemCredencial()).create_charge(_cobranca())
    assert "segredo-que-nao-pode-vazar" not in str(erro.value)


# --------------------------------------------------------------------- erros


async def test_erro_do_psp_chega_legivel():
    psp = PspFalso()
    psp.erro_da_cobranca = (
        400,
        {
            "title": "Requisicao invalida",
            "detail": "A requisicao esta mal formada",
            "violacoes": [{"razao": "valor.original deve ser string"}],
        },
    )
    with pytest.raises(PaymentError) as erro:
        await _provedor(psp).create_charge(_cobranca())
    assert "mal formada" in str(erro.value)
    assert "valor.original" in str(erro.value)


async def test_erro_sem_corpo_json_nao_quebra():
    class Mudo(PspFalso):
        def _responder(self, pedido):
            if pedido.url.path == "/oauth/token":
                return super()._responder(pedido)
            self.pedidos.append(pedido)
            return httpx.Response(502, text="<html>bad gateway</html>")

    with pytest.raises(PaymentError, match="502"):
        await _provedor(Mudo()).create_charge(_cobranca())


# ------------------------------------------------------------------ consulta


async def test_capture_relata_o_que_o_psp_diz():
    """A versao anterior devolvia CAPTURED sem perguntar nada a ninguem."""
    txid = PixProvider._txid("INV-1042")
    for estado, esperado in [
        ("CONCLUIDA", PaymentStatus.CAPTURED),
        ("ATIVA", PaymentStatus.PENDING),
        ("REMOVIDA_PELO_PSP", PaymentStatus.FAILED),
    ]:
        psp = PspFalso(cobrancas={txid: {"txid": txid, "status": estado}})
        resposta = await _provedor(psp).capture(txid, Decimal("10.00"))
        assert resposta.status == esperado, f"{estado} deveria virar {esperado}"


async def test_dado_pessoal_nao_vai_para_o_raw():
    """`raw` e' persistido em `Payment.raw_response` e fica la' para sempre.

    O CPF do pagador ja esta em `users`; repeti-lo numa coluna JSON que ninguem
    indexa nem expira e' guardar risco sem ganho nenhum.
    """
    psp = PspFalso()
    resposta = await _provedor(psp).create_charge(_cobranca(payer_document="12345678909"))
    assert "devedor" not in resposta.raw
    assert "12345678909" not in json.dumps(resposta.raw)


# ----------------------------------------------------------------- devolucao


async def test_devolucao_precisa_de_pagamento():
    txid = PixProvider._txid("INV-1042")
    psp = PspFalso(cobrancas={txid: {"txid": txid, "status": "ATIVA"}})
    with pytest.raises(PaymentError, match="não foi paga"):
        await _provedor(psp).refund(txid, Decimal("10.00"))


async def test_devolucao_usa_o_endtoendid_e_nao_o_txid():
    """O e2eid identifica o Pix RECEBIDO, e so' existe depois de alguem pagar."""
    txid = PixProvider._txid("INV-1042")
    psp = PspFalso(
        cobrancas={
            txid: {
                "txid": txid,
                "status": "CONCLUIDA",
                "pix": [{"endToEndId": "E12345678202609111200abcdef12345", "valor": "10.00"}],
            }
        }
    )
    resposta = await _provedor(psp).refund(txid, Decimal("10.00"))
    caminho = [p for p in psp.pedidos if "/devolucao/" in p.url.path][0].url.path
    assert caminho.startswith("/v2/pix/E12345678202609111200abcdef12345/devolucao/")
    assert resposta.status == PaymentStatus.REFUNDED


async def test_id_da_devolucao_e_deterministico():
    """Repetir a chamada nao pode devolver duas vezes."""
    txid = PixProvider._txid("INV-1042")
    cob = {
        txid: {
            "txid": txid,
            "status": "CONCLUIDA",
            "pix": [{"endToEndId": "E1234", "valor": "10.00"}],
        }
    }
    caminhos = []
    for _ in range(2):
        psp = PspFalso(cobrancas=dict(cob))
        await _provedor(psp).refund(txid, Decimal("10.00"))
        caminhos.append([p for p in psp.pedidos if "/devolucao/" in p.url.path][0].url.path)
    assert caminhos[0] == caminhos[1]


# ------------------------------------------------------------------ webhook


def test_webhook_do_pix_vira_evento_interno():
    """O PSP manda uma LISTA e nenhum campo de status.

    Sem esta traducao a integracao fica pela metade: a cobranca e' criada e o
    pagamento nunca liquida - o motorista paga e a fatura continua aberta.
    """
    recebidos = [
        {"endToEndId": "E1", "txid": "TX1", "valor": "10.00", "horario": "2026-09-11T12:00Z"},
        {"endToEndId": "E2", "txid": "TX2", "valor": "20.00", "horario": "2026-09-11T12:01Z"},
    ]
    eventos = PixProvider({}).traduzir_webhook({"pix": recebidos})
    assert [e["provider_ref"] for e in eventos] == ["TX1", "TX2"]
    assert all(e["status"] == "CONCLUIDA" for e in eventos)


def test_webhook_sem_txid_e_descartado():
    eventos = PixProvider({}).traduzir_webhook({"pix": [{"endToEndId": "E1"}]})
    assert eventos == []


def test_corpo_que_nao_e_do_pix_passa_direto():
    """Um PSP que ja mande a forma interna continua funcionando."""
    corpo = {"provider_ref": "TX1", "status": "paid"}
    assert PixProvider({}).traduzir_webhook(corpo) == [corpo]


def test_provedor_padrao_nao_traduz_nada():
    from app.services.payment_providers import MockProvider

    corpo = {"provider_ref": "x", "status": "paid"}
    assert MockProvider({}).traduzir_webhook(corpo) == [corpo]


# ------------------------------------------------- do PSP ate a fatura paga


async def test_webhook_do_pix_liquida_a_fatura(api, db, site, motorista):
    """A travessia inteira, que e' onde a integracao vale ou nao vale.

    Cobrir `create_charge` e a traducao em separado nao prova que o dinheiro
    chega: entre os dois ha `provedor_do_evento`, que descobre de qual
    estabelecimento e' o evento a partir de uma referencia no corpo - e o corpo
    do Pix nao tem referencia no topo. Se ele nao souber olhar dentro de `pix[]`,
    cai no provedor global, o corpo nunca e' traduzido, e a fatura fica aberta
    com o dinheiro ja recebido.

    E' o defeito mais caro possivel nesta parte do sistema, e o unico jeito de
    ve-lo e' percorrer o caminho todo.
    """
    import hashlib
    import hmac
    import json as _json
    import uuid as _uuid
    from datetime import UTC, datetime

    from app.core.config import settings
    from app.models.billing import Invoice, Payment, SitePaymentMethod
    from app.models.enums import InvoiceStatus, PaymentMethodKind, PaymentStatus

    txid = PixProvider._txid("INV-PIX-1")
    db.add(
        SitePaymentMethod(
            id=_uuid.uuid4(),
            site_id=site.id,
            kind=PaymentMethodKind.PIX,
            label="Pix",
            enabled=True,
            provider="pix",
            provider_config={
                "base_url": "https://pix.psp-de-mentira.com.br",
                "client_id": "c",
                "client_secret": "s",
                "chave_pix": "k",
            },
        )
    )
    fatura = Invoice(
        id=_uuid.uuid4(),
        code="INV-PIX-1",
        site_id=site.id,
        user_id=motorista.id,
        status=InvoiceStatus.OPEN,
        issued_on=datetime.now(UTC).date(),
        subtotal=10,
        total=10,
    )
    db.add(fatura)
    await db.flush()
    db.add(
        Payment(
            id=_uuid.uuid4(),
            invoice_id=fatura.id,
            method=PaymentMethodKind.PIX,
            status=PaymentStatus.PENDING,
            amount=10,
            provider="pix",
            provider_ref=txid,
        )
    )
    await db.flush()

    corpo = _json.dumps(
        {
            "pix": [
                {
                    "endToEndId": "E12345678202609111200abcdef12345",
                    "txid": txid,
                    "valor": "10.00",
                    "horario": "2026-09-11T12:00:00Z",
                }
            ]
        }
    ).encode()
    assinatura = hmac.new(
        settings.payment_webhook_secret.encode(), corpo, hashlib.sha256
    ).hexdigest()

    r = await api.post(
        "/api/v1/payments/webhook",
        content=corpo,
        headers={"x-signature": assinatura, "content-type": "application/json"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["eventos"][0]["invoice"] == "INV-PIX-1"

    atual = (
        await db.execute(
            select(Invoice).where(Invoice.id == fatura.id).execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert atual.status == InvoiceStatus.PAID, "o Pix foi recebido e a fatura continuou aberta"


async def test_webhook_do_pix_repetido_nao_paga_duas_vezes(api, db, site, motorista):
    """PSP reenvia o lote quando nao recebe 200. Idempotencia nao e' opcional."""
    import hashlib
    import hmac
    import json as _json
    import uuid as _uuid
    from datetime import UTC, datetime

    from app.core.config import settings
    from app.models.billing import Invoice, Payment, SitePaymentMethod
    from app.models.enums import InvoiceStatus, PaymentMethodKind, PaymentStatus

    txid = PixProvider._txid("INV-PIX-2")
    db.add(
        SitePaymentMethod(
            id=_uuid.uuid4(),
            site_id=site.id,
            kind=PaymentMethodKind.PIX,
            label="Pix",
            enabled=True,
            provider="pix",
            provider_config={"base_url": "https://x", "client_id": "c", "client_secret": "s"},
        )
    )
    fatura = Invoice(
        id=_uuid.uuid4(),
        code="INV-PIX-2",
        site_id=site.id,
        user_id=motorista.id,
        status=InvoiceStatus.OPEN,
        issued_on=datetime.now(UTC).date(),
        subtotal=10,
        total=10,
    )
    db.add(fatura)
    await db.flush()
    db.add(
        Payment(
            id=_uuid.uuid4(),
            invoice_id=fatura.id,
            method=PaymentMethodKind.PIX,
            status=PaymentStatus.PENDING,
            amount=10,
            provider="pix",
            provider_ref=txid,
        )
    )
    await db.flush()

    corpo = _json.dumps({"pix": [{"endToEndId": "E1", "txid": txid, "valor": "10.00"}]}).encode()
    assinatura = hmac.new(
        settings.payment_webhook_secret.encode(), corpo, hashlib.sha256
    ).hexdigest()
    cabecalhos = {"x-signature": assinatura, "content-type": "application/json"}

    primeira = await api.post("/api/v1/payments/webhook", content=corpo, headers=cabecalhos)
    segunda = await api.post("/api/v1/payments/webhook", content=corpo, headers=cabecalhos)
    assert primeira.status_code == 200
    assert segunda.status_code == 200
    assert segunda.json()["eventos"][0].get("idempotent") is True
