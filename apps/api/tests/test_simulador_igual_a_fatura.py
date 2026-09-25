"""O simulador de preco do painel da' o mesmo que a fatura daria.

`simulate` e `rate_session` aplicavam o multiplicador em ordens diferentes:
o simulador multiplicava o subtotal e so' depois comparava ao minimo; a fatura
compara o minimo ao BRUTO e trata multiplicador abaixo de 1 como abatimento. Com
minimo e multiplicador < 1 os dois divergiam - o operador simulava um preco e
cobrava outro.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.config import settings
from app.services.tariff_engine import rate_session, simulate
from tests.test_tariff_engine import make_session, make_tariff

INICIO = datetime(2026, 9, 25, 14, 0, tzinfo=UTC)
CARENCIA = 10  # minutos de tolerancia antes da ociosidade, o padrao do motor


def _tarifa(**kw):
    base = dict(
        price_per_kwh=Decimal("1.40"),
        price_per_min=Decimal("0.05"),
        idle_fee_per_min=Decimal("0.50"),
        session_fee=Decimal("1.00"),
        free_minutes=5,
    )
    base.update(kw)
    return make_tariff(**base)


def _fatura(tarifa, *, kwh, minutos, ociosos, travado=None):
    """A sessao que corresponde ao cenario do simulador."""
    fim_da_carga = INICIO + timedelta(minutes=minutos)
    sessao = make_session(
        started_at=INICIO,
        charging_stopped_at=fim_da_carga,
        ended_at=fim_da_carga + timedelta(minutes=CARENCIA + ociosos),
        energy_kwh=Decimal(str(kwh)),
        multiplicador_travado=travado,
        cor_travada="amarela" if travado is not None else None,
    )
    return rate_session(sessao, tarifa, [], idle_grace_minutes=CARENCIA, now=INICIO)


CENARIOS = [
    # (kWh, minutos, ociosos, minimo)
    (20, 40, 0, Decimal("0")),
    (20, 40, 6, Decimal("0")),
    (2, 12, 0, Decimal("8")),  # o minimo decide o valor
]
MULTIPLICADORES = [Decimal("1.00"), Decimal("1.15"), Decimal("1.30"), Decimal("0.8")]


@pytest.mark.parametrize(("kwh", "minutos", "ociosos", "minimo"), CENARIOS)
@pytest.mark.parametrize("mult", MULTIPLICADORES)
def test_simulador_e_fatura_concordam_pela_tarifa(kwh, minutos, ociosos, minimo, mult):
    tarifa = _tarifa(min_charge=minimo, dynamic_enabled=True, dynamic_multiplier=mult)
    esperado = _fatura(tarifa, kwh=kwh, minutos=minutos, ociosos=ociosos).total
    obtido = simulate(tarifa, energy_kwh=kwh, minutes=minutos, idle_minutes=ociosos, at=INICIO)
    assert obtido.total == esperado


@pytest.mark.parametrize(("kwh", "minutos", "ociosos", "minimo"), CENARIOS)
@pytest.mark.parametrize("mult", MULTIPLICADORES)
def test_simulador_e_fatura_concordam_pela_bandeira(kwh, minutos, ociosos, minimo, mult):
    tarifa = _tarifa(min_charge=minimo)
    esperado = _fatura(tarifa, kwh=kwh, minutos=minutos, ociosos=ociosos, travado=mult).total
    obtido = simulate(
        tarifa,
        energy_kwh=kwh,
        minutes=minutos,
        idle_minutes=ociosos,
        at=INICIO,
        multiplicador=mult,
    )
    assert obtido.total == esperado


def test_multiplicador_abaixo_de_um_com_minimo_o_caso_que_divergia():
    # 2 kWh x 1,40 + 7 min x 0,05 + taxa 1,00 = 2,80 + 0,35 + 1,00 = R$ 4,15 bruto.
    # O minimo de R$ 8,00 e' comparado ao bruto: completa ate' 8,00. O x0,8 e'
    # abatimento de 20% sobre o bruto (R$ 0,83), fora do minimo: R$ 7,17.
    # O simulador antigo multiplicava primeiro e subia ao minimo: R$ 8,00.
    tarifa = _tarifa(
        min_charge=Decimal("8"), dynamic_enabled=True, dynamic_multiplier=Decimal("0.8")
    )
    obtido = simulate(tarifa, energy_kwh=2, minutes=12, idle_minutes=0, at=INICIO)
    assert obtido.total == Decimal("7.17")


# ---------------------------------------------------------- a rota do painel


async def test_a_rota_simula_com_a_bandeira_atual_do_site(
    api, db, site, tarifa, como_operador_do_site, monkeypatch
):
    monkeypatch.setattr(settings, "precificacao_dinamica", True)
    site.bandeira_cor = "amarela"
    site.bandeira_multiplicador = Decimal("1.15")
    site.bandeira_calculada_em = datetime.now(UTC)
    await db.flush()

    r = await api.post(
        "/api/v1/tariffs/simulate",
        json={"tariff_id": str(tarifa.id), "energy_kwh": 20, "minutes": 30},
        headers=como_operador_do_site,
    )
    assert r.status_code == 200, r.text
    # 20 kWh x R$ 2,00 = R$ 40,00; x1,15 = R$ 46,00.
    assert r.json()["total"] == 46.0


async def test_com_a_flag_desligada_a_rota_ignora_a_bandeira(
    api, db, site, tarifa, como_operador_do_site
):
    site.bandeira_cor = "amarela"
    site.bandeira_multiplicador = Decimal("1.15")
    site.bandeira_calculada_em = datetime.now(UTC)
    await db.flush()

    r = await api.post(
        "/api/v1/tariffs/simulate",
        json={"tariff_id": str(tarifa.id), "energy_kwh": 20, "minutes": 30},
        headers=como_operador_do_site,
    )
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 40.0
