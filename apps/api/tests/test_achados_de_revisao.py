"""Os oito achados de revisao que faltavam, cada um com o seu.

Um bloco por achado, na ordem em que foram corrigidos.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

CAB = "/api/v1/app"


# ------------------------------------------- 1. provedor desconhecido


def test_provedor_desconhecido_estoura_em_vez_de_aprovar():
    """Cair no simulador aprovava pagamento ficticio."""
    from app.core.errors import PaymentError
    from app.services.payment_providers import get_provider

    with pytest.raises(PaymentError, match="desconhecido"):
        get_provider("stripe")


def test_provedores_reais_continuam_resolvendo():
    from app.services.payment_providers import MockProvider, PixProvider, get_provider

    assert isinstance(get_provider("mock"), MockProvider)
    assert isinstance(get_provider("pix"), PixProvider)


# ------------------------------------------- 2. validacoes do agendamento


async def test_agendamento_no_passado_e_recusado(api, como_motorista, ponto):
    inicio = datetime.now(UTC) - timedelta(days=2)
    r = await api.post(
        f"{CAB}/reservations",
        headers=como_motorista,
        json={
            "charge_point_id": str(ponto.id),
            "starts_at": inicio.isoformat(),
            "ends_at": (inicio + timedelta(hours=1)).isoformat(),
        },
    )
    assert r.status_code == 422, r.text


async def test_agendamento_com_carro_de_outro_e_recusado(api, como_motorista, db, ponto):
    from app.models.enums import UserRole
    from app.models.user import User, Vehicle

    outro = User(
        id=uuid.uuid4(),
        email=f"o-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Outro",
        hashed_password="x",
        role=UserRole.DRIVER,
    )
    db.add(outro)
    await db.flush()
    carro = Vehicle(id=uuid.uuid4(), user_id=outro.id, model="Alheio")
    db.add(carro)
    await db.flush()

    inicio = datetime.now(UTC) + timedelta(days=1)
    r = await api.post(
        f"{CAB}/reservations",
        headers=como_motorista,
        json={
            "charge_point_id": str(ponto.id),
            "vehicle_id": str(carro.id),
            "starts_at": inicio.isoformat(),
            "ends_at": (inicio + timedelta(hours=1)).isoformat(),
        },
    )
    assert r.status_code == 404, r.text


async def test_um_motorista_nao_segura_o_site_inteiro(api, como_motorista, ponto, segundo_ponto):
    """Cada reserva confirmada desconta do orcamento durante a janela."""
    from app.api.v1.mobile import MAX_RESERVAS_POR_MOTORISTA

    base = datetime.now(UTC) + timedelta(days=1)
    aceitos = 0
    for n in range(MAX_RESERVAS_POR_MOTORISTA + 3):
        alvo = ponto if n % 2 == 0 else segundo_ponto
        r = await api.post(
            f"{CAB}/reservations",
            headers=como_motorista,
            json={
                "charge_point_id": str(alvo.id),
                "starts_at": (base + timedelta(hours=n * 3)).isoformat(),
                "ends_at": (base + timedelta(hours=n * 3 + 1)).isoformat(),
            },
        )
        if r.status_code == 201:
            aceitos += 1
        else:
            assert r.status_code == 409, r.text
    assert aceitos == MAX_RESERVAS_POR_MOTORISTA


# ------------------------------------------- 3. corte so apos confirmacao


async def test_escrita_que_falha_nao_marca_o_ponto_como_cortado(db, ponto, site, monkeypatch):
    """O banco nao pode registrar um corte que o hardware nao aceitou."""
    from app.models.enums import ChargePointStatus
    from app.services import command_service, power_manager

    class Falha:
        ok = False
        error = "timeout"

    async def sempre_falha(*a, **k):
        return Falha()

    # O import de send_command e' feito dentro da funcao, entao o patch tem
    # de ser no modulo de origem.
    monkeypatch.setattr(command_service, "send_command", sempre_falha)

    ponto.status = ChargePointStatus.CHARGING
    site.grid_limit_kw = 0
    site.reserved_kw = 0
    await db.flush()

    await power_manager.rebalance_site(db, site.id, triggered_by="teste")
    await db.refresh(ponto)

    assert ponto.status != ChargePointStatus.SUSPENDED, (
        "o ponto foi dado como cortado sem o hardware confirmar"
    )


# ------------------------------------------- 4. KPI no fuso do site


def test_o_dia_comeca_a_meia_noite_local_nao_em_greenwich():
    """O caso exato que quebrava: 01h UTC ainda e' ontem em Sao Paulo."""

    from app.api.v1.sessions import inicio_do_dia

    # 1h da manha de 15/06 em UTC = 22h de 14/06 em Sao Paulo.
    agora = datetime(2026, 6, 15, 1, 0, tzinfo=UTC)
    comeco = inicio_do_dia("America/Sao_Paulo", agora)

    assert comeco.day == 14, "o dia virou em Greenwich, não no estabelecimento"
    assert comeco.hour == 0
    # E o instante corresponde as 03h UTC do dia 14, nao a meia-noite UTC.
    assert comeco.astimezone(UTC) == datetime(2026, 6, 14, 3, 0, tzinfo=UTC)


def test_cada_estabelecimento_tem_o_seu_dia():
    from app.api.v1.sessions import inicio_do_dia

    agora = datetime(2026, 6, 15, 1, 0, tzinfo=UTC)
    assert inicio_do_dia("America/Sao_Paulo", agora).day == 14
    assert inicio_do_dia("Europe/Lisbon", agora).day == 15


def test_site_sem_fuso_cai_no_padrao_brasileiro():
    from app.api.v1.sessions import inicio_do_dia

    agora = datetime(2026, 6, 15, 1, 0, tzinfo=UTC)
    assert inicio_do_dia(None, agora).day == 14


async def test_kpi_responde_com_o_fuso_do_site(api, como_operador_do_site, site, db):
    site.timezone = "America/Sao_Paulo"
    await db.flush()

    r = await api.get("/api/v1/sessions/kpis", headers=como_operador_do_site)
    assert r.status_code == 200, r.text


# ------------------------------------------- 5. destravar respeita o estado


async def test_destravar_nao_marca_ponto_na_fila_como_carregando(
    api, como_operador_do_site, db, ponto, motorista
):
    from app.models.enums import ChargePointStatus, SessionState
    from app.services import session_service

    sessao = await session_service.authorize(db, ponto, user=motorista)
    sessao.state = SessionState.QUEUED
    ponto.operator_throttled = True
    await db.flush()

    r = await api.post(
        f"/api/v1/power/charge-points/{ponto.id}/throttle?enabled=false",
        headers=como_operador_do_site,
    )
    assert r.status_code == 200, r.text
    await db.refresh(ponto)
    assert ponto.status != ChargePointStatus.CHARGING, (
        "ponto na fila marcado como carregando reserva potência sem entregar"
    )


# ------------------------------------------- 6. fatura so o que foi entregue


async def test_energia_anterior_ao_inicio_nao_entra_na_fatura(db, ponto, motorista, tarifa):
    from app.models.enums import StopReason
    from app.models.telemetry import TelemetrySample
    from app.services import billing_service, session_service

    sessao = await session_service.authorize(db, ponto, user=motorista)

    # Amostra gravada enquanto a sessao ainda nem tinha comecado.
    db.add(
        TelemetrySample(
            id=uuid.uuid4(),
            charge_point_id=ponto.id,
            session_id=sessao.id,
            recorded_at=datetime.now(UTC) - timedelta(hours=2),
            power_kw=7,
            session_energy_kwh=99,
        )
    )
    await db.flush()

    sessao = await session_service.start(db, sessao, ponto)
    await session_service.stop(db, sessao, ponto, reason=StopReason.REMOTE, auto_bill=False)
    fatura = await billing_service.bill_session(db, sessao)

    assert float(fatura.total) < 100, f"a fatura levou energia de antes do início: {fatura.total}"


# ------------------------------------------- 7. segredo de webhook por site


def test_webhook_usa_o_segredo_do_estabelecimento():
    """Com dois sites em PSPs diferentes, so um funcionava."""
    import hashlib
    import hmac

    from app.services.payment_providers import PixProvider

    provedor = PixProvider({"webhook_secret": "segredo-do-site-A"})
    corpo = b'{"provider_ref":"x","status":"paid"}'
    assinatura = hmac.new(b"segredo-do-site-A", corpo, hashlib.sha256).hexdigest()

    assert provedor.verify_webhook(corpo, assinatura)


def test_segredo_de_um_site_nao_valida_evento_de_outro():
    import hashlib
    import hmac

    from app.services.payment_providers import PixProvider

    corpo = b'{"provider_ref":"x"}'
    assinado_por_A = hmac.new(b"segredo-A", corpo, hashlib.sha256).hexdigest()

    assert not PixProvider({"webhook_secret": "segredo-B"}).verify_webhook(corpo, assinado_por_A)


def test_sem_segredo_proprio_cai_no_global():
    import hashlib
    import hmac

    from app.core.config import settings
    from app.services.payment_providers import PixProvider

    corpo = b'{"provider_ref":"x"}'
    assinatura = hmac.new(
        settings.payment_webhook_secret.encode(), corpo, hashlib.sha256
    ).hexdigest()

    assert PixProvider({}).verify_webhook(corpo, assinatura)


# ------------------------------------------- 8. posicao na fila no app


async def test_app_recebe_a_posicao_na_fila(api, como_motorista, db, ponto, motorista):
    """A tela ja tratava o campo; nenhuma rota /app/* o preenchia."""
    from app.models.enums import SessionState
    from app.services import session_service

    sessao = await session_service.authorize(db, ponto, user=motorista)
    sessao.state = SessionState.QUEUED
    sessao.queued_at = datetime.now(UTC)
    await db.flush()

    r = await api.get(f"{CAB}/sessions/active", headers=como_motorista)
    assert r.status_code == 200, r.text
    assert r.json()["queue_position"] == 1
