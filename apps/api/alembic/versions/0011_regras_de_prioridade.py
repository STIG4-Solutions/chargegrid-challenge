"""Regras de prioridade nomeadas.

`charge_points.priority` decide quem e servido primeiro quando falta potencia -
a decisao mais consequente do rateio - e e' um inteiro sem explicacao. O
operador ve "100" e nao sabe se e muito, nem por que aquele ponto ficou assim.

Esta tabela da nome ao numero, diz a que pontos ele se aplica e, o que o
inteiro sozinho nao permitia, deixa a prioridade mudar com a hora: a frota
corporativa precisa sair carregada as 7h, mas durante o dia quem paga a tarifa
cheia e o visitante. Com um valor fixo era preciso escolher um turno e viver
com o outro errado.

Revision ID: 0011_regras_de_prioridade
Revises: 0010_historico_de_falhas
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_regras_de_prioridade"
down_revision: str | None = "0010_historico_de_falhas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "priority_rules",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nome", sa.String(80), nullable=False),
        sa.Column("prioridade", sa.Integer(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criterio_tipo", sa.String(16), nullable=False, server_default="sempre"),
        sa.Column("criterio_valor", sa.String(400), nullable=True),
        sa.Column("janela_inicio", sa.Time(), nullable=True),
        sa.Column("janela_fim", sa.Time(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    # A resolucao le as regras do site em ordem crescente de `ordem` e para na
    # primeira que casa. O indice cobre exatamente essa leitura, que roda a cada
    # ciclo do rebalanceador.
    op.create_index("ix_priority_rules_site_ordem", "priority_rules", ["site_id", "ordem"])

    # Uma janela so faz sentido com os dois lados preenchidos: com um so, nao da
    # para saber se o outro extremo e' o inicio ou o fim do dia, e a regra
    # passaria a valer em horarios que ninguem pediu.
    op.create_check_constraint(
        "janela_completa",
        "priority_rules",
        "(janela_inicio IS NULL) = (janela_fim IS NULL)",
    )
    op.create_check_constraint(
        "criterio",
        "priority_rules",
        "criterio_tipo IN ('sempre', 'ponto', 'conector')",
    )
    # 'sempre' casa com tudo e nao usa valor; os outros dois sao inuteis sem ele.
    op.create_check_constraint(
        "valor_quando_preciso",
        "priority_rules",
        "criterio_tipo = 'sempre' OR criterio_valor IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_table("priority_rules")
