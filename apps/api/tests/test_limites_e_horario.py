"""Limites da sessao e conselho de horario — as duas features do app.

O que estes testes protegem sao promessas feitas ao motorista na tela. Um teto
que nao segura e um conselho que erra a conta falham do mesmo jeito: em
silencio, e a favor de quem cobra.
"""

import uuid
from datetime import UTC, datetime, time

import pytest

from app.models.enums import SessionState, StopReason
from app.services import session_service
from app.services import start_advice_service as sa

# ------------------------------------------------------------------ limites


def _sessao(**kw):
    from app.models.session import ChargingSession

    base = dict(
        id=uuid.uuid4(), code="S-X", site_id=uuid.uuid4(), charge_point_id=uuid.uuid4(),
        state=SessionState.CHARGING, energy_kwh=0, duration_s=0, estimated_cost=0,
        preauth_amount=0, idle_minutes=0,
    )
    base.update(kw)
    return ChargingSession(**base)


def test_cada_limite_encerra_pelo_proprio_motivo():
    """O motivo importa: e' o que a tela do motorista mostra e o que a fatura registra."""
    assert session_service.reached_limit(
        _sessao(limit_kwh=30, energy_kwh=30)
    ) == StopReason.ENERGY_LIMIT
    assert session_service.reached_limit(
        _sessao(limit_minutes=40, duration_s=40 * 60)
    ) == StopReason.TIME_LIMIT
    assert session_service.reached_limit(
        _sessao(limit_amount=50, estimated_cost=50)
    ) == StopReason.AMOUNT_LIMIT


def test_sem_limite_nao_encerra():
    assert session_service.reached_limit(_sessao(energy_kwh=999, duration_s=99999)) is None


async def test_teto_em_reais_acima_da_preauth_sobe_a_preauth(api, site, ponto, como_motorista):
    """A armadilha que esta feature quase criou.

    A pre-autorizacao TAMBEM encerra a sessao ao ser atingida. Um teto de R$ 80
    sobre a pre-autorizacao padrao de R$ 50 nunca seria alcancado: a recarga
    pararia nos 50 e o motorista veria o proprio limite ignorado, sem erro
    nenhum. Nao da para gastar mais do que se autorizou.
    """
    r = await api.post(
        f"/api/v1/app/sessions?charge_point_id={ponto.id}&limit_amount=80",
        headers=como_motorista,
    )
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["limit_amount"] == 80
    assert corpo["preauth_amount"] >= 80


async def test_teto_abaixo_da_preauth_nao_mexe_nela(api, site, ponto, como_motorista):
    r = await api.post(
        f"/api/v1/app/sessions?charge_point_id={ponto.id}&limit_amount=20&preauth_amount=50",
        headers=como_motorista,
    )
    assert r.status_code == 201
    assert r.json()["preauth_amount"] == 50


async def test_os_tres_limites_chegam_ao_banco(api, site, ponto, como_motorista):
    r = await api.post(
        f"/api/v1/app/sessions?charge_point_id={ponto.id}"
        "&limit_kwh=25&limit_minutes=90&limit_amount=40",
        headers=como_motorista,
    )
    assert r.status_code == 201
    c = r.json()
    assert (c["limit_kwh"], c["limit_minutes"], c["limit_amount"]) == (25, 90, 40)


async def test_limite_invalido_e_recusado(api, site, ponto, como_motorista):
    for q in ("limit_kwh=0", "limit_minutes=-5", "limit_amount=0", "limit_minutes=2000"):
        r = await api.post(
            f"/api/v1/app/sessions?charge_point_id={ponto.id}&{q}", headers=como_motorista
        )
        assert r.status_code == 422, f"{q} deveria ser recusado, veio {r.status_code}"


# ------------------------------------------------------- conselho de horario


@pytest.fixture
async def tarifa_com_janelas(db, site, ponto):
    """Ponta cara das 18h as 21h; fora de ponta barata no resto do dia."""
    from app.models.enums import TariffType
    from app.models.tariff import ALL_DAYS, Tariff, TariffWindow

    t = Tariff(
        id=uuid.uuid4(), site_id=site.id, name="Horária", type=TariffType.TIME_OF_USE,
        price_per_kwh=1.20, price_per_min=0, idle_fee_per_min=0,
        session_fee=0, min_charge=0, free_minutes=0, active=True,
    )
    db.add(t)
    await db.flush()
    db.add_all([
        TariffWindow(
            id=uuid.uuid4(), tariff_id=t.id, label="ponta", day_mask=ALL_DAYS,
            starts_at=time(18), ends_at=time(21),
            price_per_kwh=2.00, price_per_min=0, idle_fee_per_min=0,
        ),
        TariffWindow(
            id=uuid.uuid4(), tariff_id=t.id, label="fora de ponta", day_mask=ALL_DAYS,
            starts_at=time(21), ends_at=time(18),
            price_per_kwh=1.00, price_per_min=0, idle_fee_per_min=0,
        ),
    ])
    ponto.tariff_id = t.id
    await db.flush()
    return t


async def test_recomenda_esperar_a_ponta_passar(db, site, ponto, tarifa_com_janelas):
    """Às 18h30, esperar até as 21h vale — é o conselho que a feature existe para dar."""
    # 18h30 local (America/Sao_Paulo, UTC-3) == 21h30 UTC.
    agora = datetime(2026, 3, 10, 21, 30, tzinfo=UTC)
    r = await sa.quando_comecar(db, ponto.id, kwh=20, horas=6, agora=agora)

    assert r["disponivel"] is True
    assert r["vale_esperar"] is True
    assert r["melhor"]["hora"] == "21:00"
    assert r["economia_brl"] > 0
    assert r["agora"]["custo_brl"] > r["melhor"]["custo_brl"]


async def test_em_janela_barata_nao_manda_esperar(db, site, ponto, tarifa_com_janelas):
    """Às 2h da manhã já se está no melhor preço; sugerir espera seria ruído."""
    agora = datetime(2026, 3, 10, 5, 0, tzinfo=UTC)  # 02:00 local
    r = await sa.quando_comecar(db, ponto.id, kwh=20, horas=6, agora=agora)
    assert r["vale_esperar"] is False
    assert r["esperar_minutos"] == 0


async def test_conta_atravessa_a_virada_da_janela(db, site, ponto, tarifa_com_janelas):
    """Uma recarga longa paga os dois preços, e nenhum deles isolado.

    Comparar preço de tabela diria "R$ 2,00/kWh". A simulação caminha a sessão
    e cobra 1,00 no trecho que cai depois das 21h — é a mesma regra que o
    faturamento aplica, então o número mostrado antes bate com o cobrado depois.
    """
    agora = datetime(2026, 3, 10, 22, 30, tzinfo=UTC)  # 19:30 local, dentro da ponta
    r = await sa.quando_comecar(db, ponto.id, kwh=40, horas=1, agora=agora)

    # 40 kWh a 22 kW ≈ 1h49: começa na ponta (2,00) e termina fora dela (1,00).
    custo = r["agora"]["custo_brl"]
    assert 40 * 1.00 < custo < 40 * 2.00
    assert "→" in r["agora"]["janela"]


async def test_tarifa_sem_janelas_nao_inventa_conselho(db, site, ponto, tarifa):
    """Sem janela o preço não muda com a hora — e dizer isso é melhor que
    responder "o melhor horário é agora", que soa como análise sem ser."""
    r = await sa.quando_comecar(db, ponto.id, kwh=20, horas=6)
    assert r["disponivel"] is False
    assert "janela" in r["motivo"]


async def test_economia_irrelevante_nao_vira_conselho(db, site, ponto):
    """Ninguém adia a recarga por trinta centavos."""
    from app.models.enums import TariffType
    from app.models.tariff import ALL_DAYS, Tariff, TariffWindow

    t = Tariff(
        id=uuid.uuid4(), site_id=site.id, name="Quase igual", type=TariffType.TIME_OF_USE,
        price_per_kwh=1.00, price_per_min=0, idle_fee_per_min=0,
        session_fee=0, min_charge=0, free_minutes=0, active=True,
    )
    db.add(t)
    await db.flush()
    db.add_all([
        TariffWindow(
            id=uuid.uuid4(), tariff_id=t.id, label="cara", day_mask=ALL_DAYS,
            starts_at=time(18), ends_at=time(21),
            price_per_kwh=1.01, price_per_min=0, idle_fee_per_min=0,
        ),
        TariffWindow(
            id=uuid.uuid4(), tariff_id=t.id, label="barata", day_mask=ALL_DAYS,
            starts_at=time(21), ends_at=time(18),
            price_per_kwh=1.00, price_per_min=0, idle_fee_per_min=0,
        ),
    ])
    ponto.tariff_id = t.id
    await db.flush()

    agora = datetime(2026, 3, 10, 21, 30, tzinfo=UTC)  # 18:30 local
    r = await sa.quando_comecar(db, ponto.id, kwh=10, horas=6, agora=agora)
    assert r["vale_esperar"] is False


async def test_resposta_traz_o_horario_de_termino(db, site, ponto, tarifa_com_janelas):
    """Esperar atrasa. Economizar R$ 8 só vale se o carro puder ficar."""
    agora = datetime(2026, 3, 10, 21, 30, tzinfo=UTC)
    r = await sa.quando_comecar(db, ponto.id, kwh=20, horas=6, agora=agora)
    assert r["agora"]["hora_fim"]
    assert r["melhor"]["hora_fim"]
    assert r["melhor"]["fim"] > r["agora"]["fim"]


async def test_ponto_inexistente(db):
    r = await sa.quando_comecar(db, uuid.uuid4(), kwh=20, horas=6)
    assert r["disponivel"] is False


# -------------------------------------------------------------------- HTTP


async def test_rota_do_conselho_e_do_motorista(
    api, site, ponto, tarifa_com_janelas, como_motorista, como_operador
):
    ok = await api.get(
        f"/api/v1/app/charge-points/{ponto.id}/when-to-start", headers=como_motorista
    )
    assert ok.status_code == 200
    assert "melhor" in ok.json()

    negado = await api.get(
        f"/api/v1/app/charge-points/{ponto.id}/when-to-start", headers=como_operador
    )
    assert negado.status_code == 403


async def test_rota_do_conselho_valida_parametros(
    api, site, ponto, tarifa_com_janelas, como_motorista
):
    for q in ("kwh=0", "kwh=500", "horas=0", "horas=48"):
        r = await api.get(
            f"/api/v1/app/charge-points/{ponto.id}/when-to-start?{q}", headers=como_motorista
        )
        assert r.status_code == 422, f"{q} deveria ser recusado"
