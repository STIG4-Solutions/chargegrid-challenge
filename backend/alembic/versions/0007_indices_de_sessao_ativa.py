"""Corrige o predicado do indice de sessao ativa e o estende ao motorista.

O indice uq_active_session_per_charge_point existia desde a 0005 e nunca
protegeu nada. Ele filtrava state IN ('authorizing', 'charging', ...) - os
VALORES do StrEnum -, mas Enum(SessionState, native_enum=False) grava o NOME do
membro: 'AUTHORIZING', 'CHARGING'. O predicado casava com zero linhas, entao o
indice indexava zero linhas e a unicidade nunca era exigida. Valia em producao
tambem; a unica barreira contra duas sessoes no mesmo ponto era o SELECT da
aplicacao, que duas requisicoes simultaneas atravessam juntas.

A guarda de uma-vaga-por-motorista, adicionada depois, tinha o mesmo problema
pela raiz oposta: nunca teve indice nenhum. Ganha um aqui. user_id nulo (cartao
RFID sem usuario vinculado) fica de fora naturalmente - o Postgres trata NULLs
como distintos num indice unico, que e' exatamente o comportamento desejado.

Revision ID: 0007_indices_de_sessao_ativa
Revises: 0006_wallet_topups
Create Date: 2026-08-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_indices_de_sessao_ativa"
down_revision: str | None = "0006_wallet_topups"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Os NOMES dos membros, que e' o que a coluna guarda.
ATIVOS = "'AUTHORIZING', 'QUEUED', 'STARTING', 'CHARGING', 'SUSPENDED', 'FINISHING'"
# O que a 0005 usava, e que nunca casou com linha nenhuma.
ATIVOS_ANTIGOS = "'authorizing', 'queued', 'starting', 'charging', 'suspended', 'finishing'"


def _recriar(estados: str) -> None:
    op.execute("DROP INDEX IF EXISTS uq_active_session_per_charge_point")
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_active_session_per_charge_point
        ON charging_sessions (charge_point_id)
        WHERE state IN ({estados})
        """
    )


def upgrade() -> None:
    _recriar(ATIVOS)
    op.execute("DROP INDEX IF EXISTS uq_active_session_per_driver")
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_active_session_per_driver
        ON charging_sessions (user_id)
        WHERE user_id IS NOT NULL AND state IN ({ATIVOS})
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_active_session_per_driver")
    _recriar(ATIVOS_ANTIGOS)
