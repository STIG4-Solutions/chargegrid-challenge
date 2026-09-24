"""Produz as linhas de `site_forecasts` para as cinco janelas.

QUEM SERVE CADA JANELA, e a razao e' medida - `medir_janelas.py` produz a tabela:

  janela   quem serve                    folga da regua ao ruido
  hora     regua dow x hora, com FAIXA   -0,05 ponto  (regua no piso)
  dia      regua por dia da semana       +0,30
  semana   media movel                   +0,84
  mes      o MODELO                      +3,38  <- o unico com espaco
  ano      extrapolacao de tendencia     n=2, nao mensuravel

Folga e' a distancia entre a melhor regua e uma referencia que usa o futuro de
proposito. Onde ela e' perto de zero, nenhum modelo pode ganhar: o erro que sobra
e' ruido de contagem. Foi por isso que quatro das cinco janelas servem regua, e
`fonte` diz qual em cada linha - a tela nunca chama de previsao um numero que veio
de uma media.

A FAIXA da janela horaria nao e' enfeite. Ali o erro pontual e' ~50% com a melhor
regua e ~50% com a referencia que enxerga o futuro: o numero honesto nao e' um
ponto. A banda sai da dispersao observada do mesmo (dia da semana, hora), e o
aceite dela e' COBERTURA, nao WAPE.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from janelas import reguas
from janelas.painel import PERIODO_DA_JANELA, reamostrar

# Quem serve cada janela, e com que nome isso vai para a coluna `fonte`.
# `modelo` e' decidido em tempo de execucao: o portao pode recusa-lo.
SERVIDOR = {
    "hora": ("por_dow_e_hora", "perfil_hora"),
    "dia": ("por_dia_da_semana", "media_dow"),
    "semana": ("media_movel", "media_movel"),
    "mes": ("por_dia_da_semana", "media_dow"),
    "ano": ("tendencia", "tendencia"),
}

# Quantos buckets adiante gravar, por janela. Alinhado com o padrao que a rota
# devolve: nao faz sentido gravar 500 horas que ninguem le'.
HORIZONTE = {"hora": 24 * 14, "dia": 60, "semana": 16, "mes": 12, "ano": 3}

# A faixa da janela horaria, em quantis da dispersao observada.
QUANTIL_BAIXO, QUANTIL_ALTO = 0.10, 0.90

# Quantas semanas de historico a banda observa. Oito e' o mesmo numero das
# reguas: menos que isso e a dispersao de uma celula vira ruido dela mesma.
SEMANAS_DA_BANDA = 8


def _alvos(ultimo: pd.Timestamp, janela: str, quantos: int) -> pd.DatetimeIndex:
    """Os buckets da FONTE que compoem os proximos `quantos` buckets da janela.

    Para a janela mensal isso e' um dia por linha, porque o previsor trabalha no
    grao diario e a soma vira o mes - exatamente como `predict.prever` faz.
    """
    passo = pd.Timedelta(hours=1) if janela == "hora" else pd.Timedelta(days=1)
    inicio = ultimo + passo
    fim = (pd.Period(inicio, freq=PERIODO_DA_JANELA[janela]) + (quantos - 1)).end_time
    return pd.date_range(inicio, fim, freq="h" if janela == "hora" else "D")


def _banda_horaria(passado: pd.Series, alvos: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series]:
    """p10 e p90 por (dia da semana, hora), da dispersao OBSERVADA.

    Nao vem de modelo: vem de olhar o que aquela celula fez nas ultimas semanas.
    E' o unico jeito honesto de por faixa num alvo dominado por ruido de contagem
    - e o aceite dela e' cobertura medida, nao erro medio.

    Celula sem historico recua para os quantis da serie inteira: uma faixa com
    buraco nao e' faixa, e o CHECK `banda_completa` no banco recusaria meia banda.
    """
    chave = pd.Series(
        list(zip(passado.index.dayofweek, passado.index.hour, strict=True)),
        index=passado.index,
    )
    janelas = SEMANAS_DA_BANDA
    baixo, alto = {}, {}
    for k, x in passado.groupby(chave, observed=True):
        recente = x.tail(janelas)
        if len(recente) >= 3:
            baixo[k] = float(recente.quantile(QUANTIL_BAIXO))
            alto[k] = float(recente.quantile(QUANTIL_ALTO))

    geral_baixo = float(passado.quantile(QUANTIL_BAIXO))
    geral_alto = float(passado.quantile(QUANTIL_ALTO))
    chaves = [(t.dayofweek, t.hour) for t in alvos]
    return (
        pd.Series([baixo.get(k, geral_baixo) for k in chaves], index=alvos, dtype=float),
        pd.Series([alto.get(k, geral_alto) for k in chaves], index=alvos, dtype=float),
    )


def _soma_na_janela(valores: pd.Series, janela: str) -> pd.Series:
    """Soma os buckets da fonte em buckets da janela, DESCARTANDO os parciais.

    Uma versao anterior nao descartava nada, sob o argumento de que "todo bucket
    e' futuro e completo por construcao". Falso, e um teste pegou: a serie
    terminava numa quarta e o primeiro bucket SEMANAL saia rotulado com a segunda
    anterior - uma data no PASSADO -, somando tres dias como se fosse semana
    cheia. `_alvos` comeca no meio do periodo corrente, sempre.

    Entao a regra e' a mesma do passado, e por isso reusa `painel.reamostrar`:
    bucket entra so' quando a extensao dele esta' inteira dentro dos alvos.
    """
    return reamostrar(valores, janela)


def linhas_da_janela(
    passado: pd.Series,
    janela: str,
    tarifa: float | None,
    previsao_do_modelo: pd.Series | None = None,
) -> list[dict]:
    """Uma linha por bucket futuro desta janela.

    `previsao_do_modelo` e' o kWh DIARIO previsto pelo modelo, quando o portao o
    aprovou para esta janela. Passado `None`, serve a regua declarada em
    `SERVIDOR` - que e' o caso de quatro das cinco janelas, por medicao.
    """
    if passado.empty:
        return []
    quantos = HORIZONTE[janela]
    alvos = _alvos(passado.index.max(), janela, quantos)

    if previsao_do_modelo is not None:
        por_bucket = previsao_do_modelo.reindex(alvos).ffill()
        fonte = "modelo"
    else:
        nome, fonte = SERVIDOR[janela]
        por_bucket = reguas.prever(nome, passado, alvos)

    # Nunca negativo: uma praca nao devolve energia. O CHECK do banco tambem
    # recusaria, e falhar aqui com numero errado seria pior que corrigir.
    por_bucket = por_bucket.clip(lower=0.0)
    kwh = _soma_na_janela(por_bucket, janela)

    p10 = p90 = None
    if janela == "hora":
        baixo, alto = _banda_horaria(passado, alvos)
        p10 = _soma_na_janela(baixo.clip(lower=0.0), janela)
        p90 = _soma_na_janela(alto.clip(lower=0.0), janela)

    linhas = []
    for bucket, valor in kwh.items():
        if not np.isfinite(valor):
            continue
        linha = {
            "granularidade": janela,
            "bucket_inicio": bucket.to_pydatetime(),
            # `competencia` fica sendo o primeiro dia do mes do bucket: a coluna
            # e' antiga e continua servindo a rota mensal.
            "competencia": bucket.to_period("M").to_timestamp().date(),
            "kwh_previsto": round(float(valor), 3),
            "fonte": fonte,
            "kwh_p10": None,
            "kwh_p90": None,
        }
        if p10 is not None and bucket in p10.index and bucket in p90.index:
            b, a = float(p10.loc[bucket]), float(p90.loc[bucket])
            if np.isfinite(b) and np.isfinite(a) and a >= b:
                linha["kwh_p10"] = round(b, 3)
                linha["kwh_p90"] = round(a, 3)
        # Faturamento e' kWh x tarifa vigente, DEPOIS da agregacao - tarifa nunca
        # foi feature do modelo, e um reajuste de preco nao pode invalidar nada.
        if tarifa is not None:
            linha["faturamento_previsto_brl"] = round(linha["kwh_previsto"] * tarifa, 2)
            for de, para in (("kwh_p10", "fat_p10_brl"), ("kwh_p90", "fat_p90_brl")):
                linha[para] = None if linha[de] is None else round(linha[de] * tarifa, 2)
        linhas.append(linha)
    return linhas


def todas_as_janelas(
    passado_horario: pd.Series,
    passado_diario: pd.Series,
    tarifa: float | None,
    modelo_mensal: pd.Series | None = None,
) -> list[dict]:
    """As cinco janelas de um escopo. A hora vem do grao horario."""
    saida = []
    saida.extend(linhas_da_janela(passado_horario, "hora", tarifa))
    for janela in ("dia", "semana", "ano"):
        saida.extend(linhas_da_janela(passado_diario, janela, tarifa))
    saida.extend(linhas_da_janela(passado_diario, "mes", tarifa, modelo_mensal))
    return saida


__all__ = ["HORIZONTE", "SERVIDOR", "linhas_da_janela", "todas_as_janelas"]
