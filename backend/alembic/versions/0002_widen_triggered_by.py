"""Alarga command_logs.triggered_by.

O campo guardava so o papel (32 chars), mas os endpoints gravam
"<papel>:<email>" para identificar o operador. Com e-mail real isso estoura e
derruba o comando com erro 500. 280 cobre o maior e-mail aceito em users.email.

Revision ID: 0002_widen_triggered_by
Revises: 0001_initial
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_widen_triggered_by"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "command_logs",
        "triggered_by",
        existing_type=sa.String(32),
        type_=sa.String(280),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Trunca o que nao couber, senao o ALTER falha com dados existentes.
    op.execute("UPDATE command_logs SET triggered_by = left(triggered_by, 32)")
    op.alter_column(
        "command_logs",
        "triggered_by",
        existing_type=sa.String(280),
        type_=sa.String(32),
        existing_nullable=False,
    )
