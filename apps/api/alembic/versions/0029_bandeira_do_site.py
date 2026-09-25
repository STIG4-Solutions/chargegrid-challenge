"""Bandeira do site e multiplicador travado na sessao.

O rebalanceador passa a gravar no site a bandeira que calcula a cada ciclo
(cor, multiplicador, folga e motivo, com o instante do calculo). Fica em `sites`
e nao em `tariffs`: a tarifa e' configuracao do operador, a bandeira e' estado
operacional que muda a cada 15 s.

A sessao ganha o multiplicador e a cor copiados do site no inicio da recarga.
Nulos para todas as sessoes existentes - e' o que faz o motor tratar o passado
exatamente como tratava.

Revision ID: 0029_bandeira_do_site
Revises: 0028_previsao_por_janela
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029_bandeira_do_site"
down_revision: str | None = "0028_previsao_por_janela"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sites", sa.Column("bandeira_cor", sa.String(10), nullable=True))
    op.add_column("sites", sa.Column("bandeira_multiplicador", sa.Numeric(5, 3), nullable=True))
    op.add_column("sites", sa.Column("bandeira_folga_pct", sa.Numeric(5, 1), nullable=True))
    op.add_column("sites", sa.Column("bandeira_motivo", sa.String(160), nullable=True))
    op.add_column(
        "sites", sa.Column("bandeira_calculada_em", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "charging_sessions", sa.Column("multiplicador_travado", sa.Numeric(5, 3), nullable=True)
    )
    op.add_column("charging_sessions", sa.Column("cor_travada", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("charging_sessions", "cor_travada")
    op.drop_column("charging_sessions", "multiplicador_travado")
    op.drop_column("sites", "bandeira_calculada_em")
    op.drop_column("sites", "bandeira_motivo")
    op.drop_column("sites", "bandeira_folga_pct")
    op.drop_column("sites", "bandeira_multiplicador")
    op.drop_column("sites", "bandeira_cor")
