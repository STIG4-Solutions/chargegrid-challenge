"""Tokens de entrada servidos do cache de prompt do Azure.

O cache cobra com desconto a parte repetida da requisicao (ferramentas e
instrucoes). Sem esta coluna, o custo estimado a partir de `tokens_entrada`
fica maior do que a fatura, e a cota diaria de tokens nao tem como saber quanto
do consumo foi barato.

Coluna nova numa migration nova, e nao na 0028: uma migration ja' aplicada nao
muda, senao o schema passa a depender de QUANDO cada banco rodou.

Revision ID: 0029_tokens_em_cache
Revises: 0028_assistente
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029_tokens_em_cache"
down_revision: str | None = "0028_assistente"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("assistant_messages", sa.Column("tokens_em_cache", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("assistant_messages", "tokens_em_cache")
