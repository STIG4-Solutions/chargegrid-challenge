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
from modelo import COBERTURA_DECLARADA, alinhar_limiar_do_pipeline  # noqa: E402
from modelo.prever import prever  # noqa: E402
from pipeline import features as _features  # noqa: E402

# A versao de artefato que este exportador sabe ler. O 2.0.0 tem `modelos` com as
# chaves `forma` e `nivel`; um artefato 1.x tem `mediana`/`p10`/`p90`, e seguir
# com ele daria `KeyError` no meio da gravacao - depois de algumas linhas escritas.
VERSAO_MINIMA = 2

# Depois disto o artefato esta velho. O numero vem do proprio pipeline: a demanda
# muda de estacao para estacao ao longo do ano, e um modelo de tres meses atras
# ja nao viu a sazonalidade que esta chegando.
DIAS_ATE_ENVELHECER = 60

_UPSERT = text(
    """
    INSERT INTO site_forecasts (
        id, site_id, granularidade, bucket_inicio, competencia, gerado_em,
        kwh_previsto, kwh_p10, kwh_p90,
        faturamento_previsto_brl, fat_p10_brl, fat_p90_brl,
        media_diaria_28d, modelo_aplicavel, fonte, modelo_versao, dias_de_historico,
        cobertura_declarada_pct, cobertura_medida_pct,
        wape_modelo_pct, wape_baseline_pct,
        created_at, updated_at
    )
    SELECT :id, s.id, 'mes',
           -- O inicio do bucket, no fuso DA PRACA. Calculado aqui, ao lado do
           -- `JOIN sites`, porque e' o unico lugar que conhece o fuso - e porque
           -- ele tem de concordar com `competencia`, que e' a mesma data.
           -- `CAST(... AS ...)` e nao `::`: dois-pontos colado a um parametro
           -- confunde o parser do `text()`, e o erro que sai e' um "syntax error
           -- at or near :" sem dizer onde.
           (CAST(:competencia AS timestamp) AT TIME ZONE s.timezone),
           :competencia, :gerado_em,
           :kwh_previsto, :kwh_p10, :kwh_p90,
           :fat_prev, :fat_p10, :fat_p90,
           :media_28d, :aplicavel, :fonte, :versao, :dias,
           :declarada, :medida,
           :wape_modelo, :wape_regua,
           now(), now()
    FROM sites s WHERE s.slug = :slug
    -- A chave passou a incluir a janela e o inicio do bucket. Este job grava
    -- so' a janela mensal, entao `'mes'` e a competencia a identificam - mas o
    -- alvo do ON CONFLICT tem de ser a chave que EXISTE, senao o UPSERT falha.
    ON CONFLICT (site_id, granularidade, bucket_inicio) DO UPDATE SET
        gerado_em = EXCLUDED.gerado_em,
        kwh_previsto = EXCLUDED.kwh_previsto,
        kwh_p10 = EXCLUDED.kwh_p10,
        kwh_p90 = EXCLUDED.kwh_p90,
        faturamento_previsto_brl = EXCLUDED.faturamento_previsto_brl,
        fat_p10_brl = EXCLUDED.fat_p10_brl,
        fat_p90_brl = EXCLUDED.fat_p90_brl,
        media_diaria_28d = EXCLUDED.media_diaria_28d,
        modelo_aplicavel = EXCLUDED.modelo_aplicavel,
        fonte = EXCLUDED.fonte,
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


def _pela_media_movel(linha) -> float:
    """O numero da media movel de 28 dias para esta estacao, no mes alvo.

    Duas origens, porque o previsor preenche coisas diferentes em cada caso:
    quando ele previu a estacao, `media_diaria_28d` tem a media e basta
    multiplicar pelos dias; quando ela caiu no fallback dele, `kwh_prev` JA e' a
    media movel e `media_diaria_28d` vem NaN - ler dela gravaria zero num site
    que tem movimento.
    """
    media = _ou_nulo(linha.get("media_diaria_28d"))
    if media is not None:
        return media * int(linha["dias"])
    return _ou_nulo(linha.get("kwh_prev")) or 0.0


def _pela_regua(linha, qual: str) -> tuple[float, str]:
    """O numero da regua elegida E o nome dela, no mesmo par.

    UM par, e nao duas expressoes separadas: o numero e o rotulo TEM de concordar, e
    foi por eles serem calculados em lugares diferentes que uma praca em fallback de
    media movel foi gravada como `fonte = 'ano_a_ano'`.

    A escolha e' por praca, e nao so' global. Uma praca sem ano anterior nao tem
    `kwh_regua_ano` mesmo quando a regua de ano-a-ano ganhou na rede inteira: ali a
    media movel e' a unica que existe, e cair para ela e' o certo - desde que a
    `fonte` diga isso.
    """
    if qual == "ano_a_ano":
        valor = _ou_nulo(linha.get("kwh_regua_ano"))
        if valor is not None:
            return valor, "ano_a_ano"
    return _pela_media_movel(linha), "media_movel"


def _alinhar_limiar(artefato: dict) -> None:
    """Usa o MESMO limiar de historico minimo que o treino usou.

    O numero vem do artefato, e nao da constante deste processo: o que importa e'
    que a previsao monte as features como o treino montou. Se o codigo mudar o
    limiar depois de um treino, e' o artefato que manda ate o proximo retreino.
    """
    alinhar_limiar_do_pipeline()
    do_artefato = artefato.get("min_hist_dias")
    if do_artefato is not None and int(do_artefato) != _features.MIN_HIST_DIAS:
        print(
            f"[ATENCAO] o artefato foi treinado com min_hist_dias={do_artefato} e este"
            f" codigo usa {_features.MIN_HIST_DIAS}."
        )
        print("          Seguindo com o do ARTEFATO, para treino e previsao concordarem.")
        _features.MIN_HIST_DIAS = int(do_artefato)


def _recusar_versao_antiga(artefato: dict) -> None:
    """Para antes de gravar se o artefato nao tem a forma que este codigo le.

    O 2.0.0 tem dois modelos com outras chaves. Seguir com um 1.x daria `KeyError`
    no meio do laco de gravacao - depois de algumas linhas ja' escritas, com a
    tabela metade velha e metade nova. Recusar antes de abrir a transacao e' o
    que mantem a tabela consistente.
    """
    versao = str(artefato.get("versao_pipeline", "0"))
    if int(versao.split(".")[0]) < VERSAO_MINIMA:
        raise SystemExit(
            f"artefato na versao {versao}, e este exportador le {VERSAO_MINIMA}.x.\n"
            "\n"
            "O previsor mudou de forma: dois modelos em vez de um, e faixa\n"
            "calibrada em vez dos modelos de quantil. Retreine:\n"
            "\n"
            "    npm run forecast:train"
        )


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
        # E' AQUI que um clone novo para, e a mensagem tem de dizer o que
        # fazer. O modelo nao e' versionado de proposito - 2 MB de binario
        # por retreino, com diff irrevisavel -, entao o primeiro export de
        # QUALQUER ambiente esbarra nisto. Dizer so' "nao encontrado" manda
        # a pessoa procurar um arquivo que nunca existiu.
        raise SystemExit(
            f"artefato nao encontrado em {caminho}\n"
            "\n"
            "O modelo nao vai para o git (ver apps/forecast/README.md).\n"
            "Treine o seu com o banco ja populado - uma vez por ambiente:\n"
            "\n"
            "    npm run forecast        # treina e exporta, da raiz do repo\n"
            "\n"
            "Ou so' o treino, para conferir as metricas antes de exportar:\n"
            "\n"
            "    npm run forecast:train"
        )

    artefato = joblib.load(caminho)
    _recusar_versao_antiga(artefato)
    _alinhar_limiar(artefato)
    _avisar_se_velho(artefato)

    engine = conectar()
    painel, estacoes, tarifas = carregar(engine)
    print("Historico disponivel:")
    print(resumo(painel))

    # A cobertura MEDIDA continua indo para a tela ao lado da declarada. Com a
    # faixa conforme as duas devem coincidir - e o dia em que divergirem de novo,
    # e' este numero que diz isso em vez de esconder.
    #
    # A mensal e' a que descreve o card: a linha gravada aqui e' um TOTAL de mes, e
    # a cobertura de uma faixa diaria nao vale para a soma de trinta dias.
    #
    # AUSENTE e' diferente de NAO MEDIDA, e era um `or` que juntava as duas. Artefato
    # antigo nao TEM a chave mensal, e ai a diaria e' a melhor aproximacao
    # disponivel. Artefato novo TEM a chave com valor `None` quando a cobertura nao
    # pode ser medida - e' o caso de staging, onde 3 pracas dao 18 residuos mensais
    # contra o minimo de 30. Nesse caso a diaria nao serve: o card anunciaria 81,2%
    # de cobertura sobre uma faixa que ninguem mediu, com numero de outro grao.
    metricas = artefato.get("metricas_backtest", {})
    if "cobertura_p10_p90_mensal" in metricas:
        medida = metricas["cobertura_p10_p90_mensal"]
    else:
        medida = metricas.get("cobertura_p10_p90_diaria")
    wape_modelo = metricas.get("wape_mensal")

    # AS DUAS REGUAS, e a melhor delas e' a barra. Comparar so' com a media movel
    # era barra baixa: medido em 24 meses ela faz 13,57% e a de ano-a-ano 9,95%,
    # entao um modelo com 13% "batia a regua" perdendo de longe da melhor
    # disponivel. `min` sobre as que EXISTEM - artefato antigo nao tem a metrica
    # nova, e `None` nao pode entrar na comparacao.
    reguas = {
        "media_movel": metricas.get("wape_mensal_baseline_m28"),
        "ano_a_ano": metricas.get("wape_mensal_baseline_ano"),
    }
    disponiveis = {k: v for k, v in reguas.items() if v is not None}
    regua_escolhida = min(disponiveis, key=disponiveis.get) if disponiveis else "media_movel"
    wape_regua = disponiveis.get(regua_escolhida)

    # A ESCOLHA. O modelo so' e' usado quando MEDE melhor que a MELHOR regua no
    # backtest; caso contrario grava-se a regua, e `fonte` diz qual.
    #
    # Nem promover nem desistir e' decisao de quem escreve codigo: o backtest
    # inverte isto sozinho quando o numero mudar de lado.
    #
    # Havia aqui uma medicao de que combinar os dois nao resolvia, com uma
    # correlacao de 0,944 entre os erros mensais. Ela saiu por duas razoes: vinha
    # de um artefato que nenhum atual reproduz, e a pergunta mudou. Combinar era
    # tentador quando modelo e regua empatavam porque os dois eram essencialmente
    # "nivel x dias"; agora o modelo mensal corrige a regua de ano-a-ano por
    # construcao, entao ele JA' e' a combinacao dos dois - razao 1,0 devolve a
    # regua, e o que ele aprende e' o residuo.
    #
    # Sem metrica nenhuma no artefato, o modelo NAO e' usado: e' o valor
    # conservador, e um artefato sem backtest nao provou nada.
    modelo_vence = wape_modelo is not None and wape_regua is not None and wape_modelo < wape_regua

    print("\nReguas medidas: " + ", ".join(f"{k} {v}%" for k, v in sorted(disponiveis.items())))
    if not modelo_vence and wape_modelo is not None and wape_regua is not None:
        print(
            f"[ATENCAO] este artefato NAO supera a melhor regua: erro de {wape_modelo}%\n"
            f"          contra {wape_regua}% de `{regua_escolhida}`.\n"
            f"          O numero gravado sera' o da REGUA, e `fonte` dira' `{regua_escolhida}`.\n"
            "          O modelo continua treinado e volta sozinho quando ganhar."
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
            # Usa o modelo so' quando ele CONHECE o local E MEDE melhor que a
            # regua. Os dois casos em que nao usa produzem o mesmo numero - a
            # media movel - mas por motivos diferentes, e a tela precisa dizer
            # qual foi.
            usa_modelo = aplicavel and modelo_vence
            media = _ou_nulo(linha.get("media_diaria_28d"))
            # O par sai daqui mesmo quando nao e' usado: e' ele que da' a `fonte`
            # da linha, e calcular os dois juntos e' o que impede que discordem.
            kwh_regua, fonte_regua = _pela_regua(linha, regua_escolhida)

            if usa_modelo:
                kwh = _ou_nulo(linha["kwh_prev"]) or 0.0
                faturamento = _ou_nulo(linha.get("fat_prev"))
            else:
                # `kwh_prev` ja E' a media movel quando a estacao caiu no
                # fallback do pipeline - e nesse caso `media_diaria_28d` vem
                # NaN, porque nao houve janela de 28 dias para calcular.
                # Recalcular a partir dela gravaria zero num site que tem
                # movimento; e' preciso pegar o numero de onde ele existe.
                kwh = kwh_regua
                preco = _ou_nulo(linha.get("price_per_kwh"))
                faturamento = kwh * preco if preco is not None else None

            conexao.execute(
                _UPSERT,
                {
                    "id": uuid.uuid4(),
                    "slug": str(linha["location_id"]),
                    "competencia": competencia,
                    "gerado_em": agora,
                    "kwh_previsto": kwh,
                    # Banda so' quando o numero vem do modelo: desenhar incerteza
                    # em volta de uma media movel daria ares de previsao a uma
                    # conta de padaria. O CHECK do banco tambem recusa.
                    "kwh_p10": _ou_nulo(linha.get("kwh_p10")) if usa_modelo else None,
                    "kwh_p90": _ou_nulo(linha.get("kwh_p90")) if usa_modelo else None,
                    "fat_prev": faturamento,
                    "fat_p10": _ou_nulo(linha.get("fat_p10")) if usa_modelo else None,
                    "fat_p90": _ou_nulo(linha.get("fat_p90")) if usa_modelo else None,
                    "media_28d": media,
                    "aplicavel": aplicavel,
                    # `fonte` nomeia o previsor que produziu ESTE numero.
                    # Gravar a regua de ano-a-ano como `media_movel` diria ao
                    # operador que o numero e' a media dos ultimos 28 dias
                    # quando nao e', e sao 3,6 pontos medidos entre as duas.
                    "fonte": "modelo" if usa_modelo else fonte_regua,
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
        aplicavel = bool(linha["modelo_aplicavel"])
        kwh_regua, fonte_regua = _pela_regua(linha, regua_escolhida)
        if not aplicavel:
            marca = f"  ({fonte_regua}: historico curto demais)"
        elif not modelo_vence:
            marca = f"  ({fonte_regua}: o modelo perde da regua)"
        else:
            marca = ""
        valor = float(linha["kwh_prev"]) if aplicavel and modelo_vence else kwh_regua
        print(f"  {str(linha['location_id']):<28} {valor:>10.1f} kWh{marca}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
