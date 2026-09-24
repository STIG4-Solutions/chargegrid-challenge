"""Grava as previsoes por JANELA: hora, dia, semana, mes e ano.

    python exportar_janelas.py

Irmao de `exportar.py`, e nao substituto. A divisao e' deliberada:

  exportar.py          a linha do PROXIMO MES por praca, vinda do MODELO quando o
                       portao o aprova. E' o numero que a aba de demanda
                       contratada le', e o contrato dela nao muda.
  exportar_janelas.py  todas as outras: as cinco janelas, para cada praca E para a
                       rede inteira.

POR QUE O MES COMECA NO SEGUNDO BUCKET AQUI. O modelo e' um previsor DIRETO de um
mes a frente: as features dele descrevem o historico ate' a origem, e a origem e' o
fim do mes anterior ao alvo. Para o mes+2 esse historico nao existe ainda. Entao o
mes+1 pertence ao `exportar.py`, que o tira do modelo, e os meses seguintes saem de
regua - com `fonte` dizendo qual, como sempre. Gravar os dois no mesmo bucket faria
um sobrescrever o outro na chave unica.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

from banco import carregar, conectar  # noqa: E402
from janelas.gravar import todas_as_janelas  # noqa: E402
from janelas.painel import na_rede, painel_horario, serie  # noqa: E402

# As colunas que este job preenche. As metricas do artefato NAO entram: elas
# descrevem o backtest do modelo mensal, e colar em linha de regua horaria
# sugeriria que aquele erro vale para esta janela.
_COMUNS = """
    granularidade, bucket_inicio, competencia, gerado_em,
    kwh_previsto, kwh_p10, kwh_p90,
    faturamento_previsto_brl, fat_p10_brl, fat_p90_brl,
    modelo_aplicavel, fonte, created_at, updated_at
"""
_VALORES = """
    :granularidade, :bucket_inicio, :competencia, :gerado_em,
    :kwh_previsto, :kwh_p10, :kwh_p90,
    :fat_prev, :fat_p10, :fat_p90,
    false, :fonte, now(), now()
"""
_ATUALIZA = """
    gerado_em = EXCLUDED.gerado_em,
    kwh_previsto = EXCLUDED.kwh_previsto,
    kwh_p10 = EXCLUDED.kwh_p10,
    kwh_p90 = EXCLUDED.kwh_p90,
    faturamento_previsto_brl = EXCLUDED.faturamento_previsto_brl,
    fat_p10_brl = EXCLUDED.fat_p10_brl,
    fat_p90_brl = EXCLUDED.fat_p90_brl,
    fonte = EXCLUDED.fonte,
    updated_at = now()
"""

# Duas sentencas, e nao uma com CASE: a da praca resolve o slug em UUID pelo
# `JOIN sites`, e a da rede grava `site_id` NULL. Misturar as duas num unico SQL
# esconderia justamente a diferenca que importa.
_UPSERT_PRACA = text(
    f"""
    INSERT INTO site_forecasts (id, site_id, {_COMUNS})
    SELECT :id, s.id, {_VALORES}
    FROM sites s WHERE s.slug = :slug
    ON CONFLICT (site_id, granularidade, bucket_inicio) DO UPDATE SET {_ATUALIZA}
    """
)

_UPSERT_REDE = text(
    f"""
    INSERT INTO site_forecasts (id, site_id, {_COMUNS})
    VALUES (:id, NULL, {_VALORES})
    ON CONFLICT (site_id, granularidade, bucket_inicio) DO UPDATE SET {_ATUALIZA}
    """
)


def _tarifa_por_praca(tarifas: pd.DataFrame, quando: pd.Timestamp) -> dict[str, float]:
    """A tarifa vigente de cada praca. Mesma regra de `predict._tarifa_vigente`."""
    t = tarifas.copy()
    t["vigencia_inicio"] = pd.to_datetime(t["vigencia_inicio"])
    t = t[t["vigencia_inicio"] <= quando].sort_values("vigencia_inicio")
    return t.groupby("location_id")["price_per_kwh"].last().astype(float).to_dict()


def _sem_o_primeiro_mes(linhas: list[dict]) -> list[dict]:
    """Tira o bucket mensal mais proximo: ele pertence a `exportar.py`.

    Sem isto, os dois jobs gravariam o mesmo `(site, 'mes', bucket)` e o ultimo a
    rodar venceria - trocando uma previsao de modelo por uma de regua, em silencio.

    SO' PARA PRACA. `exportar.py` percorre `sites`, logo nao escreve nada para a
    rede: aplicar o recorte lá deixava a rede SEM o mes+1, que e' justamente o
    bucket mensal que alguem olha primeiro. O buraco apareceu conferindo o banco
    depois da primeira execucao, nao em teste.
    """
    mensais = sorted(linha["bucket_inicio"] for linha in linhas if linha["granularidade"] == "mes")
    if not mensais:
        return linhas
    primeiro = mensais[0]
    return [
        linha
        for linha in linhas
        if not (linha["granularidade"] == "mes" and linha["bucket_inicio"] == primeiro)
    ]


def _gravar(conexao, sentenca, linhas: list[dict], agora: datetime, slug: str | None) -> int:
    n = 0
    for linha in linhas:
        parametros = {
            "id": uuid.uuid4(),
            "gerado_em": agora,
            "granularidade": linha["granularidade"],
            "bucket_inicio": linha["bucket_inicio"],
            "competencia": linha["competencia"],
            "kwh_previsto": linha["kwh_previsto"],
            "kwh_p10": linha["kwh_p10"],
            "kwh_p90": linha["kwh_p90"],
            "fat_prev": linha.get("faturamento_previsto_brl"),
            "fat_p10": linha.get("fat_p10_brl"),
            "fat_p90": linha.get("fat_p90_brl"),
            "fonte": linha["fonte"],
        }
        if slug is not None:
            parametros["slug"] = slug
        conexao.execute(sentenca, parametros)
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="Previsao por janela, praca e rede")
    ap.add_argument("--ate", help="ultimo dia do historico (AAAA-MM-DD). Padrao: ontem")
    args = ap.parse_args()
    # Ontem, e nao hoje: o dia corrente esta' pela metade, e usa-lo como ultimo
    # ponto da serie poria um dia incompleto dentro do historico das reguas.
    ate = date.fromisoformat(args.ate) if args.ate else date.today() - timedelta(days=1)

    engine = conectar()
    diario, estacoes, tarifas = carregar(engine, ate=ate)
    horario = painel_horario(engine, ate=ate)
    agora = datetime.now(UTC)
    precos = _tarifa_por_praca(tarifas, pd.Timestamp(ate))

    print(f"historico ate' {ate}")
    total = 0
    with engine.begin() as conexao:
        # ------------------------------------------------------------- a rede
        # Sem tarifa: a rede mistura pracas com precos diferentes, e um preco
        # medio ponderado seria um numero que nao existe em contrato nenhum. O
        # faturamento da rede e' a soma do faturamento das pracas, e quem soma e'
        # a tela - nao este job.
        linhas = todas_as_janelas(
            serie(na_rede(horario)),
            serie(na_rede(diario.rename(columns={"date": "bucket"}))),
            tarifa=None,
        )
        n = _gravar(conexao, _UPSERT_REDE, linhas, agora, None)
        total += n
        print(f"  rede                          {n:5d} linha(s)")

        # ------------------------------------------------------------ pracas
        for slug in sorted(estacoes["location_id"].astype(str)):
            uma_h = horario[horario["location_id"] == slug]
            uma_d = diario[diario["location_id"] == slug].rename(columns={"date": "bucket"})
            if uma_h.empty or uma_d.empty:
                print(f"  {slug:<30}    - sem historico no painel")
                continue
            linhas = _sem_o_primeiro_mes(
                todas_as_janelas(serie(uma_h), serie(uma_d), precos.get(slug))
            )
            n = _gravar(conexao, _UPSERT_PRACA, linhas, agora, slug)
            total += n
            print(f"  {slug:<30}{n:5d} linha(s)")

    print(f"\n{total} linha(s) gravada(s).")
    print(
        "A janela mensal mais proxima NAO esta' aqui: ela e' do `exportar.py`, que a\n"
        "tira do modelo quando o portao aprova. O modelo preve' um mes a frente, e\n"
        "nao doze - os meses seguintes saem de regua, e `fonte` diz isso."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
