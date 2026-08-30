"""O contrato de idempotencia que o painel usa.

A chave devolve o pagamento anterior - inclusive um que falhou. E' o
comportamento correto para a mesma tentativa, e e' por isso que o painel nao
pode reaproveitar a chave numa RETENTATIVA: ele receberia de volta a recusa
antiga sem que ninguem falasse com o provedor, e o botao "Cobrar" viraria um
no-op silencioso.

Estes testes travam o contrato dos dois lados: mesma chave nao cobra de novo,
chave nova cobra.
"""

import uuid
from datetime import UTC, datetime

from app.models.billing import Invoice, Payment, SitePaymentMethod
from app.models.enums import InvoiceStatus, PaymentMethodKind, PaymentStatus
from app.services import payment_service


async def _fatura(db, site, motorista, total=30):
    db.add(
        SitePaymentMethod(
            id=uuid.uuid4(),
            site_id=site.id,
            kind=PaymentMethodKind.WALLET,
            label="Carteira",
            enabled=True,
        )
    )
    inv = Invoice(
        id=uuid.uuid4(),
        code=f"INV-{uuid.uuid4().hex[:6].upper()}",
        site_id=site.id,
        user_id=motorista.id,
        status=InvoiceStatus.OPEN,
        issued_on=datetime.now(UTC).date(),
        subtotal=total,
        total=total,
    )
    db.add(inv)
    await db.flush()
    return inv


async def test_mesma_chave_devolve_o_mesmo_pagamento(db, site, motorista):
    fatura = await _fatura(db, site, motorista)
    chave = uuid.uuid4().hex

    p1 = await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.WALLET, idempotency_key=chave, payer=motorista
    )
    p2 = await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.WALLET, idempotency_key=chave, payer=motorista
    )
    assert p1.id == p2.id, "a mesma chave gerou dois pagamentos"


async def test_chave_repetida_devolve_ate_a_recusa_anterior(db, site, motorista):
    """O motivo de o painel precisar de chave nova por tentativa."""
    fatura = await _fatura(db, site, motorista)
    chave = uuid.uuid4().hex

    recusado = Payment(
        id=uuid.uuid4(),
        invoice_id=fatura.id,
        method=PaymentMethodKind.WALLET,
        status=PaymentStatus.FAILED,
        amount=fatura.total,
        idempotency_key=chave,
        failure_reason="saldo insuficiente",
    )
    db.add(recusado)
    await db.flush()

    devolvido = await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.WALLET, idempotency_key=chave, payer=motorista
    )
    assert devolvido.id == recusado.id
    assert devolvido.status == PaymentStatus.FAILED, (
        "reaproveitar a chave depois de uma recusa devolve a recusa"
    )


async def test_chave_nova_tenta_de_verdade(db, site, motorista):
    """Com chave nova a retentativa cobra - e' o que a correcao do painel garante."""
    fatura = await _fatura(db, site, motorista)

    recusado = Payment(
        id=uuid.uuid4(),
        invoice_id=fatura.id,
        method=PaymentMethodKind.WALLET,
        status=PaymentStatus.FAILED,
        amount=fatura.total,
        idempotency_key="tentativa-antiga",
        failure_reason="saldo insuficiente",
    )
    db.add(recusado)
    await db.flush()

    novo = await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.WALLET, idempotency_key="tentativa-nova", payer=motorista
    )
    assert novo.id != recusado.id, "a chave nova deveria abrir um pagamento novo"
    assert novo.status != PaymentStatus.FAILED
