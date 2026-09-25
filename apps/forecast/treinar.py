"""Treina o modelo de previsao com os dados deste banco.

    python treinar.py            (de dentro de apps/forecast)

POR QUE RETREINAR. O artefato que veio junto com o pipeline conhece oito estacoes
ficticias (`BR*XYZ*L0001`..`L0008`). `location_id` e' variavel categorica: local
que o modelo nao viu vira categoria desconhecida e cai no fallback de media
movel - sem erro, sem aviso, com a tela continuando a parecer correta. Sem
retreinar, o modelo entregue nao serve para nenhum site real.

POR QUE ESTE ARQUIVO EXISTE, e nao `python -m pipeline.train`. O `main()` do
pipeline le painel e cadastro de CSV; aqui eles vem do Postgres. E o que se treina
nao e' mais o modelo do pipeline: e' o de `modelo/`, que tem dois estagios e uma
faixa calibrada. `pipeline/` fica byte a byte igual a origem, e o que e' do
ChargeGrid mora em `modelo/` - lintado e com teste proprio.

DOIS MODELOS, E POR QUE. `modelo/__init__.py` traz a tabela de medicao completa;
o resumo e' que nivel e forma tem vencedores diferentes:

    o numero do card (mes)   modelo mensal sobre a regua de ano-a-ano
    a curva do mes (dia)     modelo diario, preso ao nivel

O QUE ESTES NUMEROS SIGNIFICAM. As metricas medem o modelo contra o historico
deste banco, que hoje e' gerado pelo seed. Servem para comparar o modelo com as
reguas e para detectar regressao entre versoes; NAO sao estimativa de desempenho
em operacao real. O seed repete a sazonalidade mensal ano a ano por construcao,
entao o eixo de ano-a-ano e' generoso aqui de um jeito que nao se repete numa
rede real - o mecanismo e' real, a magnitude e' circular.
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
from modelo import (  # noqa: E402
    COBERTURA_DECLARADA,
    MIN_HIST_DIAS,
    PARAMS,
    alinhar_limiar_do_pipeline,
    colunas_de_ano,
)
from modelo.aferir import backtest  # noqa: E402
from modelo.forma import features_da_forma, treinar_forma  # noqa: E402
from modelo.limiares import recusar_se_nenhuma_praca_elegivel  # noqa: E402
from modelo.nivel import painel_mensal, treinar_nivel  # noqa: E402
from modelo.perda import DETERMINISMO  # noqa: E402
from pipeline.features import CATEGORICAS, FEATURES, construir_treino  # noqa: E402
from pipeline.schema import validar_painel  # noqa: E402

# 2.0.0 e nao 1.0.x: o previsor tem outra forma. `modelos` passa a ter as chaves
# `forma` e `nivel` em vez de `mediana`/`p10`/`p90`, e a faixa vem de
# `metricas_backtest["fatores_da_faixa"]` em vez dos modelos de quantil. Um
# artefato 1.x nao carrega em `modelo/prever.py`, e versao maior e' o que faz isso
# falhar alto em vez de prever com meio artefato.
VERSAO_PIPELINE = "2.0.0"

# O piso do proprio pipeline. Abaixo disso o treino nao tem o que aprender, e
# falhar alto e' melhor que entregar um modelo que so' repete a media.
MINIMO_DE_LINHAS = 500


def main() -> int:
    ap = argparse.ArgumentParser(description="Treina o modelo com os dados do banco")
    ap.add_argument("--saida", default=str(RAIZ / "modelos"))
    # 12 e nao 3. O backtest agora calibra a faixa com os meses ANTERIORES a cada
    # mes alvo, e com 3 meses reportados os primeiros ficariam sem calibracao. E'
    # tambem o que da' n=84 registros mensais em vez de 21 - com 21, um mes
    # estranho move a metrica em pontos inteiros.
    ap.add_argument("--meses-backtest", type=int, default=12)
    # A data de corte e' ARGUMENTO. O padrao e' o ultimo dia do mes anterior, mas
    # quem precisa reproduzir um artefato antigo passa a janela que ele declara em
    # `periodo_treino` e chega ao mesmo lugar. Sem isto a reprodutibilidade tem
    # prazo de validade: o historico do seed e' ancorado em `now()`.
    ap.add_argument(
        "--ate",
        default=None,
        metavar="AAAA-MM-DD",
        help="ultimo dia do historico; padrao e' o ultimo dia do mes anterior",
    )
    args = ap.parse_args()

    # O limiar de historico minimo passa a ser um so'. Ver `modelo/limiares.py`:
    # `features.py` usava 150 e o aviso de `schema.py` dizia 180 e afirmava que a
    # praca seria ignorada - o que nao acontecia.
    anterior = alinhar_limiar_do_pipeline()
    if anterior != MIN_HIST_DIAS:
        print(f"Historico minimo por praca: {MIN_HIST_DIAS} dias (era {anterior} em features.py)")

    engine = conectar()
    # O historico para no ultimo dia do mes ANTERIOR. O mes corrente esta pela
    # metade, e o backtest o trataria como mes inteiro: o modelo preveria trinta
    # dias, a realidade teria nove, e parte do erro medido seria do calendario.
    if args.ate:
        ate = date.fromisoformat(args.ate)
    else:
        ate = date.today().replace(day=1) - timedelta(days=1)
    painel, estacoes, _tarifas = carregar(engine, ate=ate)

    print(f"\nHistorico disponivel (ate {ate}):")
    print(resumo(painel))

    print("\n1. Validando painel...")
    validacao = validar_painel(painel, estacoes)
    validacao.imprimir()
    validacao.levantar_se_invalido()

    print("\n2. Construindo features...")
    # Antes de `construir_treino`, porque ela estoura com `KeyError: 'archetype'`
    # quando nenhuma praca qualifica - ver `modelo/limiares.py`.
    elegiveis = recusar_se_nenhuma_praca_elegivel(painel)
    print(f"   {len(elegiveis)} praca(s) com {MIN_HIST_DIAS}+ dias de historico valido")
    ds = construir_treino(painel, estacoes)
    ds = ds[ds["y_kwh"].notna()].copy()
    ds = ds[ds["hist_m28"].replace(0, np.nan).notna()].copy()
    # O eixo de ano-a-ano, que o pipeline nao tinha: `hist_ano_atras` apontava
    # para o mes anterior ao alvo, um ano antes, e era nivel em vez de razao.
    ds = colunas_de_ano(ds, painel)
    features = features_da_forma(FEATURES)
    print(
        f"   {len(ds):,} linhas | {len(features)} features | "
        f"{ds['location_id'].nunique()} pracas | "
        f"ano anterior em {ds['tem_ano'].mean() * 100:.0f}% das linhas"
    )
    if len(ds) < MINIMO_DE_LINHAS:
        raise SystemExit(
            f"apenas {len(ds)} linhas de treino - historico insuficiente.\n"
            "O seed precisa gerar pelo menos ~6 meses de operacao por site:\n"
            "  npm run infra:down -- -v && npm run infra:up"
        )

    # Impressao digital do que entrou no treino. Existe por uma pergunta que ficou
    # sem resposta: o WAPE mensal saiu 8,31 de manha e 9,94 a tarde, com a MESMA
    # janela, as mesmas 1.647 linhas e a MESMA regua. A reinvestigacao derrubou as
    # hipoteses uma a uma - inclusive "o banco mudou", porque regua identica prova
    # dado identico. Este hash e' para a PROXIMA vez: hash igual aponta para o
    # ambiente, hash diferente para o banco.
    impressao = hashlib.sha256(
        ds.sort_values(["location_id", "date", "horizonte"])[features + ["y_kwh", "nivel_ano"]]
        .to_csv(index=False)
        .encode()
    ).hexdigest()[:32]
    print(f"   impressao digital do treino: {impressao}")

    print(f"\n3. Backtest ({args.meses_backtest} meses fora da amostra)...")
    metricas = backtest(ds, args.meses_backtest, CATEGORICAS, features)
    for chave, valor in metricas.items():
        print(f"   {chave:32s} {valor}")

    # O PORTAO usa a MELHOR regua, e nao a mais conveniente. Bater a media movel
    # era barra baixa: ela faz ~13,6% no mes e a regua de ano-a-ano faz ~9,9%.
    reguas = [
        v
        for v in (
            metricas.get("wape_mensal_baseline_m28"),
            metricas.get("wape_mensal_baseline_ano"),
        )
        if v is not None
    ]
    if reguas and (metricas.get("wape_mensal") or float("inf")) >= min(reguas):
        print(
            f"\n   [ATENCAO] o modelo NAO bateu a melhor regua ({min(reguas)}%).\n"
            "   Uma regua de tres linhas faria igual ou melhor - nao promova esta versao."
        )

    cobertura = metricas.get("cobertura_p10_p90_diaria")
    if cobertura is not None and abs(cobertura - COBERTURA_DECLARADA) > 5:
        print(
            f"\n   [ATENCAO] a faixa p10-p90 cobriu {cobertura}% e declara "
            f"{COBERTURA_DECLARADA:.0f}%.\n"
            "   A calibracao conforme deveria fechar essa diferenca; se nao fechou,\n"
            "   os meses de calibracao nao representam o mes alvo."
        )

    print("\n4. Treinando modelos finais (historico completo)...")
    mensal = painel_mensal(ds)
    modelo_nivel = treinar_nivel(mensal)
    if modelo_nivel is None:
        print(
            f"   [ATENCAO] {len(mensal)} registros mensais - poucos para o modelo do\n"
            "   nivel. O card sera' servido pela regua de ano-a-ano, e `fonte` dira' isso."
        )
    modelos = {"forma": treinar_forma(ds, features, CATEGORICAS), "nivel": modelo_nivel}

    artefato = {
        "versao_pipeline": VERSAO_PIPELINE,
        "treinado_em": dt.datetime.now().isoformat(timespec="seconds"),
        # O comando que refaz ESTE artefato. Sem ele, `periodo_treino` conta onde o
        # modelo chegou mas nao como voltar la'.
        "reproduzir_com": (f"python treinar.py --ate {ate} --meses-backtest {args.meses_backtest}"),
        "versoes": {
            "lightgbm": lgb.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "modelos": modelos,
        "features": features,
        "categoricas": CATEGORICAS,
        # `params` declara a perda que os modelos REALMENTE usam. Era aqui que o
        # artefato mentia: `PARAMS` dizia tweedie e o treino final passava "l1"
        # explicito, entao a metrica publicada descrevia outro modelo.
        "params": PARAMS,
        "min_hist_dias": MIN_HIST_DIAS,
        "metricas_backtest": metricas,
        "estacoes_treinadas": sorted(ds["location_id"].astype(str).unique()),
        "periodo_treino": [str(ds["date"].min().date()), str(ds["date"].max().date())],
        "n_linhas_treino": int(len(ds)),
        "n_registros_mensais": int(len(mensal)),
        "impressao_do_treino": impressao,
    }

    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    carimbo = dt.datetime.now().strftime("%Y%m%d_%H%M")
    joblib.dump(artefato, destino / f"modelo_{carimbo}.joblib", compress=3)

    atual = destino / "modelo_atual.joblib"
    atual.unlink(missing_ok=True)
    joblib.dump(artefato, atual, compress=3)
    # As metricas saem duas vezes: com carimbo, para o historico local, e com nome
    # fixo, porque `metricas_atual.json` E' o arquivo versionado. Ele e' a
    # EVIDENCIA dos numeros publicados no README - o modelo em si nao vai para o
    # git, mas a afirmacao que se faz sobre ele tem de ser conferivel.
    prova = {
        "gerado_por": artefato["reproduzir_com"],
        "versao_pipeline": VERSAO_PIPELINE,
        "versoes": artefato["versoes"],
        "periodo_treino": artefato["periodo_treino"],
        "n_linhas_treino": artefato["n_linhas_treino"],
        "n_registros_mensais": artefato["n_registros_mensais"],
        "min_hist_dias": MIN_HIST_DIAS,
        # Muda com os DADOS, nao com o codigo. E' o que separa "o modelo piorou"
        # de "o banco e' outro" na proxima vez que a metrica mexer.
        "impressao_do_treino": impressao,
        "estacoes_treinadas": artefato["estacoes_treinadas"],
        "determinismo": DETERMINISMO,
        "metricas": metricas,
    }
    texto = json.dumps(prova, indent=2, ensure_ascii=False) + "\n"
    (destino / f"metricas_{carimbo}.json").write_text(texto, encoding="utf-8")
    (destino / "metricas_atual.json").write_text(texto, encoding="utf-8")

    print(f"\nArtefato: {atual}")
    print(f"Pracas treinadas: {', '.join(artefato['estacoes_treinadas'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
