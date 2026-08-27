"""Ambiente do Alembic - roda com o engine assincrono da aplicacao."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import settings
from app.models import Base  # importa todos os modelos

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Indices criados por SQL cru nas migrations (BRIN e o unique parcial de sessao
# ativa) nao existem no metadata. Sem este filtro, o proximo --autogenerate
# emitiria drop_index para todos eles - apagando a protecao contra duas sessoes
# simultaneas no mesmo ponto e os indices de serie temporal.
INDICES_MANUAIS = {
    "ix_telemetry_samples_recorded_at_brin",
    "ix_site_meter_readings_recorded_at_brin",
    "ix_command_logs_sent_at_brin",
    "ix_audit_logs_occurred_at_brin",
    "ix_telemetry_samples_cp_time",
    "ix_session_events_session_time",
    "uq_active_session_per_charge_point",
    "ix_charging_sessions_queue",
}


def include_object(objeto, nome, tipo, reflexo, comparador):
    if tipo == "index" and nome in INDICES_MANUAIS:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
