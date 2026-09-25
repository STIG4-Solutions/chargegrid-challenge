"""O backtest: walk-forward, e todas as reguas ao lado de cada numero.

O QUE MUDA EM RELACAO AO BACKTEST DO PIPELINE:

1. A REGUA DO PORTAO PASSA A SER A MELHOR. Antes o portao comparava o modelo com
   a media movel de 28 dias, e so'. A media movel faz 13,57% no mes, mas a regua
   de ano-a-ano faz 9,95% - bater a media movel era uma barra baixa que nao
   provava nada. Agora as duas sao medidas e o portao usa a melhor.

2. NIVEL E FORMA SAO MEDIDOS SEPARADO, porque tem vencedores diferentes e porque
   um numero so' escondia isso: o modelo antigo empatava no mes (13,34% contra
   13,57%) e ganhava no dia por 6 pontos, e o card so' mostrava o mes.

3. A FAIXA E' CALIBRADA, e a cobertura medida FORA da calibracao. Para o mes
   alvo M os fatores saem dos residuos de M-`N_CALIB`..M-1, cada um previsto por
   um modelo treinado so' com o que vinha antes DELE. Nenhum residuo de
   calibracao vem de um modelo que viu o mes daquele residuo, e nenhum mes alvo
   entra na propria calibracao.

O CUSTO: o backtest precisa de `n_meses + N_CALIB` meses de walk-forward em vez
de `n_meses`, e cada mes treina dois modelos em vez de um. Em troca, a cobertura
que vai para a tela e' uma medicao fora da amostra, e nao a esperanca de que a
perda de quantil se comporte.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.train import wape

from .faixa import QUANTIS, aplicar_faixa, cobertura, fatores_conformes, residuos
from .forma import features_da_forma, prever_forma, treinar_forma
from .nivel import painel_mensal, prever_nivel, treinar_nivel

# Meses de calibracao antes de cada mes alvo, por grao.
#
# No DIA sobram ~30 residuos por praca-mes, entao 3 meses de 7 pracas dao ~600 -
# folgado para os percentis 10 e 90.
#
# No MES sobra UM residuo por praca-mes: 3 meses dariam 21, abaixo do minimo de
# 30 da conforme. Por isso a janela mensal e' mais longa - 6 meses de 7 pracas
# dao 42. Nao e' arbitrario: e' o menor numero que atravessa o piso.
N_CALIB_DIA = 3
N_CALIB_MES = 6
N_CALIB = max(N_CALIB_DIA, N_CALIB_MES)


def _arred(v, casas: int = 2):
    """Arredonda deixando `None` passar - metrica ausente nao e' zero."""
    return None if v is None else round(v, casas)


def _regua_dow(df: pd.DataFrame) -> pd.Series:
    """A media daquele dia da semana nos ultimos 56 dias, usada CRUA.

    Volta para m28 quando NaN: praca com menos de 56 dias nao tem media por dia
    da semana, e uma regua com buraco nao e' comparavel - o WAPE sairia NaN e o
    artefato gravaria `null` onde deveria haver numero.
    """
    return df["hist_dow"].fillna(df["hist_m28"])


def _uma_origem(
    tr: pd.DataFrame, te: pd.DataFrame, features: list[str], categoricas: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Treina forma e nivel com o passado e preve um mes. Sem vazamento."""
    modelo_forma = treinar_forma(tr, features, categoricas)
    p = te.copy()
    p["yhat"] = prever_forma(modelo_forma, te, features)
    p["regua_dow"] = _regua_dow(te)

    tm, em = painel_mensal(tr), painel_mensal(te)
    modelo_nivel = treinar_nivel(tm)
    em["prev"] = prever_nivel(modelo_nivel, em)
    # A forma presa soma exatamente `nivel_ano x dias`, que e' a regua - guardar
    # a soma dela ao lado permite medir o que o modelo do nivel acrescentou.
    em = em.merge(
        p.groupby(["location_id", "mes_alvo"], observed=True)
        .agg(soma_da_forma=("yhat", "sum"), regua_dow=("regua_dow", "sum"))
        .reset_index(),
        on=["location_id", "mes_alvo"],
        how="left",
    )
    return p, em


def backtest(
    ds: pd.DataFrame,
    n_meses: int = 3,
    categoricas: list[str] | None = None,
    features: list[str] | None = None,
) -> dict:
    """Walk-forward por mes. Estas metricas sao a evidencia do modelo.

    `ds` precisa ter passado por `colunas_de_ano`: e' de la' que vem `nivel_ano`.
    """
    from pipeline.features import CATEGORICAS, FEATURES

    categoricas = categoricas or CATEGORICAS
    features = features or features_da_forma(FEATURES)

    meses = sorted(ds["mes_alvo"].unique())
    if len(meses) <= n_meses:
        return {"aviso": "historico insuficiente para backtest"}

    # Os meses de calibracao tambem precisam de previsao walk-forward, entao a
    # janela medida comeca antes da janela reportada.
    janela = meses[-(n_meses + N_CALIB) :]
    alvos = meses[-n_meses:]

    diario: dict = {}
    mensal: dict = {}
    for mes in janela:
        tr, te = ds[ds["mes_alvo"] < mes], ds[ds["mes_alvo"] == mes]
        if tr.empty or te.empty:
            continue
        diario[mes], mensal[mes] = _uma_origem(tr, te, features, categoricas)

    if not any(m in diario for m in alvos):
        return {"aviso": "backtest sem particoes validas"}

    partes_dia, partes_mes = [], []
    for mes in alvos:
        if mes not in diario:
            continue
        i = janela.index(mes)
        d, m = diario[mes].copy(), mensal[mes].copy()

        antes_dia = [diario[c] for c in janela[max(0, i - N_CALIB_DIA) : i] if c in diario]
        f_dia = (
            fatores_conformes(
                residuos(
                    pd.concat(antes_dia)["y_kwh"],
                    pd.concat(antes_dia)["yhat"],
                )
            )
            if antes_dia
            else None
        )
        d["p10"], d["p90"] = aplicar_faixa(d["yhat"], f_dia)

        antes_mes = [mensal[c] for c in janela[max(0, i - N_CALIB_MES) : i] if c in mensal]
        f_mes = (
            fatores_conformes(residuos(pd.concat(antes_mes)["real"], pd.concat(antes_mes)["prev"]))
            if antes_mes
            else None
        )
        m["p10"], m["p90"] = aplicar_faixa(m["prev"], f_mes)

        partes_dia.append(d)
        partes_mes.append(m)

    pr = pd.concat(partes_dia, ignore_index=True)
    me = pd.concat(partes_mes, ignore_index=True)

    # Os fatores que vao para o ARTEFATO saem de toda a janela walk-forward, que
    # e' o maior conjunto de residuos fora da amostra disponivel. A cobertura
    # reportada acima NAO os usa - ela vem da calibracao rolante, que e' a
    # medicao honesta.
    tudo_dia = pd.concat(diario.values(), ignore_index=True) if diario else pd.DataFrame()
    tudo_mes = pd.concat(mensal.values(), ignore_index=True) if mensal else pd.DataFrame()
    fatores = {
        "dia": fatores_conformes(residuos(tudo_dia["y_kwh"], tudo_dia["yhat"]))
        if len(tudo_dia)
        else None,
        "mes": fatores_conformes(residuos(tudo_mes["real"], tudo_mes["prev"]))
        if len(tudo_mes)
        else None,
    }

    return {
        "meses_testados": [str(pd.Timestamp(m).date()) for m in alvos if m in diario],
        "n_obs_teste": int(len(pr)),
        "n_obs_mensal": int(len(me)),
        # --- NIVEL: o numero do card -------------------------------------------
        "wape_mensal": _arred(wape(me["real"], me["prev"])),
        # A regua antiga do portao, mantida porque e' a serie historica das
        # metricas e comparar versoes exige o mesmo numero ao longo do tempo.
        "wape_mensal_baseline_m28": _arred(wape(me["real"], me["hist_m28"] * me["dias"])),
        # A regua NOVA, e a que o portao passa a usar: e' a melhor honesta.
        "wape_mensal_baseline_ano": _arred(wape(me["real"], me["base_regua"])),
        # A regua `dow` no eixo mensal PERDE, e fica registrada por isso: e' a
        # evidencia de que normalizar por `hist_dow` foi testado e recusado. Na
        # soma do mes o dia da semana cancela - todo mes tem ~4 de cada - e o que
        # sobra da media por dow e' mais variancia, porque ela estima com 8
        # observacoes por dia da semana contra 28 da media movel.
        "wape_mensal_baseline_dow": _arred(wape(me["real"], me["regua_dow"])),
        # A soma da forma presa E' a regua de ano por construcao. Sai como
        # conferencia: se divergir da linha acima, o prendimento quebrou.
        "wape_mensal_forma_somada": _arred(wape(me["real"], me["soma_da_forma"])),
        "vies_medio_pct": _arred(
            float(((me["prev"] - me["real"]) / me["real"].replace(0, np.nan)).mean() * 100)
        ),
        # --- FORMA: a curva do mes ---------------------------------------------
        "wape_diario": _arred(wape(pr["y_kwh"], pr["yhat"])),
        "wape_diario_baseline_m28": _arred(wape(pr["y_kwh"], pr["hist_m28"])),
        "wape_diario_baseline_ano": _arred(wape(pr["y_kwh"], pr["nivel_ano"])),
        # No eixo DIARIO esta e' a melhor das tres - 29,85% contra 36,31% da media
        # movel e 34,67% da de ano-a-ano. Cada eixo tem a sua vencedora, e e' por
        # isso que as tres ficam medidas nos dois.
        "wape_diario_baseline_dow": _arred(wape(pr["y_kwh"], pr["regua_dow"])),
        # --- FAIXA: cobertura medida fora da calibracao -------------------------
        # Quantas linhas de teste receberam faixa. Sem este numero, uma cobertura de
        # 80% podia vir de metade do conjunto - o resto sem faixa e sem aviso -, e a
        # janela de calibracao podia encurtar sem nada acusar. Foi o teste de mutacao
        # que mostrou a lacuna: nenhum assert detectava a janela reduzida.
        "n_com_faixa_diaria": int(pr["p10"].notna().sum()) if "p10" in pr else 0,
        "n_com_faixa_mensal": int(me["p10"].notna().sum()) if "p10" in me else 0,
        "cobertura_p10_p90_diaria": _arred(cobertura(pr["y_kwh"], pr.get("p10"), pr.get("p90")), 1),
        "cobertura_p10_p90_mensal": _arred(cobertura(me["real"], me.get("p10"), me.get("p90")), 1),
        "quantis_da_faixa": list(QUANTIS),
        "fatores_da_faixa": fatores,
        "meses_de_calibracao": {"dia": N_CALIB_DIA, "mes": N_CALIB_MES},
    }
