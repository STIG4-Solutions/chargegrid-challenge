"""Reporte de problema pelo motorista, e conta corporativa.

REPORTES. `charge_point_faults` cobre o que o equipamento sabe de si: bits de
registrador. Nao cobre cabo cortado, tela apagada, vaga tomada por um carro a
combustao nem adesivo de QR arrancado - nesses casos o ponto reporta
"disponivel" com toda a sinceridade, porque do ponto de vista dele esta tudo
bem. Quem ve e a pessoa que chegou ali e nao conseguiu carregar, e ela ve
antes de qualquer sensor.

FROTA. Quem dirige nao e quem paga. `users.fleet_id` agrupa os motoristas da
empresa e `vehicles.cost_center` diz de qual area e o carro - no veiculo, nao
na pessoa, porque o carro pertence ao departamento e roda com motoristas
diferentes.

Revision ID: 0013_reportes_e_frota
Revises: 0012_push
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_reportes_e_frota"
down_revision: str | None = "0012_push"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIAS = (
    "nao_inicia",
    "conector_travado",
    "cabo_danificado",
    "tela_apagada",
    "vaga_ocupada",
    "qr_ilegivel",
    "outro",
)


def upgrade() -> None:
    # ---------------------------------------------------------- reportes
    op.create_table(
        "charge_point_reports",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "charge_point_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("charge_points.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SET NULL, nao CASCADE: apagar a conta de quem reportou nao pode
        # apagar o defeito. O ponto continua com o cabo rompido.
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "session_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("charging_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("categoria", sa.String(24), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolucao", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_charge_point_reports_cp_time", "charge_point_reports", ["charge_point_id", "created_at"]
    )
    op.create_index(
        "ix_charge_point_reports_abertos",
        "charge_point_reports",
        ["charge_point_id"],
        postgresql_where=sa.text("resolved_at IS NULL"),
    )
    # A lista fechada vive no banco tambem. Categoria digitada errada nao
    # agrega com as outras: viraria um problema solitario num relatorio que
    # deveria mostrar tres pessoas reclamando do mesmo cabo.
    op.create_check_constraint(
        "categoria",
        "charge_point_reports",
        "categoria IN ('" + "', '".join(CATEGORIAS) + "')",
    )
    # Resolver exige dizer quando. Sem isso um registro com `resolucao`
    # preenchida e `resolved_at` nulo continuaria aparecendo como aberto.
    op.create_check_constraint(
        "resolucao_completa",
        "charge_point_reports",
        "(resolved_at IS NULL) OR (resolved_by IS NOT NULL)",
    )

    # ------------------------------------------------------------- frota
    op.create_table(
        "fleets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("document", sa.String(32), nullable=True),
        sa.Column("billing_email", sa.String(255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "fleet_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fleets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_users_fleet_id", "users", ["fleet_id"])
    op.add_column(
        "users",
        sa.Column("fleet_manager", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.add_column("vehicles", sa.Column("cost_center", sa.String(60), nullable=True))
    op.create_index("ix_vehicles_cost_center", "vehicles", ["cost_center"])


def downgrade() -> None:
    op.drop_index("ix_vehicles_cost_center", table_name="vehicles")
    op.drop_column("vehicles", "cost_center")
    op.drop_column("users", "fleet_manager")
    op.drop_index("ix_users_fleet_id", table_name="users")
    op.drop_column("users", "fleet_id")
    op.drop_table("fleets")
    op.drop_index("ix_charge_point_reports_abertos", table_name="charge_point_reports")
    op.drop_index("ix_charge_point_reports_cp_time", table_name="charge_point_reports")
    op.drop_table("charge_point_reports")
