"""Tarifa de demanda do contrato com a distribuidora.

No Grupo A a conta tem duas partes: energia (kWh) e DEMANDA (kW). A demanda e'
faturada pela maior media de 15 minutos do mes, contra o valor contratado -
ultrapassar penaliza, e a penalidade nao e' proporcional.

Sem esses campos nao da para dizer quanto o rateio economiza: a conta so' existe
se soubermos quanto custa o kW contratado.

Revision ID: 0009_tarifa_de_demanda
Revises: 0008_reconcilia_indices
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_tarifa_de_demanda"
down_revision: str | None = "0008_reconcilia_indices"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sites",
        sa.Column(
            "demand_tariff_brl_per_kw",
            sa.Numeric(10, 2),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "sites",
        sa.Column(
            "contracted_demand_kw",
            sa.Numeric(8, 2),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("sites", "contracted_demand_kw")
    op.drop_column("sites", "demand_tariff_brl_per_kw")
