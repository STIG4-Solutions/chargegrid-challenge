"""Cobranca e carteira.

O provedor real de pagamento ainda nao existe - so' o mock. O que estes testes
protegem e' a logica em volta dele, que ja vale dinheiro: idempotencia contra
retry do app, saldo que nao pode ficar negativo, e fatura que nao pode ser paga
duas vezes.
"""

from decimal import Decimal

import pytest

from app.core.errors import Conflict, PaymentError
from app.models.billing import SitePaymentMethod
from app.models.enums import (
    AuthMethod,
    InvoiceStatus,
    PaymentMethodKind,
    PaymentStatus,
    SessionState,
    StopReason,
)
from app.services import billing_service, payment_service, session_service


async def _fatura(db, ponto, motorista, *, energia=10.0):
    """Sessao encerrada e faturada: R$ 2/kWh, entao 10 kWh = R$ 20."""
    sessao = await session_service.authorize(
        db, ponto, user=motorista, auth_method=AuthMethod.OPERATOR
    )
    await session_service.start(db, sessao, ponto)
    sessao.energy_kwh = energia
    sessao.duration_s = 3600
    sessao.state = SessionState.FINISHED
    sessao.stop_reason = StopReason.REMOTE
    await db.flush()
    return await billing_service.bill_session(db, sessao)


async def _habilitar(db, site, kind, *, percentual=0.0, fixo=0.0):
    db.add(
        SitePaymentMethod(
            site_id=site.id,
            kind=kind,
            label=str(kind),
            enabled=True,
            fee_percent=percentual,
            fee_fixed=fixo,
        )
    )
    await db.flush()


# ------------------------------------------------------------------- carteira


async def test_carteira_debita_o_saldo(db, site, ponto, motorista, tarifa):
    await _habilitar(db, site, PaymentMethodKind.WALLET)
    motorista.wallet_balance = 100
    await db.flush()

    fatura = await _fatura(db, ponto, motorista)  # R$ 20
    pagamento = await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.WALLET, payer=motorista
    )

    assert pagamento.status == PaymentStatus.CAPTURED
    assert float(motorista.wallet_balance) == pytest.approx(80.0)
    assert fatura.status == InvoiceStatus.PAID
    assert fatura.paid_at is not None


async def test_saldo_insuficiente_nao_deixa_negativo(db, site, ponto, motorista, tarifa):
    """A carteira e' pre-paga: sem saldo, a cobranca falha em vez de fiar."""
    await _habilitar(db, site, PaymentMethodKind.WALLET)
    motorista.wallet_balance = 5
    await db.flush()

    fatura = await _fatura(db, ponto, motorista)  # R$ 20

    with pytest.raises(PaymentError):
        await payment_service.charge_invoice(db, fatura, PaymentMethodKind.WALLET, payer=motorista)

    assert float(motorista.wallet_balance) == pytest.approx(5.0)
    assert fatura.status != InvoiceStatus.PAID


async def test_carteira_exige_usuario_identificado(db, site, ponto, motorista, tarifa):
    await _habilitar(db, site, PaymentMethodKind.WALLET)
    fatura = await _fatura(db, ponto, motorista)

    with pytest.raises(PaymentError):
        await payment_service.charge_invoice(db, fatura, PaymentMethodKind.WALLET, payer=None)


async def test_recarga_soma_ao_saldo(db, motorista):
    antes = Decimal(str(motorista.wallet_balance))
    atualizado = await payment_service.topup_wallet(db, motorista, Decimal("50"))
    assert Decimal(str(atualizado.wallet_balance)) == antes + Decimal("50")


# --------------------------------------------------------------- idempotencia


async def test_mesma_chave_nao_cobra_duas_vezes(db, site, ponto, motorista, tarifa):
    """O app repete a requisicao quando a rede cai; o motorista nao pode pagar 2x."""
    await _habilitar(db, site, PaymentMethodKind.WALLET)
    motorista.wallet_balance = 100
    await db.flush()

    fatura = await _fatura(db, ponto, motorista)
    chave = "tentativa-unica-123"

    primeiro = await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.WALLET, payer=motorista, idempotency_key=chave
    )
    # Neste ponto a fatura ja esta paga. O retry precisa devolver o pagamento
    # original, e nao "fatura ja paga" - a resposta da primeira e' que se perdeu.
    segundo = await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.WALLET, payer=motorista, idempotency_key=chave
    )

    assert primeiro.id == segundo.id
    assert float(motorista.wallet_balance) == pytest.approx(80.0)


async def test_fatura_ja_paga_e_recusada(db, site, ponto, motorista, tarifa):
    await _habilitar(db, site, PaymentMethodKind.WALLET)
    motorista.wallet_balance = 100
    await db.flush()

    fatura = await _fatura(db, ponto, motorista)
    await payment_service.charge_invoice(db, fatura, PaymentMethodKind.WALLET, payer=motorista)

    with pytest.raises(Conflict):
        await payment_service.charge_invoice(db, fatura, PaymentMethodKind.WALLET, payer=motorista)


async def test_fatura_sem_valor_nao_gera_cobranca(db, site, ponto, motorista, tarifa):
    await _habilitar(db, site, PaymentMethodKind.WALLET)
    fatura = await _fatura(db, ponto, motorista)
    fatura.total = 0
    await db.flush()

    with pytest.raises(PaymentError):
        await payment_service.charge_invoice(db, fatura, PaymentMethodKind.WALLET, payer=motorista)


# ------------------------------------------------------- liquidacao e taxas


async def test_cartao_fica_autorizado_e_espera_a_captura(db, site, ponto, motorista, tarifa):
    """Cartao nao liquida na criacao: autoriza e aguarda a confirmacao do adquirente.

    Enquanto isso a fatura continua em aberto e a taxa nao e' descontada - dar
    a fatura por paga aqui inflaria a receita com dinheiro que nao entrou.
    """
    await _habilitar(db, site, PaymentMethodKind.CREDIT_CARD, percentual=3.2, fixo=0.39)
    fatura = await _fatura(db, ponto, motorista)  # R$ 20

    pagamento = await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.CREDIT_CARD, payer=motorista
    )

    assert pagamento.status == PaymentStatus.AUTHORIZED
    assert fatura.status == InvoiceStatus.OPEN
    assert float(fatura.processing_fee) == 0


async def test_pix_nasce_pendente_com_copia_e_cola(db, site, ponto, motorista, tarifa):
    await _habilitar(db, site, PaymentMethodKind.PIX, percentual=0.99)
    fatura = await _fatura(db, ponto, motorista)

    pagamento = await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.PIX, payer=motorista
    )

    assert pagamento.status == PaymentStatus.PENDING
    assert pagamento.qr_code and pagamento.qr_code.startswith("00020126")
    assert fatura.status == InvoiceStatus.OPEN


async def test_liquidacao_pela_carteira_desconta_a_taxa(db, site, ponto, motorista, tarifa):
    """A carteira captura na hora, entao e' por ela que da para observar a taxa."""
    await _habilitar(db, site, PaymentMethodKind.WALLET, percentual=1.0)
    motorista.wallet_balance = 100
    await db.flush()

    fatura = await _fatura(db, ponto, motorista)  # R$ 20
    await payment_service.charge_invoice(db, fatura, PaymentMethodKind.WALLET, payer=motorista)

    assert fatura.status == InvoiceStatus.PAID
    assert float(fatura.processing_fee) == pytest.approx(0.20, abs=0.01)
    assert float(fatura.net_amount) == pytest.approx(19.80, abs=0.01)
    assert float(fatura.total) == pytest.approx(20.0)


async def test_meio_de_pagamento_nao_habilitado_e_recusado(db, ponto, motorista, tarifa):
    """Nenhum SitePaymentMethod cadastrado: a cobranca nao pode simplesmente passar."""
    fatura = await _fatura(db, ponto, motorista)

    with pytest.raises((PaymentError, Conflict)):
        await payment_service.charge_invoice(db, fatura, PaymentMethodKind.PIX, payer=motorista)
