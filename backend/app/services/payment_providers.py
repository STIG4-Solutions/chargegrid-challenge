"""Gateways de pagamento atras de uma interface unica.

O desafio deixa a escolha do gateway em aberto. O acoplamento fica aqui: trocar
Pix por Stripe (ou somar os dois) e escrever uma classe, nao mexer no dominio.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal

from app.core.config import settings
from app.core.errors import PaymentError
from app.models.enums import PaymentMethodKind, PaymentStatus


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

    # Segredo deste provedor. Cada estabelecimento tem o seu, guardado em
    # SitePaymentMethod.provider_config; o do .env e' o fallback de instalacao
    # unica.
    config: dict = {}

    @property
    def webhook_secret(self) -> str:
        return self.config.get("webhook_secret") or settings.payment_webhook_secret

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
    """Esqueleto de PSP Pix (cobranca imediata + webhook de liquidacao).

    As credenciais e a URL do PSP vem de SitePaymentMethod.provider_config, para
    cada estabelecimento usar a propria conta - o dinheiro cai direto no lojista.
    """

    name = "pix"

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def create_charge(self, request: ChargeRequest) -> ChargeResponse:
        raise NotImplementedError(
            "Integrar com o PSP escolhido: POST /cob (Pix cobranca imediata), "
            "guardar txid em provider_ref e liquidar via webhook."
        )

    async def capture(self, provider_ref: str, amount: Decimal) -> ChargeResponse:
        # Pix e liquidacao unica: nao existe captura em duas fases.
        return ChargeResponse(status=PaymentStatus.CAPTURED, provider_ref=provider_ref)

    async def refund(self, provider_ref: str, amount: Decimal) -> ChargeResponse:
        raise NotImplementedError("PUT /pix/{e2eid}/devolucao/{id}")


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
    if provider_cls is PixProvider:
        return PixProvider(config)
    return provider_cls()
