"""ChargeGrid Intelligence - API do dashboard comercial de recarga EV."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import DomainError
from app.core.logging import configure_logging, get_logger
from app.db.session import engine
from app.workers.poller import start_workers, stop_workers

log = get_logger(__name__)

DESCRIPTION = """
Plataforma de orquestração de recarga EV para **estabelecimentos comerciais** —
o desafio ChargeGrid Intelligence (FIAP × GoodWe).

O eletroposto GoodWe HCA G2 protege apenas o próprio disjuntor, o SEMS+ não expõe
API de EV Charger e, sem OCPP, não existe cobrança. Esta API cobre esses três vazios.

### Gerenciamento de Potência
Orçamento do site recalculado a cada ciclo (`rede + solar + bateria − reserva predial
− agendamentos`), rateio por faixa de prioridade e escrita do teto no registrador
**10029**. Corte imediato sem derrubar sessões pelo registrador **10000**.

Política do operador persiste em campo próprio (`operator_max_kw`, `operator_throttled`):
o rateio automático distribui a potência disponível, mas nunca sobrepõe uma decisão humana.

### Ciclo da Sessão
Máquina de estados da autorização ao faturamento, com trilha de eventos que alimenta a
linha do tempo do painel. Sem folga no site a sessão entra em **fila de espera** e é
promovida quando o orçamento abre — quem já carrega nunca é cortado para dar lugar a um
recém-chegado.

### Tarifação & Pagamento
A cobrança rateia energia e tempo sobre a telemetria, aplicando o preço da **janela
horária vigente**: uma sessão das 17h40 às 19h20 paga ponta e fora de ponta corretamente.
Toda aritmética em `Decimal`. A fatura guarda o retrato da tarifa aplicada, então mudar o
preço amanhã não reescreve a cobrança de ontem.

---

**Autenticação:** clique em *Authorize* e use uma conta criada pelo seed — o
e-mail do operador com a senha de `SEED_OPERATOR_PASSWORD` (ou a que o seed imprimiu)
(contas criadas por `python -m app.seed`).

**Erros de domínio** respondem `{"code": "...", "detail": "..."}` — o `code` é estável e
serve para o cliente distinguir causas sem interpretar texto.
"""

TAGS = [
    {
        "name": "autenticação",
        "description": (
            "Login do painel e do app mobile pelo mesmo emissor. O *access token* dura 1 h "
            "e o *refresh* 30 dias. Papéis: `admin`, `operator` (painel) e `driver` (app)."
        ),
    },
    {
        "name": "recarga ev · potência",
        "description": (
            "Controle de demanda. `GET /power/overview` entrega orçamento, KPIs e pontos numa "
            "chamada só; `GET /power/plan` calcula o rateio **sem tocar no hardware**."
        ),
    },
    {
        "name": "recarga ev · sessões",
        "description": (
            "Ciclo completo da recarga, incluindo a fila de espera. Toda transição vira evento "
            "consultável em `GET /sessions/{id}`."
        ),
    },
    {
        "name": "recarga ev · tarifação e pagamento",
        "description": (
            "Políticas de preço, janelas horárias, faturas e cobrança. O tipo declarado da "
            "tarifa restringe os componentes que ela pode cobrar."
        ),
    },
    {
        "name": "campanhas",
        "description": (
            "Desconto na fatura e cashback em carteira, com missões e orçamento. Uma campanha "
            "declara **um** tipo de benefício: desconto sai da margem do estabelecimento, "
            "cashback sai da rede — e misturar os dois tornaria impossível dizer quanto ela "
            "custou."
        ),
    },
    {
        "name": "plataforma",
        "description": (
            "O contrato entre a rede e o estabelecimento: plano, prazo mínimo, cobrança mensal "
            "e multa de rescisão. Tabela separada de `invoices` de propósito — a direção do "
            "dinheiro é oposta, e somar as duas envenenaria todo relatório de receita."
        ),
    },
    {
        "name": "contas",
        "description": (
            "Operadores e administradores da rede, criados por admin. Motorista não entra aqui: "
            "ele se cadastra sozinho pelo app. Não há apagar — as referências de auditoria são "
            "`SET NULL`, então desligar preserva o rastro de quem fez o quê."
        ),
    },
    {
        "name": "app mobile",
        "description": (
            "Escopo do motorista: mapa de estações, início com pré-autorização, agendamento, "
            "carteira e faturas próprias. Um agendamento **segura potência** no orçamento do "
            "site até ser usado."
        ),
    },
    {
        "name": "tempo real",
        "description": (
            "O SEMS+ só responde a consulta. Este WebSocket empurra telemetria e plano de "
            "potência, e é o que faz o painel mudar sozinho."
        ),
    },
    {
        "name": "assistente",
        "description": (
            "Assistente do operador (Azure OpenAI). Só consulta: cada número da resposta vem "
            "de uma rota GET das abas do painel, executada em transação somente leitura e no "
            "escopo da praça. A resposta sai em `text/event-stream`."
        ),
    },
    {"name": "infra", "description": "Checagem de vida usada pelo Docker e pelo balanceador."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("api.starting", env=settings.env, driver=settings.charger_driver)
    tasks = start_workers()
    try:
        yield
    finally:
        await stop_workers(tasks)
        await engine.dispose()
        log.info("api.stopped")


app = FastAPI(
    title=settings.app_name,
    description=DESCRIPTION,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=TAGS,
    lifespan=lifespan,
    contact={"name": "ChargeGrid Intelligence", "url": "https://www.goodwe.com"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Erro de dominio vira resposta HTTP consistente, sem try/except nas rotas."""
    return JSONResponse(
        status_code=exc.status_code, content={"code": exc.code, "detail": exc.message}
    )


@app.get("/health", tags=["infra"])
async def health() -> dict:
    """Checagem de vida usada pelo Docker e pelo balanceador."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        database = "up"
    except Exception as exc:  # noqa: BLE001
        database = f"down: {exc}"
    return {
        "status": "ok" if database == "up" else "degraded",
        "env": settings.env,
        "database": database,
        "charger_driver": settings.charger_driver,
        "workers": settings.enable_workers,
    }


app.include_router(api_router, prefix=settings.api_v1_prefix)
