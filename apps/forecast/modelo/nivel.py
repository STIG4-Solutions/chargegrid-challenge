"""O NIVEL do mes: o numero que vai para o card, previsto no grao dele.

POR QUE UM SEGUNDO MODELO. Nivel e forma tem vencedores diferentes, e um modelo
so' para os dois eixos fazia cada um estragar o outro. Medido com 24 meses:

    eixo          quem ganha                      numero
    forma diaria  modelo diario                   29,90%  (regua: 36,10%)
    nivel mensal  modelo MENSAL sobre a regua       8,62%  (regua:  9,95%)

O modelo diario, mesmo preso ao nivel, nao pode melhorar o nivel - prende-lo foi
justamente tirar dele esse poder. Quem melhora o nivel e' um modelo no grao em
que o nivel existe: um registro por praca-mes, com o previsor de ano-a-ano como
ponto de partida e a tarefa de corrigi-lo.

E ele CORRIGE, mas por MENOS do que o plano pedia. Medido com 12 meses no banco
local, n=84 registros mensais:

    regua de ano-a-ano        8,67%
    modelo do nivel           8,06%      ganho de 0,61 ponto

O criterio de aceite do plano era bater a melhor regua por >= 1 ponto no mes.
0,61 NAO atende. E' o unico lugar deste pipeline onde ML bate a regua em vez de
empatar com ela - antes o modelo perdia por 0,01 da media movel e a media movel
perdia por 5,3 da de ano-a-ano -, mas 0,61 ponto sobre 84 observacoes e' pequeno,
e chama-lo de vitoria seria exagerar o que a medicao suporta.

Ablacao do que custa cada decimo, mesmo walk-forward:

    limiar 150, sem as features novas      7,75%   (+0,91)
    limiar 180, sem as features novas      8,00%   (+0,67)
    limiar 180, com `tem_ano`              8,06%   (+0,61)   <- o que esta' aqui
    limiar 180, com `tem_ano` e `feriados` 8,41%   (+0,26)

Duas leituras, e as duas ficam registradas. Alinhar `MIN_HIST_DIAS` para 180 custa
0,25 ponto, e foi escolha deliberada: o que ele conserta e' um aviso que afirmava
ao operador que uma praca seria ignorada quando nao era, e isso vale mais que um
decimo de uma metrica medida sobre dado sintetico. `feriados` era erro meu -
entrou por intuicao e custava 0,35 ponto.

O ALVO. `total_do_mes / (nivel_ano x dias)`, uma razao outra vez, pelo mesmo
motivo de sempre: razao 1,0 reproduz a regua, entao o pior caso do modelo e'
empatar com ela e nao ficar abaixo.

`dias` E' FEATURE, e nao um detalhe. Fevereiro tem 28 dias e marco tem 31: 10%
de diferenca no total sem nenhuma mudanca de demanda. O calendario do mes alvo e'
conhecido na origem, entao usa-lo nao e' vazamento.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from .perda import PARAMS_NIVEL, treinar_um

# As features do grao mensal. Saem `dow`, `is_weekend`, `dia_mes` e `horizonte` -
# nenhuma existe no agregado. Entra `dias`, que e' o que sobra do calendario
# quando se soma o mes.
#
# `feriados` (a contagem de feriados do mes) NAO entra, e a razao e' medida: com
# ela o WAPE mensal sai 8,41% e sem ela 8,06%. Ela piora. A explicacao plausivel
# e' que a contagem de feriados e' quase funcao do mes do calendario, entao ela
# duplica `mes` com ruido - e um modelo de 7 folhas treinado em ~280 registros
# nao tem folga para gastar um corte nisso. `painel_mensal` continua a calcular,
# porque e' com ela que a ablacao se refaz.
FEATURES_MENSAIS = [
    "mes",
    "dias",
    "hist_m7",
    "hist_m28",
    "hist_m91",
    "hist_m182",
    "hist_std28",
    "tend_28_91",
    "tend_7_28",
    "crescimento",
    "por_dia_ano",
    "tem_ano",
    "archetype",
    "power_type",
    "n_connectors",
    "dias_operacao",
    "location_id",
]
CATEGORICAS_MENSAIS = ["archetype", "power_type", "location_id"]

# Abaixo disto o modelo do nivel nao e' treinado e o nivel fica sendo a regua.
# Um registro por praca-mes: 60 sao ~5 meses de uma rede de 12 pracas, ou 8
# meses de 7. Com menos que isso um modelo de 7 folhas tem mais folhas do que
# padroes para achar.
MINIMO_DE_REGISTROS = 60

# Teto e piso da correcao que o modelo pode aplicar a regua. O modelo trabalha em
# razao, e uma razao de 4,0 vinda de uma praca-mes estranha multiplicaria o card
# por quatro. A regua erra ~10%; permitir correcao de +-60% e' folga de sobra, e
# o limite e' o que separa "o modelo corrigiu" de "o modelo inventou".
CORRECAO_MINIMA, CORRECAO_MAXIMA = 0.4, 1.6


def painel_mensal(df: pd.DataFrame) -> pd.DataFrame:
    """Um registro por (praca, mes alvo): o total real e as features da origem.

    As features de origem sao identicas em todas as linhas do mes - vem do
    resumo do historico ate a origem -, entao `first` as agrega sem perder nada.
    O que precisa de soma e' o alvo, a contagem de dias e a de feriados.
    """
    colunas = {c: (c, "first") for c in FEATURES_MENSAIS if c not in ("dias", "location_id")}
    colunas["real"] = ("y_kwh", "sum")
    colunas["dias"] = ("date", "size")
    colunas["feriados"] = ("is_feriado", "sum")
    colunas["nivel_ano"] = ("nivel_ano", "first")
    m = df.groupby(["location_id", "mes_alvo"], observed=True).agg(**colunas).reset_index()
    m["base_regua"] = m["nivel_ano"] * m["dias"]
    return m


def tipar_mensal(df: pd.DataFrame) -> pd.DataFrame:
    """As colunas categoricas como `category`, que e' o que o LightGBM exige.

    Derivar as categorias dos dados presentes E' seguro, e isto foi medido em vez
    de suposto: o LightGBM guarda as categorias do treino e realinha por ROTULO na
    previsao. Uma praca nova cadastrada antes de um retreino desloca os CODIGOS e
    nao muda a previsao das outras - `tests/test_categoria_por_rotulo.py` prende
    esse comportamento, porque este codigo depende dele.
    """
    d = df[FEATURES_MENSAIS].copy()
    for coluna in CATEGORICAS_MENSAIS:
        d[coluna] = d[coluna].astype("category")
    return d


def treinar_nivel(tr_mensal: pd.DataFrame, **sobrepor) -> LGBMRegressor | None:
    """Treina a correcao da regua no grao mensal, ou `None` se ha' pouco dado.

    `None` nao e' falha: e' a decisao de deixar o nivel com a regua, que e' o
    valor conservador. Quem chama trata os dois casos.
    """
    # UMA guarda, e sobre as linhas UTEIS. Havia duas - uma sobre `len(tr_mensal)` e
    # outra sobre as linhas com alvo valido - e o teste de mutacao mostrou que a
    # segunda mascarava a primeira: reverter a de cima nao quebrava nada. A que ficou
    # e' a que importa, porque uma praca-mes sem `base_regua` nao treina nada.
    y = tr_mensal["real"] / tr_mensal["base_regua"].replace(0, np.nan)
    ok = y.notna() & np.isfinite(y)
    if ok.sum() < MINIMO_DE_REGISTROS:
        return None
    return treinar_um(
        tipar_mensal(tr_mensal[ok]), y[ok], CATEGORICAS_MENSAIS, PARAMS_NIVEL, **sobrepor
    )


def prever_nivel(modelo: LGBMRegressor | None, te_mensal: pd.DataFrame) -> np.ndarray:
    """Total do mes por praca. Sem modelo, devolve a regua."""
    base = te_mensal["base_regua"].to_numpy(float)
    if modelo is None:
        return base
    correcao = np.clip(modelo.predict(tipar_mensal(te_mensal)), CORRECAO_MINIMA, CORRECAO_MAXIMA)
    return correcao * base
