"""A FORMA do mes: como o total se distribui entre os dias.

O DEFEITO QUE ISTO FECHA: A SOMA VAZA. O total do mes e' a soma de trinta razoes
previstas, cada uma multiplicada pelo nivel. Se a MEDIA dessas razoes desvia de
1,0, o nivel do mes inteiro anda - e o erro de FORMA passa a ser erro de NIVEL.

Isso nao e' teoria. Normalizando pela regua de ano-a-ano, que sozinha faz 8,67%
no mes, o modelo por cima dela faz 12,20%: ele PIORA em 3,5 pontos o nivel que
recebeu pronto. A regua acerta o nivel, o modelo a desloca, e ninguem tinha
motivo para suspeitar - o modelo estava melhorando o eixo diario ao mesmo tempo.

A CORRECAO. Dividir cada razao prevista pela media das razoes previstas daquela
praca naquele mes. A soma passa a ser `nivel x dias` por construcao, o modelo
perde o poder de mexer no nivel, e fica com o unico trabalho em que ganha.

Nao e' um remendo que troca um eixo pelo outro: medido com 24 meses, prender
melhora OS DOIS. No mes, 13,34% -> 9,95% (o nivel da regua). No dia, 31,28% ->
29,90% - mais preciso TAMBEM na forma, porque a razao livre gastava capacidade
deslocando o nivel.

NADA DE FUTURO. A media e' das PREVISOES daquele mes, todas produzidas pela
mesma origem. Nenhum valor real do mes alvo entra na conta.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from .perda import PARAMS, treinar_um

# As colunas que este modelo acrescenta a `pipeline.features.FEATURES`.
EXTRAS = ["razao_ano_dia", "tem_ano"]

# A chave do bucket que a razao tem de respeitar. Praca E mes: normalizar pela
# media da rede deixaria o modelo mover o nivel de uma praca contra a outra.
BUCKET = ["location_id", "mes_alvo"]


def features_da_forma(base: list[str]) -> list[str]:
    """`FEATURES` do pipeline mais as de ano-a-ano, sem repetir."""
    return list(base) + [c for c in EXTRAS if c not in base]


def treinar_forma(
    tr: pd.DataFrame, features: list[str], categoricas: list[str], **sobrepor
) -> LGBMRegressor:
    """Treina a razao `y_kwh / nivel_ano` no grao diario."""
    y = tr["y_kwh"] / tr["nivel_ano"].replace(0, np.nan)
    ok = y.notna() & np.isfinite(y)
    return treinar_um(tr.loc[ok, features], y[ok], categoricas, PARAMS, **sobrepor)


def prender_ao_nivel(df: pd.DataFrame, razao: np.ndarray) -> np.ndarray:
    """Razao prevista -> kWh por dia, sem poder deslocar o nivel do mes.

    Uma praca-mes cuja media prevista sai zero volta a razao 1,0 - o que devolve
    `nivel_ano` puro, que e' a regua. Zero seria pior: gravaria consumo nulo num
    mes inteiro por causa de uma divisao.
    """
    r = pd.Series(np.clip(np.asarray(razao, float), 0, None), index=df.index)
    media = r.groupby([df[c] for c in BUCKET], observed=True).transform("mean")
    fator = (r / media.replace(0, np.nan)).fillna(1.0)
    return (fator * df["nivel_ano"]).to_numpy()


def prever_forma(modelo: LGBMRegressor, df: pd.DataFrame, features: list[str]) -> np.ndarray:
    """kWh por dia: preve a razao e a prende ao nivel."""
    return prender_ao_nivel(df, modelo.predict(df[features]))
