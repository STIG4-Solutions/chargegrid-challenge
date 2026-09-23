"""
Treino do modelo de previsao de energia.
========================================

Uso:
    python -m src.train --painel data/painel.parquet \
                        --estacoes data/estacoes.csv \
                        --saida modelos/

Produz um artefato versionado (.joblib) contendo os tres modelos (mediana,
p10, p90), a lista de features e as metricas do backtest. O predict.py
carrega esse artefato - nunca retreina em tempo de inferencia.

O QUE O MODELO PREVE
--------------------
Energia (kWh), nunca reais. Tarifa e decisao de negocio, nao fenomeno a ser
aprendido: se o operador reajusta o preco, um modelo treinado em R$ vira
lixo. O faturamento sai depois, em predict.py: kWh previsto x tarifa vigente.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

from .features import (CATEGORICAS, FEATURES, alvo_em_razao, construir_treino)
from .schema import validar_painel

VERSAO_PIPELINE = "1.0.0"
QUANTIS = {"p10": 0.10, "p90": 0.90}

PARAMS = dict(
    n_estimators=700,
    learning_rate=0.04,
    num_leaves=31,
    min_child_samples=30,
    subsample=0.85,
    subsample_freq=1,
    colsample_bytree=0.85,
    reg_lambda=1.0,
    random_state=42,
    verbose=-1,
)


def wape(y, yhat) -> float:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    return float(np.abs(y - yhat).sum() / np.abs(y).sum() * 100)


def treinar_um(tr: pd.DataFrame, objective="l1", alpha=None) -> lgb.LGBMRegressor:
    p = dict(PARAMS, objective=objective)
    if alpha is not None:
        p["alpha"] = alpha
    m = lgb.LGBMRegressor(**p)
    m.fit(tr[FEATURES], tr["y_ratio"], categorical_feature=CATEGORICAS)
    return m


def prever_kwh(modelo, df: pd.DataFrame) -> np.ndarray:
    """Desfaz a normalizacao: razao prevista x nivel recente (media 28d)."""
    return np.clip(modelo.predict(df[FEATURES]) * df["hist_m28"].values, 0, None)


def backtest(ds: pd.DataFrame, n_meses: int = 3) -> dict:
    """Walk-forward: para cada mes de teste, treina so com o passado.

    Sem vazamento por construcao - o modelo que preve maio nunca viu maio.
    Estas metricas sao a unica evidencia de que o modelo funciona; rode
    sempre antes de promover uma versao.
    """
    meses = sorted(ds["mes_alvo"].unique())
    if len(meses) <= n_meses:
        return {"aviso": "historico insuficiente para backtest"}

    preds = []
    for mes in meses[-n_meses:]:
        tr, te = ds[ds["mes_alvo"] < mes], ds[ds["mes_alvo"] == mes]
        if tr.empty or te.empty:
            continue
        m = treinar_um(tr)
        p = te.copy()
        p["yhat"] = prever_kwh(m, te)
        for nome, a in QUANTIS.items():
            p[f"yhat_{nome}"] = prever_kwh(treinar_um(tr, "quantile", a), te)
        preds.append(p)

    if not preds:
        return {"aviso": "backtest sem particoes validas"}

    pr = pd.concat(preds, ignore_index=True)

    # A SEGUNDA REGUA. `hist_dow` e' a media daquele dia da semana nos ultimos
    # 56 dias - ja' calculada, ja' feature do modelo. Usada CRUA ela e' uma
    # previsao completa, e mede a pergunta que a media movel nao faz: o modelo
    # extrai das features mais do que uma delas ja' diz sozinha?
    #
    # Sem esta coluna o artefato nao consegue distinguir "o modelo aprendeu
    # sazonalidade semanal" de "o modelo copiou hist_dow". Sao a mesma curva na
    # tela e conclusoes opostas sobre manter LightGBM.
    #
    # Volta para m28 quando NaN: estacao com menos de 56 dias nao tem media por
    # dia da semana, e uma regua com buraco nao e' comparavel.
    pr["base_dow"] = pr["hist_dow"].fillna(pr["hist_m28"])

    mensal = pr.groupby(["location_id", "mes_alvo"], observed=True).agg(
        real=("y_kwh", "sum"), prev=("yhat", "sum"),
        base=("hist_m28", "sum"), base_dow=("base_dow", "sum")).reset_index()

    return {
        "meses_testados": [str(pd.Timestamp(m).date()) for m in meses[-n_meses:]],
        "n_obs_teste": int(len(pr)),
        "n_obs_mensal": int(len(mensal)),
        "wape_diario": round(wape(pr["y_kwh"], pr["yhat"]), 2),
        "wape_mensal": round(wape(mensal["real"], mensal["prev"]), 2),
        # Baseline obrigatorio: se o modelo nao bate a media movel, nao ha
        # motivo para colocar ML em producao.
        "wape_mensal_baseline_m28": round(wape(mensal["real"], mensal["base"]), 2),
        "wape_mensal_baseline_dow": round(wape(mensal["real"], mensal["base_dow"]), 2),
        # O eixo diario tinha o erro do modelo e NENHUMA regua ao lado - um
        # numero sozinho, que nao diz se e' bom. As duas reguas entram aqui
        # pelo mesmo motivo que a mensal tem a dela.
        "wape_diario_baseline_m28": round(wape(pr["y_kwh"], pr["hist_m28"]), 2),
        "wape_diario_baseline_dow": round(wape(pr["y_kwh"], pr["base_dow"]), 2),
        "vies_medio_pct": round(
            float(((mensal["prev"] - mensal["real"]) / mensal["real"]).mean() * 100), 2),
        "cobertura_p10_p90_diaria": round(float(
            ((pr["y_kwh"] >= pr["yhat_p10"]) & (pr["y_kwh"] <= pr["yhat_p90"])).mean()
            * 100), 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Treina o modelo de previsao de kWh")
    ap.add_argument("--painel", required=True, help="parquet/csv do painel diario")
    ap.add_argument("--estacoes", required=True, help="csv do cadastro de estacoes")
    ap.add_argument("--saida", default="modelos", help="diretorio do artefato")
    ap.add_argument("--meses-backtest", type=int, default=3)
    ap.add_argument("--pular-validacao", action="store_true")
    args = ap.parse_args()

    ler = pd.read_parquet if str(args.painel).endswith(".parquet") else pd.read_csv
    painel = ler(args.painel)
    painel["date"] = pd.to_datetime(painel["date"])
    estacoes = pd.read_csv(args.estacoes, parse_dates=["opened_at"])

    print("1. Validando painel...")
    v = validar_painel(painel, estacoes)
    v.imprimir()
    if not args.pular_validacao:
        v.levantar_se_invalido()

    print("\n2. Construindo features...")
    ds = alvo_em_razao(construir_treino(painel, estacoes))
    print(f"   {len(ds):,} linhas | {len(FEATURES)} features | "
          f"{ds['location_id'].nunique()} estacoes")
    if len(ds) < 500:
        raise ValueError(
            f"apenas {len(ds)} linhas de treino - historico insuficiente. "
            "Necessario ~6 meses de dado valido por estacao.")

    print(f"\n3. Backtest ({args.meses_backtest} meses fora da amostra)...")
    metricas = backtest(ds, args.meses_backtest)
    for k, val in metricas.items():
        print(f"   {k:32s} {val}")

    if "wape_mensal" in metricas:
        if metricas["wape_mensal"] >= metricas["wape_mensal_baseline_m28"]:
            print("\n   [ATENCAO] o modelo NAO bateu a media movel de 28 dias. "
                  "Investigar antes de promover esta versao.")

    print("\n4. Treinando modelo final (historico completo)...")
    modelos = {"mediana": treinar_um(ds, "l1")}
    for nome, a in QUANTIS.items():
        modelos[nome] = treinar_um(ds, "quantile", a)

    artefato = {
        "versao_pipeline": VERSAO_PIPELINE,
        "treinado_em": dt.datetime.now().isoformat(timespec="seconds"),
        "modelos": modelos,
        "features": FEATURES,
        "categoricas": CATEGORICAS,
        "params": PARAMS,
        "metricas_backtest": metricas,
        "estacoes_treinadas": sorted(ds["location_id"].astype(str).unique()),
        "periodo_treino": [str(ds["date"].min().date()), str(ds["date"].max().date())],
        "n_linhas_treino": int(len(ds)),
    }

    out = Path(args.saida)
    out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    caminho = out / f"modelo_{stamp}.joblib"
    joblib.dump(artefato, caminho, compress=3)

    # Ponteiro estavel para o predict.py e para o deploy.
    atalho = out / "modelo_atual.joblib"
    atalho.unlink(missing_ok=True)
    joblib.dump(artefato, atalho, compress=3)
    (out / f"metricas_{stamp}.json").write_text(
        json.dumps(metricas, indent=2, ensure_ascii=False))

    print(f"\nArtefato salvo: {caminho}")
    print(f"Ponteiro atual: {atalho}")


if __name__ == "__main__":
    main()
