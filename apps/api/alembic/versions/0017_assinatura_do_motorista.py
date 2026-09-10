"""Plano de recarga assinado pelo motorista.

Quem assina paga uma mensalidade e recebe, em toda recarga, o que o plano
promete: desconto percentual, kWh inclusos e isencao da taxa de conexao. O
beneficio entra no motor pelo MESMO `Beneficio` que as campanhas ja usam - nada
novo em `rate_session`, que continua puro.

`invoices.site_id` VIRA NULAVEL, e essa e' a mudanca com alcance. A mensalidade
e' cobrada da rede, nao de uma praca: nao existe estabelecimento a que atribui-la.
As quatro consultas que filtram por site usam `Invoice.site_id == :site_id`, que
ja exclui NULL - entao a mensalidade nao entra na receita de recarga de ninguem,
que e' exatamente o desejado. Sem isso, atribuir a mensalidade a um site
qualquer inflaria o faturamento dele com dinheiro que ele nao recebeu.

O QUE NAO EXISTE AQUI, e nao por esquecimento: isencao de taxa de ociosidade.
A ociosidade nao e' receita - e' o mecanismo que libera a vaga. Isentar o
assinante transformaria o melhor cliente naquele que mais trava o conector, e
uma coluna para isso ja seria um convite.

Revision ID: 0017_assinatura_do_motorista
Revises: 0016_previsao_de_demanda
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017_assinatura_do_motorista"
down_revision: str | None = "0016_previsao_de_demanda"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = sa.dialects.postgresql.UUID

ESTADOS = ("ativa", "cancelada", "inadimplente")


def _carimbo() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade() -> None:
    # ------------------------------------------------------------- catalogo
    op.create_table(
        "driver_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("codigo", sa.String(24), nullable=False),
        sa.Column("nome", sa.String(80), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("preco_mensal_brl", sa.Numeric(10, 2), nullable=False),
        sa.Column("desconto_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("kwh_inclusos", sa.Numeric(10, 3), nullable=False, server_default="0"),
        sa.Column(
            "isenta_taxa_de_conexao", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_carimbo(),
        sa.UniqueConstraint("codigo", name="uq_driver_plans_codigo"),
    )
    op.create_check_constraint(
        "ck_driver_plans_desconto", "driver_plans", "desconto_pct >= 0 AND desconto_pct <= 100"
    )
    op.create_check_constraint("ck_driver_plans_kwh", "driver_plans", "kwh_inclusos >= 0")
    op.create_check_constraint("ck_driver_plans_preco", "driver_plans", "preco_mensal_brl >= 0")
    # Plano que nao da nada e' mensalidade sem contrapartida. Barrar aqui evita
    # que ele exista; descobrir depois exigiria estornar quem ja assinou.
    op.create_check_constraint(
        "ck_driver_plans_entrega_algo",
        "driver_plans",
        "desconto_pct > 0 OR kwh_inclusos > 0 OR isenta_taxa_de_conexao",
    )

    # ---------------------------------------------------------- assinaturas
    op.create_table(
        "driver_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # RESTRICT: nao se apaga plano que alguem assinou. O preco e as regras
        # dele explicam faturas ja emitidas.
        sa.Column(
            "plan_id",
            UUID(as_uuid=True),
            sa.ForeignKey("driver_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("estado", sa.String(14), nullable=False, server_default="ativa"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_start", sa.Date(), nullable=False),
        sa.Column("current_period_end", sa.Date(), nullable=False),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "kwh_consumidos_no_periodo", sa.Numeric(10, 3), nullable=False, server_default="0"
        ),
        *_carimbo(),
    )
    op.create_check_constraint(
        "ck_driver_subscriptions_estado",
        "driver_subscriptions",
        f"estado IN ({', '.join(repr(e) for e in ESTADOS)})",
    )
    op.create_check_constraint(
        "ck_driver_subscriptions_periodo",
        "driver_subscriptions",
        "current_period_end > current_period_start",
    )
    # Cancelar exige dizer quando. Sem isso um registro pode se declarar
    # cancelado sem que se saiba a partir de que momento parou de valer - e a
    # pergunta "esta recarga tinha desconto?" fica sem resposta.
    op.create_check_constraint(
        "ck_driver_subscriptions_cancelamento_completo",
        "driver_subscriptions",
        "estado <> 'cancelada' OR canceled_at IS NOT NULL",
    )
    # Uma pessoa, uma assinatura ativa. Mesmo desenho de
    # `uq_active_session_per_driver`: a checagem da aplicacao e' um SELECT
    # seguido de INSERT, e dois toques simultaneos a atravessam juntos.
    op.create_index(
        "uq_driver_subscription_ativa",
        "driver_subscriptions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'ativa'"),
    )

    # ------------------------------------------------------------- fatura
    # A mensalidade e' da rede, nao de uma praca. As consultas que filtram por
    # site usam `= :site_id` e ja excluem NULL, entao ela nao entra na receita
    # de recarga de nenhum estabelecimento.
    op.alter_column("invoices", "site_id", existing_type=UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    # Fatura sem site nao cabe na coluna obrigatoria; some com ela antes.
    op.execute("DELETE FROM invoices WHERE site_id IS NULL")
    op.alter_column("invoices", "site_id", existing_type=UUID(as_uuid=True), nullable=False)

    op.drop_index("uq_driver_subscription_ativa", table_name="driver_subscriptions")
    op.drop_table("driver_subscriptions")
    op.drop_table("driver_plans")
