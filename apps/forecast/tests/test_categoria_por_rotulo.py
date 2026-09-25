"""O LightGBM realinha categoria por ROTULO, e o codigo depende disso.

UMA HIPOTESE MINHA QUE A MEDICAO DERRUBOU, registrada aqui para ninguem
re-derivar. O raciocinio era: `pipeline/features.py::_tipar` faz
`astype("category")`, que deriva as categorias dos dados presentes em ordem
alfabetica; o LightGBM guarda feature categorica pelo CODIGO; logo uma praca nova
cadastrada antes de um retreino deslocaria os codigos das outras e cada uma seria
prevista com o que o modelo aprendeu da vizinha - sem erro e sem aviso.

Escrevi um modulo para alinhar as categorias pelo artefato, e o teste que devia
provar o defeito provou o contrario. Os codigos DESLOCAM mesmo:

    so' as treinadas      ['m-praca', 'n-praca', 'z-praca']  ->  [0, 1, 2]
    com uma nova na frente ['a-nova', 'm-...', 'n-...', 'z-...'] -> [0, 1, 2, 3]

e as previsoes das treinadas NAO mudam: [10.02, 20.00, 29.98] nos dois casos. O
LightGBM guarda as categorias vistas no treino e converte a entrada da previsao
por rotulo. O modulo saiu; este teste ficou.

POR QUE MANTER O TESTE se o defeito nao existe. Porque o codigo PASSOU A DEPENDER
desse comportamento: `modelo/nivel.py::tipar_mensal` deriva as categorias dos
dados presentes. Se uma versao futura do LightGBM alinhar por codigo, o defeito
que eu imaginei passa a ser real - e ai a previsao de cada praca sai com o numero
da vizinha, calada. Este teste e' o que acusa isso antes de producao.

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

from modelo.perda import treinar_um  # noqa: E402

TREINADAS = ["m-praca", "n-praca", "z-praca"]
CATEGORICAS = ["location_id"]
FEATS = ["location_id", "nivel"]


def _dados(n: int = 60) -> pd.DataFrame:
    """Cada praca tem um alvo bem diferente, para o deslocamento ser visivel.

    Se todas tivessem o mesmo alvo, trocar o codigo de uma pela outra nao mudaria a
    previsao e o teste passaria com o defeito presente.
    """
    linhas = [
        {"location_id": praca, "nivel": 1.0, "y": 10.0 * (i + 1)}
        for i, praca in enumerate(TREINADAS)
        for _ in range(n)
    ]
    return pd.DataFrame(linhas)


def _tipar(df: pd.DataFrame) -> pd.DataFrame:
    """O que `_tipar` do pipeline e `tipar_mensal` fazem: categorias dos dados."""
    d = df.copy()
    d["location_id"] = d["location_id"].astype("category")
    return d


def _modelo():
    treino = _dados()
    return treinar_um(_tipar(treino)[FEATS], treino["y"], CATEGORICAS, n_estimators=60)


def test_os_codigos_realmente_deslocam():
    """A metade da hipotese que estava CERTA.

    Sem este assert, o teste seguinte poderia passar por nao haver deslocamento
    nenhum a ser corrigido - e nao provaria que o LightGBM realinha.
    """
    so_treinadas = _tipar(pd.DataFrame({"location_id": TREINADAS, "nivel": 1.0}))
    com_nova = _tipar(pd.DataFrame({"location_id": ["a-nova", *TREINADAS], "nivel": 1.0}))
    assert list(so_treinadas["location_id"].cat.codes) == [0, 1, 2]
    assert list(com_nova["location_id"].cat.codes) == [0, 1, 2, 3]


def test_uma_praca_nova_nao_muda_a_previsao_das_treinadas():
    """A metade que estava ERRADA, e a dependencia que o codigo tem hoje.

    "a-nova" vem antes das tres no alfabeto, o pior caso: se o alinhamento fosse por
    codigo, as tres receberiam a previsao da vizinha. Recebem a mesma de antes.
    """
    modelo = _modelo()
    sem = modelo.predict(_tipar(pd.DataFrame({"location_id": TREINADAS, "nivel": 1.0}))[FEATS])
    com = modelo.predict(
        _tipar(pd.DataFrame({"location_id": ["a-nova", *TREINADAS], "nivel": 1.0}))[FEATS]
    )
    assert np.allclose(sem, com[1:]), (
        "o LightGBM deixou de realinhar categoria por rotulo. `tipar_mensal` deriva "
        "as categorias dos dados presentes e passa a estar ERRADO: a previsao de "
        "cada praca vira a da vizinha. Alinhar pelas categorias do treino, "
        "guardadas no artefato, e' a correcao."
    )


def test_o_modelo_realmente_separa_as_pracas():
    """A premissa do teste de cima: o alvo depende de `location_id`.

    Se o modelo ignorasse a coluna, as previsoes seriam iguais de qualquer jeito e o
    `allclose` acima passaria sem medir nada.

    O assert e' de SEPARACAO, e nao de igualdade com 10/20/30: com 60 arvores e perda
    tweedie o modelo chega a 10,8 / 20,0 / 29,1, e exigir o alvo exato mediria a
    convergencia do LightGBM em vez do que este arquivo trata.
    """
    previsto = _modelo().predict(
        _tipar(pd.DataFrame({"location_id": TREINADAS, "nivel": 1.0}))[FEATS]
    )
    assert previsto[0] < previsto[1] < previsto[2], previsto
    # Bem separadas: a menor distancia entre duas delas e' maior que qualquer erro
    # de convergencia plausivel, entao trocar duas pelo codigo seria visivel.
    assert min(np.diff(previsto)) > 5.0, previsto
