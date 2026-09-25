"""O multiplicador travado na sessao, dentro do motor de tarifacao.

Funcao pura: `rate_session` recebe a sessao e ja' encontra nela o multiplicador
copiado do site no inicio da recarga. Sessao sem ele (anterior a feature, ou com
a flag desligada) precisa sair exatamente como saia antes.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.services.tariff_engine import rate_session
from tests.test_tariff_engine import make_session, make_tariff

INICIO = datetime(2026, 9, 25, 14, 0, tzinfo=UTC)


def sessao(**kwargs):
    return make_session(
        started_at=INICIO,
        ended_at=INICIO + timedelta(minutes=40),
        charging_stopped_at=INICIO + timedelta(minutes=40),
        energy_kwh=Decimal("20"),
        **kwargs,
    )


def test_o_travado_vale_mesmo_com_o_dinamico_da_tarifa_desligado():
    # 20 kWh x R$ 1,40 = R$ 28,00; x1,30 = R$ 36,40.
    r = rate_session(
        sessao(multiplicador_travado=Decimal("1.30"), cor_travada="vermelha"),
        make_tariff(dynamic_enabled=False),
        [],
    )
    assert r.total == Decimal("36.40")


def test_o_travado_vence_o_multiplicador_da_tarifa():
    # A tarifa diz x2; a sessao travou x1,15 -> R$ 28,00 x 1,15 = R$ 32,20.
    r = rate_session(
        sessao(multiplicador_travado=Decimal("1.15"), cor_travada="amarela"),
        make_tariff(dynamic_enabled=True, dynamic_multiplier=Decimal("2")),
        [],
    )
    assert r.total == Decimal("32.20")


def test_sem_travado_a_tarifa_decide_como_antes():
    r = rate_session(
        sessao(), make_tariff(dynamic_enabled=True, dynamic_multiplier=Decimal("2")), []
    )
    assert r.total == Decimal("56.00")
    r = rate_session(sessao(), make_tariff(dynamic_enabled=False), [])
    assert r.total == Decimal("28.00")


def test_a_linha_nomeia_a_bandeira_quando_ha_travado():
    r = rate_session(
        sessao(multiplicador_travado=Decimal("1.15"), cor_travada="amarela"),
        make_tariff(),
        [],
    )
    linha = next(li for li in r.lines if li.kind == "dynamic")
    assert linha.description == "Bandeira amarela (x1,15)"


def test_o_snapshot_registra_de_onde_veio_o_multiplicador():
    r = rate_session(
        sessao(multiplicador_travado=Decimal("1.30"), cor_travada="vermelha"),
        make_tariff(),
        [],
    )
    assert r.tariff_snapshot["multiplicador_aplicado"] == 1.30
    assert r.tariff_snapshot["origem_do_multiplicador"] == "bandeira"

    r = rate_session(sessao(), make_tariff(), [])
    assert r.tariff_snapshot["multiplicador_aplicado"] == 1.0
    assert r.tariff_snapshot["origem_do_multiplicador"] == "tarifa"


def test_travado_neutro_nao_gera_linha():
    r = rate_session(
        sessao(multiplicador_travado=Decimal("1.00"), cor_travada="verde"),
        make_tariff(dynamic_enabled=True, dynamic_multiplier=Decimal("2")),
        [],
    )
    assert r.total == Decimal("28.00")
    assert not [li for li in r.lines if li.kind == "dynamic"]
