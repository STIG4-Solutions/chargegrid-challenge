"""A aplicação não pode subir em produção com segredo publicamente conhecido."""

import pytest

from app.core.config import SECRET_KEY_DEV, WEBHOOK_SECRET_DEV, Settings

SEGREDOS_DEV = {
    "secret_key": "a" * 64,
    "payment_webhook_secret": "x",
    "postgres_password": "y",
}

SEGURO = {
    "secret_key": "a" * 64,
    "payment_webhook_secret": "segredo-real-do-psp",
    "postgres_password": "senha-forte-do-banco",
    "debug": False,
    # Producao com CORS so local significa que o dominio nao chegou a
    # configuracao - a API sobe e o painel e' bloqueado. Faz parte de "prod
    # configurado corretamente".
    "cors_origins": ["https://stig4.com"],
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


def test_prod_com_cors_so_local_e_recusado():
    """A imagem Docker nao carrega config/domains.json: sem CORS_ORIGINS no
    ambiente, o default cai no painel de desenvolvimento e o painel real toma
    erro de CORS - sintoma dificil de ligar a causa."""
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        _prod(cors_origins=["http://localhost:5173"])


def test_dev_com_cors_local_continua_normal():
    Settings(env="dev", cors_origins=["http://localhost:5173"], **SEGREDOS_DEV)


# ----------------------------------------------------------------- assistente

AZURE = {
    "azure_openai_endpoint": "https://recurso.openai.azure.com",
    "azure_openai_api_key": "chave-real-do-recurso",
    "azure_openai_deployment": "gpt-operacao",
}


def test_prod_sobe_com_o_assistente_desligado_e_sem_azure():
    """Desligado, nenhuma variavel do Azure e' exigida.

    Tudo explicito: `Settings` le o `.env` da maquina, e um `.env` local com o
    assistente ligado faria o cenario deixar de ser "desligado e sem Azure".
    """
    config = _prod(
        assistant_enabled=False,
        azure_openai_endpoint=None,
        azure_openai_api_key=None,
        azure_openai_deployment=None,
    )
    assert config.assistente_configurado is False


def test_prod_recusa_assistente_ligado_com_chave_de_molde():
    with pytest.raises(ValueError, match="AZURE_OPENAI_API_KEY"):
        _prod(
            assistant_enabled=True,
            **{**AZURE, "azure_openai_api_key": "TROQUE-ME-chave-do-azure-openai"},
        )


def test_prod_recusa_assistente_ligado_sem_deployment():
    with pytest.raises(ValueError, match="AZURE_OPENAI_DEPLOYMENT"):
        _prod(assistant_enabled=True, **{**AZURE, "azure_openai_deployment": None})


def test_prod_recusa_endpoint_sem_https():
    with pytest.raises(ValueError, match="https"):
        _prod(
            assistant_enabled=True,
            **{**AZURE, "azure_openai_endpoint": "http://recurso.openai.azure.com"},
        )


def test_prod_aceita_assistente_bem_configurado():
    assert _prod(assistant_enabled=True, **AZURE).assistente_configurado is True


def test_temperatura_em_branco_vira_nula():
    """`AZURE_OPENAI_TEMPERATURE=` no .env nao pode derrubar a subida."""
    assert Settings(env="dev", azure_openai_temperature="").azure_openai_temperature is None
