"""Gera a previsao do proximo mes e grava em `site_forecasts`.

    python exportar.py           (de dentro de apps/forecast)

A API nunca executa este arquivo: ela so' LE a tabela. Rodar aqui fora e' o que
mantem `lightgbm` longe do processo que administra potencia - um import quebrado
ou um artefato corrompido nao pode derrubar o rebalanceamento junto.

Tabela vazia significa "nao ha previsao", e a tela diz isso. E' melhor que um
numero inventado, e e' o comportamento que se obtem de graca ao nao ter
fallback nenhum aqui dentro.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import joblib  # noqa: E402
import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

from banco import carregar, conectar, resumo  # noqa: E402
from pipeline.predict import prever  # noqa: E402

# O que a faixa p10-p90 promete conter. Nao e' opiniao: e' a definicao dos
# quantis que o modelo treina.
COBERTURA_DECLARADA = 80.0

# Depois disto o artefato esta velho. O numero vem do proprio pipeline: a demanda
# muda de estacao para estacao ao longo do ano, e um modelo de tres meses atras
# ja nao viu a sazonalidade que esta chegando.
DIAS_ATE_ENVELHECER = 60

_UPSERT = text(
    """
    INSERT INTO site_forecasts (
        id, site_id, competencia, gerado_em,
        kwh_previsto, kwh_p10, kwh_p90,
        faturamento_previsto_brl, fat_p10_brl, fat_p90_brl,
        media_diaria_28d, modelo_aplicavel, modelo_versao, dias_de_historico,
        cobertura_declarada_pct, cobertura_medida_pct,
        wape_modelo_pct, wape_baseline_pct,
        created_at, updated_at
    )
    SELECT :id, s.id, :competencia, :gerado_em,
           :kwh_previsto, :kwh_p10, :kwh_p90,
           :fat_prev, :fat_p10, :fat_p90,
           :media_28d, :aplicavel, :versao, :dias,
           :declarada, :medida,
           :wape_modelo, :wape_regua,
           now(), now()
    FROM sites s WHERE s.slug = :slug
    ON CONFLICT (site_id, competencia) DO UPDATE SET
        gerado_em = EXCLUDED.gerado_em,
        kwh_previsto = EXCLUDED.kwh_previsto,
        kwh_p10 = EXCLUDED.kwh_p10,
        kwh_p90 = EXCLUDED.kwh_p90,
        faturamento_previsto_brl = EXCLUDED.faturamento_previsto_brl,
        fat_p10_brl = EXCLUDED.fat_p10_brl,
        fat_p90_brl = EXCLUDED.fat_p90_brl,
        media_diaria_28d = EXCLUDED.media_diaria_28d,
        modelo_aplicavel = EXCLUDED.modelo_aplicavel,
        modelo_versao = EXCLUDED.modelo_versao,
        dias_de_historico = EXCLUDED.dias_de_historico,
        cobertura_declarada_pct = EXCLUDED.cobertura_declarada_pct,
        cobertura_medida_pct = EXCLUDED.cobertura_medida_pct,
        wape_modelo_pct = EXCLUDED.wape_modelo_pct,
        wape_baseline_pct = EXCLUDED.wape_baseline_pct,
        updated_at = now()
    """
)


def _ou_nulo(valor):
    """NaN do pandas vira NULL no banco, e nao o texto 'nan'."""
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        return None
    return float(valor)


def _avisar_se_velho(artefato: dict) -> None:
    treinado = artefato.get("treinado_em")
    if not treinado:
        return
    idade = (datetime.now() - datetime.fromisoformat(treinado)).days
    if idade > DIAS_ATE_ENVELHECER:
        print(
            f"[ATENCAO] o modelo foi treinado ha {idade} dias. A sazonalidade que\n"
            "          esta chegando pode nao estar nele - considere retreinar."
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="Preve o proximo mes e grava no banco")
    ap.add_argument("--modelo", default=str(RAIZ / "modelos" / "modelo_atual.joblib"))
    ap.add_argument("--mes-alvo", default=None, help="AAAA-MM-01; padrao e' o mes seguinte")
    args = ap.parse_args()

    caminho = Path(args.modelo)
    if not caminho.exists():
        raise SystemExit(
            f"artefato nao encontrado em {caminho}\nRode `python treinar.py` antes."
        )

    artefato = joblib.load(caminho)
    _avisar_se_velho(artefato)

    engine = conectar()
    painel, estacoes, tarifas = carregar(engine)
    print("Historico disponivel:")
    print(resumo(painel))

    # A divergencia que a tela precisa mostrar: o backtest mediu quanto a faixa
    # realmente cobre, e o valor costuma ficar abaixo dos 80% que ela promete.
    metricas = artefato.get("metricas_backtest", {})
    medida = metricas.get("cobertura_p10_p90_diaria")
    wape_modelo = metricas.get("wape_mensal")
    wape_regua = metricas.get("wape_mensal_baseline_m28")
    if wape_modelo is not None and wape_regua is not None and wape_modelo >= wape_regua:
        # Nao aborta: a previsao ainda tem valor como referencia, e esconde-la
        # nao a torna melhor. O que nao pode acontecer e' a tela apresentar
        # como decisao um numero que perde de uma media movel - por isso os
        # dois erros vao para o banco, lado a lado.
        print(
            f"\n[ATENCAO] este artefato NAO supera a regua: erro de {wape_modelo}%\n"
            f"          contra {wape_regua}% da media movel de 28 dias.\n"
            "          A previsao continua sendo gravada - esconde-la nao a torna\n"
            "          melhor -, mas a tela vai dizer isso ao operador."
        )
    conhecidas = set(artefato.get("estacoes_treinadas", []))
    desconhecidas = sorted(set(estacoes["location_id"].astype(str)) - conhecidas)
    if desconhecidas:
        # E' AQUI que a integracao falha de verdade, e nenhum teste unitario pega:
        # o modelo cai em fallback silenciosamente e a tela parece funcionar.
        print(
            "\n[ATENCAO] estes locais NAO estao no artefato e vao cair no fallback\n"
            "          de media movel, sem previsao de verdade:\n"
            + "".join(f"            {d}\n" for d in desconhecidas)
            + "          Retreine para incluir todos."
        )

    previsao = prever(painel, estacoes, artefato, tarifas, args.mes_alvo)
    competencia = pd.Timestamp(previsao["mes_alvo"].iloc[0]).date()
    agora = datetime.now(UTC)

    dias_por_local = (
        painel[painel["kwh"] > 0].groupby("location_id", observed=True)["date"].nunique()
    )

    gravadas = 0
    with engine.begin() as conexao:
        for _, linha in previsao.iterrows():
            aplicavel = bool(linha["modelo_aplicavel"])
            conexao.execute(
                _UPSERT,
                {
                    "id": uuid.uuid4(),
                    "slug": str(linha["location_id"]),
                    "competencia": competencia,
                    "gerado_em": agora,
                    "kwh_previsto": _ou_nulo(linha["kwh_prev"]) or 0.0,
                    # Sem banda quando o modelo nao se aplica: desenhar incerteza
                    # em volta de uma media movel daria ares de previsao a uma
                    # conta de padaria. O CHECK do banco tambem recusa.
                    "kwh_p10": _ou_nulo(linha.get("kwh_p10")) if aplicavel else None,
                    "kwh_p90": _ou_nulo(linha.get("kwh_p90")) if aplicavel else None,
                    "fat_prev": _ou_nulo(linha.get("fat_prev")),
                    "fat_p10": _ou_nulo(linha.get("fat_p10")) if aplicavel else None,
                    "fat_p90": _ou_nulo(linha.get("fat_p90")) if aplicavel else None,
                    "media_28d": _ou_nulo(linha.get("media_diaria_28d")),
                    "aplicavel": aplicavel,
                    "versao": artefato.get("versao_pipeline"),
                    "dias": int(dias_por_local.get(str(linha["location_id"]), 0)),
                    "declarada": COBERTURA_DECLARADA,
                    "medida": medida,
                    "wape_modelo": wape_modelo,
                    "wape_regua": wape_regua,
                },
            )
            gravadas += 1

    print(f"\nCompetencia {competencia}: {gravadas} site(s) gravado(s).")
    for _, linha in previsao.iterrows():
        marca = "" if linha["modelo_aplicavel"] else "  (fallback: media de 28 dias)"
        print(f"  {str(linha['location_id']):<28} {linha['kwh_prev']:>10.1f} kWh{marca}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
