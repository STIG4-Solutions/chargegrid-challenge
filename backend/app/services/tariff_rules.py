"""Coerencia entre o tipo declarado da tarifa e os precos que ela cobra.

O motor de tarifacao cobra pelos componentes de preco e nunca leu o campo
`type`. Isso deixava o campo mentir: uma tarifa marcada "por tempo" com preco
por kWh preenchido cobrava os dois, entregando ao operador um modelo diferente
do que ele escolheu. As regras abaixo tornam o tipo uma restricao de verdade.
"""

from __future__ import annotations

from app.core.errors import DomainError
from app.models.enums import TariffType

# Componente que cada tipo exige, e os que ele proibe.
CONTRATO: dict[TariffType, dict[str, list[str]]] = {
    TariffType.PER_KWH: {
        "exige": ["price_per_kwh"],
        "proibe": ["price_per_min", "session_fee"],
    },
    TariffType.PER_TIME: {
        "exige": ["price_per_min"],
        "proibe": ["price_per_kwh", "session_fee"],
    },
    # As janelas horarias trazem os precos; a base serve de reserva.
    TariffType.TIME_OF_USE: {
        "exige": [],
        "proibe": ["session_fee"],
    },
    TariffType.FLAT: {
        "exige": ["session_fee"],
        "proibe": ["price_per_kwh", "price_per_min"],
    },
}

ROTULO = {
    "price_per_kwh": "preço por kWh",
    "price_per_min": "preço por minuto",
    "session_fee": "taxa de conexão",
}

# A taxa de ociosidade e o valor minimo valem para qualquer modelo: sao politicas
# de vaga e de piso, nao a forma de cobrar a recarga.


class TariffInconsistent(DomainError):
    status_code = 422
    code = "tariff_inconsistent"


def validar(tipo: TariffType, valores: dict[str, float]) -> None:
    """Levanta TariffInconsistent se os precos nao combinam com o tipo."""
    contrato = CONTRATO.get(TariffType(tipo))
    if contrato is None:
        return

    faltando = [c for c in contrato["exige"] if float(valores.get(c) or 0) <= 0]
    if faltando:
        nomes = ", ".join(ROTULO[c] for c in faltando)
        raise TariffInconsistent(f"Uma tarifa do tipo '{tipo}' precisa de {nomes} maior que zero.")

    sobrando = [c for c in contrato["proibe"] if float(valores.get(c) or 0) > 0]
    if sobrando:
        nomes = ", ".join(ROTULO[c] for c in sobrando)
        raise TariffInconsistent(
            f"Uma tarifa do tipo '{tipo}' não cobra {nomes}. Zere esse valor ou escolha outro tipo."
        )
