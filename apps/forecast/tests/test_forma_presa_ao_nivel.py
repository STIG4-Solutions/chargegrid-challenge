"""A forma nao pode mexer no nivel do mes.

O DEFEITO QUE ISTO PRENDE. O total do mes e' a soma de trinta razoes previstas.
Se a MEDIA dessas razoes desvia de 1,0, o nivel do mes inteiro anda, e o erro de
FORMA vira erro de NIVEL. Medido: o modelo normalizado pela regua de ano-a-ano,
que sozinha faz 8,67% no mes, PIORAVA para 12,20% - ele estragava o nivel que
recebeu pronto, enquanto melhorava o eixo diario, o que tornava o problema
invisivel em qualquer metrica isolada.

O teste central e' o primeiro: a soma das previsoes de uma praca-mes tem de ser
exatamente `nivel x dias`, seja qual for a razao que o modelo devolva. Tirar a
divisao pela media faz esse assert cair.

    docker compose --profile forecast run --rm forecast python -m pytest tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from modelo.forma import BUCKET, prender_ao_nivel  # noqa: E402


def _quadro(nivel=10.0, dias=30, pracas=("a", "b")) -> pd.DataFrame:
    linhas = [
        {"location_id": praca, "mes_alvo": pd.Timestamp("2026-02-01"), "nivel_ano": nivel}
        for praca in pracas
        for _ in range(dias)
    ]
    return pd.DataFrame(linhas)


def test_a_soma_do_mes_e_exatamente_nivel_vezes_dias():
    """O assert que fecha a fuga. Razao enviesada para cima, soma intocada."""
    df = _quadro(nivel=10.0, dias=30, pracas=("a",))
    # Uma razao com media 2,0: solta, ela DOBRARIA o total do mes.
    razao = np.full(len(df), 2.0)
    yhat = prender_ao_nivel(df, razao)
    assert np.isclose(yhat.sum(), 10.0 * 30), yhat.sum()


def test_a_forma_relativa_sobrevive():
    """Prender o nivel nao pode achatar a curva - se achatasse, nao haveria modelo.

    Uma razao que vale 3 num dia e 1 nos outros tem de continuar valendo 3 vezes
    mais que os outros depois de presa.
    """
    df = _quadro(nivel=10.0, dias=4, pracas=("a",))
    razao = np.array([3.0, 1.0, 1.0, 1.0])
    yhat = prender_ao_nivel(df, razao)
    assert np.isclose(yhat[0] / yhat[1], 3.0)
    assert np.isclose(yhat.sum(), 40.0)


def test_cada_praca_tem_o_seu_proprio_nivel():
    """A media e' por PRACA e mes, e nao da rede.

    Normalizar pela media da rede deixaria o modelo mover o nivel de uma praca
    contra a outra: uma ficaria com o total da vizinha. Aqui as duas tem razoes
    de escalas diferentes e cada soma tem de dar o proprio nivel.
    """
    assert BUCKET == ["location_id", "mes_alvo"]
    df = _quadro(nivel=10.0, dias=10, pracas=("a", "b"))
    razao = np.concatenate([np.full(10, 0.2), np.full(10, 9.0)])
    df["yhat"] = prender_ao_nivel(df, razao)
    for _, g in df.groupby("location_id"):
        assert np.isclose(g["yhat"].sum(), 100.0), g["yhat"].sum()


def test_meses_diferentes_nao_se_misturam():
    """A chave inclui o mes: dois meses do mesmo local sao buckets separados."""
    df = _quadro(nivel=10.0, dias=5, pracas=("a",))
    outro = df.copy()
    outro["mes_alvo"] = pd.Timestamp("2026-03-01")
    outro["nivel_ano"] = 40.0
    junto = pd.concat([df, outro], ignore_index=True)
    junto["yhat"] = prender_ao_nivel(junto, np.full(len(junto), 1.7))
    totais = junto.groupby("mes_alvo")["yhat"].sum().to_dict()
    assert np.isclose(totais[pd.Timestamp("2026-02-01")], 50.0)
    assert np.isclose(totais[pd.Timestamp("2026-03-01")], 200.0)


def test_razao_toda_zero_devolve_o_nivel_e_nao_zero():
    """Gravar consumo nulo num mes inteiro por causa de uma divisao seria pior.

    Media zero faz a divisao dar NaN; o fallback e' razao 1,0, que devolve a
    regua. Sem ele o card mostraria zero kWh numa praca com movimento.
    """
    df = _quadro(nivel=12.0, dias=6, pracas=("a",))
    yhat = prender_ao_nivel(df, np.zeros(len(df)))
    assert np.isclose(yhat.sum(), 12.0 * 6), yhat.sum()
    assert (yhat > 0).all()


def test_razao_negativa_nao_produz_consumo_negativo():
    """O `clip` em zero: um modelo de arvore pode extrapolar para baixo de zero,
    e energia entregue negativa nao existe."""
    df = _quadro(nivel=10.0, dias=4, pracas=("a",))
    yhat = prender_ao_nivel(df, np.array([-5.0, 1.0, 1.0, 1.0]))
    assert (yhat >= 0).all(), yhat
