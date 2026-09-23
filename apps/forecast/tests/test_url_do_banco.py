"""De onde o pipeline le o historico.

Parece detalhe de configuracao, e e' o tipo de coisa que falha em silencio: com
a URL errada o treino nao quebra - ele treina contra OUTRO banco, publica
metricas plausiveis, e a previsao do staging fica com numeros de outro lugar.

O caso concreto: o workflow de migrations ja' tem `STAGING_DATABASE_URL`, no
formato da API (`postgresql+asyncpg://`). O pipeline e' pandas e fala `psycopg`.
Reusar o segredo exige trocar o driver; NAO reusar exige um segundo segredo com
o mesmo conteudo, que e' como os dois saem de sincronia.
"""

import pytest

from banco import DRIVER, com_driver_sincrono, url_do_banco


@pytest.mark.parametrize(
    "entrada",
    [
        "postgresql+asyncpg://u:s@h:5432/b",
        "postgresql://u:s@h:5432/b",
        "postgres://u:s@h:5432/b",
    ],
)
def test_troca_o_driver_preservando_o_resto(entrada):
    saida = com_driver_sincrono(entrada)

    assert saida.startswith(DRIVER + "://")
    assert saida.endswith("u:s@h:5432/b"), "usuario, senha, host ou banco se perderam"


def test_url_que_ja_esta_certa_passa_intacta():
    url = f"{DRIVER}://u:s@h:5432/b"

    assert com_driver_sincrono(url) == url


def test_nao_confunde_senha_que_parece_driver():
    """O prefixo e' trocado so' no INICIO da string.

    Uma senha contendo "postgresql://" e' improvavel, mas trocar por busca solta
    corromperia a URL sem erro nenhum - e o sintoma seria falha de conexao com
    uma mensagem que nao aponta para aqui.
    """
    url = f"{DRIVER}://u:postgresql://x@h:5432/b"

    assert com_driver_sincrono(url) == url


def test_o_override_vence_as_variaveis_soltas(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_DB", "local")
    monkeypatch.setenv("DATABASE_URL_OVERRIDE", "postgresql+asyncpg://u:s@remoto:5432/staging")

    url = url_do_banco()

    assert "remoto" in url and "staging" in url
    assert "localhost" not in url
    assert url.startswith(DRIVER + "://")


def test_sem_override_usa_as_variaveis_soltas(monkeypatch):
    """E' o caminho do compose local, que nao pode depender do segredo remoto."""
    monkeypatch.delenv("DATABASE_URL_OVERRIDE", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "chargegrid")
    monkeypatch.setenv("POSTGRES_PASSWORD", "segredo")
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "chargegrid")

    assert url_do_banco() == f"{DRIVER}://chargegrid:segredo@db:5432/chargegrid"


def test_override_vazio_nao_conta(monkeypatch):
    """String vazia e' variavel nao definida em quase todo CI."""
    monkeypatch.setenv("DATABASE_URL_OVERRIDE", "")
    monkeypatch.setenv("POSTGRES_HOST", "db")

    assert "@db:" in url_do_banco()
