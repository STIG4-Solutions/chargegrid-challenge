"""O eixo de ano-a-ano aponta para o mes CERTO, e transporta forma sem nivel.

O defeito que estes testes prendem esta' em `pipeline/features.py`:
`hist_ano_atras = hist.tail(395).head(31)` com a origem no ultimo dia do mes M
cobre origem-394..origem-364 - o mes ANTERIOR ao alvo, um ano antes. Com origem
2026-01-31 e alvo fevereiro, ela cobre janeiro de 2025.

Dar essa janela ao modelo como razao nao vale nada (medido: 14,01% contra 13,96%);
alinhada ao mes alvo vale 2 pontos. Entao o que precisa de teste nao e' "existe uma
coluna de ano-a-ano" - e' "ela cobre o mes alvo, e nao o vizinho".

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

from modelo.ano_a_ano import LIMITE_DE_CRESCIMENTO, UM_ANO, colunas_de_ano  # noqa: E402

PRACA = "praca-a"


def _painel(inicio="2024-01-01", dias=900, por_mes=None) -> pd.DataFrame:
    """Painel diario onde cada mes do calendario tem um nivel PROPRIO.

    Sem essa diferenca por mes, apontar para o mes errado daria o mesmo numero e
    o teste nao mediria nada - que e' exatamente por que o defeito sobreviveu.
    """
    por_mes = por_mes or {1: 10.0, 2: 50.0, 3: 20.0}
    datas = pd.date_range(inicio, periods=dias, freq="D")
    return pd.DataFrame(
        {
            "location_id": PRACA,
            "date": datas,
            "kwh": [por_mes.get(d.month, 30.0) for d in datas],
        }
    )


def _linhas(mes_alvo: str, origem: str, datas: list[str], hist_m28: float = 30.0) -> pd.DataFrame:
    """As linhas de feature que `colunas_de_ano` recebe.

    `hist_m28` e' o nivel na ORIGEM e entra como parametro porque e' o numerador do
    fator de crescimento: o denominador e' o nivel da origem um ano antes, que sai
    do painel.
    """
    return pd.DataFrame(
        {
            "location_id": PRACA,
            "mes_alvo": pd.Timestamp(mes_alvo),
            "origem": pd.Timestamp(origem),
            "date": [pd.Timestamp(d) for d in datas],
            "hist_m28": hist_m28,
        }
    )


def test_o_nivel_do_ano_vem_do_MES_ALVO_e_nao_do_anterior():
    """Alvo fevereiro -> a referencia e' fevereiro do ano passado, nao janeiro.

    E' o defeito inteiro, em um assert. Fevereiro vale 50 e janeiro vale 10 neste
    painel: se a janela escorregar um mes, `por_dia_ano` cai de 50 para 10 e o
    numero fica cinco vezes menor.
    """
    painel = _painel()
    linhas = _linhas("2026-02-01", "2026-01-31", ["2026-02-01", "2026-02-15"])
    d = colunas_de_ano(linhas, painel)

    assert d["por_dia_ano"].round(3).eq(50.0).all(), d["por_dia_ano"].tolist()
    # E nao 10,0, que e' o valor de janeiro - o mes que `hist_ano_atras` pegava.
    assert not d["por_dia_ano"].eq(10.0).any()


def test_a_referencia_do_dia_preserva_o_dia_da_semana():
    """364 dias, e nao 365: 52 semanas exatas.

    Com 365 o alinhamento anda um dia por ano e uma terca passa a ser comparada
    com uma segunda. Numa praca corporativa sabado e segunda diferem por um fator
    de tres, entao um dia de deslocamento nao e' detalhe.
    """
    assert UM_ANO == pd.Timedelta(days=364)
    alvo = pd.Timestamp("2026-02-10")  # terca
    assert (alvo - UM_ANO).dayofweek == alvo.dayofweek


def test_a_razao_do_dia_e_forma_e_nao_nivel():
    """`razao_ano_dia` tem de ser ~1,0 num painel plano, qualquer que seja o nivel.

    Ela transporta a FORMA daquele dia, porque o nivel de hoje ja' entra por
    `hist_m28`. Se ela devolvesse o kWh absoluto, multiplicar por `nivel_ano`
    aplicaria o nivel duas vezes.
    """
    painel = _painel(por_mes={m: 40.0 for m in range(1, 13)})
    d = colunas_de_ano(_linhas("2026-02-01", "2026-01-31", ["2026-02-10"]), painel)
    assert np.isclose(d["razao_ano_dia"].iloc[0], 1.0, atol=0.01), d["razao_ano_dia"].iloc[0]


def test_o_crescimento_corrige_o_volume_do_ano_passado():
    """Uma praca que dobrou de nivel nao deve receber o volume do ano passado.

    Sem o fator de crescimento, a previsao devolveria o ano anterior numa rede que
    cresce ~30% ao ano e subestimaria tudo por construcao.
    """
    # Nivel 20 ate' meados de 2025 e 40 depois. Na origem (2026-01-31) o nivel e'
    # 40; um ano antes (2025-01-31) era 20. O crescimento tem de sair 2,0.
    datas = pd.date_range("2024-01-01", periods=900, freq="D")
    painel = pd.DataFrame(
        {
            "location_id": PRACA,
            "date": datas,
            "kwh": [20.0 if d < pd.Timestamp("2025-07-01") else 40.0 for d in datas],
        }
    )
    d = colunas_de_ano(_linhas("2026-02-01", "2026-01-31", ["2026-02-10"], hist_m28=40.0), painel)
    assert np.isclose(d["crescimento"].iloc[0], 2.0, atol=0.05), d["crescimento"].iloc[0]
    # O nivel previsto e' o do ano passado (fevereiro de 2025, 20 kWh/dia) VEZES o
    # crescimento. Sem o fator, a previsao devolveria 20 numa praca que faz 40.
    assert np.isclose(d["nivel_ano"].iloc[0], 20.0 * 2.0, atol=1.0), d["nivel_ano"].iloc[0]


def test_o_crescimento_tem_teto():
    """Praca que abriu no meio do ano anterior tem nivel antigo perto de zero.

    Sem teto, `hist_m28 / m28_de_um_ano_atras` explode e leva `nivel_ano` com
    ela - o card mostraria um numero absurdo para a praca mais nova da rede.
    """
    datas = pd.date_range("2024-01-01", periods=900, freq="D")
    # 0,5 kWh/dia um ano atras, 60 agora: razao de 120x sem o teto.
    painel = pd.DataFrame(
        {
            "location_id": PRACA,
            "date": datas,
            "kwh": [0.5 if d < pd.Timestamp("2025-07-01") else 60.0 for d in datas],
        }
    )
    d = colunas_de_ano(_linhas("2026-02-01", "2026-01-31", ["2026-02-10"], hist_m28=60.0), painel)
    assert d["crescimento"].iloc[0] == LIMITE_DE_CRESCIMENTO


def test_sem_ano_anterior_o_nivel_volta_para_a_media_movel():
    """Toda praca no primeiro ano de operacao cai aqui - nao e' caso raro.

    E `tem_ano` tem de dizer isso: sem a coluna, o modelo trataria uma linha em
    regime de media movel como se fosse uma em regime de ano-a-ano.
    """
    painel = _painel(inicio="2025-11-01", dias=120)
    d = colunas_de_ano(_linhas("2026-02-01", "2026-01-31", ["2026-02-10"]), painel)
    assert not d["tem_ano"].iloc[0]
    assert d["nivel_ano"].iloc[0] == d["hist_m28"].iloc[0]
    assert d["nivel_ano"].notna().all()
