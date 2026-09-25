"""O eixo ano-a-ano, que era o que faltava.

O DEFEITO. `pipeline/features.py` tem uma feature chamada `hist_ano_atras`:

    ano_atras = hist.tail(395).head(31)

Com a origem no ultimo dia do mes M, `tail(395)` termina na origem e `head(31)`
pega os 31 primeiros desses 395 - ou seja, origem-394 ate origem-364. Com origem
2026-01-31 e alvo fevereiro, isso e' 2025-01-02 ate 2025-02-01. A feature
chamada "um ano atras" cobre o mes ANTERIOR ao alvo, um ano antes. O alvo um ano
antes seria 2025-02-01..2025-02-28.

E ela e' NIVEL, nao razao. `tend_28_91` e `tend_7_28` sao razoes - o padrao
existe no pipeline. Para usar um nivel de um ano atras a arvore teria de formar o
quociente `hist_ano_atras / hist_m28`, e corte axial representa quociente mal.

O que cada defeito custa, medido com walk-forward de 12 meses:

    modelo como esta'                                    13,96%
    + a razao com a janela ERRADA (hist_ano_atras/m28)   14,01%   nada
    + a razao alinhada ao mes alvo                       11,88%   2 pontos

A razao com a janela errada nao vale nada, o que isola os dois defeitos: nao era
so' a forma da feature, era o mes para onde ela apontava.

364 E NAO 365. Um ano de 364 dias sao exatas 52 semanas, entao o dia da semana se
preserva: uma terca-feira e' comparada com uma terca-feira. Com 365 o alinhamento
anda um dia por ano e a comparacao mistura sabado com domingo, que numa praca
corporativa diferem por um fator de tres.

TUDO ESTRITAMENTE DO PASSADO. O dia alvo mais distante e' origem+31, e
origem+31-364 = origem-333: nenhuma coluna aqui olha para depois da origem.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# 52 semanas. Preserva o dia da semana - ver o cabecalho.
UM_ANO = pd.Timedelta(days=364)

# Teto do fator de crescimento ano-a-ano. Uma praca que abriu no meio do ano
# anterior tem media de 28 dias daquela epoca perto de zero, e a razao
# `hist_m28 / m28_de_um_ano_atras` explodiria - levando `nivel_ano` com ela.
# Triplicar em doze meses ja' e' mais do que qualquer praca madura faz, e o
# proprio seed cresce ~30% ao ano.
LIMITE_DE_CRESCIMENTO = 3.0

# Minimo de dias para a media movel de referencia daquela epoca. Metade da
# janela: com menos que isso a media e' de um punhado de dias e nao serve de
# escala.
MIN_DIAS_NA_JANELA = 14


def _painel_indexado(painel: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Do painel diario: kWh por dia, media movel de 28 dias, e media por mes.

    A media movel e' calculada UMA vez e reusada pelas tres colunas que precisam
    de "qual era o nivel naquela epoca" - refazer o rolling por coluna seria a
    mesma conta tres vezes sobre 10 mil linhas.
    """
    p = painel[["location_id", "date", "kwh"]].copy()
    p["location_id"] = p["location_id"].astype(str)
    p = p.sort_values(["location_id", "date"])
    p["m28"] = p.groupby("location_id")["kwh"].transform(
        lambda s: s.rolling(28, min_periods=MIN_DIAS_NA_JANELA).mean()
    )
    p["mes"] = p["date"].values.astype("datetime64[M]")
    mensal = p.groupby(["location_id", "mes"]).agg(total=("kwh", "sum"), dias=("kwh", "size"))
    por_dia_do_mes = (mensal["total"] / mensal["dias"].replace(0, np.nan)).rename("por_dia")
    chave = ["location_id", "date"]
    return p.set_index(chave)["kwh"], p.set_index(chave)["m28"], por_dia_do_mes


def colunas_de_ano(df: pd.DataFrame, painel: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta as colunas de ano-a-ano a um dataset de features.

    Serve tanto para `construir_treino` quanto para `construir_previsao`: as
    duas produzem `location_id`, `date`, `origem`, `mes_alvo` e `hist_m28`, que
    e' tudo o que se usa aqui. Uma funcao so' para treino e previsao pela mesma
    razao que `features.py` da' no cabecalho dele - montar as colunas com
    codigos diferentes nos dois lados e' training/serving skew, que degrada
    calado.

    Colunas produzidas:

    `nivel_ano`   o previsor de nivel: quanto a praca fez por dia no mesmo mes
                  do calendario um ano antes, corrigido pelo crescimento. E' o
                  normalizador do modelo da forma, e serve de regua sozinho.
    `tem_ano`     se havia ano anterior. Entra como feature: a linha que caiu
                  para media movel esta' num regime diferente, e o modelo tem
                  de poder ver isso em vez de tratar as duas igual.
    `razao_ano_dia`  a forma daquele DIA um ano antes, sem nivel. E' o que sobra
                  para o modelo depois que `nivel_ano` levou o nivel do mes.
    `crescimento` o fator, exposto porque o modelo do nivel o usa como feature.
    """
    kwh, m28, por_dia_do_mes = _painel_indexado(painel)

    d = df.copy()
    loc = d["location_id"].astype(str)

    # O MESMO mes do calendario, um ano antes. `DateOffset(years=1)` e nao 364
    # dias: aqui a unidade e' mes de calendario, e 364 dias nao cai no mesmo mes.
    mes_um_ano_antes = (pd.to_datetime(d["mes_alvo"]) - pd.DateOffset(years=1)).values.astype(
        "datetime64[M]"
    )
    d["por_dia_ano"] = pd.Series(
        pd.MultiIndex.from_arrays([loc, pd.to_datetime(mes_um_ano_antes)]).map(por_dia_do_mes),
        index=d.index,
    ).astype(float)

    # Crescimento: nivel na origem sobre o nivel na origem um ano antes. Sem
    # isto o previsor devolveria o volume do ano passado numa rede que cresce
    # 30% ao ano, e subestimaria tudo por construcao.
    origem_um_ano_antes = pd.to_datetime(d["origem"]) - pd.DateOffset(years=1)
    nivel_antigo = pd.Series(
        m28.reindex(pd.MultiIndex.from_arrays([loc, origem_um_ano_antes])).to_numpy(),
        index=d.index,
    )
    d["crescimento"] = (d["hist_m28"] / nivel_antigo.replace(0, np.nan)).clip(
        upper=LIMITE_DE_CRESCIMENTO
    )

    nivel = (d["por_dia_ano"] * d["crescimento"]).replace([0, np.inf, -np.inf], np.nan)
    d["tem_ano"] = nivel.notna()
    # Sem ano anterior o nivel volta a ser a media movel. Nao e' um caso raro -
    # e' toda praca no primeiro ano de operacao, e o `tem_ano` acima e' o que
    # deixa o modelo distinguir os dois regimes.
    d["nivel_ano"] = nivel.fillna(d["hist_m28"])

    dia_um_ano_antes = pd.MultiIndex.from_arrays([loc, d["date"] - UM_ANO])
    d["razao_ano_dia"] = pd.Series(
        kwh.reindex(dia_um_ano_antes).to_numpy(), index=d.index
    ) / pd.Series(m28.reindex(dia_um_ano_antes).to_numpy(), index=d.index).replace(0, np.nan)
    return d
