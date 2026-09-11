"""A carteira fecha: o que o razao soma e' o saldo que o motorista tem.

A tabela guardava so' credito. O debito - pagar uma fatura com saldo - mexia em
`users.wallet_balance` e nao deixava linha, entao metade dos movimentos nao
existia em lugar nenhum. Com o cashback das campanhas creditando sozinho, o
motorista passou a ver o numero mudar sem ter o que conferir.

A invariante que estes testes fixam e' uma so':

    SUM(wallet_entries.amount) == users.wallet_balance

Ela e' o que separa um razao de uma lista de eventos soltos, e e' ela que
quebra se alguem voltar a mexer no saldo sem gravar a linha.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.errors import PaymentError
from app.models.billing import Invoice, SitePaymentMethod, WalletEntry
from app.models.enums import InvoiceStatus, PaymentMethodKind
from app.services import payment_service, wallet_service

ROTA = "/api/v1/app/wallet/statement"


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
    fatura = Invoice(
        id=uuid.uuid4(),
        code=f"INV-{uuid.uuid4().hex[:6].upper()}",
        site_id=site.id,
        user_id=motorista.id,
        status=InvoiceStatus.OPEN,
        issued_on=datetime.now(UTC).date(),
        subtotal=total,
        total=total,
    )
    db.add(fatura)
    await db.flush()
    return fatura


async def _razao(db, user_id) -> Decimal:
    soma = (
        await db.execute(
            select(func.coalesce(func.sum(WalletEntry.amount), 0)).where(
                WalletEntry.user_id == user_id
            )
        )
    ).scalar_one()
    return Decimal(str(soma))


async def _saldo(db, motorista) -> Decimal:
    from app.models.user import User

    valor = (
        await db.execute(
            select(User.wallet_balance)
            .where(User.id == motorista.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    return Decimal(str(valor))


# --------------------------------------------------------------- a invariante


async def test_pagar_com_a_carteira_deixa_a_linha_do_debito(db, site, motorista):
    """O teste que quebra se alguem voltar a debitar sem gravar.

    Era exatamente este o buraco: `_charge_wallet` subtraia do saldo e seguia.
    """
    fatura = await _fatura(db, site, motorista, total=30)
    await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.WALLET, payer=motorista
    )

    debito = (
        (
            await db.execute(
                select(WalletEntry).where(
                    WalletEntry.user_id == motorista.id, WalletEntry.origem == "pagamento"
                )
            )
        )
        .scalars()
        .one()
    )
    assert Decimal(str(debito.amount)) == Decimal("-30.00"), "o debito nao e' negativo"
    assert debito.invoice_id == fatura.id, "o debito nao diz qual fatura pagou"


async def test_o_razao_fecha_com_o_saldo_depois_de_credito_e_debito(db, site, motorista):
    """Credito e debito no mesmo motorista, e a soma tem de bater no fim."""
    await payment_service.topup_wallet(
        db, motorista, Decimal("40.00"), idempotency_key=uuid.uuid4().hex
    )
    fatura = await _fatura(db, site, motorista, total=55)
    await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.WALLET, payer=motorista
    )

    saldo = await _saldo(db, motorista)
    assert saldo == Decimal("85.00"), "100 + 40 - 55"
    assert await _razao(db, motorista.id) == saldo, "o razao nao fecha com o saldo"


async def test_saldo_insuficiente_nao_deixa_linha_nenhuma(db, site, motorista):
    """A recusa acontece antes de qualquer escrita.

    Um debito gravado sem o dinheiro ter saido seria pior que nenhum: o razao
    passaria a contradizer o saldo, que e' o oposto do que ele existe para
    fazer.
    """
    fatura = await _fatura(db, site, motorista, total=500)
    with pytest.raises(PaymentError):
        await payment_service.charge_invoice(
            db, fatura, PaymentMethodKind.WALLET, payer=motorista
        )

    pagamentos = (
        (
            await db.execute(
                select(WalletEntry).where(
                    WalletEntry.user_id == motorista.id, WalletEntry.origem == "pagamento"
                )
            )
        )
        .scalars()
        .all()
    )
    assert pagamentos == []
    assert await _razao(db, motorista.id) == await _saldo(db, motorista)


async def test_a_mesma_fatura_nao_debita_duas_vezes(db, site, motorista):
    """A chave do debito e' deterministica pela fatura, e o UNIQUE e' quem barra.

    Sem isso, o retry de uma cobranca ja capturada gravaria um segundo debito e
    o razao passaria a somar menos que o saldo.
    """
    fatura = await _fatura(db, site, motorista, total=20)
    chave = uuid.uuid4().hex
    await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.WALLET, idempotency_key=chave, payer=motorista
    )
    await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.WALLET, idempotency_key=chave, payer=motorista
    )

    debitos = (
        (
            await db.execute(
                select(WalletEntry).where(
                    WalletEntry.user_id == motorista.id, WalletEntry.origem == "pagamento"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(debitos) == 1
    assert await _razao(db, motorista.id) == await _saldo(db, motorista)


# ------------------------------------------------------------ o banco recusa


async def test_banco_recusa_cashback_negativo(db, motorista):
    """O sinal nao pode divergir da origem.

    Um 'cashback' negativo passa por qualquer validacao em Python e so'
    apareceria quando o saldo de alguem nao fechasse.
    """
    db.add(
        WalletEntry(
            id=uuid.uuid4(),
            user_id=motorista.id,
            amount=Decimal("-5.00"),
            balance_after=Decimal("95.00"),
            idempotency_key=uuid.uuid4().hex,
            origem="cashback",
        )
    )
    with pytest.raises((IntegrityError, DBAPIError)):
        await db.flush()
    await db.rollback()


async def test_banco_recusa_pagamento_positivo(db, motorista):
    db.add(
        WalletEntry(
            id=uuid.uuid4(),
            user_id=motorista.id,
            amount=Decimal("5.00"),
            balance_after=Decimal("105.00"),
            idempotency_key=uuid.uuid4().hex,
            origem="pagamento",
        )
    )
    with pytest.raises((IntegrityError, DBAPIError)):
        await db.flush()
    await db.rollback()


async def test_banco_recusa_origem_desconhecida(db, motorista):
    db.add(
        WalletEntry(
            id=uuid.uuid4(),
            user_id=motorista.id,
            amount=Decimal("5.00"),
            balance_after=Decimal("105.00"),
            idempotency_key=uuid.uuid4().hex,
            origem="mesada",
        )
    )
    with pytest.raises((IntegrityError, DBAPIError)):
        await db.flush()
    await db.rollback()


# ----------------------------------------------------------------- o extrato


async def test_extrato_traduz_a_origem(db, site, motorista):
    """`cashback` cru nao diz nada a quem recebeu o dinheiro."""
    fatura = await _fatura(db, site, motorista, total=12)
    await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.WALLET, payer=motorista
    )

    extrato = await wallet_service.extrato(db, motorista.id)
    debito = next(m for m in extrato["movimentos"] if m["origem"] == "pagamento")
    assert debito["rotulo"] == f"Pagamento de recarga — {fatura.code}"
    assert debito["valor"] == -12.0


async def test_extrato_soma_tudo_e_nao_so_a_pagina(db, motorista):
    """O saldo do topo vem da tabela inteira.

    Somar so' a pagina faria quem tem muitos movimentos ver um saldo que nao e'
    o dele - e um extrato que contradiz o proprio topo nao serve para conferir
    nada.
    """
    for _ in range(3):
        await payment_service.topup_wallet(
            db, motorista, Decimal("10.00"), idempotency_key=uuid.uuid4().hex
        )

    extrato = await wallet_service.extrato(db, motorista.id, limite=1)
    assert len(extrato["movimentos"]) == 1
    assert Decimal(str(extrato["saldo"])) == await _saldo(db, motorista)


async def test_extrato_do_motorista_e_sempre_o_proprio(api, como_motorista, motorista):
    """Nao ha parametro que permita pedir o extrato de outra pessoa.

    O `user_id` na URL e' ignorado porque a rota nao o declara - o dono vem do
    token. O teste existe para que adicionar esse parametro amanha quebre algo.
    """
    alheio = uuid.uuid4()
    r = await api.get(f"{ROTA}?user_id={alheio}", headers=como_motorista)
    assert r.status_code == 200, r.text
    assert r.json()["movimentos"], "o proprio extrato veio vazio"
    assert Decimal(str(r.json()["saldo"])) == Decimal(str(motorista.wallet_balance))


async def test_extrato_exige_autenticacao(api):
    assert (await api.get(ROTA)).status_code in (401, 403)
