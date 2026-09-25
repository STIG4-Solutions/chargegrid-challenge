"""Os parametros do LightGBM, e um lugar so' onde a perda e' decidida.

O DEFEITO QUE ISTO FECHA. `treinar.py` sobrepunha `pipeline.train.PARAMS` com
tweedie e o backtest passava a medir tweedie - mas o treino final chamava
`treinar_um(ds, "l1")`, objetivo EXPLICITO, que vencia a sobreposicao. O
resultado: o backtest media um modelo e o artefato guardava outro, com
`artefato["params"]` declarando tweedie e os modelos dentro sendo l1.

O comentario que estava no proprio `treinar.py` proibia isso com estas palavras:
"o backtest PRECISA usar os mesmos parametros do treino final: medir com uma
configuracao e publicar outra e' comparar coisas diferentes". O codigo fazia
exatamente o que o comentario proibia.

Aqui `treinar_um` NAO tem parametro de objetivo com default. Quem quer outra
perda passa `**sobrepor`, e quem nao passa nada recebe a perda de `PARAMS` -
entao nao existe mais o caminho em que um objetivo implicito vence a decisao.

Quanto valia a divergencia, medido: no banco local l1 da' 13,99% mensal e
tweedie 13,96%. Praticamente empate - o ganho de trocar a perda nao e' o motivo
de consertar isto. O motivo e' que a metrica publicada tem de descrever o modelo
servido.
"""

from __future__ import annotations

import lightgbm as lgb
import pandas as pd

# O que `random_state=42` do pipeline NAO fixa, e o que cada peca faz. Herdado de
# `treinar.py`, onde a investigacao esta' registrada por extenso: `num_threads`
# fixo e' a peca que remove uma variavel de maquina, porque a ordem em que as
# somas parciais se juntam depende do numero de threads e soma de ponto
# flutuante nao e' associativa. `deterministic` e `force_row_wise` sao
# preventivos - `tests/test_determinismo.py` tentou reproduzir a divergencia com
# 900, 8.000 e 30.000 linhas e nao conseguiu.
DETERMINISMO = {"deterministic": True, "force_row_wise": True, "num_threads": 4}

# A PERDA. `l1` ajusta a MEDIANA condicional, e o numero que vai para a tela e'
# uma SOMA de trinta dias: somar medianas subestima o total, porque energia
# diaria e' assimetrica a direita.
#
# `tweedie` com potencia 1,2 e' a perda para dado nao-negativo com massa em zero
# e cauda a direita - que e' o processo aqui: contagem de sessoes (Poisson) x
# energia por sessao (lognormal). Poisson composto.
PERDA = {"objective": "tweedie", "tweedie_variance_power": 1.2}

# O modelo da FORMA: grao diario, ~8.700 linhas. Os valores vem do pipeline.
PARAMS = dict(
    n_estimators=700,
    learning_rate=0.04,
    num_leaves=31,
    min_child_samples=30,
    subsample=0.85,
    subsample_freq=1,
    colsample_bytree=0.85,
    reg_lambda=1.0,
    random_state=42,
    verbose=-1,
    **DETERMINISMO,
    **PERDA,
)

# O modelo do NIVEL: grao mensal, ~290 registros. Arvore rasa e passo curto
# porque sao trinta vezes menos linhas que o grao diario - com folha larga ele
# tem no `location_id` uma categoria por praca e decora a praca em vez de
# aprender o mes. `tests/test_nivel.py` mede a alternativa e prende o numero.
PARAMS_NIVEL = dict(
    PARAMS,
    n_estimators=300,
    learning_rate=0.03,
    num_leaves=7,
    min_child_samples=20,
)


def treinar_um(
    X: pd.DataFrame,
    y: pd.Series,
    categoricas: list[str],
    params: dict | None = None,
    **sobrepor,
) -> lgb.LGBMRegressor:
    """Treina um regressor. A perda vem de `params`; `sobrepor` vence.

    Nao existe argumento `objective` com default: era ele que, com valor
    implicito, fazia o treino final desobedecer a perda escolhida.
    """
    p = dict(params or PARAMS, **sobrepor)
    # `alpha` so' tem sentido com perda de quantil, e o LightGBM o aceita calado
    # em qualquer perda - passar os dois juntos por engano nao daria erro.
    if p.get("alpha") is not None and p.get("objective") != "quantile":
        raise ValueError(f"alpha={p['alpha']} sem objective='quantile' nao faz nada")
    m = lgb.LGBMRegressor(**p)
    m.fit(X, y, categorical_feature=[c for c in categoricas if c in X.columns])
    return m
