"""Para onde a notificacao vai de fato.

Mesmo desenho dos provedores de pagamento, pelo mesmo motivo: o envio depende
de credencial externa que nao existe em desenvolvimento, e o codigo que decide
O QUE notificar nao pode ficar amarrado a quem entrega.

Um nome desconhecido estoura em vez de cair no simulador. E' a licao do
`PAYMENT_PROVIDER=stripe`, que passava na validacao e caia no mock aprovando
pagamento ficticio: aqui o estrago seria menor - notificacao que nunca chega -
mas o modo de falhar e' o mesmo, silencioso e so' visivel em producao.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

# A Expo aceita ate 100 mensagens por chamada. Acima disso ela recusa o lote
# inteiro, entao o corte tem de ser nosso.
LOTE_MAXIMO = 100
TIMEOUT_S = 10


@dataclass(slots=True)
class Mensagem:
    token: str
    titulo: str
    corpo: str
    dados: dict


class PushError(Exception):
    pass


class PushSender(ABC):
    @abstractmethod
    def send(self, mensagens: list[Mensagem]) -> int:
        """Entrega o lote. Devolve quantas foram aceitas."""


class LogSender(PushSender):
    """Padrao em desenvolvimento: registra em vez de enviar.

    Nao e' um stub vazio - ele exercita todo o caminho ate a borda, entao o
    worker, a selecao de eventos e a montagem da mensagem sao os mesmos que
    rodariam em producao. So' a ultima linha muda.
    """

    def send(self, mensagens: list[Mensagem]) -> int:
        for m in mensagens:
            log.info("push.simulado", token=m.token[-8:], titulo=m.titulo, corpo=m.corpo)
        return len(mensagens)


class ExpoSender(PushSender):
    """Entrega pelo servico de push da Expo.

    Um lote recusado nao marca os eventos como enviados - eles voltam no ciclo
    seguinte. Por isso o erro sobe: engolir aqui transformaria "nao entreguei"
    em "entreguei", e a notificacao sumiria para sempre.
    """

    URL = "https://exp.host/--/api/v2/push/send"

    def send(self, mensagens: list[Mensagem]) -> int:
        enviadas = 0
        for i in range(0, len(mensagens), LOTE_MAXIMO):
            lote = mensagens[i : i + LOTE_MAXIMO]
            corpo = json.dumps(
                [
                    {
                        "to": m.token,
                        "title": m.titulo,
                        "body": m.corpo,
                        "data": m.dados,
                        "sound": "default",
                    }
                    for m in lote
                ]
            ).encode("utf-8")
            pedido = urllib.request.Request(
                self.URL,
                data=corpo,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(pedido, timeout=TIMEOUT_S) as resposta:
                    if resposta.status >= 400:
                        raise PushError(f"expo devolveu {resposta.status}")
            except urllib.error.URLError as erro:
                raise PushError(f"falha ao falar com a Expo: {erro}") from erro
            enviadas += len(lote)
        return enviadas


SENDERS: dict[str, type[PushSender]] = {"log": LogSender, "expo": ExpoSender}


def get_sender(nome: str | None = None) -> PushSender:
    escolhido = nome or settings.push_provider
    classe = SENDERS.get(escolhido)
    if classe is None:
        raise PushError(
            f"provedor de push desconhecido: {escolhido!r} "
            f"(disponíveis: {', '.join(sorted(SENDERS))})"
        )
    return classe()
