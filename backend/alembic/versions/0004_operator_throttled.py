"""Adiciona charge_points.operator_throttled.

O corte manual do operador (reg 10000) vivia so no campo status, entao o poller
e o rateio automatico o desfaziam em segundos - o botao do painel parecia
funcionar e revertia sozinho. Persistir a intencao separa politica do operador
de estado observado no hardware, igual ja e feito com operator_max_kw.

Revision ID: 0004_operator_throttled
Revises: 0003_operator_max_kw
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_operator_throttled"
down_revision: str | None = "0003_operator_max_kw"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "charge_points",
        sa.Column("operator_throttled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("charge_points", "operator_throttled", server_default=None)


def downgrade() -> None:
    op.drop_column("charge_points", "operator_throttled")
