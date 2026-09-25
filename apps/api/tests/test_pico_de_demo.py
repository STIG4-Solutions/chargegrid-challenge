"""Gatilho de demo: um pico simulado de consumo do predio, por tempo limitado.

Existe para a banca ver a bandeira mudar ao vivo. Por isso as guardas importam
tanto quanto o efeito: so' administrador dispara, e so' quando carregadores E
medidor sao simulados - num site com hardware real, "aumentar o consumo do
predio" seria falsificar a medicao que decide o preco de alguem.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.services import power_manager
from app.workers import virtual_meter

ROTA = "/api/v1/power/demo/pico-predio"


@pytest.fixture
def ligada(monkeypatch):
    monkeypatch.setattr(settings, "precificacao_dinamica", True)


async def _disparar(api, site, cabecalho, **corpo):
    return await api.post(f"{ROTA}?site_id={site.id}", json=corpo, headers=cabecalho)


async def test_motorista_e_operador_nao_disparam(
    api, site, ponto, como_motorista, como_operador_do_site
):
    assert (await _disparar(api, site, como_motorista)).status_code == 403
    assert (await _disparar(api, site, como_operador_do_site)).status_code == 403


async def test_recusado_com_carregador_de_verdade(api, site, ponto, como_admin, monkeypatch):
    monkeypatch.setattr(settings, "charger_driver", "modbus")
    r = await _disparar(api, site, como_admin)
    assert r.status_code == 409
    assert "simulador" in r.json()["detail"]


async def test_recusado_com_medidor_de_verdade(api, site, ponto, como_admin, monkeypatch):
    monkeypatch.setattr(settings, "meter_source", "push")
    r = await _disparar(api, site, como_admin)
    assert r.status_code == 409
    assert "medidor" in r.json()["detail"]


async def test_o_overview_diz_se_o_gatilho_esta_disponivel(
    api, site, ponto, como_operador_do_site, monkeypatch
):
    r = await api.get("/api/v1/power/overview", headers=como_operador_do_site)
    assert r.json()["demo_disponivel"] is True

    monkeypatch.setattr(settings, "charger_driver", "modbus")
    r = await api.get("/api/v1/power/overview", headers=como_operador_do_site)
    assert r.json()["demo_disponivel"] is False


async def test_o_pico_deixa_a_bandeira_vermelha_na_hora(
    api, db, site, ponto, como_admin, como_operador_do_site, ligada
):
    await power_manager.rebalance_site(db, site.id, triggered_by="teste")
    antes = await api.get("/api/v1/power/overview", headers=como_operador_do_site)
    assert antes.json()["bandeira"]["cor"] == "verde"

    r = await _disparar(api, site, como_admin, duracao_min=5)
    assert r.status_code == 200, r.text
    assert r.json()["pico_simulado_ate"] is not None

    # Sem esperar o worker: o proprio gatilho roda o ciclo do site.
    depois = await api.get("/api/v1/power/overview", headers=como_operador_do_site)
    assert depois.json()["bandeira"]["cor"] == "vermelha"
    assert depois.json()["pico_simulado_ate"] is not None


async def test_o_pico_expira_sozinho_e_a_bandeira_volta_ao_verde(
    api, db, site, ponto, como_admin, como_operador_do_site, ligada
):
    r = await _disparar(api, site, como_admin, duracao_min=1)
    assert r.status_code == 200, r.text
    await db.refresh(site)
    assert site.pico_simulado_ate is not None

    # Passado o prazo, a proxima leitura do medidor volta a curva normal...
    depois_do_prazo = datetime.now(UTC) + timedelta(minutes=2)
    leitura = await virtual_meter.leitura_do_site(db, site, depois_do_prazo)
    await db.flush()
    assert float(leitura.building_load_kw) < float(site.grid_limit_kw) * 0.5
    assert site.pico_simulado_ate is None
    assert site.pico_simulado_kw is None

    # ...e o ciclo seguinte devolve a cor, sem ninguem cancelar nada.
    await power_manager.rebalance_site(db, site.id, triggered_by="teste")
    fim = await api.get("/api/v1/power/overview", headers=como_operador_do_site)
    assert fim.json()["bandeira"]["cor"] == "verde"
    assert fim.json()["pico_simulado_ate"] is None


async def test_duracao_fora_do_limite_e_recusada(api, site, ponto, como_admin):
    assert (await _disparar(api, site, como_admin, duracao_min=0)).status_code == 422
    assert (await _disparar(api, site, como_admin, duracao_min=16)).status_code == 422
