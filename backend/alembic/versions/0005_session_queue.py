"""Fila de espera para sessoes sem potencia disponivel.

Antes, uma sessao sem folga no site falhava com 422 e liberava o ponto: o
motorista tinha que ficar tentando de novo. Agora ela entra em QUEUED e o
rebalanceador promove quando o orcamento abre.

QUEUED conta como sessao ativa (o motorista esta na vaga esperando), entao o
indice parcial que impede duas sessoes no mesmo ponto precisa incluir o estado.

Revision ID: 0005_session_queue
Revises: 0004_operator_throttled
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_session_queue"
down_revision: str | None = "0004_operator_throttled"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ATIVOS_ANTES = "'authorizing', 'starting', 'charging', 'suspended', 'finishing'"
ATIVOS_DEPOIS = "'authorizing', 'queued', 'starting', 'charging', 'suspended', 'finishing'"


def _recriar_indice(estados: str) -> None:
    op.execute("DROP INDEX IF EXISTS uq_active_session_per_charge_point")
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_active_session_per_charge_point
        ON charging_sessions (charge_point_id)
        WHERE state IN ({estados})
        """
    )


def upgrade() -> None:
    op.add_column(
        "charging_sessions", sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True)
    )
    # A fila e varrida por site em ordem de chegada a cada ciclo do rebalanceador.
    op.create_index(
        "ix_charging_sessions_queue",
        "charging_sessions",
        ["site_id", "queued_at"],
        unique=False,
        postgresql_where=sa.text("state = 'queued'"),
    )
    _recriar_indice(ATIVOS_DEPOIS)


def downgrade() -> None:
    # Sessoes na fila nao existem no schema antigo: encerra antes de voltar.
    op.execute("UPDATE charging_sessions SET state = 'error' WHERE state = 'queued'")
    _recriar_indice(ATIVOS_ANTES)
    op.drop_index("ix_charging_sessions_queue", table_name="charging_sessions")
    op.drop_column("charging_sessions", "queued_at")
