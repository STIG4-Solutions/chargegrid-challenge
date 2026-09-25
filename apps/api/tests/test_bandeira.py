"""Bandeira do site: da folga de potencia ao multiplicador do preco.

Funcao pura sobre o orcamento que o rebalanceador ja montou - sem banco, sem
relogio. Os valores esperados sao os da decisao do time (>= 50% verde a 1,00;
20% a 50% amarela a 1,15; < 20% ou acima do orcamento vermelha a 1,30), escritos
como literais aqui para que o teste nao recalcule a regra que ele verifica.
"""

from decimal import Decimal

import pytest

from app.services.bandeira import Faixas, calcular
from app.services.power_manager import PowerBudget


def orcamento(
    *,
    grid: float = 100,
    pv: float = 0,
    bateria: float = 0,
    predio: float = 0,
    reserva: float = 0,
    agendado: float = 0,
) -> PowerBudget:
    return PowerBudget(
        grid_limit_kw=grid,
        pv_kw=pv,
        battery_kw=bateria,
        reserved_kw=reserva,
        building_load_kw=predio,
        ev_load_kw=0,
        booked_kw=agendado,
    )


@pytest.mark.parametrize(
    ("predio", "cor", "multiplicador"),
    [
        (0, "verde", Decimal("1.00")),  # folga 100%
        (50, "verde", Decimal("1.00")),  # folga 50%: a borda ja' e' verde
        (50.01, "amarela", Decimal("1.15")),  # 49,99%
        (80, "amarela", Decimal("1.15")),  # folga 20%: a borda ja' e' amarela
        (80.01, "vermelha", Decimal("1.30")),  # 19,99%
        (100, "vermelha", Decimal("1.30")),  # folga zero
    ],
)
def test_a_folga_escolhe_a_faixa(predio, cor, multiplicador):
    b = calcular(orcamento(grid=100, predio=predio), over_budget=False)
    assert b.cor == cor
    assert b.multiplicador == multiplicador


def test_a_folga_sai_em_percentual_da_capacidade():
    # 40 kW livres de 100: 40%.
    b = calcular(orcamento(grid=100, predio=60), over_budget=False)
    assert b.folga_pct == Decimal("40.0")


def test_acima_do_orcamento_e_vermelha_mesmo_com_folga_alta():
    b = calcular(orcamento(grid=100, predio=0), over_budget=True)
    assert b.cor == "vermelha"
    assert b.multiplicador == Decimal("1.30")


def test_sem_capacidade_e_vermelha():
    b = calcular(orcamento(grid=0), over_budget=False)
    assert b.cor == "vermelha"
    assert b.folga_pct == Decimal("0.0")


def test_solar_e_bateria_contam_na_capacidade():
    # Rede 50 + solar 30 + bateria 20 = 100; o predio consome 40 -> 60% de folga.
    # Sem solar e bateria na capacidade, a conta daria 10/50 = 20% (amarela).
    b = calcular(orcamento(grid=50, pv=30, bateria=20, predio=40), over_budget=False)
    assert b.cor == "verde"
    assert b.folga_pct == Decimal("60.0")


def test_as_faixas_vem_da_configuracao():
    faixas = Faixas(
        folga_verde=Decimal("0.70"),
        folga_amarela=Decimal("0.40"),
        mult_verde=Decimal("1.00"),
        mult_amarela=Decimal("1.10"),
        mult_vermelha=Decimal("1.50"),
    )
    # 60% de folga: verde no padrao, amarela com estas faixas.
    b = calcular(orcamento(grid=100, predio=40), over_budget=False, faixas=faixas)
    assert b.cor == "amarela"
    assert b.multiplicador == Decimal("1.10")


def test_o_motivo_diz_o_que_pesou():
    assert "prédio" in calcular(orcamento(grid=100, predio=90), over_budget=False).motivo
    assert "orçamento" in calcular(orcamento(grid=100), over_budget=True).motivo
    assert "confortável" in calcular(orcamento(grid=100), over_budget=False).motivo
