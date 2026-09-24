"""Conversas do assistente do operador.

Duas tabelas: a conversa, amarrada a um usuario e a uma praca, e as mensagens
dela - inclusive as chamadas de ferramenta, que sao o rastro de onde saiu cada
numero que o modelo respondeu.

A FK da mensagem se chama `conversa_id`: com `conversation_id` a convencao de
nome da FK passava de 60 caracteres, e o Postgres trunca em 63 sem avisar.

Revision ID: 0028_assistente
Revises: 0027_catalogo_de_planos
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0028_assistente"
down_revision: str | None = "0027_catalogo_de_planos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assistant_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("titulo", sa.String(120), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_assistant_conversations_user_updated",
        "assistant_conversations",
        ["user_id", "updated_at"],
    )

    op.create_table(
        "assistant_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversa_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("papel", sa.String(16), nullable=False),
        sa.Column("conteudo", sa.Text(), nullable=True),
        sa.Column("ferramenta", sa.String(64), nullable=True),
        sa.Column("argumentos", postgresql.JSONB(), nullable=True),
        sa.Column("resultado", sa.Text(), nullable=True),
        sa.Column("tokens_entrada", sa.Integer(), nullable=True),
        sa.Column("tokens_saida", sa.Integer(), nullable=True),
        sa.Column("latencia_ms", sa.Integer(), nullable=True),
        sa.Column("fim", sa.String(32), nullable=True),
        sa.Column("bloqueio", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    # Cobre as duas leituras quentes: o historico de uma conversa, em ordem, e
    # a cota por minuto/dia, que conta mensagens recentes do usuario.
    op.create_index(
        "ix_assistant_messages_conversa_created",
        "assistant_messages",
        ["conversa_id", "created_at"],
    )
    op.create_check_constraint(
        "papel",
        "assistant_messages",
        "papel IN ('user', 'assistant', 'tool')",
    )
    op.create_check_constraint(
        "ferramenta_nomeada",
        "assistant_messages",
        "papel <> 'tool' OR ferramenta IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_table("assistant_messages")
    op.drop_table("assistant_conversations")
