"""Correcoes das correcoes.

A revisao apontada para o monorepo encontrou defeitos introduzidos pela leva
anterior de correcoes. Estes testes cobrem cada um deles.
"""

import uuid
from datetime import UTC, datetime, timedelta

CAB = "/api/v1/app"


async def test_horario_sem_fuso_devolve_422_e_nao_500(api, como_motorista, ponto):
    """A comparacao com now(UTC) estourava TypeError com datetime ingenuo."""
    r = await api.post(
        f"{CAB}/reservations",
        headers=como_motorista,
        json={
            "charge_point_id": str(ponto.id),
            "starts_at": "2026-12-01T10:00:00",
            "ends_at": "2026-12-01T11:00:00",
        },
    )
    assert r.status_code == 422, r.text
    assert "fuso" in r.text.lower()


async def test_horario_com_fuso_continua_aceito(api, como_motorista, ponto):
    inicio = datetime.now(UTC) + timedelta(days=3)
    r = await api.post(
        f"{CAB}/reservations",
        headers=como_motorista,
        json={
            "charge_point_id": str(ponto.id),
            "starts_at": inicio.isoformat(),
            "ends_at": (inicio + timedelta(hours=1)).isoformat(),
        },
    )
    assert r.status_code == 201, r.text


async def test_ponto_com_motorista_na_fila_nao_e_anunciado_livre(
    api, como_operador_do_site, como_motorista, db, ponto, motorista
):
    """Trocar CHARGING por AVAILABLE so mudou de erro: o ponto esta ocupado."""
    from app.models.enums import SessionState
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

    vagas = (
        await api.get(f"{CAB}/stations/{ponto.site_id}/charge-points", headers=como_motorista)
    ).json()
    alvo = next(v for v in vagas if v["id"] == str(ponto.id))
    assert alvo["available"] is False, "ponto com motorista na fila anunciado como livre"


def test_config_do_site_chega_a_qualquer_provedor():
    """Tratar so o Pix descartava a config no caso mais comum, que e' o mock."""
    from app.services.payment_providers import get_provider

    provedor = get_provider("mock", {"webhook_secret": "segredo-do-site"})
    assert provedor.webhook_secret == "segredo-do-site"


def test_provedores_nao_compartilham_config():
    """config como atributo de classe seria o mesmo dict para todo mundo."""
    from app.services.payment_providers import get_provider

    a = get_provider("mock", {"webhook_secret": "site-A"})
    b = get_provider("mock", {"webhook_secret": "site-B"})
    assert a.webhook_secret == "site-A"
    assert b.webhook_secret == "site-B"


async def test_sessao_que_nunca_energizou_nao_tem_o_que_cobrar(db, ponto, motorista, tarifa):
    """started_at nulo caia no ramo SEM filtro, o oposto do pretendido."""
    from app.models.telemetry import TelemetrySample
    from app.services import billing_service, session_service

    sessao = await session_service.authorize(db, ponto, user=motorista)
    db.add(
        TelemetrySample(
            id=uuid.uuid4(),
            charge_point_id=ponto.id,
            session_id=sessao.id,
            recorded_at=datetime.now(UTC),
            power_kw=7,
            session_energy_kwh=50,
        )
    )
    await db.flush()

    amostras = await billing_service._amostras_cobraveis(db, sessao)
    assert amostras == [], "sessão que nunca começou trouxe telemetria cobrável"


async def test_previa_e_fatura_olham_a_mesma_telemetria(db, ponto, motorista, tarifa):
    """Se divergirem, o valor mostrado durante a recarga nao fecha com a fatura."""
    from app.models.enums import StopReason
    from app.models.telemetry import TelemetrySample
    from app.services import billing_service, session_service

    sessao = await session_service.authorize(db, ponto, user=motorista)
    db.add(
        TelemetrySample(
            id=uuid.uuid4(),
            charge_point_id=ponto.id,
            session_id=sessao.id,
            recorded_at=datetime.now(UTC) - timedelta(hours=3),
            power_kw=7,
            session_energy_kwh=80,
        )
    )
    await db.flush()
    sessao = await session_service.start(db, sessao, ponto)

    previa = await billing_service.preview_session(db, sessao)
    await session_service.stop(db, sessao, ponto, reason=StopReason.REMOTE, auto_bill=False)
    fatura = await billing_service.bill_session(db, sessao)

    assert float(previa["total"]) == float(fatura.total), (
        f"prévia {previa['total']} ≠ fatura {fatura.total}"
    )


async def test_post_de_sessao_devolve_a_posicao_na_fila(api, como_motorista, db, ponto, site):
    """E' a chamada em que o motorista pode cair na fila."""
    from app.models.enums import SessionState

    site.grid_limit_kw = 0
    site.reserved_kw = 0
    await db.flush()

    r = await api.post(f"{CAB}/sessions?charge_point_id={ponto.id}", headers=como_motorista)
    assert r.status_code == 201, r.text
    corpo = r.json()
    if corpo["state"] == SessionState.QUEUED:
        assert corpo["queue_position"] is not None, "caiu na fila sem dizer a posição"
