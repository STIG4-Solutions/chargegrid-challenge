"""Isolamento entre estabelecimentos e entre motoristas.

O escopo multi-tenant existia - `ScopedSiteId` - mas tinha sido aplicado em
umas rotas e esquecido em outras. `GET /invoices/{id}` exigia apenas um token
valido: qualquer motorista lia a fatura de qualquer outro pelo identificador,
com valor, linhas e pagamentos. A cobranca so barrava motorista, entao um
operador cobrava fatura de outro site - e no metodo carteira debitava o saldo
de alguem que nao era cliente dele. E o detalhe, a previa, a telemetria e o
faturamento de sessao liam qualquer sessao do sistema.
"""

import uuid

import pytest


async def _outro_motorista(db):
    from app.models.enums import UserRole
    from app.models.user import User

    u = User(
        id=uuid.uuid4(),
        email=f"outro-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Outro Motorista",
        hashed_password="x",
        role=UserRole.DRIVER,
        wallet_balance=500,
    )
    db.add(u)
    await db.flush()
    return u


async def _fatura_de(db, site_id, user_id, total=42):
    from datetime import UTC, datetime

    from app.models.billing import Invoice
    from app.models.enums import InvoiceStatus

    inv = Invoice(
        id=uuid.uuid4(),
        code=f"INV-{uuid.uuid4().hex[:6].upper()}",
        site_id=site_id,
        user_id=user_id,
        status=InvoiceStatus.OPEN,
        issued_on=datetime.now(UTC).date(),
        subtotal=total,
        total=total,
    )
    db.add(inv)
    await db.flush()
    return inv


# ------------------------------------------------- fatura entre motoristas


async def test_motorista_nao_le_fatura_de_outro(api, como_motorista, db, site):
    vitima = await _outro_motorista(db)
    fatura = await _fatura_de(db, site.id, vitima.id)

    r = await api.get(f"/api/v1/invoices/{fatura.id}", headers=como_motorista)
    assert r.status_code == 404, f"leu a fatura alheia: {r.text}"


async def test_motorista_le_a_propria_fatura(api, como_motorista, db, site, motorista):
    fatura = await _fatura_de(db, site.id, motorista.id)

    r = await api.get(f"/api/v1/invoices/{fatura.id}", headers=como_motorista)
    assert r.status_code == 200, r.text
    assert r.json()["code"] == fatura.code


async def test_motorista_nao_cobra_fatura_de_outro(api, como_motorista, db, site):
    vitima = await _outro_motorista(db)
    fatura = await _fatura_de(db, site.id, vitima.id)

    r = await api.post(
        f"/api/v1/invoices/{fatura.id}/charge",
        headers=como_motorista,
        json={"method": "wallet"},
    )
    assert r.status_code == 404


# ------------------------------------------------- fatura entre estabelecimentos


async def test_operador_nao_le_fatura_de_outro_site(
    api, como_operador_vizinho, db, site, motorista
):
    fatura = await _fatura_de(db, site.id, motorista.id)

    r = await api.get(f"/api/v1/invoices/{fatura.id}", headers=como_operador_vizinho)
    assert r.status_code == 404, f"operador vizinho leu a fatura: {r.text}"


async def test_operador_nao_debita_carteira_de_cliente_alheio(
    api, como_operador_vizinho, db, site, motorista
):
    """O dano concreto: cobrar no metodo carteira tirava dinheiro de verdade."""
    saldo_antes = float(motorista.wallet_balance)
    fatura = await _fatura_de(db, site.id, motorista.id, total=25)

    r = await api.post(
        f"/api/v1/invoices/{fatura.id}/charge",
        headers=como_operador_vizinho,
        json={"method": "wallet"},
    )
    assert r.status_code == 404, r.text
    await db.refresh(motorista)
    assert float(motorista.wallet_balance) == saldo_antes, "o saldo foi debitado"


async def test_operador_do_proprio_site_cobra_normalmente(
    api, como_operador_do_site, db, site, motorista
):
    """A guarda nao pode quebrar o caso legitimo."""
    from app.models.billing import SitePaymentMethod
    from app.models.enums import PaymentMethodKind

    db.add(
        SitePaymentMethod(
            id=uuid.uuid4(),
            site_id=site.id,
            kind=PaymentMethodKind.WALLET,
            label="Carteira",
            enabled=True,
        )
    )
    await db.flush()
    fatura = await _fatura_de(db, site.id, motorista.id, total=10)

    r = await api.post(
        f"/api/v1/invoices/{fatura.id}/charge",
        headers=como_operador_do_site,
        json={"method": "wallet"},
    )
    assert r.status_code == 201, r.text


# ------------------------------------------------- sessao entre estabelecimentos


@pytest.fixture
async def sessao_do_site(db, ponto, motorista):
    from app.services import session_service

    return await session_service.authorize(db, ponto, user=motorista)


@pytest.mark.parametrize(
    "rota", ["", "/preview", "/telemetry"]
)
async def test_operador_vizinho_nao_le_sessao(
    api, como_operador_vizinho, sessao_do_site, rota
):
    r = await api.get(f"/api/v1/sessions/{sessao_do_site.id}{rota}", headers=como_operador_vizinho)
    assert r.status_code == 404, f"rota '{rota}' vazou a sessão: {r.text}"


async def test_operador_vizinho_nao_fatura_sessao_alheia(
    api, como_operador_vizinho, sessao_do_site
):
    r = await api.post(f"/api/v1/sessions/{sessao_do_site.id}/bill", headers=como_operador_vizinho)
    assert r.status_code == 404, r.text


async def test_operador_do_site_le_a_propria_sessao(
    api, como_operador_do_site, sessao_do_site
):
    r = await api.get(f"/api/v1/sessions/{sessao_do_site.id}", headers=como_operador_do_site)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == str(sessao_do_site.id)


async def test_token_de_motorista_nao_entra_nas_rotas_de_sessao(
    api, como_motorista, sessao_do_site
):
    r = await api.get(f"/api/v1/sessions/{sessao_do_site.id}", headers=como_motorista)
    assert r.status_code == 403
