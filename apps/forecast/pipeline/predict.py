"""
Previsao do mes seguinte.
=========================

Uso:
    python -m src.predict --painel data/painel.parquet \
                          --estacoes data/estacoes.csv \
                          --modelo modelos/modelo_atual.joblib \
                          --tarifas data/tarifas.csv \
                          --saida saida/previsao.csv

Carrega o artefato treinado e produz, por estacao:
    kWh previsto (mediana, p10, p90)  e  faturamento = kWh x tarifa vigente

Nao retreina. Se o painel tiver estacao que o modelo nunca viu, ela cai no
fallback e vem marcada como tal.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .features import construir_previsao
from .schema import validar_painel


def _tarifa_vigente(tarifas: pd.DataFrame, mes: pd.Timestamp) -> pd.Series:
    """Ultima tarifa com vigencia iniciada ate o mes alvo, por estacao.

    A tarifa NAO entra como feature do modelo. Ela so converte kWh em R$ no
    final. E isso que faz um reajuste de preco nao invalidar o modelo -
    troca-se a linha na tabela e a previsao de faturamento se ajusta sozinha.
    """
    t = tarifas.copy()
    t["vigencia_inicio"] = pd.to_datetime(t["vigencia_inicio"])
    t = t[t["vigencia_inicio"] <= mes].sort_values("vigencia_inicio")
    return t.groupby("location_id")["price_per_kwh"].last()


def _fallback(painel: pd.DataFrame, loc: str, dias: int) -> float:
    """Estacao nova ou fora do treino: media dos ultimos 28 dias validos.

    Baseline honesto e transparente. Melhor devolver isso, sinalizado, do que
    extrapolar um modelo para uma estacao sem historico.
    """
    h = painel[painel["location_id"] == loc]["kwh"].dropna().tail(28)
    return float(h.mean() * dias) if len(h) else np.nan


def prever(painel: pd.DataFrame, estacoes: pd.DataFrame, artefato: dict,
           tarifas: pd.DataFrame | None = None,
           mes_alvo=None) -> pd.DataFrame:
    feats = construir_previsao(painel, estacoes, mes_alvo)
    if feats.empty:
        raise ValueError("nenhuma estacao com historico suficiente para prever")

    mes = feats["mes_alvo"].iloc[0]
    cols = artefato["features"]

    # Alinha as categorias do treino: categoria nova quebraria o predict.
    conhecidas = set(artefato["estacoes_treinadas"])
    feats["_conhecida"] = feats["location_id"].astype(str).isin(conhecidas)

    for nome, chave in [("kwh_prev", "mediana"), ("kwh_p10", "p10"), ("kwh_p90", "p90")]:
        m = artefato["modelos"][chave]
        feats[nome] = np.clip(m.predict(feats[cols]) * feats["hist_m28"].values, 0, None)

    out = feats.groupby("location_id", observed=True).agg(
        mes_alvo=("mes_alvo", "first"),
        dias=("date", "size"),
        kwh_prev=("kwh_prev", "sum"),
        kwh_p10=("kwh_p10", "sum"),
        kwh_p90=("kwh_p90", "sum"),
        media_diaria_28d=("hist_m28", "first"),
        modelo_aplicavel=("_conhecida", "first"),
    ).reset_index()

    # Estacoes do cadastro que ficaram de fora (historico curto) -> fallback.
    faltantes = set(estacoes["location_id"]) - set(out["location_id"].astype(str))
    if faltantes:
        n_dias = int(feats["date"].nunique())
        extra = pd.DataFrame([{
            "location_id": loc, "mes_alvo": mes, "dias": n_dias,
            "kwh_prev": _fallback(painel, loc, n_dias),
            "kwh_p10": np.nan, "kwh_p90": np.nan,
            "media_diaria_28d": np.nan, "modelo_aplicavel": False,
        } for loc in sorted(faltantes)])
        out = pd.concat([out, extra], ignore_index=True)

    # Conversao para faturamento - unico ponto onde o preco entra.
    if tarifas is not None:
        tar = _tarifa_vigente(tarifas, mes)
        out["price_per_kwh"] = out["location_id"].astype(str).map(tar)
        for a, b in [("fat_prev", "kwh_prev"), ("fat_p10", "kwh_p10"),
                     ("fat_p90", "kwh_p90")]:
            out[a] = out[b] * out["price_per_kwh"]

    out = out.merge(estacoes[["location_id", "location_name", "archetype"]],
                    on="location_id", how="left")
    return out.sort_values("kwh_prev", ascending=False).reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Preve energia e faturamento do mes seguinte")
    ap.add_argument("--painel", required=True)
    ap.add_argument("--estacoes", required=True)
    ap.add_argument("--modelo", default="modelos/modelo_atual.joblib")
    ap.add_argument("--tarifas", help="csv: location_id, vigencia_inicio, price_per_kwh")
    ap.add_argument("--mes", help="AAAA-MM (default: mes seguinte ao fim do painel)")
    ap.add_argument("--saida", default="saida/previsao.csv")
    args = ap.parse_args()

    ler = pd.read_parquet if str(args.painel).endswith(".parquet") else pd.read_csv
    painel = ler(args.painel)
    painel["date"] = pd.to_datetime(painel["date"])
    estacoes = pd.read_csv(args.estacoes, parse_dates=["opened_at"])
    tarifas = pd.read_csv(args.tarifas) if args.tarifas else None

    v = validar_painel(painel, estacoes)
    v.imprimir()

    artefato = joblib.load(args.modelo)
    print(f"\nModelo: {artefato['treinado_em']} | pipeline v{artefato['versao_pipeline']}")
    print(f"WAPE mensal no backtest: {artefato['metricas_backtest'].get('wape_mensal')}%")

    # Guarda-corpo operacional: modelo velho preve mal um mundo que mudou.
    idade = (pd.Timestamp.now() - pd.Timestamp(artefato["treinado_em"])).days
    if idade > 60:
        print(f"[ATENCAO] modelo treinado ha {idade} dias - considerar retreino")

    out = prever(painel, estacoes, artefato, tarifas, args.mes)

    Path(args.saida).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.saida, index=False)

    print(f"\nPrevisao para {pd.Timestamp(out['mes_alvo'].iloc[0]):%Y-%m}:")
    mostra = [c for c in ["location_id", "kwh_prev", "kwh_p10", "kwh_p90",
                          "fat_prev", "modelo_aplicavel"] if c in out]
    print(out[mostra].round(0).to_string(index=False))
    if not out["modelo_aplicavel"].all():
        print("\n  modelo_aplicavel=False -> fallback de media movel "
              "(estacao sem historico suficiente)")
    print(f"\nSalvo em {args.saida}")


if __name__ == "__main__":
    main()
