"""Configuração central da aplicação (12-factor: tudo vem do ambiente)."""

import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, computed_field, field_validator, model_validator
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
    "TROQUE-ME-chave-do-azure-openai",
}

# Comprimento minimo de uma chave de assinatura. openssl rand -hex 32 da 64.
SECRET_KEY_MIN = 32


# Enderecos do projeto, lidos de config/domains.json na raiz do repositorio.
#
# O arquivo e' a fonte unica: mudar o dominio ali muda API, dashboard e site publico.
# Cada consumidor ainda aceita variavel de ambiente por cima - aqui e'
# CORS_ORIGINS -, porque em producao o endereco costuma vir do ambiente e nao
# do repositorio.
# A API fica em apps/api no checkout e em /app no container.
# .parent continua na raiz do sistema quando config/ nao foi empacotado.
_RAIZ = Path(__file__).resolve().parents[2].parent.parent


def _dominios() -> dict:
    arquivo = _RAIZ / "config" / "domains.json"
    try:
        return json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # A imagem Docker copia so o backend: sem o arquivo, os defaults de
        # desenvolvimento abaixo bastam, e producao passa CORS_ORIGINS.
        return {}


def _e_local(origem: str) -> bool:
    return any(marca in origem for marca in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]"))


def _origens_padrao() -> list[str]:
    d = _dominios()
    origens = []
    if d.get("dashboard") and d.get("protocolo"):
        origens.append(f"{d['protocolo']}://{d['dashboard']}")
    # O painel de staging entra na lista padrao, e nao substitui o de producao:
    # sao ambientes diferentes, e cada um so' fala com a API do seu proprio - o
    # endereco da API fica assado no pacote de cada build.
    #
    # Isso vale para quem roda a API a partir do repositorio. Na Azure o arquivo
    # nem existe (a imagem copia so' `apps/api`), entao la' quem manda e'
    # CORS_ORIGINS, como o roteiro de deploy instrui.
    dashboard_staging = (d.get("staging") or {}).get("dashboard")
    if dashboard_staging and d.get("protocolo"):
        origens.append(f"{d['protocolo']}://{dashboard_staging}")
    dashboard_dev = (d.get("desenvolvimento") or {}).get("dashboard", "http://localhost:5173")
    # O dashboard de desenvolvimento continua liberado: sem isso, trabalhar
    # localmente exigiria editar o .env a cada clone.
    origens.extend([dashboard_dev, dashboard_dev.replace("localhost", "127.0.0.1")])
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

    # Precificacao dinamica pela folga de potencia (bandeira do site).
    # Desligada (o padrao), tudo fica como era: o rebalanceador nao grava
    # bandeira, a sessao nao trava multiplicador e o motor usa so' o
    # multiplicador da tarifa. Liga-se por ambiente: PRECIFICACAO_DINAMICA=true.
    precificacao_dinamica: bool = False
    # Folga = potencia disponivel / (rede + solar + bateria). As bordas pertencem
    # a faixa de cima: 50% ja' e' verde, 20% ja' e' amarela.
    bandeira_folga_verde: Decimal = Decimal("0.50")
    bandeira_folga_amarela: Decimal = Decimal("0.20")
    bandeira_mult_verde: Decimal = Decimal("1.00")
    bandeira_mult_amarela: Decimal = Decimal("1.15")
    bandeira_mult_vermelha: Decimal = Decimal("1.30")
    # Bandeira mais velha que isto nao trava preco: o rebalanceador parou (a
    # instancia hibernou) e a cor na tela ja' nao descreve o site. Quatro ciclos.
    bandeira_validade_s: int = 60

    # Notificacao push.
    #   log  - registra em vez de enviar; exercita todo o caminho ate a borda
    #   expo - entrega pelo servico da Expo
    # Um nome fora desta lista estoura, em vez de cair no simulador em silencio.
    push_provider: Literal["log", "expo"] = "log"
    push_interval_s: int = 20

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

    # Assistente do operador (Azure OpenAI).
    #
    # Desligado por padrao: sem ele a API sobe inteira e o widget do painel some.
    # Ligar exige os tres campos do Azure - `assistente_configurado` diz se estao
    # todos la', e a guarda de producao recusa subir ligado com chave de molde.
    assistant_enabled: bool = False
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    # Nome do DEPLOYMENT no Azure, e nao do modelo: e' ele que vai no `model=`.
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    # Nulo = nao envia. Modelos de raciocinio (familia o) recusam o parametro.
    azure_openai_temperature: float | None = 0.2
    azure_openai_timeout_s: float = 60.0

    assistant_max_input_chars: int = Field(default=2000, ge=100, le=20000)
    # Rodadas de ferramenta antes de a ultima ser forcada a responder sem elas.
    assistant_max_tool_iterations: int = Field(default=5, ge=1, le=10)
    assistant_max_tool_calls_per_round: int = Field(default=4, ge=1, le=10)
    assistant_max_output_tokens: int = Field(default=1200, ge=100, le=8000)
    assistant_tool_result_max_chars: int = Field(default=12000, ge=1000, le=100000)
    assistant_tool_timeout_s: float = Field(default=10.0, gt=0, le=60)
    assistant_history_messages: int = Field(default=10, ge=0, le=50)
    assistant_rate_per_min: int = Field(default=6, ge=1)
    assistant_rate_per_day: int = Field(default=200, ge=1)
    # Tetos de CUSTO, em tokens (entrada + saida). Mensagem por dia nao limita
    # gasto: uma pergunta que puxa varias consultas custa dez comuns. Estes sim.
    #   por resposta - passou, a proxima rodada vai sem ferramentas;
    #   por usuario/dia e total/dia - passou, a pergunta seguinte toma 429.
    # O total protege o credito da conta Azure contra muitos usuarios juntos.
    assistant_max_input_tokens_per_answer: int = Field(default=30000, ge=2000)
    assistant_daily_tokens_per_user: int = Field(default=300_000, ge=1000)
    assistant_daily_tokens_total: int = Field(default=2_000_000, ge=1000)

    @field_validator("azure_openai_temperature", mode="before")
    @classmethod
    def _temperatura_em_branco_e_nula(cls, valor):
        # `AZURE_OPENAI_TEMPERATURE=` no .env chega como "" - e "" nao e' float.
        return None if isinstance(valor, str) and not valor.strip() else valor

    @property
    def assistente_configurado(self) -> bool:
        return bool(
            self.assistant_enabled
            and self.azure_openai_endpoint
            and self.azure_openai_api_key
            and self.azure_openai_deployment
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
        if self.assistant_enabled:
            # So' com o assistente ligado: desligado, a chave nem e' lida, e
            # exigi-la obrigaria todo ambiente a ter uma conta Azure para subir.
            if self.azure_openai_api_key in SEGREDOS_PUBLICOS:
                problemas.append(
                    "AZURE_OPENAI_API_KEY é o valor de molde do .env.example. "
                    "Use a chave do recurso Azure OpenAI, ou ASSISTANT_ENABLED=false."
                )
            if not self.assistente_configurado:
                problemas.append(
                    "ASSISTANT_ENABLED=true sem AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY "
                    "e AZURE_OPENAI_DEPLOYMENT. Preencha os três ou desligue o assistente."
                )
            elif not self.azure_openai_endpoint.startswith("https://"):
                problemas.append("AZURE_OPENAI_ENDPOINT precisa ser https.")

        # QUALQUER endereco local na lista de producao e' problema - nao apenas
        # uma lista inteiramente local.
        #
        # Sao dois cenarios distintos e os dois passavam antes. Na imagem Docker
        # o config/domains.json nao existe (o build usa contexto ./apps/api), o
        # default fica so com os enderecos de desenvolvimento e o painel real
        # toma erro de CORS. Rodando de um checkout, o arquivo existe e o default
        # traz o dominio JUNTO dos locais: a API sobe limpa e deixa localhost
        # permanentemente liberado em producao.
        #
        # Exigir que TODAS fossem locais deixava o segundo caso passar - que e'
        # o mais perigoso dos dois, porque nao da nenhum sintoma.
        locais = [origem for origem in self.cors_origins if _e_local(origem)]
        if locais:
            problemas.append(
                f"CORS_ORIGINS contém endereço local em {self.env}: {', '.join(locais)}. "
                "Defina CORS_ORIGINS apenas com os domínios reais."
            )

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
