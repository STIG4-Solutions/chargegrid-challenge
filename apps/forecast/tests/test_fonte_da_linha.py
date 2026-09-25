"""`fonte` nomeia o previsor que produziu AQUELE numero.

O DEFEITO, que foi meu e apareceu lendo a saida do export. A regua escolhida e'
global - a que ganhou o backtest na rede inteira -, e `fonte` usava essa global.
Mas `residencial-vila-mariana` caiu no fallback de media movel por ter historico
curto, e foi gravada como `fonte = 'ano_a_ano'`: o rotulo dizia "mesmo mes um ano
antes" sobre um numero que era a media dos ultimos 28 dias.

    slug                       fonte       kwh
    residencial-vila-mariana   ano_a_ano   1541    <- o rotulo mentia

E' a mesma classe de defeito que este trabalho conserta em outro lugar: a metrica
publicada nao descrevia o modelo servido.

A CORRECAO E' ESTRUTURAL. Valor e fonte saem de UMA funcao, num par. Enquanto
forem duas expressoes separadas, sempre havera' um caminho em que uma muda e a
outra nao - e o teste que prende isso e' o primeiro daqui.

    docker compose --profile forecast run --rm forecast python -m pytest tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from exportar import _pela_media_movel, _pela_regua  # noqa: E402


def _linha(**campos) -> pd.Series:
    base = {"dias": 30, "media_diaria_28d": 10.0, "kwh_prev": 300.0, "kwh_regua_ano": 400.0}
    return pd.Series({**base, **campos})


def test_com_ano_anterior_o_numero_e_a_fonte_sao_os_de_ano_a_ano():
    valor, fonte = _pela_regua(_linha(), "ano_a_ano")
    assert (valor, fonte) == (400.0, "ano_a_ano")


def test_sem_ano_anterior_a_fonte_CAI_junto_com_o_numero():
    """O defeito, em um assert.

    A praca nao tem `kwh_regua_ano`: o numero vem da media movel, e a `fonte` TEM de
    vir com ele. Se alguem voltar a usar a regua global aqui, o par devolve
    `(300.0, "ano_a_ano")` e este teste cai.
    """
    valor, fonte = _pela_regua(_linha(kwh_regua_ano=np.nan), "ano_a_ano")
    assert fonte == "media_movel", "a fonte ficou na regua global e o numero nao"
    assert valor == 300.0


def test_quando_a_media_movel_ganha_a_fonte_e_ela():
    valor, fonte = _pela_regua(_linha(), "media_movel")
    assert (valor, fonte) == (300.0, "media_movel")


def test_a_media_movel_de_uma_praca_em_fallback_nao_vira_zero():
    """`media_diaria_28d` vem NaN quando a praca caiu no fallback do previsor.

    Ali `kwh_prev` JA' e' a media movel do mes. Ler de `media_diaria_28d` e
    multiplicar por 30 gravaria ZERO num site que tem movimento - e o card mostraria
    uma praca parada.
    """
    assert _pela_media_movel(_linha(media_diaria_28d=np.nan, kwh_prev=1541.2)) == 1541.2


def test_sem_numero_em_lugar_nenhum_devolve_zero_e_nao_NaN():
    """NaN iria para a coluna NOT NULL do banco e derrubaria a gravacao no meio.

    Zero e' o valor conservador: a praca aparece com nada previsto, que e' verdade.
    """
    vazia = _linha(media_diaria_28d=np.nan, kwh_prev=np.nan, kwh_regua_ano=np.nan)
    valor, fonte = _pela_regua(vazia, "ano_a_ano")
    assert valor == 0.0
    assert fonte == "media_movel"
