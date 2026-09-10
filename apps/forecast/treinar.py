"""Treina o modelo de previsao com os dados deste banco.

    python treinar.py            (de dentro de apps/forecast)

POR QUE RETREINAR. O artefato que veio junto com o pipeline conhece oito estacoes
ficticias (`BR*XYZ*L0001`..`L0008`). `location_id` e' variavel categorica: local
que o modelo nao viu vira categoria desconhecida e cai no fallback de media
movel - sem erro, sem aviso, com a tela continuando a parecer correta. Sem
retreinar, o modelo entregue nao serve para nenhum site real.

POR QUE ESTE ARQUIVO EXISTE, e nao `python -m pipeline.train`. O `main()` do
pipeline le painel e cadastro de CSV; aqui eles vem do Postgres. As pecas do
meio - validacao, features, backtest, treino - sao as mesmas, chamadas uma a uma,
e `pipeline/` fica intocado para poder ser reatualizado a partir do repositorio
de modelagem sem conflito.

O QUE ESTES NUMEROS SIGNIFICAM. As metricas medem o modelo contra o historico
deste banco, que hoje e' gerado pelo seed. Servem para comparar o modelo com a
regua de media movel e para detectar regressao entre versoes; NAO sao estimativa
de desempenho em operacao real. O repositorio de modelagem original insiste no
mesmo ponto.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import joblib  # noqa: E402

from banco import carregar, conectar, resumo  # noqa: E402
from pipeline.features import (  # noqa: E402
    CATEGORICAS,
    FEATURES,
    alvo_em_razao,
    construir_treino,
)
from pipeline.schema import validar_painel  # noqa: E402
from pipeline.train import (  # noqa: E402
    PARAMS,
    QUANTIS,
    VERSAO_PIPELINE,
    backtest,
    treinar_um,
)

# O piso do proprio pipeline. Abaixo disso o treino nao tem o que aprender, e
# falhar alto e' melhor que entregar um modelo que so' repete a media.
MINIMO_DE_LINHAS = 500


def main() -> int:
    ap = argparse.ArgumentParser(description="Treina o modelo com os dados do banco")
    ap.add_argument("--saida", default=str(RAIZ / "modelos"))
    ap.add_argument("--meses-backtest", type=int, default=3)
    args = ap.parse_args()

    engine = conectar()
    # O historico para no ultimo dia do mes ANTERIOR. O mes corrente esta pela
    # metade, e o backtest o trataria como mes inteiro: o modelo preveria trinta
    # dias, a realidade teria nove, e parte do erro medido seria do calendario.
    #
    # O corte e' correto, mas nao foi o que explicava o resultado ruim: com ele o
    # WAPE mensal ficou em 12,36 contra 11,1 sem ele, e a regua de media movel
    # continuou ganhando. Fica registrado para ninguem refazer a hipotese.
    hoje = date.today()
    ate = hoje.replace(day=1) - timedelta(days=1)
    painel, estacoes, _tarifas = carregar(engine, ate=ate)

    print(f"Historico disponivel (ate {ate}):")
    print(resumo(painel))

    print("\n1. Validando painel...")
    validacao = validar_painel(painel, estacoes)
    validacao.imprimir()
    validacao.levantar_se_invalido()

    print("\n2. Construindo features...")
    ds = alvo_em_razao(construir_treino(painel, estacoes))
    print(
        f"   {len(ds):,} linhas | {len(FEATURES)} features | "
        f"{ds['location_id'].nunique()} estacoes"
    )
    if len(ds) < MINIMO_DE_LINHAS:
        raise SystemExit(
            f"apenas {len(ds)} linhas de treino - historico insuficiente.\n"
            "O seed precisa gerar pelo menos ~6 meses de operacao por site:\n"
            "  npm run infra:down -- -v && npm run infra:up"
        )

    print(f"\n3. Backtest ({args.meses_backtest} meses fora da amostra)...")
    metricas = backtest(ds, args.meses_backtest)
    for chave, valor in metricas.items():
        print(f"   {chave:32s} {valor}")

    if metricas.get("wape_mensal", 0) >= metricas.get("wape_mensal_baseline_m28", 0):
        print(
            "\n   [ATENCAO] o modelo NAO bateu a media movel de 28 dias.\n"
            "   Uma regua de tres linhas faria igual ou melhor - nao promova esta versao."
        )

    cobertura = metricas.get("cobertura_p10_p90_diaria")
    if cobertura is not None and cobertura < 75:
        print(
            f"\n   [ATENCAO] a faixa p10-p90 cobriu {cobertura}% dos casos, e deveria\n"
            "   cobrir ~80%. Ela e' mais estreita do que anuncia: o valor real cai\n"
            "   fora dela com mais frequencia do que o modelo declara. A tela mostra\n"
            "   este numero ao operador em vez de escondê-lo."
        )

    print("\n4. Treinando modelo final (historico completo)...")
    modelos = {"mediana": treinar_um(ds, "l1")}
    for nome, alpha in QUANTIS.items():
        modelos[nome] = treinar_um(ds, "quantile", alpha)

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

    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    carimbo = dt.datetime.now().strftime("%Y%m%d_%H%M")
    joblib.dump(artefato, destino / f"modelo_{carimbo}.joblib", compress=3)

    atual = destino / "modelo_atual.joblib"
    atual.unlink(missing_ok=True)
    joblib.dump(artefato, atual, compress=3)
    (destino / f"metricas_{carimbo}.json").write_text(
        json.dumps(metricas, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\nArtefato: {atual}")
    print(f"Estacoes treinadas: {', '.join(artefato['estacoes_treinadas'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
