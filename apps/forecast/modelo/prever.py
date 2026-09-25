"""A previsao do proximo mes, com os dois modelos e a faixa calibrada.

POR QUE NAO `pipeline/predict.py`. Aquele arquivo desnormaliza por `hist_m28`,
tem um modelo so' e monta a faixa com os modelos de quantil - as tres coisas que
a medicao mandou trocar. Ele continua la', byte a byte igual a origem, e nao e'
mais o caminho do ChargeGrid.

A SAIDA E' A MESMA. As colunas sao as que `exportar.py` ja' consome, para que a
troca do previsor nao virasse uma reescrita do exportador: `kwh_prev`, `kwh_p10`,
`kwh_p90`, `media_diaria_28d`, `modelo_aplicavel`, `fat_*` e o cadastro.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.features import construir_previsao

# Importado, e nao recopiado. A regra - ultima tarifa com vigencia iniciada ate o
# mes alvo - e' do pipeline, e duplica-la abriria caminho para as duas versoes
# divergirem calado. O nome e' privado: se a origem o renomear, este import
# FALHA no start em vez de passar a calcular preco de outro jeito.
from pipeline.predict import _tarifa_vigente

from .ano_a_ano import colunas_de_ano
from .faixa import aplicar_faixa
from .forma import prever_forma
from .limiares import recusar_se_nenhuma_praca_elegivel
from .nivel import painel_mensal, prever_nivel

# Janela do fallback de quem nao tem historico para o modelo. E' a mesma do
# `_fallback` do pipeline, e de proposito: o numero que a tela mostra para uma
# praca imatura nao deve mudar so' porque o previsor das maduras mudou.
DIAS_DO_FALLBACK = 28


def _fallback(painel: pd.DataFrame, local: str, dias: int) -> float:
    """Praca nova ou fora do treino: media dos ultimos 28 dias validos x dias."""
    h = painel[painel["location_id"].astype(str) == local]["kwh"].dropna().tail(DIAS_DO_FALLBACK)
    return float(h.mean() * dias) if len(h) else np.nan


def prever(
    painel: pd.DataFrame,
    estacoes: pd.DataFrame,
    artefato: dict,
    tarifas: pd.DataFrame | None = None,
    mes_alvo=None,
) -> pd.DataFrame:
    """Previsao de kWh e faturamento do mes alvo, uma linha por praca."""
    # Antes de `construir_previsao`: ela termina em `_tipar`, que faz
    # `df["archetype"]` e levanta `KeyError` num quadro vazio em vez de devolver
    # vazio. O `feats.empty` abaixo nunca era alcancado.
    recusar_se_nenhuma_praca_elegivel(painel)
    feats = construir_previsao(painel, estacoes, mes_alvo)
    if feats.empty:
        raise ValueError("nenhuma praca com historico suficiente para prever")
    feats = colunas_de_ano(feats, painel)

    mes = feats["mes_alvo"].iloc[0]
    conhecidas = set(map(str, artefato.get("estacoes_treinadas", [])))
    feats["_conhecida"] = feats["location_id"].astype(str).isin(conhecidas)

    # --- NIVEL: o numero do card ------------------------------------------------
    mensal = painel_mensal(feats)
    mensal["kwh_prev"] = prever_nivel(artefato["modelos"].get("nivel"), mensal)

    # --- FAIXA: fatores conformes do artefato, no grao do mes -------------------
    fatores = (artefato.get("metricas_backtest", {}).get("fatores_da_faixa") or {}).get("mes")
    mensal["kwh_p10"], mensal["kwh_p90"] = aplicar_faixa(mensal["kwh_prev"], fatores)

    # --- FORMA: a curva do mes, para as janelas mais curtas ---------------------
    # Nao entra no card, mas e' o que prova que a forma e o nivel concordam: a
    # soma da forma tem de reproduzir a regua de ano-a-ano.
    if artefato["modelos"].get("forma") is not None:
        feats["kwh_dia"] = prever_forma(artefato["modelos"]["forma"], feats, artefato["features"])

    # `base_regua` sai junto porque quem grava precisa dela: quando o modelo
    # perde no backtest, o numero gravado e' o da regua, e recalcula-la no
    # exportador seria uma segunda implementacao da mesma conta.
    mensal = mensal.rename(columns={"base_regua": "kwh_regua_ano"})
    out = mensal[
        ["location_id", "mes_alvo", "dias", "kwh_prev", "kwh_p10", "kwh_p90", "kwh_regua_ano"]
    ].copy()
    out = out.merge(
        feats.groupby("location_id", observed=True)
        .agg(media_diaria_28d=("hist_m28", "first"), modelo_aplicavel=("_conhecida", "first"))
        .reset_index(),
        on="location_id",
        how="left",
    )

    # Pracas do cadastro que ficaram fora por historico curto -> fallback.
    faltantes = set(estacoes["location_id"].astype(str)) - set(out["location_id"].astype(str))
    if faltantes:
        n_dias = int(feats["date"].nunique())
        out = pd.concat(
            [
                out,
                pd.DataFrame(
                    [
                        {
                            "location_id": local,
                            "mes_alvo": mes,
                            "dias": n_dias,
                            "kwh_prev": _fallback(painel, local, n_dias),
                            # NULA de proposito. Sem historico nao ha' ano
                            # anterior, e e' a ausencia desta coluna que faz o
                            # exportador gravar `fonte = 'media_movel'` para esta
                            # praca. Preenche-la com o fallback daria o numero
                            # certo com o rotulo errado - foi o que aconteceu, e
                            # `residencial-vila-mariana` ficou gravada como
                            # `ano_a_ano` sobre uma media de 28 dias.
                            "kwh_regua_ano": np.nan,
                            "kwh_p10": np.nan,
                            "kwh_p90": np.nan,
                            "media_diaria_28d": np.nan,
                            "modelo_aplicavel": False,
                        }
                        for local in sorted(faltantes)
                    ]
                ),
            ],
            ignore_index=True,
        )

    # Unico ponto onde o preco entra. Tarifa nao e' feature: se o operador
    # reajusta, a previsao de faturamento se ajusta sozinha e o modelo continua
    # valendo.
    if tarifas is not None:
        preco = _tarifa_vigente(tarifas, mes)
        out["price_per_kwh"] = out["location_id"].astype(str).map(preco)
        for destino, origem in [
            ("fat_prev", "kwh_prev"),
            ("fat_p10", "kwh_p10"),
            ("fat_p90", "kwh_p90"),
        ]:
            out[destino] = out[origem] * out["price_per_kwh"]

    out["location_id"] = out["location_id"].astype(str)
    cadastro = estacoes[["location_id", "location_name", "archetype"]].copy()
    cadastro["location_id"] = cadastro["location_id"].astype(str)
    out = out.merge(cadastro, on="location_id", how="left")
    return out.sort_values("kwh_prev", ascending=False).reset_index(drop=True)
