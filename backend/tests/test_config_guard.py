"""A aplicação não pode subir em produção com segredo publicamente conhecido."""

import pytest

from app.core.config import SECRET_KEY_DEV, WEBHOOK_SECRET_DEV, Settings

SEGURO = {
    "secret_key": "a" * 64,
    "payment_webhook_secret": "segredo-real-do-psp",
    "postgres_password": "senha-forte-do-banco",
    "debug": False,
}


def _prod(**ajustes):
    return Settings(env="prod", **{**SEGURO, **ajustes})


def test_dev_aceita_os_padroes():
    """Desenvolvimento continua sem atrito — a guarda só vale em ambiente protegido."""
    config = Settings(env="dev", secret_key=SECRET_KEY_DEV, debug=True)
    assert config.env == "dev"


def test_prod_recusa_secret_key_do_repositorio():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        _prod(secret_key=SECRET_KEY_DEV)


def test_prod_recusa_placeholder_do_env_example():
    """O caminho mais provável de todos: copiar o .env.example e subir.

    Checar só o padrão do código deixaria esse passar.
    """
    with pytest.raises(ValueError, match="SECRET_KEY"):
        _prod(secret_key="troque-esta-chave-em-producao-0123456789abcdef")


def test_prod_recusa_secret_key_curta():
    with pytest.raises(ValueError, match="caracteres"):
        _prod(secret_key="curta-demais")


def test_prod_recusa_segredo_de_webhook_publico():
    with pytest.raises(ValueError, match="PAYMENT_WEBHOOK_SECRET"):
        _prod(payment_webhook_secret=WEBHOOK_SECRET_DEV)


def test_prod_recusa_debug_ligado():
    with pytest.raises(ValueError, match="DEBUG"):
        _prod(debug=True)


def test_prod_lista_todos_os_problemas_de_uma_vez():
    """Corrigir um por vez, a cada tentativa de deploy, é tempo perdido."""
    with pytest.raises(ValueError) as erro:
        Settings(
            env="prod",
            secret_key=SECRET_KEY_DEV,
            payment_webhook_secret=WEBHOOK_SECRET_DEV,
            postgres_password="chargegrid",
            debug=True,
        )
    mensagem = str(erro.value)
    for esperado in ("SECRET_KEY", "PAYMENT_WEBHOOK_SECRET", "POSTGRES_PASSWORD", "DEBUG"):
        assert esperado in mensagem


def test_prod_configurado_corretamente_sobe():
    config = _prod()
    assert config.env == "prod"
    assert not config.debug


def test_staging_tambem_e_protegido():
    """Staging costuma ter dado real — a mesma régua vale."""
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(env="staging", **{**SEGURO, "secret_key": SECRET_KEY_DEV})
