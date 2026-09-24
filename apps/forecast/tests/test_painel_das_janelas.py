"""O recorte do tempo em `janelas/painel.py`.

Duas armadilhas, e as duas ja' aconteceram nesta sessao:

1. BUCKET PARCIAL. Um mes pela metade comparado contra a previsao do mes inteiro
   infla o erro de todos - setembro deu +98% no modelo E na regua numa primeira
   medicao, e o achado inteiro daquela rodada foi para o lixo.
2. COMPLETUDE POR CONTAGEM. Fevereiro tem 28 dias e janeiro 31. Decidir "esta
   completo se tem tantas linhas quanto o maior" descarta todo fevereiro como se
   fosse mes partido - era o primeiro rascunho de `reamostrar`.

Sem banco: o que se testa aqui e' aritmetica de calendario.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from janelas.painel import PERIODO_DA_JANELA, na_rede, reamostrar, serie  # noqa: E402


def _horas(inicio: str, fim: str, valor: float = 1.0) -> pd.Series:
    idx = pd.date_range(inicio, fim, freq="h")
    return pd.Series(valor, index=idx, dtype=float)


def _dias(inicio: str, fim: str, valor: float = 1.0) -> pd.Series:
    idx = pd.date_range(inicio, fim, freq="D")
    return pd.Series(valor, index=idx, dtype=float)


# ------------------------------------------------------------ bucket parcial


def test_o_mes_pela_metade_nao_entra():
    """A serie vai ate 13 de setembro: setembro nao pode aparecer.

    E' a regressao mais importante deste arquivo. Se setembro entrar somando 13
    dias, ele sera' comparado contra uma previsao de 30 e o erro estoura.
    """
    s = _dias("2026-06-01", "2026-09-13")
    r = reamostrar(s, "mes")
    meses = [d.strftime("%Y-%m") for d in r.index]
    assert meses == ["2026-06", "2026-07", "2026-08"]
    assert "2026-09" not in meses


def test_o_primeiro_bucket_tambem_sai_quando_parcial():
    """A praca abriu no dia 10: junho nao esta' completo e sai."""
    s = _dias("2026-06-10", "2026-08-31")
    r = reamostrar(s, "mes")
    meses = [d.strftime("%Y-%m") for d in r.index]
    assert meses == ["2026-07", "2026-08"]


def test_fevereiro_nao_e_descartado_por_ter_menos_dias():
    """O defeito que este arquivo existe para prender.

    Fevereiro tem 28 dias, janeiro 31. Um teste de completude por contagem de
    linhas eliminaria fevereiro em todo ano de toda serie.
    """
    s = _dias("2026-01-01", "2026-04-30")
    r = reamostrar(s, "mes")
    meses = [d.strftime("%Y-%m") for d in r.index]
    assert meses == ["2026-01", "2026-02", "2026-03", "2026-04"]
    # E a soma de fevereiro e' 28, nao 31 nem NaN.
    assert r.iloc[1] == pytest.approx(28.0)


def test_o_mes_completo_que_termina_as_23h_entra():
    """Serie HORARIA: o ultimo registro de agosto e' 31/08 as 23h.

    Sem a folga de um passo da fonte, o mes pareceria terminar antes da
    meia-noite e seria descartado - agosto inteiro perdido por uma hora.
    """
    s = _horas("2026-08-01 00:00", "2026-08-31 23:00")
    r = reamostrar(s, "mes")
    assert [d.strftime("%Y-%m") for d in r.index] == ["2026-08"]
    assert r.iloc[0] == pytest.approx(31 * 24.0)


# ----------------------------------------------------------------- rotulos


def test_o_rotulo_do_bucket_e_o_inicio_dele():
    """`competencia` no banco guarda o primeiro dia do mes.

    Rotular pelo fim faria a linha gravada dizer o mes seguinte.
    """
    s = _dias("2026-06-01", "2026-08-31")
    r = reamostrar(s, "mes")
    assert [str(d.date()) for d in r.index] == ["2026-06-01", "2026-07-01", "2026-08-01"]


def test_a_janela_semanal_comeca_na_segunda():
    s = _dias("2026-06-01", "2026-06-28")  # 2026-06-01 e' uma segunda
    r = reamostrar(s, "semana")
    assert all(d.dayofweek == 0 for d in r.index)
    assert (r == 7.0).all()


def test_a_soma_por_janela_conserva_o_total_quando_nada_e_parcial():
    """Reamostrar nao pode criar nem perder energia."""
    s = _dias("2026-01-01", "2026-12-31", valor=3.0)
    for janela in ("dia", "mes", "ano"):
        assert reamostrar(s, janela).sum() == pytest.approx(s.sum()), janela


def test_janela_desconhecida_falha_alto():
    with pytest.raises(ValueError, match="janela desconhecida"):
        reamostrar(_dias("2026-01-01", "2026-01-31"), "quinzena")


def test_serie_vazia_atravessa_sem_explodir():
    vazia = pd.Series([], index=pd.DatetimeIndex([]), dtype=float)
    assert reamostrar(vazia, "mes").empty


def test_toda_janela_declarada_tem_periodo():
    assert set(PERIODO_DA_JANELA) == {"hora", "dia", "semana", "mes", "ano"}


# -------------------------------------------------------------------- rede


def test_a_rede_e_a_soma_das_pracas_e_nao_a_media():
    """Uma praca que abriu ontem contribui com o que vende, nao com peso igual."""
    painel = pd.DataFrame(
        {
            "location_id": ["a", "b", "a", "b"],
            "bucket": pd.to_datetime(["2026-06-01", "2026-06-01", "2026-06-02", "2026-06-02"]),
            "kwh": [100.0, 10.0, 200.0, 20.0],
            "sessions": [4.0, 1.0, 8.0, 2.0],
            "revenue": [250.0, 25.0, 500.0, 50.0],
        }
    )
    r = na_rede(painel)
    assert len(r) == 2
    assert r["kwh"].tolist() == [110.0, 220.0]
    assert r["sessions"].tolist() == [5.0, 10.0]
    assert r["revenue"].tolist() == [275.0, 550.0]


def test_a_serie_sai_ordenada_no_tempo():
    """As reguas usam `shift` e `rolling`: fora de ordem elas mentem em silencio."""
    painel = pd.DataFrame(
        {
            "bucket": pd.to_datetime(["2026-06-03", "2026-06-01", "2026-06-02"]),
            "kwh": [3.0, 1.0, 2.0],
        }
    )
    s = serie(painel)
    assert s.index.is_monotonic_increasing
    assert s.tolist() == [1.0, 2.0, 3.0]
