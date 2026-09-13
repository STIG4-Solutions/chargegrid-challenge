"""Ajuste manual passa a exigir MOTIVO e RESPONSAVEL.

`wallet_entries.origem` aceita `estorno` e `ajuste` desde a 0021, e nada no
sistema criava nenhum dos dois. Eram dois valores declarados e inalcancaveis -
mesma classe de defeito que `inadimplente` (0023) e `patrocinador = 'frota'`
(0024).

Os dois ganham caminho agora, e sao coisas diferentes:

  - ESTORNO devolve o que saiu. Nasce de uma fatura, tem valor determinado por
    ela e nao depende de ninguem decidir quanto. Nao precisa de justificativa
    porque a fatura E' a justificativa.
  - AJUSTE cria ou destroi saldo por decisao humana. Nao ha documento por tras,
    e e' o unico lancamento do razao em que alguem escolhe o numero.

Dai as duas colunas, e o CHECK que so' vale para `ajuste`:

  `motivo`      - por que o saldo mudou. Ajuste sem motivo e' dinheiro que
                  aparece na conta de alguem sem ninguem saber explicar. Num
                  razao, isso e' o defeito, nao o campo faltando.
  `criado_por`  - QUEM decidiu. SET NULL porque a saida do funcionario nao pode
                  apagar o lancamento, mas enquanto ele existir o nome fica.

As linhas de abertura que a 0021 criou sao `ajuste` sem motivo, e passariam a
violar o CHECK. Recebem o motivo que sempre tiveram, so' que agora escrito.

Revision ID: 0025_estorno_e_ajuste
Revises: 0024_campanha_de_frota
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0025_estorno_e_ajuste"
down_revision: str | None = "0024_campanha_de_frota"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("wallet_entries", sa.Column("motivo", sa.String(200), nullable=True))
    op.add_column(
        "wallet_entries",
        sa.Column(
            "criado_por",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # As aberturas da 0021 e as do seed. O motivo delas sempre existiu - estava
    # no docstring da migration, e nao na linha. Agora esta na linha.
    op.execute(
        "UPDATE wallet_entries SET motivo = 'Saldo de abertura do razão' "
        "WHERE origem = 'ajuste' AND motivo IS NULL"
    )

    op.create_check_constraint(
        "ajuste_com_motivo",
        "wallet_entries",
        "origem <> 'ajuste' OR motivo IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ajuste_com_motivo", "wallet_entries", type_="check")
    op.drop_column("wallet_entries", "criado_por")
    op.drop_column("wallet_entries", "motivo")
