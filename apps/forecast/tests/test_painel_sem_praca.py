"""O painel quando nenhuma praca alcanca o corte do treino.

Aconteceu em staging, na primeira execucao real do job: a unica praca abriu em
2026-09-03 e o corte padrao de `treinar.py` e' o ultimo dia do mes anterior -
2026-08-31. Toda praca foi descartada, a lista de pedacos ficou vazia, e
`pd.concat([])` levantou `ValueError: No objects to concatenate`.

Aquela mensagem nao diz nada a quem abre a execucao. Nao aponta o corte, nem a
idade da praca, nem o que fazer - e o passo seguinte do log era um traceback do
pandas. O que se testa aqui e' a MENSAGEM, porque e' ela que tem valor: o erro em
si e' inevitavel quando nao ha historico.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from datetime import date  # noqa: E402

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from banco import _grade_completa  # noqa: E402


def _estacoes(abertas_em: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "location_id": [f"praca-{i}" for i in range(len(abertas_em))],
            "opened_at": pd.to_datetime(abertas_em),
        }
    )


def _medido() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "location_id": pd.Series([], dtype="string"),
            "date": pd.Series([], dtype="datetime64[ns]"),
            "kwh": pd.Series([], dtype="float64"),
            "sessions": pd.Series([], dtype="float64"),
            "revenue": pd.Series([], dtype="float64"),
        }
    )


def test_praca_nascida_depois_do_corte_explica_o_que_aconteceu():
    """A regressao de staging, com as datas reais daquela corrida."""
    estacoes = _estacoes(["2026-09-03"])

    with pytest.raises(SystemExit) as erro:
        _grade_completa(estacoes, _medido(), date(2026, 8, 31))

    texto = str(erro.value)
    # O corte, para quem nao sabe qual e' o padrao.
    assert "2026-08-31" in texto
    # A idade da praca, que e' o dado que falta.
    assert "2026-09-03" in texto
    # A distancia, em dias, do lado certo do sinal.
    assert "3 dia(s) DEPOIS" in texto
    # E o que fazer.
    assert "--ate" in texto
    assert "150" in texto


def test_a_praca_mais_antiga_e_a_citada():
    """Com varias pracas novas, a mensagem cita a que chegou primeiro.

    Citar qualquer outra faria a distancia parecer maior do que e', e quem fosse
    ajustar `--ate` erraria o alvo.
    """
    estacoes = _estacoes(["2026-09-20", "2026-09-05", "2026-09-12"])

    with pytest.raises(SystemExit) as erro:
        _grade_completa(estacoes, _medido(), date(2026, 9, 1))

    texto = str(erro.value)
    assert "2026-09-05" in texto
    assert "2026-09-20" not in texto


def test_uma_praca_dentro_do_corte_basta_para_haver_painel():
    """Nao e' "todas ou nada": a que alcanca o corte entra, a nova fica fora.

    E' o caso normal de uma rede em crescimento, e ele NAO pode levantar.
    """
    estacoes = _estacoes(["2025-01-01", "2026-09-03"])

    painel = _grade_completa(estacoes, _medido(), date(2026, 8, 31))

    assert not painel.empty
    assert set(painel["location_id"]) == {"praca-0"}
    assert painel["date"].min() == pd.Timestamp("2025-01-01")
    assert painel["date"].max() == pd.Timestamp("2026-08-31")
    # Dia sem sessao e' ZERO, nao ausencia - a razao de a grade ser preenchida.
    assert (painel["kwh"] == 0.0).all()
