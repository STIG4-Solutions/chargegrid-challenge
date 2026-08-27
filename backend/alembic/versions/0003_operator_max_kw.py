"""Adiciona charge_points.operator_max_kw.

Separa o teto definido pelo operador no dashboard do teto fisico do equipamento.
Antes, o rateio automatico usava o nominal como demanda e sobrescrevia o ajuste
manual no ciclo seguinte - o slider do painel nao surtia efeito.

Revision ID: 0003_operator_max_kw
Revises: 0002_widen_triggered_by
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_operator_max_kw"
down_revision: str | None = "0002_widen_triggered_by"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nulo = sem politica definida, vale o nominal do equipamento.
    op.add_column("charge_points", sa.Column("operator_max_kw", sa.Numeric(6, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("charge_points", "operator_max_kw")
