"""Infraestrutura dos testes que tocam o banco.

Rodam contra um **Postgres de verdade**, num banco separado (`<db>_test`), e
nao contra SQLite. Dois motivos concretos: os modelos usam tipos que so'
existem no Postgres (UUID nativo, JSONB) e o codigo das sessoes vem de uma
`SEQUENCE` criada pela migration. Um SQLite fingindo ser Postgres passaria em
testes que a producao reprovaria - que e' o pior tipo de teste.

O schema e' construido com **alembic**, nao com `Base.metadata.create_all`:
as sequences e os indices BRIN so' existem nas migrations, e testar contra um
schema diferente do que roda em producao esvazia o teste.

Cada teste roda dentro de uma transacao desfeita no fim. Os servicos chamam
`db.commit()` livremente; o `join_transaction_mode="create_savepoint"` faz
esses commits caírem em savepoints internos, entao o rollback externo limpa
tudo. Nenhum teste enxerga o que outro escreveu, e nada sobra no banco.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings, settings

_settings = get_settings()
BANCO_DE_TESTE = f"{_settings.postgres_db}_test"


def _url(database: str) -> str:
    return (
        f"postgresql+asyncpg://{_settings.postgres_user}:{_settings.postgres_password}"
        f"@{_settings.postgres_host}:{_settings.postgres_port}/{database}"
    )


@pytest.fixture(scope="session")
def url_de_teste() -> str:
    return _url(BANCO_DE_TESTE)


@pytest.fixture(scope="session", autouse=True)
async def preparar_banco(url_de_teste: str):
    """Cria o banco de teste (se faltar) e aplica as migrations nele."""
    import asyncpg

    admin = await asyncpg.connect(
        user=_settings.postgres_user,
        password=_settings.postgres_password,
        host=_settings.postgres_host,
        port=_settings.postgres_port,
        database="postgres",
    )
    try:
        existe = await admin.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", BANCO_DE_TESTE
        )
        if not existe:
            await admin.execute(f'CREATE DATABASE "{BANCO_DE_TESTE}"')
    finally:
        await admin.close()

    # O env.py do alembic faz `config.set_main_option("sqlalchemy.url",
    # settings.database_url)` no import, sobrescrevendo qualquer URL passada por
    # fora. Entao o caminho que funciona e' apontar o proprio singleton - e
    # devolve-lo ao valor original depois, para nao contaminar o resto.
    anterior = settings.database_url_override
    settings.database_url_override = url_de_teste
    try:
        from alembic.config import Config

        from alembic import command

        cfg = Config("alembic.ini")
        # Numa thread propria: o env.py chama asyncio.run(), que recusa rodar
        # dentro de um laco de eventos ja em execucao - e o pytest-asyncio ja
        # abriu o dele.
        await asyncio.to_thread(command.upgrade, cfg, "head")
        yield
    finally:
        settings.database_url_override = anterior


@pytest.fixture(scope="session")
async def engine(url_de_teste: str, preparar_banco):
    motor = create_async_engine(url_de_teste, pool_pre_ping=True)
    yield motor
    await motor.dispose()


@pytest.fixture
async def db(engine) -> AsyncSession:
    """Sessao isolada: tudo que o teste escrever e' desfeito no fim."""
    async with engine.connect() as conexao:
        transacao = await conexao.begin()
        sessao = AsyncSession(
            bind=conexao,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield sessao
        finally:
            await sessao.close()
            await transacao.rollback()


# --------------------------------------------------------------- cenario base


@pytest.fixture
async def site(db: AsyncSession):
    """Site com folga de potencia. Quem quiser aperto baixa o grid_limit_kw."""
    from app.models.site import Site

    s = Site(
        id=uuid.uuid4(),
        name="Site de Teste",
        slug="site-de-teste",
        grid_limit_kw=75,
        reserved_kw=20,
        allow_pv_kw=False,
        allow_battery_kw=False,
    )
    db.add(s)
    await db.flush()
    return s


@pytest.fixture
async def tarifa(db: AsyncSession, site):
    """Por energia, com minimo de R$ 5 e 10 minutos livres de ociosidade."""
    from app.models.enums import TariffType
    from app.models.tariff import Tariff

    t = Tariff(
        id=uuid.uuid4(),
        site_id=site.id,
        name="Tarifa de Teste",
        type=TariffType.PER_KWH,
        price_per_kwh=2,
        idle_fee_per_min=0.5,
        min_charge=5,
        free_minutes=10,
        active=True,
    )
    db.add(t)
    await db.flush()
    site.default_tariff_id = t.id
    await db.flush()
    return t


@pytest.fixture
async def ponto(db: AsyncSession, site, tarifa):
    from app.models.charge_point import ChargePoint
    from app.models.enums import ChargePointStatus, ConnectorType, PhaseType

    cp = ChargePoint(
        id=uuid.uuid4(),
        site_id=site.id,
        code="CP-TESTE",
        name="Ponto de Teste",
        serial_number="SIMTESTE01",
        connector=ConnectorType.TYPE2,
        phase_type=PhaseType.THREE,
        rated_kw=22,
        min_kw=4.2,
        limit_kw=22,
        operator_max_kw=22,
        status=ChargePointStatus.AVAILABLE,
        priority=100,
        enabled=True,
        tariff_id=tarifa.id,
    )
    db.add(cp)
    await db.flush()
    return cp


@pytest.fixture
async def segundo_ponto(db: AsyncSession, site, tarifa):
    """Prioridade menor: e' o primeiro a ser cortado quando falta potencia."""
    from app.models.charge_point import ChargePoint
    from app.models.enums import ChargePointStatus, ConnectorType, PhaseType

    cp = ChargePoint(
        id=uuid.uuid4(),
        site_id=site.id,
        code="CP-TESTE-2",
        name="Ponto de Teste 2",
        serial_number="SIMTESTE02",
        connector=ConnectorType.CCS2,
        phase_type=PhaseType.THREE,
        rated_kw=22,
        min_kw=4.2,
        limit_kw=22,
        operator_max_kw=22,
        status=ChargePointStatus.AVAILABLE,
        priority=50,
        enabled=True,
        tariff_id=tarifa.id,
    )
    db.add(cp)
    await db.flush()
    return cp


@pytest.fixture
async def motorista(db: AsyncSession):
    from app.models.billing import WalletEntry
    from app.models.enums import UserRole
    from app.models.user import User

    u = User(
        id=uuid.uuid4(),
        email=f"motorista-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Motorista de Teste",
        hashed_password="x",
        role=UserRole.DRIVER,
        wallet_balance=100,
    )
    db.add(u)
    await db.flush()
    # O saldo de abertura tem linha no razao, como em producao: a migration
    # 0021 cria uma para todo saldo herdado. Sem ela o motorista de teste
    # nasceria com a invariante `SUM(wallet_entries) = wallet_balance` ja
    # quebrada, e o teste que a confere nao provaria nada.
    db.add(
        WalletEntry(
            id=uuid.uuid4(),
            user_id=u.id,
            amount=100,
            balance_after=100,
            idempotency_key=f"teste:abertura:{u.id}",
            provider="fixture",
            origem="ajuste",
            # Obrigatorio desde a 0025: ajuste sem motivo e' saldo que aparece
            # sem ninguem saber explicar.
            motivo="Saldo de abertura do razao",
        )
    )
    await db.flush()
    return u


@pytest.fixture
def agora() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ camada HTTP
#
# Ate aqui todo teste chamava servico ou handler direto, passando o usuario como
# argumento. Isso pula justamente o que o FastAPI faz por nos: resolver o token,
# aplicar a guarda de papel, validar o corpo e serializar a resposta. Foi por
# isso que as rotas /app/* ficaram sem guarda de motorista sem ninguem notar -
# nenhum teste tinha como perceber.
#
# As fixtures abaixo sobem a aplicacao de verdade sobre a MESMA sessao de banco
# do teste, entao a transacao continua sendo desfeita no fim.


@pytest.fixture
async def api(db: AsyncSession):
    """Cliente HTTP falando com o app real, no banco da transacao do teste."""
    from httpx import ASGITransport, AsyncClient

    from app.core.deps import get_db
    from app.main import app

    async def _db_do_teste():
        yield db

    app.dependency_overrides[get_db] = _db_do_teste
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://teste"
        ) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)


def _cabecalho(user) -> dict[str, str]:
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


@pytest.fixture
async def operador(db: AsyncSession):
    from app.models.enums import UserRole
    from app.models.user import User

    u = User(
        id=uuid.uuid4(),
        email=f"operador-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Operador de Teste",
        hashed_password="x",
        role=UserRole.OPERATOR,
    )
    db.add(u)
    await db.flush()
    return u


@pytest.fixture
async def administrador(db: AsyncSession):
    from app.models.enums import UserRole
    from app.models.user import User

    u = User(
        id=uuid.uuid4(),
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Admin de Teste",
        hashed_password="x",
        role=UserRole.ADMIN,
    )
    db.add(u)
    await db.flush()
    return u


@pytest.fixture
async def segundo_motorista(db: AsyncSession):
    """Outro motorista, para provar que um nao alcanca o dado do outro."""
    from app.models.enums import UserRole
    from app.models.user import User

    u = User(
        id=uuid.uuid4(),
        email=f"outro-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Outro Motorista",
        hashed_password="x",
        role=UserRole.DRIVER,
        wallet_balance=100,
    )
    db.add(u)
    await db.flush()
    return u


@pytest.fixture
def como_segundo_motorista(segundo_motorista):
    return _cabecalho(segundo_motorista)


@pytest.fixture
def como_motorista(motorista):
    """Cabecalho de autorizacao de um motorista."""
    return _cabecalho(motorista)


@pytest.fixture
def como_operador(operador):
    return _cabecalho(operador)


@pytest.fixture
def como_admin(administrador):
    return _cabecalho(administrador)


@pytest.fixture
async def segundo_site(db: AsyncSession):
    """Outro estabelecimento, para provar que um nao enxerga o outro."""
    from app.models.site import Site

    s = Site(
        id=uuid.uuid4(),
        name="Site Vizinho",
        slug="site-vizinho",
        grid_limit_kw=75,
        reserved_kw=10,
        allow_pv_kw=False,
        allow_battery_kw=False,
    )
    db.add(s)
    await db.flush()
    return s


async def _operador_de(db: AsyncSession, site_id):
    from app.models.enums import UserRole
    from app.models.user import User

    u = User(
        id=uuid.uuid4(),
        email=f"op-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Operador",
        hashed_password="x",
        role=UserRole.OPERATOR,
        site_id=site_id,
    )
    db.add(u)
    await db.flush()
    return u


@pytest.fixture
async def como_operador_do_site(db: AsyncSession, site):
    return _cabecalho(await _operador_de(db, site.id))


@pytest.fixture
async def como_operador_vizinho(db: AsyncSession, segundo_site):
    return _cabecalho(await _operador_de(db, segundo_site.id))
