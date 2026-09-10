"""O estabelecimento assinando a plataforma da GoodWe.

Dinheiro na direcao OPOSTA ao resto do sistema: em `invoices` o motorista paga o
estabelecimento; aqui o estabelecimento paga a rede.

`platform_invoices` e' tabela SEPARADA por necessidade, e nao por organizacao.
`utilization_service` e `portfolio_service` somam `invoices` por `site_id`, e a
mensalidade da plataforma entraria como receita de recarga do proprio lojista que
a pagou - inflando o faturamento dele com dinheiro que ele nao recebeu, mas
gastou.

PRAZO MINIMO. `minimo_ate` nao avanca na renovacao automatica. Prender por mais
doze meses quem apenas deixou o contrato correr e' abusivo, e o modelo de negocio
nao se sustenta numa discussao se depender disso.

Os nomes de constraint aqui vao SEM o prefixo `ck_<tabela>_`: a NAMING_CONVENTION
o acrescenta. Escrever o nome completo o duplica, e na 0017 isso passou dos 63
caracteres do Postgres - ver a 0018.

Revision ID: 0019_assinatura_da_plataforma
Revises: 0018_acertos_de_schema
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019_assinatura_da_plataforma"
down_revision: str | None = "0018_acertos_de_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = sa.dialects.postgresql.UUID


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
        "platform_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("codigo", sa.String(24), nullable=False),
        sa.Column("nome", sa.String(80), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("preco_mensal_brl", sa.Numeric(10, 2), nullable=False),
        sa.Column("preco_por_ponto_brl", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("pontos_inclusos", sa.Integer(), nullable=False, server_default="0"),
        # A parte que faz o modelo valer: percentual sobre o faturamento do site.
        sa.Column("fee_percent_transacao", sa.Numeric(6, 3), nullable=False, server_default="0"),
        sa.Column("meses_minimos", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_carimbo(),
        sa.UniqueConstraint("codigo", name="uq_platform_plans_codigo"),
    )
    op.create_check_constraint("preco_nao_negativo", "platform_plans", "preco_mensal_brl >= 0")
    op.create_check_constraint(
        "preco_por_ponto_nao_negativo", "platform_plans", "preco_por_ponto_brl >= 0"
    )
    op.create_check_constraint("pontos_nao_negativo", "platform_plans", "pontos_inclusos >= 0")
    op.create_check_constraint(
        "fee_entre_zero_e_cem",
        "platform_plans",
        "fee_percent_transacao >= 0 AND fee_percent_transacao <= 100",
    )
    op.create_check_constraint(
        "meses_minimos_nao_negativo", "platform_plans", "meses_minimos >= 0"
    )

    # ------------------------------------------------------------- contratos
    op.create_table(
        "site_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # RESTRICT: nao se apaga plano contratado; o preco dele explica cobrancas
        # ja emitidas.
        sa.Column(
            "plan_id",
            UUID(as_uuid=True),
            sa.ForeignKey("platform_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("estado", sa.String(16), nullable=False, server_default="ativa"),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("minimo_ate", sa.Date(), nullable=False),
        sa.Column("renova_em", sa.Date(), nullable=False),
        sa.Column("encerra_em", sa.Date(), nullable=True),
        sa.Column(
            "renovacao_automatica", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("multa_percentual", sa.Numeric(5, 2), nullable=False, server_default="0"),
        *_carimbo(),
    )
    op.create_check_constraint(
        "estado_conhecido",
        "site_subscriptions",
        "estado IN ('ativa', 'em_aviso_previo', 'encerrada', 'inadimplente')",
    )
    op.create_check_constraint(
        "minimo_depois_do_inicio", "site_subscriptions", "minimo_ate >= starts_on"
    )
    # Encerrar exige dizer quando: sem a data, "esta competencia ainda e'
    # cobravel?" fica sem resposta no mes seguinte.
    op.create_check_constraint(
        "encerramento_completo",
        "site_subscriptions",
        "estado <> 'encerrada' OR encerra_em IS NOT NULL",
    )
    op.create_check_constraint(
        "multa_ate_cem", "site_subscriptions", "multa_percentual >= 0 AND multa_percentual <= 100"
    )
    # Um contrato vivo por site. Encerrados nao contam - o estabelecimento pode
    # voltar depois, e barrar isso o obrigaria a apagar o proprio historico.
    op.create_index(
        "uq_site_subscription_vigente",
        "site_subscriptions",
        ["site_id"],
        unique=True,
        postgresql_where=sa.text("estado <> 'encerrada'"),
    )

    # ------------------------------------------------------------- cobrancas
    op.create_table(
        "platform_invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_subscription_id",
            UUID(as_uuid=True),
            # RESTRICT: o historico de cobranca nao some com o contrato.
            sa.ForeignKey("site_subscriptions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("emitida_em", sa.Date(), nullable=False),
        sa.Column("vence_em", sa.Date(), nullable=False),
        sa.Column("paga_em", sa.Date(), nullable=True),
        # Tres parcelas separadas: "R$ 480" nao explica nada, e o lojista precisa
        # conferir cada uma contra o proprio extrato.
        sa.Column("assinatura_brl", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("pontos_brl", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("transacao_brl", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("multa_brl", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_brl", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("pontos_cobrados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("faturamento_base_brl", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("estado", sa.String(12), nullable=False, server_default="aberta"),
        *_carimbo(),
        # A protecao contra faturar o mesmo mes duas vezes: o defeito classico de
        # cobranca recorrente, e o unico que realmente machuca o cliente.
        sa.UniqueConstraint(
            "site_subscription_id", "competencia", name="uq_platform_invoices_competencia"
        ),
    )
    op.create_check_constraint(
        "estado_conhecido", "platform_invoices", "estado IN ('aberta', 'paga', 'cancelada')"
    )
    op.create_check_constraint("total_nao_negativo", "platform_invoices", "total_brl >= 0")
    op.create_check_constraint(
        "pagamento_completo", "platform_invoices", "estado <> 'paga' OR paga_em IS NOT NULL"
    )
    op.create_index("ix_platform_invoices_competencia", "platform_invoices", ["competencia"])


def downgrade() -> None:
    op.drop_index("ix_platform_invoices_competencia", table_name="platform_invoices")
    op.drop_table("platform_invoices")
    op.drop_index("uq_site_subscription_vigente", table_name="site_subscriptions")
    op.drop_table("site_subscriptions")
    op.drop_table("platform_plans")
