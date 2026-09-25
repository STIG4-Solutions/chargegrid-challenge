"""A bandeira aparece onde o operador e o motorista olham.

- `GET /power/overview`: o estado inicial da aba Potencia.
- evento `power_plan`: o que o rebalanceador publica no WebSocket a cada ciclo.
- `GET /app/stations/{id}/charge-points`: a tela do app antes de iniciar.

Site do conftest: rede de 75 kW, reserva de 20 kW (verde, 73,3% de folga).
Tarifa: R$ 2,00/kWh, sem janela.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.config import settings
from app.services import power_manager


@pytest.fixture
def ligada(monkeypatch):
    monkeypatch.setattr(settings, "precificacao_dinamica", True)


async def _pintar(db, site, reserva_kw: float) -> dict:
    site.reserved_kw = reserva_kw
    await db.flush()
    return await power_manager.rebalance_site(db, site.id, triggered_by="teste")


async def test_o_overview_traz_a_bandeira_do_site(
    api, db, site, ponto, como_operador_do_site, ligada
):
    await _pintar(db, site, 45)  # amarela
    r = await api.get("/api/v1/power/overview", headers=como_operador_do_site)
    assert r.status_code == 200, r.text
    b = r.json()["bandeira"]
    assert b["cor"] == "amarela"
    assert b["multiplicador"] == 1.15
    assert b["folga_pct"] == 40.0
    assert b["motivo"]
    assert b["desatualizada"] is False


async def test_bandeira_velha_aparece_como_desatualizada(
    api, db, site, ponto, como_operador_do_site, ligada
):
    await _pintar(db, site, 45)
    site.bandeira_calculada_em = datetime.now(UTC) - timedelta(
        seconds=settings.bandeira_validade_s + 30
    )
    await db.flush()
    r = await api.get("/api/v1/power/overview", headers=como_operador_do_site)
    assert r.json()["bandeira"]["desatualizada"] is True


async def test_com_a_flag_desligada_o_overview_nao_traz_bandeira(
    api, db, site, ponto, como_operador_do_site
):
    site.bandeira_cor = "vermelha"
    site.bandeira_multiplicador = Decimal("1.30")
    site.bandeira_calculada_em = datetime.now(UTC)
    await db.flush()
    r = await api.get("/api/v1/power/overview", headers=como_operador_do_site)
    assert r.json()["bandeira"] is None


async def test_o_plano_publicado_leva_a_bandeira(db, site, ponto, ligada):
    # `rebalance_once` publica `resultado["plan"]` como evento `power_plan`.
    resultado = await _pintar(db, site, 65)
    assert resultado["plan"]["bandeira"]["cor"] == "vermelha"
    assert resultado["plan"]["bandeira"]["multiplicador"] == 1.30


async def test_o_app_ve_a_bandeira_e_o_preco_final_antes_de_iniciar(
    api, db, site, ponto, como_motorista, ligada
):
    await _pintar(db, site, 45)  # amarela, x1,15
    r = await api.get(f"/api/v1/app/stations/{site.id}/charge-points", headers=como_motorista)
    assert r.status_code == 200, r.text
    p = r.json()[0]
    assert p["bandeira"]["cor"] == "amarela"
    # R$ 2,00/kWh x 1,15 = R$ 2,30/kWh.
    assert p["preco_kwh_final"] == 2.30


async def test_bandeira_velha_no_app_mostra_o_preco_sem_multiplicador(
    api, db, site, ponto, como_motorista, ligada
):
    await _pintar(db, site, 65)
    site.bandeira_calculada_em = datetime.now(UTC) - timedelta(
        seconds=settings.bandeira_validade_s + 30
    )
    await db.flush()
    r = await api.get(f"/api/v1/app/stations/{site.id}/charge-points", headers=como_motorista)
    p = r.json()[0]
    assert p["bandeira"]["desatualizada"] is True
    assert p["preco_kwh_final"] == 2.00


async def test_com_a_flag_desligada_o_app_ve_o_preco_da_tarifa(
    api, db, site, ponto, como_motorista
):
    # Bandeira vermelha fresca gravada de quando a flag estava ligada: desligar
    # a flag tem de ignora-la, e nao cobrar x1,30 na tela.
    site.bandeira_cor = "vermelha"
    site.bandeira_multiplicador = Decimal("1.30")
    site.bandeira_folga_pct = Decimal("10.0")
    site.bandeira_motivo = "teste"
    site.bandeira_calculada_em = datetime.now(UTC)
    await db.flush()
    r = await api.get(f"/api/v1/app/stations/{site.id}/charge-points", headers=como_motorista)
    p = r.json()[0]
    assert p["bandeira"] is None
    assert p["preco_kwh_final"] == 2.00
