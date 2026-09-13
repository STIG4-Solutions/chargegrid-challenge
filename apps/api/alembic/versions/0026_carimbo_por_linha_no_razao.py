"""O razao carimba cada linha no instante dela, nao no da transacao.

`created_at` herda `server_default=now()` do `TimestampMixin`, e no Postgres
`now()` e' o instante em que a TRANSACAO comecou - identico para todas as linhas
gravadas nela. Para quase toda tabela isso e' irrelevante. Para um razao, nao:

  - o extrato promete "do mais novo ao mais antigo", e ordena por
    `created_at DESC, id DESC`. Com carimbos iguais, o desempate cai no `id`,
    que e' UUID sorteado - ordem arbitraria;
  - `balance_after` so' faz sentido em ordem. Duas linhas fora de sequencia
    fazem o saldo corrido parecer andar para tras na tela, e o teste de fumaca
    tem uma checagem exatamente sobre isso.

E ACONTECE EM PRODUCAO, nao so' em teste: `conceder_pendentes` credita todas as
recompensas pendentes e da UM commit. Um motorista que concluiu duas missoes na
mesma passada do worker recebe duas linhas com o mesmo carimbo.

`clock_timestamp()` le o relogio a cada chamada, entao cada INSERT recebe o seu.
A alternativa seria uma coluna de sequencia, que resolveria o mesmo com mais
peso - e o que se quer aqui e' justamente o instante do lancamento.

So' `wallet_entries` muda. As demais tabelas continuam com `now()`, que e' o
comportamento correto para elas: `created_at` de uma sessao ou de uma fatura
descreve a operacao, e todas as linhas da mesma operacao compartilharem o
carimbo e' informacao, nao ruido.

Revision ID: 0026_carimbo_por_linha
Revises: 0025_estorno_e_ajuste
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0026_carimbo_por_linha"
down_revision: str | None = "0025_estorno_e_ajuste"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "wallet_entries",
        "created_at",
        server_default=sa.text("clock_timestamp()"),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "wallet_entries",
        "created_at",
        server_default=sa.text("now()"),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
