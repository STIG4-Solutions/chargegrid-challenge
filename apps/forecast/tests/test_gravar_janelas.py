"""As linhas que `janelas/gravar.py` produz para `site_forecasts`.

O que estes testes prendem:

1. Cada janela declara a FONTE certa. A tabela de folga decidiu que quatro das
   cinco servem regua, e `fonte` e' o que faz a tela nao chamar de previsao um
   numero que veio de uma media.
2. Somente a janela de HORA traz faixa - e SEMPRE traz. O CHECK do banco recusa
   meia banda, e recusa banda em `media_dow`/`media_movel`.
3. Os buckets sao FUTUROS, contiguos e sem o presente. Gravar um bucket que ja'
   aconteceu e' previsao do passado.
4. Faturamento e' kWh x tarifa, depois da agregacao.

Sem banco: o que se testa e' a forma das linhas, nao a escrita.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from janelas.gravar import (  # noqa: E402
    HORIZONTE,
    SERVIDOR,
    linhas_da_janela,
    todas_as_janelas,
)

TARIFA = 2.60


def _horario(dias: int = 200) -> pd.Series:
    """Serie horaria com vale de madrugada, pico de noite e fim de semana."""
    idx = pd.date_range("2025-01-06", periods=dias * 24, freq="h")
    v = [
        100.0
        * (0.1 if t.hour < 6 else (2.0 if 18 <= t.hour <= 21 else 1.0))
        * (1.5 if t.dayofweek >= 5 else 1.0)
        for t in idx
    ]
    return pd.Series(v, index=idx, dtype=float)


def _diario(dias: int = 500) -> pd.Series:
    idx = pd.date_range("2024-06-03", periods=dias, freq="D")
    v = [100.0 * (2.0 if d.dayofweek >= 5 else 1.0) for d in idx]
    return pd.Series(v, index=idx, dtype=float)


# ------------------------------------------------------------------- a fonte


@pytest.mark.parametrize("janela", ["dia", "semana", "ano"])
def test_cada_janela_declara_a_fonte_que_a_serve(janela):
    """`fonte` e' o que a tela le' para NAO chamar uma media de previsao."""
    linhas = linhas_da_janela(_diario(), janela, TARIFA)
    assert linhas
    esperada = SERVIDOR[janela][1]
    assert {linha["fonte"] for linha in linhas} == {esperada}


def test_a_janela_horaria_declara_perfil_hora():
    linhas = linhas_da_janela(_horario(), "hora", TARIFA)
    assert linhas
    assert {linha["fonte"] for linha in linhas} == {"perfil_hora"}


def test_o_mes_declara_modelo_somente_quando_o_modelo_e_passado():
    """O portao decide fora daqui; esta funcao so' obedece.

    Sem previsao do modelo a janela mensal serve regua e DIZ isso - foi por servir
    media movel sem declarar que a tela chegou a apresentar conta de padaria como
    previsao.
    """
    s = _diario()
    sem = linhas_da_janela(s, "mes", TARIFA)
    assert {linha["fonte"] for linha in sem} == {SERVIDOR["mes"][1]}

    futuro = pd.date_range(s.index.max() + pd.Timedelta(days=1), periods=400, freq="D")
    do_modelo = pd.Series(123.0, index=futuro)
    com = linhas_da_janela(s, "mes", TARIFA, do_modelo)
    assert {linha["fonte"] for linha in com} == {"modelo"}
    # E o numero vem do modelo, nao da regua: 123 kWh em CADA dia do mes. O
    # comprimento sai do calendario, nao de uma aproximacao - fevereiro tem 28.
    primeiro = pd.Timestamp(com[0]["bucket_inicio"])
    dias_no_mes = primeiro.days_in_month
    assert com[0]["kwh_previsto"] == pytest.approx(123.0 * dias_no_mes, rel=1e-6)


# -------------------------------------------------------------------- a faixa


def test_so_a_janela_horaria_traz_faixa():
    """Media nao declara quantil, e o CHECK do banco recusaria a banda.

    `banda_com_quantil` aceita faixa de `modelo`, `perfil_hora` e `tendencia`.
    `media_dow` e `media_movel` servem dia, semana e mes - e vao sem faixa.
    """
    for janela in ("dia", "semana"):
        for linha in linhas_da_janela(_diario(), janela, TARIFA):
            assert linha["kwh_p10"] is None, janela
            assert linha["kwh_p90"] is None, janela


def test_a_faixa_horaria_vem_completa_e_ordenada():
    """Meia banda e' recusada pelo banco, e p10 acima de p90 nao e' faixa."""
    linhas = linhas_da_janela(_horario(), "hora", TARIFA)
    assert linhas
    com_faixa = [linha for linha in linhas if linha["kwh_p10"] is not None]
    assert len(com_faixa) == len(linhas), "toda hora tem de trazer faixa"
    for linha in com_faixa:
        assert linha["kwh_p90"] is not None
        assert linha["kwh_p10"] <= linha["kwh_previsto"] <= linha["kwh_p90"]


# ------------------------------------------------------------- os buckets


def test_nenhum_bucket_comeca_no_passado():
    """A regressao que este arquivo existe para prender.

    A serie termina numa quarta. Sem descartar bucket parcial, o primeiro bucket
    SEMANAL saia rotulado com a segunda anterior - data no passado - somando tres
    dias como se fosse semana cheia. Um bucket rotulado no passado e' previsao do
    que ja' aconteceu, e no banco colidiria com a linha real daquela semana.
    """
    s = _diario()
    ultimo = s.index.max()
    for janela in ("dia", "semana", "mes", "ano"):
        linhas = linhas_da_janela(s, janela, TARIFA)
        assert linhas, janela
        for linha in linhas:
            assert pd.Timestamp(linha["bucket_inicio"]) > ultimo, (janela, linha)


def test_os_buckets_sao_unicos_e_crescentes():
    """Bucket repetido colidiria na chave unica do banco."""
    for s, janela in ((_horario(), "hora"), (_diario(), "dia"), (_diario(), "mes")):
        buckets = [linha["bucket_inicio"] for linha in linhas_da_janela(s, janela, TARIFA)]
        assert len(buckets) == len(set(buckets)), janela
        assert buckets == sorted(buckets), janela


def test_o_horizonte_de_cada_janela_e_respeitado():
    linhas = linhas_da_janela(_horario(), "hora", TARIFA)
    assert len(linhas) <= HORIZONTE["hora"]
    assert len(linhas) >= HORIZONTE["hora"] - 1


def test_a_competencia_acompanha_o_mes_do_bucket():
    """A coluna e' antiga e continua servindo a rota mensal."""
    for linha in linhas_da_janela(_diario(), "dia", TARIFA):
        bucket = pd.Timestamp(linha["bucket_inicio"])
        assert linha["competencia"].year == bucket.year
        assert linha["competencia"].month == bucket.month
        assert linha["competencia"].day == 1


# --------------------------------------------------------------- faturamento


def test_o_faturamento_e_kwh_vezes_tarifa():
    """Tarifa nunca foi feature do modelo: entra DEPOIS da agregacao."""
    for linha in linhas_da_janela(_diario(), "dia", TARIFA):
        assert linha["faturamento_previsto_brl"] == pytest.approx(
            linha["kwh_previsto"] * TARIFA, rel=1e-6
        )


def test_sem_tarifa_nao_se_inventa_faturamento():
    """Praca sem tarifa cadastrada nao recebe reais chutados."""
    for linha in linhas_da_janela(_diario(), "dia", None):
        assert "faturamento_previsto_brl" not in linha


def test_a_faixa_em_reais_acompanha_a_faixa_em_kwh():
    for linha in linhas_da_janela(_horario(), "hora", TARIFA):
        if linha["kwh_p10"] is None:
            assert linha["fat_p10_brl"] is None
            continue
        assert linha["fat_p10_brl"] == pytest.approx(linha["kwh_p10"] * TARIFA, rel=1e-6)
        assert linha["fat_p90_brl"] == pytest.approx(linha["kwh_p90"] * TARIFA, rel=1e-6)


# ----------------------------------------------------------------- o conjunto


def test_todas_as_janelas_cobre_as_cinco():
    linhas = todas_as_janelas(_horario(), _diario(), TARIFA)
    assert {linha["granularidade"] for linha in linhas} == {
        "hora",
        "dia",
        "semana",
        "mes",
        "ano",
    }


def test_nenhum_kwh_negativo():
    """Praca nao devolve energia, e o CHECK do banco recusaria."""
    for linha in todas_as_janelas(_horario(), _diario(), TARIFA):
        assert linha["kwh_previsto"] >= 0.0


def test_serie_vazia_nao_produz_linha():
    vazia = pd.Series([], index=pd.DatetimeIndex([]), dtype=float)
    assert linhas_da_janela(vazia, "dia", TARIFA) == []
    assert todas_as_janelas(vazia, vazia, TARIFA) == []
