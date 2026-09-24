"""O backtest mede o modelo contra reguas que nao usam modelo nenhum?

Havia uma assimetria no dicionario de metricas: `wape_mensal` vinha com
`wape_mensal_baseline_m28` ao lado, e `wape_diario` vinha sozinho. Um erro sem
regua nao e' avaliavel - 25,94% pode ser otimo ou pessimo, e nada no artefato
decide qual.

A assimetria escondeu um resultado concreto. Medido no painel do staging, o
modelo faz 25,94% no eixo diario e `hist_dow` CRU faz 25,91%: as 700 arvores
reproduzem uma das proprias features. Enquanto a metrica diaria nao tivesse
regua, esse fato nao tinha onde aparecer.

Estes testes prendem as quatro reguas ao backtest, e prendem em especial a que
distingue as duas conclusoes: a regua `dow` precisa vir de `hist_dow`, nao de
`hist_m28`.

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
import pytest  # noqa: E402

from pipeline.features import CATEGORICAS  # noqa: E402
from pipeline.train import backtest  # noqa: E402

MESES = ["2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01"]

REGUAS = [
    "wape_mensal_baseline_m28",
    "wape_mensal_baseline_dow",
    "wape_diario_baseline_m28",
    "wape_diario_baseline_dow",
]


def _dataset(n_por_mes: int = 120, dow_certeiro: bool = True) -> pd.DataFrame:
    """Painel sintetico onde `hist_dow` e `hist_m28` discordam DE PROPOSITO.

    O alvo tem sazonalidade semanal de verdade: fim de semana vale o dobro.
    `hist_dow` conhece essa sazonalidade; `hist_m28` e' o nivel achatado, cego
    a ela. Sem essa divergencia as duas reguas dariam o mesmo numero e trocar
    uma pela outra passaria despercebido - o teste nao mediria nada.
    """
    rng = np.random.default_rng(11)
    linhas = []
    for mes in MESES:
        inicio = pd.Timestamp(mes)
        for i in range(n_por_mes):
            data = inicio + pd.Timedelta(days=i % 28)
            dow = int(data.dayofweek)
            fds = dow >= 5
            nivel = 100.0
            real = nivel * (2.0 if fds else 1.0) * float(rng.normal(1, 0.05))
            linhas.append(
                {
                    "mes_alvo": pd.Timestamp(mes),
                    "date": data,
                    "location_id": ["a-station", "b-station"][i % 2],
                    "horizonte": (i % 28) + 1,
                    "dow": dow,
                    "is_weekend": int(fds),
                    "mes": data.month,
                    "dia_mes": data.day,
                    "is_feriado": 0,
                    "is_vespera_feriado": 0,
                    "hist_m7": nivel,
                    "hist_m28": nivel,
                    "hist_m91": nivel,
                    "hist_m182": nivel,
                    "hist_std28": 10.0,
                    "hist_ano_atras": nivel,
                    "tend_28_91": 1.0,
                    "tend_7_28": 1.0,
                    # A regua que enxerga o fim de semana - ou, quando
                    # `dow_certeiro` e' falso, uma que nao enxerga.
                    "hist_dow": nivel * (2.0 if (fds and dow_certeiro) else 1.0),
                    "archetype": "shopping",
                    "power_type": "dc",
                    "n_connectors": 4,
                    "dias_operacao": 500,
                    "y_kwh": real,
                    "y_ratio": real / nivel,
                }
            )
    df = pd.DataFrame(linhas)
    for coluna in CATEGORICAS:
        df[coluna] = df[coluna].astype("category")
    return df


@pytest.fixture(scope="module")
def metricas() -> dict:
    return backtest(_dataset(), n_meses=2)


def test_as_quatro_reguas_saem_no_artefato(metricas):
    """Cada erro do modelo tem a sua regua ao lado, nos dois eixos."""
    faltando = [r for r in REGUAS if r not in metricas]
    assert not faltando, f"regua ausente do backtest: {faltando}"
    assert all(isinstance(metricas[r], float) for r in REGUAS)


def test_a_regua_dow_vem_de_hist_dow_e_nao_da_media_movel(metricas):
    """O teste que separa as duas conclusoes possiveis sobre o modelo.

    O alvo aqui tem fim de semana valendo o dobro. `hist_dow` sabe disso e
    `hist_m28` nao, entao a regua `dow` TEM de errar menos. Se alguem trocar
    `hist_dow` por `hist_m28` na origem da coluna, os dois numeros colapsam e
    esta comparacao morre - que e' o unico jeito de a troca ser notada.
    """
    assert metricas["wape_diario_baseline_dow"] < metricas["wape_diario_baseline_m28"]
    assert metricas["wape_diario_baseline_m28"] - metricas["wape_diario_baseline_dow"] > 5.0


def test_a_regua_m28_ignora_o_fim_de_semana(metricas):
    """A regua simples erra MUITO neste painel, e isso e' a prova de que ela e'
    mesmo o nivel achatado - um numero pequeno aqui significaria que a coluna
    foi trocada por alguma que enxerga o dia da semana."""
    assert metricas["wape_diario_baseline_m28"] > 20.0


def test_a_regua_dow_cai_para_m28_quando_nao_ha_historico_de_dia_da_semana():
    """Estacao com menos de 56 dias nao tem `hist_dow`: a coluna vem NaN.

    Sem o fallback, o WAPE da regua sai NaN e o artefato grava `null` onde
    deveria haver um numero - o portao passaria a comparar contra nada. Aqui
    todo `hist_dow` e' NaN, entao a regua `dow` tem de ser exatamente a m28.
    """
    ds = _dataset()
    ds["hist_dow"] = np.nan
    m = backtest(ds, n_meses=2)
    assert m["wape_diario_baseline_dow"] == m["wape_diario_baseline_m28"]
    assert not np.isnan(m["wape_diario_baseline_dow"])


def test_o_eixo_mensal_tambem_ganha_a_regua_dow(metricas):
    """A regua `dow` existe nos DOIS eixos.

    Foi no mensal que ela mudou a decisao: no painel do staging faz 8,43%
    contra 9,07% da media movel, ou seja, bate o que hoje vai para producao.
    Uma regua so' no eixo diario deixaria isso invisivel outra vez.
    """
    assert metricas["wape_mensal_baseline_dow"] < metricas["wape_mensal_baseline_m28"]


def test_o_numero_de_observacoes_mensais_aparece(metricas):
    """9 observacoes mensais no staging - 3 locais x 3 meses.

    O portao decide promover o modelo por diferencas de decimo de ponto. Sem o
    tamanho da amostra ao lado, `9.26 vs 9.07` parece uma medicao; com ele,
    fica visivel que a diferenca cabe no ruido.
    """
    assert metricas["n_obs_mensal"] == 4  # 2 locais x 2 meses de teste
