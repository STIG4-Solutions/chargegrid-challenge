"""A carteira passa a ter razao de verdade: credito E debito.

`wallet_topups` so' guardava entrada. O debito - pagar uma fatura com saldo -
alterava `users.wallet_balance` e nao deixava linha nenhuma. O efeito e' que a
propria pergunta que a tabela foi criada para responder ("de onde veio esse
dinheiro?") nao tinha resposta no sentido inverso: o motorista via o saldo cair
e nao havia o que conferir.

Isso ficou pior com a gamificacao. Cashback de missao credita a carteira, entao o
saldo muda sozinho - e sem razao completa o motorista ve um numero diferente sem
explicacao nenhuma.

TRES MUDANCAS, e a ordem importa:

1. A tabela vira `wallet_entries` e aceita valor negativo. Uma tabela chamada
   "topups" contendo debito seria um nome que mente no schema, e nome que mente
   e' defeito que so' aparece meses depois. Duas tabelas separadas seriam
   piores: `balance_after` deixa de fazer sentido quando os movimentos se
   intercalam, e reconciliar exigiria UNION.

2. O passado e' reconstruido. Os debitos que nunca foram gravados sao deduzidos
   de `payments` (method WALLET, capturado); o que sobra de diferenca vira uma
   linha de abertura por motorista, como qualquer razao que herda saldo. Sem
   isso a invariante abaixo nasceria falsa.

3. `SUM(amount) = users.wallet_balance` passa a ser conferivel. E' essa a
   invariante que o teste fixa, e e' ela que faz a diferenca entre um razao e
   uma lista de eventos soltos.

Revision ID: 0021_razao_da_carteira
Revises: 0020_fonte_da_previsao
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0021_razao_da_carteira"
down_revision: str | None = "0020_fonte_da_previsao"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("wallet_topups", "wallet_entries")
    op.execute("ALTER INDEX ix_wallet_topups_user_id RENAME TO ix_wallet_entries_user_id")
    op.execute("ALTER INDEX ix_wallet_topups_provider_ref RENAME TO ix_wallet_entries_provider_ref")
    op.execute(
        "ALTER INDEX ix_wallet_topups_idempotency_key RENAME TO ix_wallet_entries_idempotency_key"
    )
    op.execute("ALTER TABLE wallet_entries RENAME CONSTRAINT pk_wallet_topups TO pk_wallet_entries")
    op.execute(
        "ALTER TABLE wallet_entries RENAME CONSTRAINT "
        "fk_wallet_topups_user_id_users TO fk_wallet_entries_user_id_users"
    )

    # A coluna em `rewards` tambem passaria a mentir depois do rename.
    op.alter_column("rewards", "wallet_topup_id", new_column_name="wallet_entry_id")
    op.execute(
        "ALTER TABLE rewards RENAME CONSTRAINT "
        "fk_rewards_wallet_topup_id_wallet_topups TO fk_rewards_wallet_entry_id_wallet_entries"
    )

    # O debito diz QUAL fatura pagou. Sem isto o extrato mostra "-R$ 43,20" e o
    # motorista nao tem como amarrar a linha a recarga que fez.
    op.add_column(
        "wallet_entries",
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # ------------------------------------------------------- reconstrucao
    # Os debitos que nunca foram gravados. `payments` ja tem valor, fatura e
    # instante - e' tudo que a linha precisa; o que ele nao tem e' o saldo
    # resultante, recalculado logo abaixo para a tabela inteira.
    op.execute(
        """
        INSERT INTO wallet_entries (
            id, user_id, amount, balance_after, idempotency_key,
            provider, provider_ref, origem, origem_ref, invoice_id,
            created_at, updated_at
        )
        SELECT gen_random_uuid(), i.user_id, -p.amount, 0,
               'migracao:pagamento:' || p.id::text,
               'wallet', p.provider_ref, 'pagamento', NULL, i.id,
               COALESCE(p.captured_at, p.created_at), now()
        FROM payments p
        JOIN invoices i ON i.id = p.invoice_id
        WHERE p.method = 'wallet' AND p.status = 'captured' AND i.user_id IS NOT NULL
        """
    )

    # Saldo herdado. Qualquer diferenca que sobra e' dinheiro que entrou sem
    # passar por aqui - o seed credita direto, por exemplo. Um razao que comeca
    # no meio precisa declarar de quanto comecou, senao a soma nunca fecha.
    op.execute(
        """
        INSERT INTO wallet_entries (
            id, user_id, amount, balance_after, idempotency_key,
            provider, provider_ref, origem, origem_ref, invoice_id,
            created_at, updated_at
        )
        SELECT gen_random_uuid(), u.id, d.delta, 0,
               'migracao:abertura:' || u.id::text,
               'migracao', NULL, 'ajuste', NULL, NULL,
               u.created_at, now()
        FROM users u
        JOIN LATERAL (
            SELECT u.wallet_balance
                 - COALESCE((SELECT SUM(e.amount) FROM wallet_entries e
                             WHERE e.user_id = u.id), 0) AS delta
        ) d ON true
        WHERE d.delta <> 0
        """
    )

    # `balance_after` so' faz sentido em ordem. Recalcular a tabela inteira e'
    # obrigatorio: as linhas novas entraram no meio do historico de quem ja
    # tinha credito, e o saldo gravado nas antigas passou a estar errado.
    op.execute(
        """
        WITH corrido AS (
            SELECT id, SUM(amount) OVER (
                       PARTITION BY user_id ORDER BY created_at, id
                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                   ) AS saldo
            FROM wallet_entries
        )
        UPDATE wallet_entries e SET balance_after = c.saldo
        FROM corrido c WHERE c.id = e.id
        """
    )

    # ------------------------------------------------------- as guardas
    # SQL cru de proposito: `op.drop_constraint` aplica a convencao
    # `ck_<tabela>_<nome>` ao que recebe, e o nome herdado ja' vem dobrado - o
    # modelo declarava o nome completo e a convencao prefixava por cima. Nao
    # existe nome curto que gere `ck_wallet_topups_ck_wallet_topups_origem`
    # numa tabela que agora se chama outra coisa.
    op.execute(
        "ALTER TABLE wallet_entries "
        "DROP CONSTRAINT ck_wallet_topups_ck_wallet_topups_origem"
    )
    op.create_check_constraint(
        "origem",
        "wallet_entries",
        "origem IN ('topup', 'cashback', 'estorno', 'ajuste', 'pagamento')",
    )
    # O sinal nao pode divergir da origem. Um 'cashback' negativo ou um
    # 'pagamento' positivo passariam por qualquer validacao Python e so'
    # apareceriam quando o saldo de alguem nao fechasse.
    #
    # `ajuste` e' o unico de sinal livre, e de proposito: correcao de operador
    # existe nos dois sentidos, e e' tambem a linha de abertura desta migration.
    op.create_check_constraint(
        "sinal_da_origem",
        "wallet_entries",
        "(origem = 'pagamento' AND amount < 0) "
        "OR (origem IN ('topup', 'cashback', 'estorno') AND amount > 0) "
        "OR (origem = 'ajuste' AND amount <> 0)",
    )


def downgrade() -> None:
    op.execute("DELETE FROM wallet_entries WHERE idempotency_key LIKE 'migracao:%'")
    op.execute("DELETE FROM wallet_entries WHERE origem = 'pagamento'")
    op.drop_constraint("sinal_da_origem", "wallet_entries", type_="check")
    op.drop_constraint("origem", "wallet_entries", type_="check")
    op.create_check_constraint(
        "origem", "wallet_entries", "origem IN ('topup', 'cashback', 'estorno', 'ajuste')"
    )
    op.drop_column("wallet_entries", "invoice_id")
    op.execute(
        "ALTER TABLE rewards RENAME CONSTRAINT "
        "fk_rewards_wallet_entry_id_wallet_entries TO fk_rewards_wallet_topup_id_wallet_topups"
    )
    op.alter_column("rewards", "wallet_entry_id", new_column_name="wallet_topup_id")
    op.execute(
        "ALTER TABLE wallet_entries RENAME CONSTRAINT "
        "fk_wallet_entries_user_id_users TO fk_wallet_topups_user_id_users"
    )
    op.execute("ALTER TABLE wallet_entries RENAME CONSTRAINT pk_wallet_entries TO pk_wallet_topups")
    op.execute("ALTER INDEX ix_wallet_entries_user_id RENAME TO ix_wallet_topups_user_id")
    op.execute("ALTER INDEX ix_wallet_entries_provider_ref RENAME TO ix_wallet_topups_provider_ref")
    op.execute(
        "ALTER INDEX ix_wallet_entries_idempotency_key RENAME TO ix_wallet_topups_idempotency_key"
    )
    op.rename_table("wallet_entries", "wallet_topups")
