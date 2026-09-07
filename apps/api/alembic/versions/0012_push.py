"""Notificacao push: aparelhos registrados e marca de envio nos eventos.

O app fazia polling. Funciona enquanto ele esta aberto na tela certa - e o
momento em que a notificacao importa e' justamente o outro: o motorista foi
almocar, a recarga terminou, e o conector fica ocupado gerando taxa de
ociosidade para ele e fila para os outros.

Os eventos ja existiam em `session_events`. O que faltava era para onde
mandar (push_devices) e o registro de que ja foi mandado (notified_at). A
marca fica na propria tabela de eventos em vez de uma fila separada: o evento
ja e' a fonte da verdade, e duplicar isso criaria duas historias que podem
divergir.

Revision ID: 0012_push
Revises: 0011_regras_de_prioridade
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_push"
down_revision: str | None = "0011_regras_de_prioridade"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "push_devices",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(200), nullable=False),
        sa.Column("platform", sa.String(16), nullable=False, server_default="android"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_push_devices_user", "push_devices", ["user_id"])
    # Unico de verdade, no banco: dois registros do mesmo aparelho fariam a
    # notificacao sair duplicada no mesmo celular. E' o banco que decide, nao
    # um SELECT antes do INSERT - dois logins simultaneos passariam pela
    # verificacao juntos.
    op.create_unique_constraint("uq_push_devices_token", "push_devices", ["token"])

    op.add_column(
        "session_events", sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Indice parcial: o worker so' procura o que ainda nao foi enviado, e essa
    # fatia e' minuscula perto do historico inteiro de eventos. Indexar a tabela
    # toda desperdicaria espaco proporcional a algo que nunca e' consultado.
    op.create_index(
        "ix_session_events_pendentes",
        "session_events",
        ["occurred_at"],
        postgresql_where=sa.text("notified_at IS NULL"),
    )

    # Tudo que ja aconteceu nasce marcado como notificado.
    #
    # Sem isto, a primeira volta do worker num sistema em uso encontraria o
    # historico inteiro pendente e dispararia "recarga concluida" para sessoes
    # de dias atras - dezenas de notificacoes de uma vez, sobre carros que o
    # motorista ja levou para casa. A feature comeca a valer daqui para frente.
    op.execute("UPDATE session_events SET notified_at = now() WHERE notified_at IS NULL")


def downgrade() -> None:
    op.drop_index("ix_session_events_pendentes", table_name="session_events")
    op.drop_column("session_events", "notified_at")
    op.drop_table("push_devices")
