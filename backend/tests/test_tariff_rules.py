"""O tipo declarado da tarifa precisa combinar com os preços que ela cobra."""

import pytest

from app.models.enums import TariffType
from app.services.tariff_rules import TariffInconsistent, validar


def test_por_tempo_nao_pode_cobrar_energia():
    """Regressão: uma tarifa 'por tempo' com R$/kWh preenchido cobrava os dois.

    Medido antes da correção: R$ 21 de tempo + R$ 28 de energia = R$ 49 numa
    tarifa que o operador escolheu como sendo só por tempo.
    """
    with pytest.raises(TariffInconsistent) as erro:
        validar(TariffType.PER_TIME, {"price_per_min": 0.35, "price_per_kwh": 1.40})
    assert "preço por kWh" in erro.value.message


def test_por_tempo_coerente_e_aceita():
    validar(TariffType.PER_TIME, {"price_per_min": 0.35, "price_per_kwh": 0, "session_fee": 0})


def test_tipo_exige_o_componente_que_o_define():
    with pytest.raises(TariffInconsistent):
        validar(TariffType.PER_KWH, {"price_per_kwh": 0, "price_per_min": 0})
    with pytest.raises(TariffInconsistent):
        validar(TariffType.FLAT, {"session_fee": 0})


def test_valor_fixo_nao_cobra_energia_nem_tempo():
    validar(TariffType.FLAT, {"session_fee": 10, "price_per_kwh": 0, "price_per_min": 0})
    with pytest.raises(TariffInconsistent):
        validar(TariffType.FLAT, {"session_fee": 10, "price_per_kwh": 1.4})


def test_por_horario_tira_os_precos_das_janelas():
    """TIME_OF_USE tem preço base como reserva; as janelas é que mandam."""
    validar(TariffType.TIME_OF_USE, {"price_per_kwh": 1.40, "price_per_min": 0, "session_fee": 0})
