"""O treino produz o MESMO modelo em maquinas diferentes?

Esta pergunta nao e' academica. `modelos/metricas_atual.json` esta versionado e
o README publica os numeros dele; se o treino variar com a maquina, ninguem
consegue conferir a afirmacao - e uma metrica que so' vale no computador de quem
a publicou nao e' evidencia de nada.

O `random_state=42` do pipeline NAO basta. Ele fixa a amostragem (`subsample`,
`colsample_bytree`). A construcao dos histogramas do LightGBM depende do numero
de threads: a ordem em que as somas parciais se juntam muda, e soma de ponto
flutuante nao e' associativa. Mesmos dados, mesma semente, maquinas com
contagens de nucleo diferentes - arvores diferentes.

    docker run --rm -v "$PWD/apps/forecast":/forecast chargegrid-forecast \\
        python -m pytest tests -q

Fora do pytest da API de proposito: estas dependencias (lightgbm, numpy) nao
entram na imagem que roda o rebalanceamento de potencia.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from pipeline import train as _train  # noqa: E402
from pipeline.features import CATEGORICAS, FEATURES  # noqa: E402
from treinar import DETERMINISMO  # noqa: E402

# Poucas arvores: o que se mede aqui e' se dois treinos coincidem, nao a
# qualidade do modelo. Com 700 o teste levaria minutos para provar o mesmo.
ARVORES = 60


def _dados(n: int = 900) -> pd.DataFrame:
    """Painel sintetico com a forma que `construir_treino` produz.

    Sintetico e nao o banco: o teste responde sobre o TREINO, e prende-lo ao
    Postgres o faria falhar por motivos que nao sao o assunto dele.
    """
    rng = np.random.default_rng(7)
    locais = ["a-station", "b-station", "c-station"]
    df = pd.DataFrame(
        {
            "horizonte": rng.integers(1, 30, n),
            "dow": rng.integers(0, 7, n),
            "is_weekend": rng.integers(0, 2, n),
            "mes": rng.integers(1, 13, n),
            "dia_mes": rng.integers(1, 29, n),
            "is_feriado": rng.integers(0, 2, n),
            "is_vespera_feriado": rng.integers(0, 2, n),
            "hist_m7": rng.gamma(3, 12, n),
            "hist_m28": rng.gamma(3, 12, n),
            "hist_m91": rng.gamma(3, 12, n),
            "hist_m182": rng.gamma(3, 12, n),
            "hist_std28": rng.gamma(2, 4, n),
            "hist_ano_atras": rng.gamma(3, 12, n),
            "tend_28_91": rng.normal(1, 0.2, n),
            "tend_7_28": rng.normal(1, 0.2, n),
            "hist_dow": rng.gamma(3, 12, n),
            "archetype": rng.choice(["corporativo", "shopping", "rodovia"], n),
            "power_type": rng.choice(["ac", "dc"], n),
            "n_connectors": rng.integers(2, 9, n),
            "dias_operacao": rng.integers(200, 900, n),
            "location_id": rng.choice(locais, n),
            "y_ratio": rng.normal(1, 0.3, n),
        }
    )
    for coluna in CATEGORICAS:
        df[coluna] = df[coluna].astype("category")
    return df


def _treinar(dados: pd.DataFrame, **extra) -> str:
    """Treina e devolve as ARVORES como texto, que e' o que se compara.

    `model_to_string()` e' o dump nativo do LightGBM: cada corte de cada arvore.
    Dois modelos com o mesmo texto sao o mesmo modelo.

    O bloco `parameters:` do fim fica FORA da comparacao, e nao por conveniencia:
    ele ecoa os parametros usados, `num_threads` entre eles. Compara-lo faria o
    teste de independencia de threads falhar por conter a propria pergunta - foi
    exatamente o que aconteceu na primeira versao deste arquivo, com as 109 mil
    primeiras letras identicas e a divergencia inteira em `[num_threads: 8]`.
    """
    params = dict(_train.PARAMS, objective="l1", n_estimators=ARVORES, **extra)
    import lightgbm as lgb

    modelo = lgb.LGBMRegressor(**params)
    modelo.fit(dados[FEATURES], dados["y_ratio"], categorical_feature=CATEGORICAS)
    texto = modelo.booster_.model_to_string()
    return texto.split("parameters:")[0]


@pytest.fixture(scope="module")
def dados() -> pd.DataFrame:
    return _dados()


def test_treinar_importa_o_determinismo_no_pipeline():
    """`treinar.py` reescreve `train.PARAMS`, e `backtest` le essa global.

    Se a reescrita deixar de acontecer, o backtest passa a medir uma
    configuracao e o treino final a publicar outra - e as duas metades do
    numero publicado deixam de falar da mesma coisa.
    """
    for chave, valor in DETERMINISMO.items():
        assert _train.PARAMS.get(chave) == valor, f"{chave} nao chegou em train.PARAMS"


def test_mesmo_numero_de_threads_da_o_mesmo_modelo(dados):
    """O minimo. Se isto falhar, nem `random_state` esta valendo."""
    assert _treinar(dados) == _treinar(dados)


def test_numeros_de_threads_DIFERENTES_dao_o_mesmo_modelo(dados):
    """A garantia que importa, e a que `random_state` sozinho nao da.

    E' este o caso do colega que clona o repositorio numa maquina com outra
    contagem de nucleos e obtem metricas que nao batem com o README.
    """
    assert _treinar(dados, num_threads=1) == _treinar(dados, num_threads=8)


def test_sem_as_guardas_nao_se_observou_divergencia(dados):
    """O experimento que NAO deu no que se esperava, registrado como tal.

    O padrao deste projeto e' teste de mutacao: reverter a guarda e confirmar
    que algo quebra. Aqui isso nao aconteceu. Desligando `deterministic` e
    `force_row_wise` e treinando com 1 e com 8 threads, os modelos sairam
    IGUAIS - e o mesmo com 8.000 e 30.000 linhas, em maquina de 20 nucleos.

    Entao o teste afirma o que se observou, e nao o que se queria observar. As
    duas flags continuam em `DETERMINISMO` porque a documentacao do LightGBM e'
    explicita quanto ao contrato e elas custam pouco, mas quem passar por aqui
    precisa saber que **elas sao preventivas, nao demonstradas**. A guarda que
    de fato remove a variavel de maquina e' `num_threads` fixo, coberta pelo
    teste acima.

    Se um dia a divergencia aparecer - outra versao do LightGBM, outro OpenMP,
    base maior -, este teste comeca a falhar, e essa falha e' a noticia.
    """
    solto = {"deterministic": False, "force_row_wise": False, "force_col_wise": False}
    assert _treinar(dados, num_threads=1, **solto) == _treinar(dados, num_threads=8, **solto), (
        "a divergencia por numero de threads APARECEU - o que ate aqui nao se "
        "conseguiu reproduzir. Troque este teste pela afirmacao contraria e "
        "corrija o comentario de DETERMINISMO em treinar.py."
    )
