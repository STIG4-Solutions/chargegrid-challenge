"""
Engenharia de features.
=======================

Modulo COMPARTILHADO entre treino e previsao. Isto e proposital: se treino e
previsao montarem features com codigos diferentes, o modelo recebe em
producao algo distinto do que viu no treino (training/serving skew) e degrada
silenciosamente. Uma funcao so, dois chamadores.

ESTRATEGIA: previsao DIRETA, sem recursao.
------------------------------------------
Origem da previsao = ultimo dia do mes M.
Alvo               = cada dia do mes M+1.

Toda feature vem de dado disponivel ATE a origem. Nenhum lag de 1 dia, porque
no momento real da previsao ele nao existiria. Evita a recursao (prever o dia
1 para poder prever o dia 2), que acumula erro ao longo do horizonte.

ALVO EM RAZAO
-------------
O modelo nao preve kWh absoluto: preve `kwh / media_28d`. Arvore de decisao
nao extrapola - com a frota crescendo ~30% ao ano, um modelo treinado em nivel
absoluto fica preso no maximo que ja viu e subestima sistematicamente.
Prevendo a razao, o nivel vem da media recente (que ja incorpora o
crescimento) e o modelo aprende so o desvio: sazonalidade semanal, feriado,
tendencia. Bonus: normaliza estacoes de portes diferentes, o que permite um
modelo global unico.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

MIN_HIST_DIAS = 150   # historico minimo para uma estacao entrar no dataset

FEATURES = [
    "horizonte", "dow", "is_weekend", "mes", "dia_mes",
    "is_feriado", "is_vespera_feriado",
    "hist_m7", "hist_m28", "hist_m91", "hist_m182", "hist_std28",
    "hist_ano_atras", "tend_28_91", "tend_7_28", "hist_dow",
    "archetype", "power_type", "n_connectors", "dias_operacao",
    "location_id",
]
CATEGORICAS = ["archetype", "power_type", "location_id"]


# ---------------------------------------------------------------------------
# Calendario
# ---------------------------------------------------------------------------

def _pascoa(ano: int) -> dt.date:
    """Meeus/Jones/Butcher - domingo de Pascoa."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    return dt.date(ano, (h + l - 7 * m + 114) // 31,
                   ((h + l - 7 * m + 114) % 31) + 1)


def feriados_br(anos) -> set[dt.date]:
    """Feriados nacionais. Para producao, considerar tambem os municipais das
    cidades onde ha estacao - em rodovia e shopping o efeito e forte."""
    out: set[dt.date] = set()
    for ano in anos:
        p = _pascoa(ano)
        out |= {
            dt.date(ano, 1, 1), dt.date(ano, 4, 21), dt.date(ano, 5, 1),
            dt.date(ano, 9, 7), dt.date(ano, 10, 12), dt.date(ano, 11, 2),
            dt.date(ano, 11, 15), dt.date(ano, 11, 20), dt.date(ano, 12, 25),
            p - dt.timedelta(days=48), p - dt.timedelta(days=47),
            p - dt.timedelta(days=2), p + dt.timedelta(days=60),
        }
    return out


# ---------------------------------------------------------------------------
# Resumo do historico ate a origem
# ---------------------------------------------------------------------------

def _resumo_historico(hist: pd.Series) -> dict:
    """Estatisticas da serie diaria de kWh terminando na origem.

    NaN (dias indisponiveis) sao ignorados pelo .mean(), que e o
    comportamento correto: downtime nao deve puxar a media para baixo.
    """
    def media(n: int) -> float:
        j = hist.tail(n)
        return float(j.mean()) if j.notna().any() else np.nan

    m7, m28, m91, m182 = media(7), media(28), media(91), media(182)
    ult = hist.tail(56)
    por_dow = ult.groupby(ult.index.dayofweek).mean().to_dict()

    ano_atras = hist.tail(395).head(31)
    m_ano = float(ano_atras.mean()) if len(ano_atras) and ano_atras.notna().any() \
        else np.nan

    return {
        "hist_m7": m7, "hist_m28": m28, "hist_m91": m91, "hist_m182": m182,
        "hist_std28": float(hist.tail(28).std()),
        "hist_ano_atras": m_ano,
        # Razoes capturam tendencia melhor que niveis e generalizam entre
        # estacoes de portes diferentes.
        "tend_28_91": m28 / m91 if m91 and m91 > 0 else np.nan,
        "tend_7_28": m7 / m28 if m28 and m28 > 0 else np.nan,
        "_por_dow": por_dow,
    }


def _linhas_alvo(loc, meta, resumo, por_dow, datas, feriados,
                 alvos: pd.Series | None, origem) -> list[dict]:
    linhas = []
    for data in datas:
        dow = data.dayofweek
        linhas.append({
            "location_id": loc,
            "origem": origem,
            "mes_alvo": pd.Timestamp(data).to_period("M").to_timestamp(),
            "date": data,
            "horizonte": (data - origem).days,
            # calendario do dia alvo
            "dow": dow,
            "is_weekend": int(dow >= 5),
            "mes": data.month,
            "dia_mes": data.day,
            "is_feriado": int(data.date() in feriados),
            "is_vespera_feriado": int((data + pd.Timedelta(days=1)).date() in feriados),
            # historico ate a origem
            **resumo,
            "hist_dow": por_dow.get(dow, np.nan),
            # estacao
            "archetype": meta["archetype"],
            "power_type": meta["power_type"],
            "n_connectors": meta["n_connectors"],
            "dias_operacao": (data - meta["opened_at"]).days,
            # alvo (ausente na previsao de mes futuro)
            "y_kwh": float(alvos.get(data, np.nan)) if alvos is not None else np.nan,
        })
    return linhas


def _tipar(df: pd.DataFrame) -> pd.DataFrame:
    for c in CATEGORICAS:
        df[c] = df[c].astype("category")
    return df


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

def construir_treino(painel: pd.DataFrame, estacoes: pd.DataFrame) -> pd.DataFrame:
    """Dataset historico de (origem, dia alvo) para treino e backtest."""
    meta = estacoes.set_index("location_id").to_dict("index")
    p = painel.copy()
    p["mes"] = p["date"].values.astype("datetime64[M]")
    meses = sorted(p["mes"].unique())
    fer = feriados_br(range(p["date"].dt.year.min(), p["date"].dt.year.max() + 2))

    linhas = []
    for loc, g in p.groupby("location_id", sort=False):
        if loc not in meta:
            continue
        g = g.set_index("date").sort_index()
        serie = g["kwh"]
        for mes_alvo in meses[1:]:
            origem = pd.Timestamp(mes_alvo) - pd.Timedelta(days=1)
            hist = serie.loc[:origem]
            if hist.notna().sum() < MIN_HIST_DIAS:
                continue
            r = _resumo_historico(hist)
            por_dow = r.pop("_por_dow")
            datas = g.index[g.index.values.astype("datetime64[M]") == mes_alvo]
            if not len(datas):
                continue
            linhas.extend(_linhas_alvo(loc, meta[loc], r, por_dow, datas,
                                       fer, serie, origem))
    return _tipar(pd.DataFrame(linhas))


def construir_previsao(painel: pd.DataFrame, estacoes: pd.DataFrame,
                       mes_alvo: pd.Timestamp | str | None = None) -> pd.DataFrame:
    """Features para prever UM mes futuro, para o qual nao ha alvo.

    Usa como origem o ultimo dia disponivel de cada estacao no painel.
    """
    meta = estacoes.set_index("location_id").to_dict("index")
    p = painel.copy()

    if mes_alvo is None:
        prox = (p["date"].max().to_period("M") + 1).to_timestamp()
    else:
        prox = pd.Timestamp(mes_alvo).to_period("M").to_timestamp()

    dias_alvo = pd.date_range(prox, (prox + pd.offsets.MonthEnd(1)), freq="D")
    fer = feriados_br(range(prox.year - 1, prox.year + 2))

    linhas = []
    for loc, g in p.groupby("location_id", sort=False):
        if loc not in meta:
            continue
        g = g.set_index("date").sort_index()
        hist = g["kwh"].loc[:prox - pd.Timedelta(days=1)]
        if hist.notna().sum() < MIN_HIST_DIAS:
            continue  # estacao imatura: cai no fallback do predict.py
        r = _resumo_historico(hist)
        por_dow = r.pop("_por_dow")
        origem = hist.index.max()
        linhas.extend(_linhas_alvo(loc, meta[loc], r, por_dow, dias_alvo,
                                   fer, None, origem))
    return _tipar(pd.DataFrame(linhas))


def alvo_em_razao(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona y_ratio = y_kwh / hist_m28 e descarta linhas sem alvo."""
    d = df[df["y_kwh"].notna()].copy()
    d["y_ratio"] = d["y_kwh"] / d["hist_m28"].replace(0, np.nan)
    return d[d["y_ratio"].notna()]
