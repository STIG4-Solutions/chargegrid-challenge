"""O backtest mede o modelo contra a MELHOR regua, e nao contra a mais conveniente.

O defeito original era uma assimetria: `wape_mensal` vinha com
`wape_mensal_baseline_m28` ao lado, e `wape_diario` vinha sozinho. Um erro sem
regua nao e' avaliavel.

Depois a medicao mostrou um defeito maior. A media movel de 28 dias nao e' a melhor
regua, nem de longe - e comparar so' com ela era uma barra baixa que nao provava
nada. Medido no banco local com 12 meses de walk-forward, n=84 registros mensais:

    eixo     m28      dow      ano-a-ano
    dia    36,31    29,85         34,67
    mes    13,95    14,20          8,67

Nenhuma ganha nos dois eixos, e no mes a distancia entre a melhor e a que o portao
usava e' de 5,3 pontos. Entao as TRES ficam medidas nos dois eixos, e o portao usa
a melhor.

Estes testes prendem as seis metricas e, em especial, que cada regua venha da
coluna certa: trocar a origem de uma delas colapsa a comparacao e o portao volta a
promover o modelo contra uma barra que nao existe.

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

from modelo.aferir import N_CALIB, backtest  # noqa: E402
from modelo.forma import features_da_forma  # noqa: E402
from pipeline.features import CATEGORICAS, FEATURES  # noqa: E402

# Meses suficientes para os 2 alvos MAIS a janela de calibracao da faixa.
MESES = [f"2025-{mes:02d}-01" for mes in range(1, 13)] + [
    f"2026-{mes:02d}-01" for mes in range(1, 4)
]

REGUAS = [
    "wape_mensal_baseline_m28",
    "wape_mensal_baseline_dow",
    "wape_mensal_baseline_ano",
    "wape_diario_baseline_m28",
    "wape_diario_baseline_dow",
    "wape_diario_baseline_ano",
]

FEATURES_DA_FORMA = features_da_forma(FEATURES)


def _dataset(dow_certeiro: bool = True, ano_certeiro: bool = True) -> pd.DataFrame:
    """Painel sintetico onde as TRES reguas discordam de proposito.

    O alvo tem duas sazonalidades de verdade: fim de semana vale o dobro, e o mes
    do calendario tem um fator proprio. `hist_dow` conhece a primeira, `nivel_ano`
    conhece a segunda, e `hist_m28` e' o nivel achatado, cego as duas. Sem essa
    divergencia as reguas dariam o mesmo numero e trocar uma pela outra passaria
    despercebido - o teste nao mediria nada.

    A media de `razao_ano_dia` no mes e' 1,0 de proposito (8/7 nos cinco dias de
    semana e 2 x 7/8 nos dois de fim de semana): assim `nivel_ano` e' o nivel
    MEDIO do mes, e nao o de um dia de semana.
    """
    rng = np.random.default_rng(11)
    fator_do_mes = {m: 1.0 + 0.4 * ((m % 3) - 1) for m in range(1, 13)}
    linhas = []
    for mes in MESES:
        inicio = pd.Timestamp(mes)
        for i in range(120):
            data = inicio + pd.Timedelta(days=i % 28)
            dow = int(data.dayofweek)
            fds = dow >= 5
            nivel = 100.0
            fator = fator_do_mes[data.month]
            real = nivel * fator * (2.0 if fds else 1.0) * float(rng.normal(1, 0.05))
            linhas.append(
                {
                    "mes_alvo": pd.Timestamp(mes),
                    "date": data,
                    "origem": inicio - pd.Timedelta(days=1),
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
                    # A regua que enxerga o MES: o nivel medio do mesmo mes um ano
                    # antes, ja' corrigido pelo crescimento.
                    "nivel_ano": nivel * (fator * 9 / 7 if ano_certeiro else 1.0),
                    "razao_ano_dia": (2.0 if fds else 1.0) * 7 / 9,
                    "tem_ano": True,
                    "crescimento": 1.3,
                    "por_dia_ano": nivel,
                    "archetype": "shopping",
                    "power_type": "dc",
                    "n_connectors": 4,
                    "dias_operacao": 500,
                    "y_kwh": real,
                }
            )
    df = pd.DataFrame(linhas)
    for coluna in CATEGORICAS:
        df[coluna] = df[coluna].astype("category")
    return df


@pytest.fixture(scope="module")
def metricas() -> dict:
    return backtest(_dataset(), n_meses=2, categoricas=CATEGORICAS, features=FEATURES_DA_FORMA)


def test_as_seis_reguas_saem_no_artefato(metricas):
    """Cada erro do modelo tem as TRES reguas ao lado, nos dois eixos."""
    faltando = [r for r in REGUAS if r not in metricas]
    assert not faltando, f"regua ausente do backtest: {faltando}"
    assert all(isinstance(metricas[r], float) for r in REGUAS)


def test_a_regua_dow_vem_de_hist_dow_e_nao_da_media_movel(metricas):
    """O teste que separa duas conclusoes possiveis sobre o eixo diario.

    O alvo tem fim de semana valendo o dobro. `hist_dow` sabe disso e `hist_m28`
    nao, entao a regua `dow` TEM de errar menos no dia. Trocar a coluna de origem
    colapsa os dois numeros e esta comparacao morre.
    """
    assert metricas["wape_diario_baseline_dow"] < metricas["wape_diario_baseline_m28"]
    # 3 pontos, e nao 5: o painel deste teste ganhou uma SEGUNDA sazonalidade - a
    # mensal, que a regua `dow` tambem nao ve. Isso sobe os dois erros e estreita a
    # diferenca entre eles. Medido: 44,28 contra 39,98.
    assert metricas["wape_diario_baseline_m28"] - metricas["wape_diario_baseline_dow"] > 3.0


def test_a_regua_de_ano_vem_de_nivel_ano_e_ganha_no_MES(metricas):
    """A regua que o portao passa a usar, e a prova de que ela vem do lugar certo.

    O alvo tem um fator por mes que so' `nivel_ano` conhece. No eixo mensal ela TEM
    de bater as outras duas; se alguem apontar a metrica para `hist_m28`, os
    numeros colapsam.
    """
    assert metricas["wape_mensal_baseline_ano"] < metricas["wape_mensal_baseline_m28"]
    assert metricas["wape_mensal_baseline_ano"] < metricas["wape_mensal_baseline_dow"]


def test_a_regua_m28_ignora_as_duas_sazonalidades(metricas):
    """A regua simples erra MUITO neste painel, e isso e' a prova de que ela e'
    mesmo o nivel achatado - um numero pequeno significaria que a coluna foi
    trocada por alguma que enxerga o dia da semana ou o mes."""
    assert metricas["wape_diario_baseline_m28"] > 20.0


def test_a_regua_dow_cai_para_m28_quando_nao_ha_historico_de_dia_da_semana():
    """Praca com menos de 56 dias nao tem `hist_dow`: a coluna vem NaN.

    Sem o fallback, o WAPE da regua sai NaN e o artefato grava `null` onde deveria
    haver numero - o portao passaria a comparar contra nada.
    """
    ds = _dataset()
    ds["hist_dow"] = np.nan
    m = backtest(ds, n_meses=2, categoricas=CATEGORICAS, features=FEATURES_DA_FORMA)
    assert m["wape_diario_baseline_dow"] == m["wape_diario_baseline_m28"]
    assert not np.isnan(m["wape_diario_baseline_dow"])


def test_a_forma_somada_reproduz_a_regua_de_ano(metricas):
    """A conferencia de que o prendimento nao quebrou.

    A forma presa soma `nivel_ano x dias` por construcao, entao esta metrica tem de
    ser IGUAL a regua de ano-a-ano. Divergirem significa que a razao voltou a poder
    mexer no nivel - o defeito que custava 3,5 pontos.
    """
    assert metricas["wape_mensal_forma_somada"] == metricas["wape_mensal_baseline_ano"]


def test_o_numero_de_observacoes_aparece_nos_dois_graos(metricas):
    """O portao decide por diferencas de decimo de ponto.

    Sem o tamanho da amostra ao lado, `8,06 vs 8,67` parece uma medicao; com ele
    fica visivel quanta folga a diferenca tem.
    """
    assert metricas["n_obs_mensal"] == 4  # 2 locais x 2 meses de teste
    assert metricas["n_obs_teste"] > 0


def test_a_janela_do_backtest_inclui_os_meses_de_calibracao(metricas):
    """A faixa precisa de meses ANTES de cada alvo, e eles nao sao reportados.

    O assert que importa e' o ultimo: TODA linha de teste tem de ter faixa. Se a
    janela do walk-forward fosse so' os meses alvo, o primeiro ficaria sem meses de
    calibracao antes dele, sairia sem faixa, e a cobertura viria de um subconjunto
    sem dizer que era um subconjunto.

    Foi o teste de mutacao que apontou a lacuna: encurtar a janela nao matava nenhum
    assert, porque `meses_testados` continuava com dois e `N_CALIB` era so' uma
    constante.
    """
    assert N_CALIB >= 3
    assert len(metricas["meses_testados"]) == 2
    assert metricas["n_com_faixa_diaria"] == metricas["n_obs_teste"], (
        "alguma linha de teste ficou sem faixa - a janela de calibracao nao cobre "
        "todos os meses alvo"
    )


def test_a_cobertura_sai_nos_dois_graos(metricas):
    """O card e' um total mensal: a cobertura de uma faixa diaria nao vale para a
    soma de trinta dias, e o exportador precisa da mensal."""
    assert "cobertura_p10_p90_diaria" in metricas
    assert "cobertura_p10_p90_mensal" in metricas
    assert metricas["fatores_da_faixa"]["dia"] is not None
