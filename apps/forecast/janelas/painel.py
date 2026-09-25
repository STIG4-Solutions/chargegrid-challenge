"""O painel nos dois graos (hora e dia) e nos dois escopos (rede e praca).

`banco.py` da' o painel DIARIO por praca, e joga a hora fora num `::date`. A
hora existe na origem - `charging_sessions.started_at` e' timestamp -, e e' o
grao que a janela de uma hora precisa.

POR QUE A REDE E NAO SO' A PRACA. Medido no banco: a celula hora x praca tem 20%
de ocupacao e 1,26 sessao quando ocupada; a celula da REDE tem 54%, e no plato
diurno (10h as 23h) sobe para 67-79% dos dias. Prever a hora de uma praca e'
prever se um carro especifico aparece, o que e' ruido. Prever a hora da rede
nao e'.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import text

# Mesmo recorte do `_SESSOES` de `banco.py` - `state = 'BILLED'`, fatura nao
# anulada - trocando o `::date` por `date_trunc('hour', ...)`. O fuso continua
# aplicado ANTES do truncamento, e nao por preciosismo: contar na hora errada
# desloca o perfil do dia inteiro, e o perfil do dia e' o sinal desta janela.
_SESSOES_POR_HORA = text(
    """
    SELECT s.slug                                                   AS location_id,
           date_trunc('hour', cs.started_at AT TIME ZONE s.timezone) AS bucket,
           sum(cs.energy_kwh)                                        AS kwh,
           count(*)::float                                           AS sessions,
           coalesce(sum(i.total), 0)                                 AS revenue
    FROM charging_sessions cs
    JOIN sites s ON s.id = cs.site_id
    LEFT JOIN invoices i ON i.session_id = cs.id AND i.status <> 'VOID'
    WHERE cs.started_at IS NOT NULL
      AND cs.state = 'BILLED'
    GROUP BY 1, 2
    -- Ordena pela mesma razao do `banco._SESSOES`: ordem sem `ORDER BY` sai do
    -- plano, e o plano muda com estatistica de tabela e paralelismo.
    ORDER BY 1, 2
    """
)

_NASCIMENTO = text(
    """
    SELECT s.slug                                      AS location_id,
           (s.created_at AT TIME ZONE s.timezone)      AS nascimento
    FROM sites s
    """
)


def painel_horario(engine, ate: date | None = None) -> pd.DataFrame:
    """Uma linha por (praca, hora), inclusive as horas sem recarga nenhuma.

    Hora sem sessao e' ZERO, nao ausencia - o mesmo motivo que
    `banco._grade_completa` documenta para o dia, e aqui ele pesa muito mais:
    sao 80% das celulas por praca. Omiti-las ensinaria uma demanda media muito
    maior que a real, e justamente nas horas de madrugada, que e' o que da'
    carater ao perfil do dia.
    """
    medido = pd.read_sql_query(_SESSOES_POR_HORA, engine)
    if medido.empty:
        raise SystemExit("nenhuma sessao faturada no banco - rode o seed antes")
    medido["location_id"] = medido["location_id"].astype("string")
    medido["bucket"] = pd.to_datetime(medido["bucket"])

    nasce = pd.read_sql_query(_NASCIMENTO, engine)
    nasce["location_id"] = nasce["location_id"].astype("string")
    nasce["nascimento"] = pd.to_datetime(nasce["nascimento"]).dt.floor("h")

    fim = pd.Timestamp(ate) + pd.Timedelta(hours=23) if ate else medido["bucket"].max()

    pedacos = []
    for _, linha in nasce.iterrows():
        inicio = linha["nascimento"]
        if inicio > fim:
            continue
        pedacos.append(
            pd.DataFrame(
                {
                    "location_id": linha["location_id"],
                    "bucket": pd.date_range(inicio, fim, freq="h"),
                }
            )
        )
    if not pedacos:
        raise SystemExit("nenhuma praca nasceu antes do corte pedido")

    grade = pd.concat(pedacos, ignore_index=True)
    grade["location_id"] = grade["location_id"].astype("string")
    painel = grade.merge(medido, on=["location_id", "bucket"], how="left")
    for coluna in ("kwh", "sessions", "revenue"):
        painel[coluna] = painel[coluna].astype("float64").fillna(0.0)
    return painel.sort_values(["location_id", "bucket"]).reset_index(drop=True)


def serie(painel: pd.DataFrame, coluna: str = "kwh", chave: str = "bucket") -> pd.Series:
    """A serie de UMA praca (ou da rede, se ja' agregada), indexada no tempo."""
    s = painel.set_index(chave)[coluna].astype(float)
    return s.sort_index()


def na_rede(painel: pd.DataFrame, chave: str = "bucket") -> pd.DataFrame:
    """Soma as pracas, bucket a bucket.

    A rede nao e' a media das pracas: e' a soma. Uma praca que abriu ontem
    contribui com o que ela vende, nao com um peso igual ao da maior.
    """
    colunas = [c for c in ("kwh", "sessions", "revenue") if c in painel.columns]
    return painel.groupby(chave, as_index=False)[colunas].sum().sort_values(chave)


# Como cada janela e' recortada do tempo, na notacao de `Period`. O rotulo do
# bucket sera' sempre o INICIO dele - `start_time` -, que e' o que `competencia`
# guarda no banco; rotular pelo fim faria a linha gravada dizer o mes errado.
PERIODO_DA_JANELA = {
    "hora": "h",
    "dia": "D",
    # `W-SUN` e' a semana que TERMINA no domingo, logo COMECA na segunda. A
    # notacao de `Period` ancora no fim, e `W-MON` daria semana de terca a
    # segunda - um teste pega isso, porque uma semana deslocada em um dia
    # embaralharia o efeito de dia da semana que a janela existe para cancelar.
    "semana": "W-SUN",
    "mes": "M",
    "ano": "Y",
}


def reamostrar(s: pd.Series, janela: str) -> pd.Series:
    """Soma a serie nos buckets da janela pedida, descartando os PARCIAIS.

    Um mes pela metade comparado contra a previsao do mes inteiro infla o erro de
    todo mundo - foi o que aconteceu numa primeira medicao desta sessao, com
    setembro dando +98% no modelo E na regua, e por isso `treinar.py` tem `--ate`.

    Completude se decide pela EXTENSAO do bucket, nunca por contagem de linhas:
    fevereiro tem 28 dias e janeiro 31, e um teste de "tem tantas linhas quanto o
    maior" descartaria todo fevereiro como se fosse mes partido.
    """
    if janela not in PERIODO_DA_JANELA:
        raise ValueError(f"janela desconhecida: {janela}")
    if s.empty:
        return s

    periodos = s.index.to_period(PERIODO_DA_JANELA[janela])
    somado = s.groupby(periodos).sum()

    inicio, fim = s.index.min(), s.index.max()
    # O passo da FONTE: o ultimo bucket da serie cobre daquele instante ate um
    # passo depois. Sem essa folga, um mes completo cujo ultimo registro e' as
    # 23h pareceria terminar antes da meia-noite e seria descartado.
    passo = (s.index[1] - s.index[0]) if len(s) > 1 else pd.Timedelta(0)

    completos = [p.start_time >= inicio and p.end_time < fim + passo for p in somado.index]
    somado = somado[completos]
    somado.index = pd.DatetimeIndex([p.start_time for p in somado.index])
    return somado
