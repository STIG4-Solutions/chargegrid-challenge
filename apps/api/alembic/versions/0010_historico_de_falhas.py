"""Historico de falhas por ponto de recarga.

`charge_points.active_faults` e' um retrato: o poller o sobrescreve a cada
ciclo. Serve para mostrar o estado agora, e nao serve para nada alem disso -
uma falha que apareceu ontem e sumiu nao deixou vestigio.

Manutencao preditiva depende de recorrencia, e recorrencia depende de
historico. Esta tabela guarda cada episodio: quando comecou, quando parou, e
quantos ciclos durou. Um ponto que repete "sobretemperatura no cabo" tres vezes
na semana esta pedindo manutencao antes de falhar de vez.

Revision ID: 0010_historico_de_falhas
Revises: 0009_tarifa_de_demanda
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_historico_de_falhas"
down_revision: str | None = "0009_tarifa_de_demanda"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "charge_point_faults",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "charge_point_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("charge_points.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("terminal", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ciclos", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_charge_point_faults_cp_time", "charge_point_faults", ["charge_point_id", "first_seen_at"]
    )
    # Um episodio ABERTO por ponto e rotulo. O poller reencontra a mesma falha a
    # cada ciclo; sem isto ele criaria uma linha por leitura, e cinco segundos de
    # falha virariam mil episodios.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_falha_aberta_por_ponto
        ON charge_point_faults (charge_point_id, label)
        WHERE resolved_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_falha_aberta_por_ponto")
    op.drop_index("ix_charge_point_faults_cp_time", table_name="charge_point_faults")
    op.drop_table("charge_point_faults")
