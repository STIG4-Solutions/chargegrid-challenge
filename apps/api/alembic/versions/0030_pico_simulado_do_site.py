"""Pico simulado de consumo do predio, para a demonstracao da bandeira.

O administrador dispara um pico por alguns minutos e o medidor virtual passa a
somar esse consumo ao do predio ate' o prazo. Persistido no site, e nao na
memoria do processo, para que a expiracao dependa so' do relogio - e seja
testavel com um relogio injetado.

Revision ID: 0030_pico_simulado_do_site
Revises: 0029_bandeira_do_site
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0030_pico_simulado_do_site"
down_revision: str | None = "0029_bandeira_do_site"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sites", sa.Column("pico_simulado_kw", sa.Numeric(8, 2), nullable=True))
    op.add_column(
        "sites", sa.Column("pico_simulado_ate", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("sites", "pico_simulado_ate")
    op.drop_column("sites", "pico_simulado_kw")
