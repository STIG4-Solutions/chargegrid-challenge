"""As reguas: o numero que se consegue SEM modelo, para cada janela.

Uma regua existe para que o erro do modelo tenha com o que ser comparado. Um
WAPE sozinho nao diz nada - 25,9% pode ser otimo ou pessimo, e nada no artefato
decide qual. Foi medindo contra a regua certa que se descobriu que as 700
arvores empatavam com uma das proprias features.

PASSADO ESTRITO em todas. A previsao de um bucket usa so' buckets ANTERIORES a
ele, que e' a mesma regra do walk-forward do pipeline. Sem isso a regua venceria
o modelo por trapaca, e a comparacao nao significaria nada - foi o erro de uma
primeira medicao desta sessao, cujo "oraculo" usava a media dos dois anos e saiu
pior que a regua simples por ser cego ao crescimento.

Funcoes puras sobre pandas: sem banco e sem LightGBM. E' o que permite
testa-las - e mutar-lhes o miolo para provar que os testes pegam.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _minimo(janelas: int, pedido: int | None) -> int:
    """Quantos buckets bastam para a regua se pronunciar.

    Metade da janela por padrao. Exigir a janela cheia deixaria os primeiros
    meses da serie sem regua nenhuma, e sao justamente os meses em que a
    estacao e' nova - o caso que mais precisa de comparacao.
    """
    return pedido if pedido is not None else max(1, janelas // 2)


def media_movel(s: pd.Series, janelas: int = 28, minimo: int | None = None) -> pd.Series:
    """A media dos `janelas` buckets anteriores. A regua de sempre.

    E' a que o portao de `exportar.py` usa. Cega a dia da semana e a mes do ano:
    olha um bloco recente e assume que o proximo bucket se parece com ele.
    """
    return s.shift(1).rolling(janelas, min_periods=_minimo(janelas, minimo)).mean()


def _por_grupo(s: pd.Series, chave, janelas: int, minimo: int) -> pd.Series:
    """Media movel DENTRO de cada grupo do calendario.

    O `shift(1)` acontece por grupo, nao na serie inteira: o que precede um
    sabado, para esta regua, e' o sabado anterior - nao a sexta.
    """
    g = pd.Series(list(chave), index=s.index)
    return s.groupby(g, observed=True).transform(
        lambda x: x.shift(1).rolling(janelas, min_periods=minimo).mean()
    )


def por_dia_da_semana(s: pd.Series, semanas: int = 8, minimo: int = 2) -> pd.Series:
    """A media do MESMO dia da semana nas `semanas` anteriores.

    Numa serie diaria, oito linhas dentro do grupo "segunda" sao oito segundas.

    E' a regua que mais importa e a que faltava: no eixo diario ela empata com o
    modelo de 700 arvores, porque `hist_dow` ja' era feature dele. E no eixo
    SEMANAL ela e' identica a media movel por aritmetica - toda semana tem uma
    segunda, uma terca e assim por diante, logo o efeito do dia da semana cancela
    exatamente na soma. Nao ha o que ganhar ali, e isso e' resultado, nao falha.
    """
    return _por_grupo(s, s.index.dayofweek, semanas, minimo)


def por_dow_e_hora(s: pd.Series, semanas: int = 8, minimo: int = 2) -> pd.Series:
    """A media da MESMA hora do MESMO dia da semana, nas `semanas` anteriores.

    A regua da janela de uma hora. Precisa das duas chaves: o perfil do dia
    (vale 0,4% as 5h e 7,5% as 20h) e o do dia da semana se multiplicam, e uma
    regua que enxergue so' uma das duas erra a outra inteira.
    """
    # `strict`: as duas vem do MESMO indice, logo tem o mesmo comprimento. Se um
    # dia deixarem de ter, o erro aparece aqui em vez de truncar a chave em
    # silencio e desalinhar a regua inteira.
    chave = zip(s.index.dayofweek, s.index.hour, strict=True)
    return _por_grupo(s, chave, semanas, minimo)


def tendencia(s: pd.Series, janelas: int = 24, minimo: int = 8) -> pd.Series:
    """Projeta um passo a frente por reta no LOG dos buckets anteriores.

    A regua da janela de um ano, e a unica que extrapola. No log porque o
    crescimento da frota e' multiplicativo: +38% ao ano nao e' "mais N kWh por
    mes", e ajustar reta no nivel subestimaria o fim da serie.

    Bucket vazio ou negativo sai do ajuste em vez de virar `-inf`. Um mes sem
    nenhuma recarga e' possivel numa praca pequena, e nao deve derrubar a regua
    inteira da praca.
    """

    def projeta(x: pd.Series) -> float:
        y = x.to_numpy(dtype=float)
        bons = np.isfinite(y) & (y > 0)
        if bons.sum() < 2:
            # Sem dois pontos positivos nao ha reta. A media do que houver e' o
            # que resta - e nao zero, que afirmaria ausencia de demanda.
            return float(np.nanmean(y)) if np.isfinite(y).any() else np.nan
        t = np.arange(len(y), dtype=float)[bons]
        inclinacao, intercepto = np.polyfit(t, np.log(y[bons]), 1)
        return float(np.exp(intercepto + inclinacao * len(y)))

    return s.shift(1).rolling(janelas, min_periods=minimo).apply(projeta, raw=False)


# As reguas de cada janela, em ordem de dificuldade. O portao tem de bater a
# MELHOR delas, nao a mais conveniente - foi por comparar so' com a media movel
# que `hist_dow` passou anos batendo o que ia para producao sem ninguem ver.
REGUAS_POR_JANELA: dict[str, tuple[str, ...]] = {
    "hora": ("media_movel", "por_dow_e_hora"),
    "dia": ("media_movel", "por_dia_da_semana"),
    # Sem `por_dia_da_semana`: na soma semanal ela E' a media movel.
    "semana": ("media_movel", "tendencia"),
    "mes": ("media_movel", "por_dia_da_semana", "tendencia"),
    "ano": ("media_movel", "tendencia"),
}
