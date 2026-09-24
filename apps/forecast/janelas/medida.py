"""Quanta FOLGA cada janela tem para um modelo ocupar.

Uma janela so' merece modelo se houver distancia entre a melhor regua e o ruido
irredutivel. Onde a regua ja' esta' no limite do dado, nenhum modelo pode ganhar
- e medir isso ANTES de treinar cinco modelos e' a unica razao de este modulo
existir.

WALK-FORWARD DE VERDADE, uma origem por bucket alvo. A primeira versao disto
calculava a regua no grao diario e somava, o que dava a cada dia do mes o direito
de ver o dia anterior: `media_movel` no mes saia 4,33% quando o backtest do
pipeline mede 15,38% para a mesma regua. Era vazamento, e fazia toda janela
agregada parecer facil. Aqui a origem e' o ultimo bucket ANTES do alvo comecar, e
o horizonte vai de 1 ate o tamanho da janela - como em producao.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from janelas import reguas
from janelas.painel import PERIODO_DA_JANELA
from pipeline.train import wape


def referencia_centrada(s: pd.Series, semanas: int = 4) -> pd.Series:
    """O melhor que se poderia saber sobre a media LOCAL. TRAPACEIA de proposito.

    Media do mesmo (dia da semana, hora) numa janela CENTRADA de +-`semanas`, sem
    o proprio ponto. Usa o futuro, logo nenhuma previsao honesta chega aqui.

    NAO E' LIMITE INFERIOR numa janela agregada, e isso importa: ela e' um
    estimador local cego a tendencia, e no total mensal uma regua de tendencia a
    bate. Ela vale como piso de RUIDO no grao da fonte - hora e dia -, onde o que
    sobra abaixo dela e' contagem aleatoria e nao erro de modelo.

    Centrada e nao expansiva porque a rede cresce ~38% ao ano: a media dos quatro
    anos inteiros seria cega ao crescimento e sairia PIOR que a regua simples -
    foi o primeiro "oraculo" desta sessao, 83% contra 72% da regua.
    """
    horario = len(s) > 1 and (s.index[1] - s.index[0]) < pd.Timedelta("1D")
    chave = (
        pd.Series(list(zip(s.index.dayofweek, s.index.hour, strict=True)), index=s.index)
        if horario
        else pd.Series(s.index.dayofweek, index=s.index)
    )
    largura = 2 * semanas + 1

    def sem_o_proprio(x: pd.Series) -> pd.Series:
        soma = x.rolling(largura, center=True, min_periods=3).sum()
        n = x.rolling(largura, center=True, min_periods=3).count()
        # Com um unico vizinho nao ha media possivel: a referencia se cala em vez
        # de devolver o proprio valor e fingir erro zero.
        return (soma - x) / (n - 1).where(n > 1)

    return s.groupby(chave, observed=True).transform(sem_o_proprio)


def _buckets_completos(s: pd.Series, janela: str) -> list:
    """Os periodos da janela inteiramente cobertos pela serie.

    Bucket parcial fica fora: um mes pela metade contra a previsao do mes inteiro
    infla o erro de todos, e foi assim que setembro deu +98% numa medicao desta
    sessao.
    """
    periodos = s.index.to_period(PERIODO_DA_JANELA[janela])
    inicio, fim = s.index.min(), s.index.max()
    passo = (s.index[1] - s.index[0]) if len(s) > 1 else pd.Timedelta(0)
    vistos = periodos.unique()
    return [p for p in vistos if p.start_time >= inicio and p.end_time < fim + passo]


def medir(s: pd.Series, janela: str, minimo_de_passado: int = 180) -> dict:
    """Erro de cada regua da janela, com uma origem por bucket alvo.

    `minimo_de_passado` em buckets da FONTE: sem historico suficiente a regua nao
    se pronuncia, e o bucket sai da conta em vez de entrar com um numero ruim que
    depois seria lido como erro do metodo.
    """
    nomes = reguas.REGUAS_POR_JANELA[janela]
    periodos = _buckets_completos(s, janela)
    if not periodos:
        return {"janela": janela, "n_obs": 0, "aviso": "nenhum bucket completo na serie"}
    ref = referencia_centrada(s)

    # UM bucket da fonte por bucket da janela? Entao a forma ROLANTE ja' e' a
    # honesta: a origem de cada alvo e' o bucket imediatamente anterior, que e'
    # exatamente uma previsao de um passo a frente. E e' vetorizada - o laco
    # abaixo em 34 mil horas e' O(n^2) e nao termina em tempo util.
    primeiro = periodos[0]
    por_bucket = int(((s.index >= primeiro.start_time) & (s.index <= primeiro.end_time)).sum())

    if por_bucket == 1:
        colunas = {nome: getattr(reguas, nome)(s) for nome in nomes}
        t = pd.DataFrame({"real": s, "referencia": ref, **colunas})
        # Mesmo corte de aquecimento das janelas grossas, para que os numeros das
        # cinco linhas da tabela sejam comparaveis entre si.
        t = t.iloc[minimo_de_passado:].dropna()
        t = t[t["real"] > 0]
        t.insert(0, "bucket", t.index)
    else:
        linhas = []
        for p in periodos:
            dentro = s.index[(s.index >= p.start_time) & (s.index <= p.end_time)]
            passado = s.loc[s.index < p.start_time]
            if len(passado) < minimo_de_passado or not len(dentro):
                continue
            real = float(s.loc[dentro].sum())
            if not np.isfinite(real) or real <= 0:
                continue
            linha = {"bucket": p.start_time, "real": real}
            for nome in nomes:
                linha[nome] = float(reguas.prever(nome, passado, dentro).sum())
            centrada = ref.loc[dentro]
            linha["referencia"] = float(centrada.sum()) if centrada.notna().all() else np.nan
            linhas.append(linha)
        if not linhas:
            return {
                "janela": janela,
                "n_obs": 0,
                "aviso": "nenhum bucket com passado bastante",
            }
        t = pd.DataFrame(linhas)

    t = t.dropna(axis=1, how="any").dropna()
    if t.empty:
        return {"janela": janela, "n_obs": 0, "aviso": "nenhum bucket sobreviveu ao corte"}
    erros = {c: round(wape(t["real"], t[c]), 2) for c in t.columns if c not in ("bucket", "real")}
    candidatas = {k: v for k, v in erros.items() if k != "referencia"}
    melhor = min((v, k) for k, v in candidatas.items())

    saida = {
        "janela": janela,
        "n_obs": int(len(t)),
        "reguas": candidatas,
        "melhor_regua": melhor[1],
        "erro_da_melhor": melhor[0],
    }
    if "referencia" in erros:
        saida["referencia"] = erros["referencia"]
        # Distancia entre a melhor regua e a referencia centrada. Vale como
        # folga so' no grao da fonte; ver a docstring de `referencia_centrada`.
        saida["folga"] = round(melhor[0] - erros["referencia"], 2)
    return saida


def tabela(serie_horaria: pd.Series, serie_diaria: pd.Series) -> list[dict]:
    """As cinco janelas. A hora vem do grao horario; as outras, do diario."""
    fonte = {"hora": (serie_horaria, 24 * 60)}
    for j in ("dia", "semana", "mes", "ano"):
        fonte[j] = (serie_diaria, 180)
    return [medir(s, j, minimo) for j, (s, minimo) in fonte.items()]


def imprimir(linhas: list[dict], titulo: str) -> None:
    print(f"\n{titulo}")
    print(f"  {'janela':<8}{'n':>5}{'melhor regua':>20}{'erro':>9}{'ref.centrada':>14}{'folga':>8}")
    print("  " + "-" * 64)
    for d in linhas:
        if d.get("aviso"):
            print(f"  {d['janela']:<8}{d['n_obs']:>5}   {d['aviso']}")
            continue
        ref = d.get("referencia")
        folga = d.get("folga")
        cauda = f"{ref:>13.2f}%{folga:>+8.2f}" if ref is not None else f"{'-':>13}{'-':>8}"
        print(
            f"  {d['janela']:<8}{d['n_obs']:>5}{d['melhor_regua']:>20}"
            f"{d['erro_da_melhor']:>8.2f}%{cauda}"
        )
    print("\n  todas as reguas:")
    for d in linhas:
        if d.get("aviso"):
            continue
        detalhe = "   ".join(f"{k} {v:.2f}%" for k, v in sorted(d["reguas"].items()))
        print(f"    {d['janela']:<8}{detalhe}")


__all__ = ["imprimir", "medir", "referencia_centrada", "tabela"]
