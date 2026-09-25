"""A faixa p10-p90, com cobertura medida em vez de prometida.

O DEFEITO. A faixa saia de dois `LGBMRegressor(objective="quantile")`, um por
ponta. Cobertura nao e' propriedade garantida dessa perda: com regularizacao,
arvores de menos ou alvo assimetrico os quantis encolhem para o centro. E foi o
que aconteceu - a faixa cobria 64,8% e anunciava 80%.

E nao era ruido. Medido mes a mes, 12 de 12 meses ficaram abaixo de 75%:

    61,4  70,5  59,0  62,2  62,7  68,4  56,2  68,6  73,7  67,1  64,5  63,1

Doze de doze abaixo do declarado e' vies, nao azar. A tela mostrava os dois
numeros lado a lado - o que era o certo a fazer - mas mostrar a divergencia nao
e' o mesmo que nao ter a divergencia.

A CORRECAO: CONFORME MULTIPLICATIVA. Pega os residuos `real / previsto` de meses
que o modelo nao viu, tira os percentis 10 e 90 deles, e a faixa passa a ser
`previsto x f10` .. `previsto x f90`. Cobertura deixa de depender do que a perda
promete e passa a ser propriedade do conjunto de calibracao.

Resultado medido, mesmos 12 meses: 80,0% no agregado, entre 75,6% e 86,2% mes a
mes. O criterio do plano era 75-85%, e 11 dos 12 meses caem dentro.

O PRECO, dito junto: a faixa fica MAIS LARGA - 113% do previsto contra 87,7% da
anterior. Uma faixa honesta de 80% e' mais larga que uma faixa que mente 80% e
entrega 65%, e a largura e' a informacao que estava sendo sonegada.

MULTIPLICATIVA, E NAO ADITIVA. As pracas tem portes muito diferentes: 30 kWh de
residuo e' quase nada numa rodovia e e' o dia inteiro num condominio. Um residuo
em kWh nao se agrupa entre elas; a RAZAO se agrupa - o mesmo motivo pelo qual o
alvo do pipeline e' razao.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

QUANTIS = (0.10, 0.90)

# O que a faixa promete conter, em pontos percentuais. Nao e' opiniao: e' a
# distancia entre os dois quantis acima.
COBERTURA_DECLARADA = (QUANTIS[1] - QUANTIS[0]) * 100

# Minimo de residuos para estimar os percentis 10 e 90. Com 30, cada cauda tem 3
# observacoes - o percentil e' grosseiro mas existe. Abaixo disso o certo e' nao
# ter faixa, e a coluna fica nula: a migracao 0028 permite `kwh_p10 IS NULL` e a
# tela ja' sabe esconder a faixa ausente.
MINIMO_DE_RESIDUOS = 30


def residuos(real: pd.Series | np.ndarray, previsto: pd.Series | np.ndarray) -> pd.Series:
    """`real / previsto`, sem os casos que nao dizem nada.

    Previsto zero sai: a razao seria infinita, e um zero previsto nao tem faixa
    multiplicativa nenhuma - zero vezes qualquer fator continua zero. Um infinito
    que ficasse levaria o percentil 90 com ele, e a faixa cobriria tudo: cobertura
    de 100% que nao informa nada.

    O filtro de infinito faz esse trabalho sozinho. Havia aqui tambem um
    `.replace(0, np.nan)` no denominador, e o teste de mutacao mostrou que ele era
    redundante - reverte-lo nao quebrava nada, porque `x/0` ja' vem como infinito e
    `0/0` ja' vem como NaN. Duas defesas para o mesmo caso davam a impressao de
    cobrir coisas diferentes.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        r = pd.Series(np.asarray(real, float) / np.asarray(previsto, float))
    return r.replace([np.inf, -np.inf], np.nan).dropna()


def fatores_conformes(
    res: pd.Series, quantis: tuple[float, float] = QUANTIS
) -> tuple[float, float] | None:
    """Os dois fatores da faixa, ou `None` se ha' residuos de menos.

    Devolver `None` em vez de um par qualquer e' o que faz a ausencia de faixa
    ser uma decisao visivel, em vez de uma faixa estreita inventada com cinco
    pontos.
    """
    if len(res) < MINIMO_DE_RESIDUOS:
        return None
    f10, f90 = float(res.quantile(quantis[0])), float(res.quantile(quantis[1]))
    # Havia aqui um `f10 = max(f10, 0.0)`, e o teste de mutacao mostrou que ele era
    # INALCANCAVEL: o residuo e' `real / previsto` com energia entregue nunca
    # negativa e previsto positivo, entao nenhum residuo pode ser negativo e nenhum
    # percentil deles tambem. Codigo que finge proteger de algo impossivel faz o
    # leitor procurar o caso que o motivou, e nao existe caso.
    #
    # `f90 > f10` FICA, e esse e' alcancavel: uma serie quase toda constante da' os
    # dois percentis iguais, e uma faixa de largura zero cobriria 0% anunciando 80%.
    if not (f90 > f10):
        return None
    return f10, f90


def aplicar_faixa(
    previsto: pd.Series | np.ndarray, fatores: tuple[float, float] | None
) -> tuple[np.ndarray, np.ndarray]:
    """`previsto` -> (p10, p90). Sem fatores, devolve duas colunas de NaN.

    NaN e nao `None`: o resultado vira coluna de DataFrame, e `None` produziria
    uma coluna de objetos em que `>=` compara errado calado. `cobertura` sabe
    ignorar NaN, e `exportar.py` grava NULL - que a migracao 0028 permite.
    """
    p = np.asarray(previsto, float)
    if fatores is None:
        vazio = np.full(p.shape, np.nan)
        return vazio, vazio.copy()
    return p * fatores[0], p * fatores[1]


def cobertura(
    real: pd.Series | np.ndarray,
    p10: pd.Series | np.ndarray | None,
    p90: pd.Series | np.ndarray | None,
) -> float | None:
    """Fracao dos reais dentro da faixa, em pontos percentuais.

    E' o numero que a tela mostra ao lado do declarado.

    Conta so' as linhas QUE TEM faixa. As sem faixa sao NaN, e `real >= NaN` e'
    False - contadas, elas entrariam como "caiu fora" e a cobertura diria que a
    faixa erra sempre em vez de que ela nao existe ali. Sem nenhuma linha com
    faixa, devolve `None`, pelo mesmo motivo.
    """
    if p10 is None or p90 is None:
        return None
    y = np.asarray(real, float)
    lo, hi = np.asarray(p10, float), np.asarray(p90, float)
    tem = ~(np.isnan(lo) | np.isnan(hi) | np.isnan(y))
    if not tem.any():
        return None
    return float(((y[tem] >= lo[tem]) & (y[tem] <= hi[tem])).mean() * 100)
