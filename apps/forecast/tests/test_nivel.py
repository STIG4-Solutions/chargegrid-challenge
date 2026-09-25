"""O modelo do nivel nunca fica ABAIXO da regua que ele deveria corrigir.

O alvo dele e' `total / (nivel_ano x dias)`: razao 1,0 reproduz a regua, entao o
pior caso e' empatar. Estes testes prendem as tres decisoes que garantem isso:

  - pouco dado -> nao treina, e o nivel FICA sendo a regua
  - a correcao e' presa em [0,4 ; 1,6], porque uma razao de 4,0 vinda de uma
    praca-mes estranha multiplicaria o card por quatro
  - `feriados` nao e' feature, e o numero que mostra por que

O QUE ESTE ARQUIVO NAO AFIRMA. Havia aqui um teste dizendo que arvore rasa bate
arvore larga no grao mensal. Ele FALHOU, e a medicao no painel real concordou com
ele: com 12 meses de teste, `num_leaves=63` faz 7,51% contra 8,06% das 7 folhas.

O que salvou `num_leaves=7` foi separar selecao de relato. Escolhendo na janela
2024-09..2025-08 e relatando em 2025-09..2026-08:

    folhas  min_child   SELECAO   RELATO
         3         20     10,40     8,72
         7         20     10,19     8,06   <- escolhido pela selecao
        15         20     10,20     7,97
        63          2     10,70     7,51
     regua                11,69     8,67

Na selecao as 63 folhas sao as PIORES da grade. O 7,51 era sorte de escolher
olhando o conjunto de teste. `num_leaves=7` fica porque e' o que uma selecao
honesta escolhe - nao porque folha larga decore a praca, que era o que eu havia
escrito e nao se sustenta.

E o achado que importa mais: a escolha de hiperparametro move o numero entre 7,51
e 8,72, enquanto o modelo bate a regua por 0,61. A dispersao da grade e' MAIOR que
a vantagem sobre a regua.

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

from modelo.nivel import (  # noqa: E402
    CORRECAO_MAXIMA,
    CORRECAO_MINIMA,
    FEATURES_MENSAIS,
    MINIMO_DE_REGISTROS,
    painel_mensal,
    prever_nivel,
    treinar_nivel,
)
from modelo.perda import PARAMS_NIVEL  # noqa: E402
from pipeline.train import wape  # noqa: E402

PRACAS = ["praca-a", "praca-b", "praca-c"]


def _mensal(n_meses: int = 36, ruido: float = 0.05, semente: int = 4) -> pd.DataFrame:
    """Registros mensais em que a regua erra de um jeito APRENDIVEL.

    A regua (`base_regua`) e' o nivel do ano passado; o real tem, por cima dela, um
    fator que depende do mes do calendario. Um modelo que use `mes` recupera esse
    fator; um que nao use fica preso na regua. Sem esse sinal, comparar modelo e
    regua nao mediria nada.
    """
    rng = np.random.default_rng(semente)
    por_mes = {m: 1.0 + 0.25 * np.sin(m / 12 * 2 * np.pi) for m in range(1, 13)}
    linhas = []
    inicio = pd.Timestamp("2023-01-01")
    for i in range(n_meses):
        mes = inicio + pd.DateOffset(months=i)
        for j, praca in enumerate(PRACAS):
            nivel = 10.0 * (j + 1)
            linhas.append(
                {
                    "location_id": praca,
                    "mes_alvo": mes,
                    "date": mes,
                    "y_kwh": nivel * mes.days_in_month * por_mes[mes.month] * rng.normal(1, ruido),
                    "nivel_ano": nivel,
                    "mes": mes.month,
                    "hist_m7": nivel,
                    "hist_m28": nivel,
                    "hist_m91": nivel,
                    "hist_m182": nivel,
                    "hist_std28": nivel * 0.1,
                    "tend_28_91": 1.0,
                    "tend_7_28": 1.0,
                    "crescimento": 1.3,
                    "por_dia_ano": nivel,
                    "tem_ano": True,
                    "archetype": "shopping",
                    "power_type": "dc",
                    "n_connectors": 4,
                    "dias_operacao": 500 + i * 30,
                    "is_feriado": 0,
                }
            )
    # O quadro ja' vem no grao mensal, entao `painel_mensal` contaria 1 dia por
    # mes: `dias` e `base_regua` sao reescritos com o calendario de verdade.
    m = painel_mensal(pd.DataFrame(linhas))
    m["dias"] = [pd.Timestamp(x).days_in_month for x in m["mes_alvo"]]
    m["base_regua"] = m["nivel_ano"] * m["dias"]
    return m


def _partir(m: pd.DataFrame, corte: str = "2025-01-01"):
    c = pd.Timestamp(corte)
    return m[m["mes_alvo"] < c], m[m["mes_alvo"] >= c].copy()


def test_o_modelo_do_nivel_bate_a_regua_que_corrige():
    """Se ele nao batesse, nao haveria razao para existir.

    O painel tem um fator sazonal por mes que a regua nao ve. O modelo tem `mes`
    como feature: ele tem de recuperar parte desse fator e errar menos.
    """
    tr, te = _partir(_mensal())
    modelo = treinar_nivel(tr)
    assert modelo is not None
    te["prev"] = prever_nivel(modelo, te)
    erro_modelo = wape(te["real"], te["prev"])
    erro_regua = wape(te["real"], te["base_regua"])
    assert erro_modelo < erro_regua, (erro_modelo, erro_regua)


def test_os_parametros_do_nivel_sao_os_que_a_selecao_escolheu():
    """O valor foi escolhido numa janela e relatado em outra - ver o cabecalho.

    O assert existe para que troca-lo seja uma decisao registrada: mexer nele sem
    refazer a selecao volta a escolher hiperparametro no conjunto de teste, e a
    dispersao da grade e' maior que a vantagem do modelo sobre a regua.
    """
    assert PARAMS_NIVEL["num_leaves"] == 7
    assert PARAMS_NIVEL["min_child_samples"] == 20
    # A perda e' a mesma do modelo da forma: medir com uma e publicar outra foi o
    # defeito que este trabalho conserta.
    assert PARAMS_NIVEL["objective"] == "tweedie"


def test_com_pouco_dado_nao_treina_e_o_nivel_fica_sendo_a_regua():
    """`None` nao e' falha: e' a decisao de nao inventar um modelo com 12 linhas.

    E `prever_nivel(None, ...)` tem de devolver a regua EXATA - devolver zero ou
    NaN apagaria o card de uma praca que tem movimento.
    """
    m = _mensal(n_meses=4)
    assert len(m) < MINIMO_DE_REGISTROS
    assert treinar_nivel(m) is None
    assert np.allclose(prever_nivel(None, m), m["base_regua"].to_numpy())


class _ModeloDeMentira:
    """Devolve sempre a mesma razao. Testa a GUARDA, e nao o LightGBM.

    A versao anterior deste teste treinava num painel com uma praca-mes absurda e
    esperava que o modelo devolvesse razao fora da faixa. O teste de mutacao mostrou
    que ele nao devolvia: tirar o clip nao quebrava nada, porque o modelo real, com
    arvore rasa e 300 arvores, nunca chegava perto dos limites. O teste media a
    prudencia do LightGBM em vez do clip.
    """

    def __init__(self, razao: float) -> None:
        self.razao = razao

    def predict(self, X):
        return np.full(len(X), self.razao)


def test_a_correcao_e_presa_por_cima():
    """Um modelo que devolva razao 9,0 nao pode nonuplicar o numero da tela."""
    _, te = _partir(_mensal())
    previsto = prever_nivel(_ModeloDeMentira(9.0), te)
    razao = previsto / te["base_regua"].to_numpy()
    assert np.allclose(razao, CORRECAO_MAXIMA), razao[:3]


def test_a_correcao_e_presa_por_baixo():
    """E nem pode apagar o card: razao 0,01 gravaria uma praca praticamente parada.

    A regua erra ~10%; permitir correcao de -60% e' folga de sobra, e o limite e' o
    que separa "o modelo corrigiu" de "o modelo inventou".
    """
    _, te = _partir(_mensal())
    razao = prever_nivel(_ModeloDeMentira(0.01), te) / te["base_regua"].to_numpy()
    assert np.allclose(razao, CORRECAO_MINIMA), razao[:3]


def test_dentro_da_faixa_o_clip_nao_toca_na_previsao():
    """A guarda nao pode encostar no caso comum.

    Um clip que mexesse em razao 1,1 estaria distorcendo toda previsao normal em vez
    de barrar as absurdas.
    """
    _, te = _partir(_mensal())
    razao = prever_nivel(_ModeloDeMentira(1.1), te) / te["base_regua"].to_numpy()
    assert np.allclose(razao, 1.1), razao[:3]


def test_feriados_nao_e_feature_do_nivel():
    """Medido: com `feriados` o WAPE mensal sai 8,41% e sem ela 8,06%.

    Ela e' quase funcao do mes do calendario, entao duplica `mes` com ruido. O
    assert existe para que devolve-la seja uma decisao, e nao um descuido.
    """
    assert "feriados" not in FEATURES_MENSAIS
    assert "mes" in FEATURES_MENSAIS


def test_dias_e_feature_porque_fevereiro_nao_e_marco():
    """28 contra 31 dias sao 10% no total, sem nenhuma mudanca de demanda.

    O calendario do mes alvo e' conhecido na origem, entao usa-lo nao e' vazamento
    - e nao usa-lo faria o modelo pagar por uma diferenca que ele podia saber.
    """
    assert "dias" in FEATURES_MENSAIS
