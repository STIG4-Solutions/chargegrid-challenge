"""O ciclo do rebalanceador grava a bandeira no site - ou nao, com a flag desligada.

Entra por `rebalance_site`, o ciclo de UM site: `rebalance_once` abre a propria
conexao com o banco e escaparia da transacao do teste.

O site do conftest tem rede de 75 kW, reserva predial de 20 kW e nem solar nem
bateria: 55 kW livres de 75, folga de 73,3% - verde. Subir a reserva e' o jeito
de apertar o orcamento sem precisar de leitura de medidor.
"""

from decimal import Decimal

import pytest

from app.core.config import settings
from app.services import power_manager


@pytest.fixture
def ligada(monkeypatch):
    monkeypatch.setattr(settings, "precificacao_dinamica", True)


async def test_o_ciclo_grava_a_bandeira_no_site(db, site, ponto, ligada):
    resultado = await power_manager.rebalance_site(db, site.id, triggered_by="teste")
    await db.refresh(site)

    assert site.bandeira_cor == "verde"
    assert Decimal(str(site.bandeira_multiplicador)) == Decimal("1.00")
    assert Decimal(str(site.bandeira_folga_pct)) == Decimal("73.3")
    assert site.bandeira_motivo
    assert site.bandeira_calculada_em is not None
    assert resultado["bandeira"]["cor"] == "verde"


async def test_o_aperto_do_orcamento_muda_a_cor(db, site, ponto, ligada):
    # Reserva de 45 kW: 30 livres de 75 = 40% -> amarela.
    site.reserved_kw = 45
    await db.flush()
    await power_manager.rebalance_site(db, site.id, triggered_by="teste")
    await db.refresh(site)
    assert site.bandeira_cor == "amarela"
    assert Decimal(str(site.bandeira_multiplicador)) == Decimal("1.15")

    # Reserva de 65 kW: 10 livres de 75 = 13,3% -> vermelha.
    site.reserved_kw = 65
    await db.flush()
    await power_manager.rebalance_site(db, site.id, triggered_by="teste")
    await db.refresh(site)
    assert site.bandeira_cor == "vermelha"
    assert Decimal(str(site.bandeira_multiplicador)) == Decimal("1.30")


async def test_com_a_flag_desligada_o_ciclo_nao_grava_bandeira(db, site, ponto):
    assert settings.precificacao_dinamica is False, "a flag nasce desligada"
    resultado = await power_manager.rebalance_site(db, site.id, triggered_by="teste")
    await db.refresh(site)

    assert site.bandeira_cor is None
    assert site.bandeira_calculada_em is None
    assert resultado.get("bandeira") is None


async def test_simulacao_do_ciclo_nao_grava_bandeira(db, site, ponto, ligada):
    # `dry_run` e' o "o que aconteceria": nao pode mudar o preco de ninguem.
    await power_manager.rebalance_site(db, site.id, triggered_by="teste", dry_run=True)
    await db.refresh(site)
    assert site.bandeira_cor is None
