"""Configuração central da aplicação (12-factor: tudo vem do ambiente)."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sentinelas da lista de bloqueio - NAO sao valores padrao.
#
# Nenhum destes e' usado como default de configuracao: segredo e senha vem do
# ambiente e nao tem fallback. Eles existem so' para a guarda de producao poder
# reconhece-los, porque ja circularam publicamente (estao no .env.example, no
# docker-compose e no historico deste repositorio). Apagar daqui nao remove
# credencial nenhuma - apenas cega a guarda para o caminho mais provavel de
# vazamento, que e' copiar o .env.example e subir em producao.
SECRET_KEY_DEV = "dev-secret-nao-use-em-producao"
WEBHOOK_SECRET_DEV = "webhook-secret-dev"
POSTGRES_PASSWORD_DEV = "chargegrid"

# Ambientes onde um segredo publicamente conhecido e inaceitavel.
AMBIENTES_PROTEGIDOS = {"staging", "prod"}

# Valores que ja circulam publicamente: os padroes do codigo mais os placeholders
# do .env.example e do docker-compose. Checar so o padrao do codigo deixaria
# passar o caminho mais provavel de todos - copiar o .env.example e subir.
SEGREDOS_PUBLICOS = {
    SECRET_KEY_DEV,
    WEBHOOK_SECRET_DEV,
    POSTGRES_PASSWORD_DEV,
    "troque-esta-chave-em-producao",
    "troque-esta-chave-em-producao-0123456789abcdef",
    # Placeholders do .env.example: copiar o molde e subir e' o caminho mais
    # provavel de vazamento, entao a guarda tem que reconhece-los tambem.
    "TROQUE-ME-senha-do-banco",
    "TROQUE-ME-openssl-rand-hex-32",
    "TROQUE-ME-segredo-do-psp",
}

# Comprimento minimo de uma chave de assinatura. openssl rand -hex 32 da 64.
SECRET_KEY_MIN = 32


# Enderecos do projeto, lidos de config/dominios.json na raiz do repositorio.
#
# O arquivo e' a fonte unica: mudar o dominio ali muda backend, painel e app.
# Cada consumidor ainda aceita variavel de ambiente por cima - aqui e'
# CORS_ORIGINS -, porque em producao o endereco costuma vir do ambiente e nao
# do repositorio.
_RAIZ = Path(__file__).resolve().parents[3]


def _dominios() -> dict:
    arquivo = _RAIZ / "config" / "dominios.json"
    try:
        return json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # A imagem Docker copia so o backend: sem o arquivo, os defaults de
        # desenvolvimento abaixo bastam, e producao passa CORS_ORIGINS.
        return {}


def _origens_padrao() -> list[str]:
    d = _dominios()
    origens = []
    if d.get("app") and d.get("protocolo"):
        origens.append(f"{d['protocolo']}://{d['app']}")
    painel_dev = (d.get("desenvolvimento") or {}).get("painel", "http://localhost:5173")
    # O painel de desenvolvimento continua liberado: sem isso, trabalhar
    # localmente exigiria editar o .env a cada clone.
    origens.extend([painel_dev, painel_dev.replace("localhost", "127.0.0.1")])
    return origens


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # API
    app_name: str = "ChargeGrid Intelligence API"
    env: Literal["dev", "staging", "prod", "test"] = "dev"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=_origens_padrao)

    # Banco
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "chargegrid"
    # Sem default: uma senha de banco embutida no codigo vale para todo mundo
    # que clonar o repositorio. Vem do .env (use o .env.example como molde).
    postgres_password: str
    postgres_db: str = "chargegrid"
    database_url_override: str | None = None

    # Segurança
    # Sem default: com ela qualquer pessoa assina um token de administrador.
    # Gere a sua com: openssl rand -hex 32
    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # Driver de hardware
    charger_driver: Literal["simulator", "modbus"] = "simulator"
    modbus_register_offset: int = 0
    modbus_timeout_s: float = 3.0

    # Workers
    enable_workers: bool = True
    poll_interval_s: int = 5
    power_rebalance_interval_s: int = 15

    # Origem das leituras do medidor do site.
    #   virtual - um worker sintetiza a curva do dia (sem medidor fisico)
    #   push    - so' aceita o que chegar por POST /power/meter-readings
    # Trocar por um coletor real e' implementar um worker novo e apontar aqui.
    meter_source: Literal["virtual", "push"] = "virtual"
    meter_interval_s: int = 30

    # Pagamento
    # O Literal lista o que existe de verdade. "stripe" estava aqui sem
    # implementacao: passava na validacao e caia no simulador, aprovando
    # pagamento ficticio. Quando houver um provedor Stripe, ele volta.
    payment_provider: Literal["mock", "pix"] = "mock"
    # Sem default: com ele um webhook forjado marca faturas como pagas.
    payment_webhook_secret: str

    # Contas criadas pelo seed. Sem valor definido, o seed sorteia uma senha e
    # a imprime uma unica vez - assim um banco de desenvolvimento nunca nasce
    # com credencial que esta escrita no repositorio.
    seed_admin_password: str | None = None
    seed_operator_password: str | None = None
    seed_driver_password: str | None = None

    # Regras de negócio
    idle_grace_minutes: int = Field(
        default=10,
        description="Minutos de tolerância após o fim da carga antes da taxa de ociosidade",
    )
    queue_timeout_minutes: int = Field(
        default=30, description="Tempo máximo que uma sessão espera na fila antes de ser liberada"
    )
    stale_telemetry_seconds: int = Field(
        default=90, description="Sem leitura nesse intervalo, o ponto é marcado OFFLINE"
    )

    @model_validator(mode="after")
    def recusar_segredo_padrao(self) -> "Settings":
        """Impede a aplicacao de subir em staging ou producao com segredo de dev.

        Documentar que "precisa trocar a chave" nao impede ninguem de esquecer, e
        o esquecimento e silencioso: a API sobe normal e assina JWT com uma chave
        publicada no repositorio - qualquer pessoa forjaria um token de admin.
        Falhar aqui transforma isso numa parada imediata, na inicializacao, com o
        comando da correcao junto.
        """
        if self.env not in AMBIENTES_PROTEGIDOS:
            return self

        problemas: list[str] = []
        if self.secret_key in SEGREDOS_PUBLICOS:
            problemas.append(
                "SECRET_KEY é um valor público do repositório — qualquer pessoa com "
                "acesso a ele poderia assinar um token de administrador. "
                "Gere uma nova com: openssl rand -hex 32"
            )
        elif len(self.secret_key) < SECRET_KEY_MIN:
            problemas.append(
                f"SECRET_KEY tem {len(self.secret_key)} caracteres; use pelo menos "
                f"{SECRET_KEY_MIN}. Gere com: openssl rand -hex 32"
            )
        if self.payment_webhook_secret in SEGREDOS_PUBLICOS:
            problemas.append(
                "PAYMENT_WEBHOOK_SECRET é um valor público do repositório — um webhook "
                "forjado marcaria faturas como pagas. Use o segredo que o PSP fornece."
            )
        if self.postgres_password in SEGREDOS_PUBLICOS:
            problemas.append("POSTGRES_PASSWORD é um valor público do repositório.")
        if self.debug:
            problemas.append("DEBUG=true expõe stack trace ao cliente. Use DEBUG=false.")

        if problemas:
            itens = "".join(f"\n  - {item}" for item in problemas)
            raise ValueError(
                f"Configuração insegura para ENV={self.env}:{itens}\n"
                "Defina essas variáveis no ambiente antes de subir."
            )
        return self

    @computed_field
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )

    @computed_field
    @property
    def sync_database_url(self) -> str:
        """Usada pelo Alembic (driver síncrono)."""
        return self.database_url.replace("+asyncpg", "+psycopg2")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
