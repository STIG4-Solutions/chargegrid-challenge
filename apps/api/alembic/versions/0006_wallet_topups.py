"""Razao dos creditos na carteira pre-paga.

Ate aqui um topup so alterava users.wallet_balance: nao havia rastro do credito
nem como impedir o duplo envio. A tabela guarda cada credito e o UNIQUE da chave
de idempotencia e' o que barra o segundo - um SELECT antes do INSERT nao barra,
porque dois toques simultaneos passam pelos dois SELECTs antes do primeiro
INSERT.

Revision ID: 0006_wallet_topups
Revises: 0005_session_queue
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_wallet_topups"
down_revision: str | None = "0005_session_queue"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wallet_topups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(12, 2), nullable=False),
        sa.Column("idempotency_key", sa.String(80), nullable=True),
        sa.Column("provider", sa.String(40), server_default="mock", nullable=False),
        sa.Column("provider_ref", sa.String(120), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_wallet_topups_user_id", "wallet_topups", ["user_id"])
    op.create_index("ix_wallet_topups_provider_ref", "wallet_topups", ["provider_ref"])
    op.create_index(
        "ix_wallet_topups_idempotency_key", "wallet_topups", ["idempotency_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_wallet_topups_idempotency_key", table_name="wallet_topups")
    op.drop_index("ix_wallet_topups_provider_ref", table_name="wallet_topups")
    op.drop_index("ix_wallet_topups_user_id", table_name="wallet_topups")
    op.drop_table("wallet_topups")
