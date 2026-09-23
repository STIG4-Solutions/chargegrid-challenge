"""As reguas de `janelas/reguas.py`.

O que estes testes prendem, por ordem de importancia:

1. PASSADO ESTRITO. Uma regua que espia o proprio bucket ganha de qualquer
   modelo, e a comparacao inteira deixa de significar algo. Um "oraculo" mal
   feito desta sessao mostrou o quanto isso engana: usava a media dos dois anos
   e saiu PIOR que a regua simples, por ser cego ao crescimento.
2. Cada regua enxerga o que a anterior nao enxerga. Se `por_dow_e_hora` errar
   como `por_dia_da_semana`, a janela de uma hora fica sem regua propria.
3. A identidade que decide o desenho: na soma SEMANAL o dia da semana cancela,
   e por isso `REGUAS_POR_JANELA["semana"]` nao traz `por_dia_da_semana`.

    docker compose --profile forecast run --rm --build forecast \
        python -m pytest tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from janelas.reguas import (  # noqa: E402
    REGUAS_POR_JANELA,
    media_movel,
    por_dia_da_semana,
    por_dow_e_hora,
    tendencia,
)
from pipeline.train import wape  # noqa: E402


def _diario(dias: int = 240, fds: float = 2.0, nivel: float = 100.0) -> pd.Series:
    """Serie diaria com fim de semana valendo `fds` vezes o dia util."""
    idx = pd.date_range("2025-01-06", periods=dias, freq="D")  # comeca segunda
    v = [nivel * (fds if d.dayofweek >= 5 else 1.0) for d in idx]
    return pd.Series(v, index=idx, dtype=float)


def _horario(dias: int = 120) -> pd.Series:
    """Serie horaria com vale de madrugada, pico de noite e fim de semana."""
    idx = pd.date_range("2025-01-06", periods=dias * 24, freq="h")
    v = []
    for t in idx:
        do_dia = 0.1 if t.hour < 6 else (2.0 if 18 <= t.hour <= 21 else 1.0)
        v.append(100.0 * do_dia * (1.5 if t.dayofweek >= 5 else 1.0))
    return pd.Series(v, index=idx, dtype=float)


# ----------------------------------------------------------- passado estrito


@pytest.mark.parametrize("regua", [media_movel, por_dia_da_semana, por_dow_e_hora, tendencia])
def test_nenhuma_regua_olha_o_proprio_bucket(regua):
    """Trocar o valor de um bucket nao pode mudar a previsao DELE.

    E' o teste que mais importa. Uma regua que inclui o proprio ponto na media
    parece excelente no backtest e nao serve para nada em producao, onde o ponto
    ainda nao aconteceu. Sem o `.shift(1)`, este teste morre.
    """
    s = _diario()
    antes = regua(s)
    alvo = s.index[-1]
    adulterada = s.copy()
    adulterada.loc[alvo] = 9_999_999.0
    depois = regua(adulterada)
    assert antes.loc[alvo] == pytest.approx(depois.loc[alvo], nan_ok=True)


def test_a_media_movel_e_a_media_dos_buckets_anteriores():
    """Valor exato, para que qualquer troca de janela apareca."""
    s = pd.Series(
        range(1, 21), index=pd.date_range("2025-01-01", periods=20, freq="D"), dtype=float
    )
    r = media_movel(s, janelas=4, minimo=4)
    # Na posicao 10 (valor 11) a previsao e' a media de 7, 8, 9 e 10.
    assert r.iloc[10] == pytest.approx((7 + 8 + 9 + 10) / 4)
    # As quatro primeiras nao tem quatro anteriores.
    assert r.iloc[:4].isna().all()


# ------------------------------------------ cada regua ve o que a outra nao ve


def test_a_regua_de_dia_da_semana_bate_a_media_movel_no_diario():
    """Fim de semana valendo o dobro: a media movel achata, a outra nao.

    Se `_por_grupo` deslocar a serie inteira em vez de deslocar DENTRO do grupo,
    as duas colapsam e esta diferenca desaparece.
    """
    s = _diario(fds=2.0)
    dow, plana = por_dia_da_semana(s), media_movel(s)
    valido = dow.notna() & plana.notna()
    erro_dow = wape(s[valido], dow[valido])
    erro_plano = wape(s[valido], plana[valido])
    assert erro_dow < erro_plano
    assert erro_plano - erro_dow > 15.0
    # A serie e' deterministica, logo a regua certa acerta em cheio.
    assert erro_dow < 1.0


def test_a_regua_horaria_bate_a_de_dia_da_semana_na_serie_horaria():
    """Perfil do dia e perfil da semana se multiplicam.

    Uma regua que agrupe so' por dia da semana mistura a madrugada com o pico da
    noite e erra as duas. Se `por_dow_e_hora` deixar de usar a hora, morre aqui.
    """
    s = _horario()
    dh, dow = por_dow_e_hora(s), por_dia_da_semana(s, semanas=8)
    valido = dh.notna() & dow.notna()
    erro_dh = wape(s[valido], dh[valido])
    erro_dow = wape(s[valido], dow[valido])
    assert erro_dh < erro_dow
    assert erro_dow - erro_dh > 30.0
    assert erro_dh < 1.0


def test_a_tendencia_acompanha_crescimento_que_a_media_movel_persegue_atrasada():
    """Serie que cresce 3% por bucket: a media movel fica sempre atras.

    A tendencia ajusta reta no LOG. Ajustar no nivel subestimaria o fim de uma
    serie multiplicativa - e' a mutacao que este teste mata.
    """
    n = 60
    idx = pd.date_range("2025-01-31", periods=n, freq="ME")
    s = pd.Series([100.0 * (1.03**i) for i in range(n)], index=idx)
    t = tendencia(s, janelas=12, minimo=12)
    plana = media_movel(s, janelas=12, minimo=12)
    valido = t.notna() & plana.notna()
    assert wape(s[valido], t[valido]) < wape(s[valido], plana[valido])
    # Crescimento puramente exponencial: a reta no log o reproduz quase exato.
    assert wape(s[valido], t[valido]) < 1.0


def test_a_tendencia_sobrevive_a_bucket_zerado():
    """Praca pequena pode ter mes sem recarga nenhuma.

    `log(0)` e' `-inf` e contaminaria o ajuste inteiro. Zero tem de sair do
    ajuste, e a regua tem de continuar devolvendo numero - nunca `inf`, e nunca
    zero, que afirmaria ausencia de demanda onde houve apenas um mes fraco.
    """
    n = 40
    idx = pd.date_range("2025-01-31", periods=n, freq="ME")
    v = [100.0 * (1.02**i) for i in range(n)]
    v[15] = 0.0
    v[16] = 0.0
    s = pd.Series(v, index=idx)
    prontos = tendencia(s, janelas=12, minimo=8).dropna()
    assert len(prontos) > 20
    assert np.isfinite(prontos.to_numpy()).all()
    assert (prontos > 0).all()


def test_a_tendencia_sem_dois_pontos_positivos_nao_devolve_zero():
    """O ramo de recuo, que so' uma parada LONGA alcanca.

    Com dois zeros isolados toda janela ainda tem dois positivos e a reta se
    ajusta normalmente - foi o furo da primeira versao deste arquivo, onde a
    mutacao que trocava o recuo por `return 0.0` sobreviveu porque o ramo nunca
    era executado.

    Aqui a praca fica fechada meses seguidos, com uma unica recarga no meio.
    Existe janela com EXATAMENTE um ponto positivo, e ali nao ha reta possivel.
    Devolver zero afirmaria que a praca nao tem demanda; o certo e' a media do
    que houver, que e' pequena mas positiva.
    """
    n = 40
    idx = pd.date_range("2025-01-31", periods=n, freq="ME")
    v = [100.0 * (1.02**i) for i in range(10)]  # aquece o minimo
    v += [0.0] * 16  # parada longa...
    v[18] = 500.0  # ...com uma unica recarga dentro dela
    v += [100.0 * (1.02**i) for i in range(26, n)]
    s = pd.Series(v, index=idx)

    r = tendencia(s, janelas=12, minimo=8)

    # As janelas com um unico positivo existem de fato - sem isto o teste
    # passaria sem exercitar nada, que foi exatamente o furo anterior.
    solitarias = [
        i for i in range(12, n) if (np.asarray(v[i - 12 : i]) > 0).sum() == 1
    ]
    assert solitarias, "a serie nao produziu janela com um unico positivo"

    for i in solitarias:
        assert r.iloc[i] > 0, f"posicao {i} devolveu {r.iloc[i]}"
        assert np.isfinite(r.iloc[i])


# ---------------------------------------- a identidade da janela semanal


def test_na_soma_semanal_o_dia_da_semana_cancela():
    """Toda semana tem uma segunda, uma terca, e assim por diante.

    Logo a soma semanal da regua de dia-da-semana e a da media movel convergem,
    por aritmetica e nao por acaso - mesmo numa serie em que no DIARIO elas
    diferem por mais de 15 pontos, como o teste acima prova. E' a razao de a
    janela semanal nao ter regua propria, e de `REGUAS_POR_JANELA` nao lista-la.

    As janelas sao casadas de proposito: 8 semanas sao 56 dias.
    """
    s = _diario(dias=364, fds=2.0)
    dow = por_dia_da_semana(s, semanas=8, minimo=8)
    plana = media_movel(s, janelas=56, minimo=56)
    valido = dow.notna() & plana.notna()
    junto = pd.DataFrame({"real": s[valido], "dow": dow[valido], "plana": plana[valido]})

    # Semanas completas apenas: numa semana partida nao ha um de cada dia, e e'
    # exatamente ali que a identidade nao vale.
    por_semana = junto.groupby(pd.Grouper(freq="W")).agg(["sum", "count"])
    cheias = por_semana[por_semana[("real", "count")] == 7]
    assert len(cheias) > 20

    diferenca = (
        (cheias[("dow", "sum")] - cheias[("plana", "sum")]).abs() / cheias[("real", "sum")]
    ).max()
    assert diferenca < 0.01, f"diferenca maxima de {diferenca:.3%}"

    assert "por_dia_da_semana" not in REGUAS_POR_JANELA["semana"]


def test_cada_janela_declara_as_reguas_que_tem_de_bater():
    """Janela sem regua e' janela sem criterio de aceite."""
    assert set(REGUAS_POR_JANELA) == {"hora", "dia", "semana", "mes", "ano"}
    for janela, nomes in REGUAS_POR_JANELA.items():
        assert nomes, janela
        assert "media_movel" in nomes, janela
    # A hora precisa da regua que enxerga a hora; sem ela, nada a compara.
    assert "por_dow_e_hora" in REGUAS_POR_JANELA["hora"]
    # O ano extrapola: media movel sozinha ignoraria o crescimento da frota.
    assert "tendencia" in REGUAS_POR_JANELA["ano"]
