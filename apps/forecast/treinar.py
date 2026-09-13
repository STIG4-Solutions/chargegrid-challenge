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
import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import joblib  # noqa: E402
import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import sklearn  # noqa: E402

from banco import carregar, conectar, resumo  # noqa: E402
from pipeline import train as _train  # noqa: E402
from pipeline.features import (  # noqa: E402
    CATEGORICAS,
    FEATURES,
    alvo_em_razao,
    construir_treino,
)
from pipeline.schema import validar_painel  # noqa: E402
from pipeline.train import QUANTIS, VERSAO_PIPELINE, backtest, treinar_um  # noqa: E402

# O que se acrescenta ao `random_state=42` do pipeline, e o que cada peca faz.
#
# `random_state` fixa a amostragem (`subsample`, `colsample_bytree`) e mais
# nada - nao fixa como os histogramas sao construidos.
#
# `num_threads` fixo e' a peca que REMOVE uma variavel de maquina: a ordem em
# que as somas parciais se juntam depende do numero de threads, e soma de ponto
# flutuante nao e' associativa. Com o valor preso, a contagem de nucleos do host
# deixa de entrar na conta. E' a garantia mais direta das tres.
#
# `deterministic` e `force_row_wise` sao PREVENTIVOS, e vale registrar o limite
# da evidencia: a documentacao do LightGBM diz que `deterministic` e' o que
# estabiliza o resultado entre numeros de threads diferentes, e que ele so' vale
# com uma estrategia de construcao fixa. Mas a divergencia NAO foi reproduzida
# aqui - `tests/test_determinismo.py` tentou com 900, 8.000 e 30.000 linhas, em
# maquina de 20 nucleos, e os modelos sairam identicos com e sem as flags.
#
# Ficam porque custam pouco e o contrato da biblioteca e' explicito; nao ficam
# porque algum teste deste repositorio as tenha exigido. O teste registra a
# tentativa para ninguem refazer o experimento achando que vai achar algo.
#
# A reprodutibilidade que ESTA medida veio de outro lugar: versoes fixas em
# `requirements.txt`, `--ate` explicito, e o retreino batendo metrica a metrica
# com a corrida anterior sobre os mesmos dados.
DETERMINISMO = {"deterministic": True, "force_row_wise": True, "num_threads": 4}

# Reescrever a global do modulo, e nao passar parametro: `backtest` chama
# `treinar_um` por dentro, e um parametro novo nao chegaria la sem tocar
# `pipeline/`. O diretorio e' vendorizado do repositorio de modelagem e fica
# intocado de proposito, para poder ser reatualizado sem conflito.
#
# O backtest PRECISA usar os mesmos parametros do treino final: medir com uma
# configuracao e publicar outra e' comparar coisas diferentes.
_train.PARAMS = dict(_train.PARAMS, **DETERMINISMO)
PARAMS = _train.PARAMS

# O piso do proprio pipeline. Abaixo disso o treino nao tem o que aprender, e
# falhar alto e' melhor que entregar um modelo que so' repete a media.
MINIMO_DE_LINHAS = 500


def main() -> int:
    ap = argparse.ArgumentParser(description="Treina o modelo com os dados do banco")
    ap.add_argument("--saida", default=str(RAIZ / "modelos"))
    ap.add_argument("--meses-backtest", type=int, default=3)
    # A data de corte vira ARGUMENTO. O padrao continua sendo o ultimo dia do
    # mes anterior, mas quem precisa reproduzir um artefato antigo passa a
    # janela que ele declara em `periodo_treino` e chega ao mesmo lugar.
    #
    # Sem isto a reprodutibilidade tem prazo de validade: o historico do seed e'
    # ancorado em `now()`, entao o mesmo comando roda sobre dados diferentes a
    # cada mes que passa - e o artefato de setembro nao se refaz em outubro.
    ap.add_argument(
        "--ate",
        default=None,
        metavar="AAAA-MM-DD",
        help="ultimo dia do historico; padrao e' o ultimo dia do mes anterior",
    )
    args = ap.parse_args()

    engine = conectar()
    # O historico para no ultimo dia do mes ANTERIOR. O mes corrente esta pela
    # metade, e o backtest o trataria como mes inteiro: o modelo preveria trinta
    # dias, a realidade teria nove, e parte do erro medido seria do calendario.
    #
    # O corte e' correto, mas nao foi o que explicava o resultado ruim: com ele o
    # WAPE mensal ficou em 12,36 contra 11,1 sem ele, e a regua de media movel
    # continuou ganhando. Fica registrado para ninguem refazer a hipotese.
    if args.ate:
        ate = date.fromisoformat(args.ate)
    else:
        ate = date.today().replace(day=1) - timedelta(days=1)
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

    # Impressao digital do que entrou no treino.
    #
    # Existe por uma pergunta que ficou sem resposta: o WAPE mensal saiu 8,31
    # de manha e 9,94 a tarde, com a MESMA janela, as mesmas 1.647 linhas, os
    # mesmos parametros e a MESMA regua (7,61 nas duas).
    #
    # A reinvestigacao posterior derrubou as hipoteses, uma a uma: o treino e'
    # deterministico, nao depende de `num_threads`, `pipeline/train.py` nao
    # mudou entre as corridas, e a procedencia gravada e' confiavel. Inclusive a
    # mais forte - "o banco mudou" - CAIU: deslocar a janela em dois dias mexe
    # na regua, entao regua identica prova dado identico. O README de forecast
    # traz a tabela.
    #
    # Nao ha o que reinvestigar de novo: o seed consome UM `random.Random(42)`
    # em sequencia com a janela ancorada em `now()`, entao o banco daquela manha
    # nao volta nem re-executando o mesmo seed. Este hash e' para a PROXIMA vez:
    # hash igual aponta para o ambiente, hash diferente para o banco.
    impressao = hashlib.sha256(
        ds.sort_values(["location_id", "date", "horizonte"])[FEATURES + ["y_ratio"]]
        .to_csv(index=False)
        .encode()
    ).hexdigest()[:32]
    print(f"   impressao digital do treino: {impressao}")

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
        # O comando que refaz ESTE artefato. Sem ele, `periodo_treino` conta
        # onde o modelo chegou mas nao como voltar la'.
        "reproduzir_com": f"python treinar.py --ate {ate} --meses-backtest {args.meses_backtest}",
        "versoes": {
            "lightgbm": lgb.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "modelos": modelos,
        "features": FEATURES,
        "categoricas": CATEGORICAS,
        "params": PARAMS,
        "metricas_backtest": metricas,
        "estacoes_treinadas": sorted(ds["location_id"].astype(str).unique()),
        "periodo_treino": [str(ds["date"].min().date()), str(ds["date"].max().date())],
        "n_linhas_treino": int(len(ds)),
        "impressao_do_treino": impressao,
    }

    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    carimbo = dt.datetime.now().strftime("%Y%m%d_%H%M")
    joblib.dump(artefato, destino / f"modelo_{carimbo}.joblib", compress=3)

    atual = destino / "modelo_atual.joblib"
    atual.unlink(missing_ok=True)
    joblib.dump(artefato, atual, compress=3)
    # As metricas saem duas vezes: com carimbo, para o historico local, e com
    # nome fixo, porque `metricas_atual.json` E' o arquivo versionado.
    #
    # Ele e' a EVIDENCIA dos numeros publicados no README. O modelo em si nao
    # vai para o git - 2 MB de binario por retreino, com diff irrevisavel - mas
    # a afirmacao que se faz sobre ele tem de ser conferivel por quem le.
    prova = {
        "gerado_por": artefato["reproduzir_com"],
        "versao_pipeline": VERSAO_PIPELINE,
        "versoes": artefato["versoes"],
        "periodo_treino": artefato["periodo_treino"],
        "n_linhas_treino": artefato["n_linhas_treino"],
        # Muda com os DADOS, nao com o codigo. E' o que separa "o modelo
        # piorou" de "o banco e' outro" na proxima vez que a metrica mexer.
        "impressao_do_treino": impressao,
        "estacoes_treinadas": artefato["estacoes_treinadas"],
        "determinismo": DETERMINISMO,
        "metricas": metricas,
    }
    texto = json.dumps(prova, indent=2, ensure_ascii=False) + "\n"
    (destino / f"metricas_{carimbo}.json").write_text(texto, encoding="utf-8")
    (destino / "metricas_atual.json").write_text(texto, encoding="utf-8")

    print(f"\nArtefato: {atual}")
    print(f"Estacoes treinadas: {', '.join(artefato['estacoes_treinadas'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
