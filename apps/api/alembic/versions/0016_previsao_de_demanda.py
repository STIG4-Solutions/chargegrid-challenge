"""Previsao de energia e faturamento do proximo mes, por site.

A API so' LE esta tabela. Quem escreve e' um job offline (`apps/forecast`), que
carrega o artefato do modelo, monta o painel diario a partir de
`charging_sessions` e grava o resultado aqui.

A separacao existe por tres motivos concretos. O processo do FastAPI tambem roda
os workers, e um `import lightgbm` que falhe derrubaria junto o rebalanceamento
de potencia - previsao de faturamento nao pode compartilhar processo com o que
impede o disjuntor de abrir. O modelo preve MES, entao servir em processo seria
pagar custo continuo por um calculo que roda doze vezes ao ano. E `lgb.predict`
e' CPU-bound, o que numa API async exigiria `run_in_executor`.

AS DUAS COLUNAS DE COBERTURA. O modelo entrega uma faixa p10-p90 que deveria
conter o valor real em ~80% das vezes; o backtest do proprio pipeline mediu
66,8%. A faixa e' mais estreita do que anuncia. Guardar o declarado e o medido
lado a lado faz a divergencia virar dado na linha, e nao nota de rodape.

Revision ID: 0016_previsao_de_demanda
Revises: 0015_campanhas_e_recompensas
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_previsao_de_demanda"
down_revision: str | None = "0015_campanhas_e_recompensas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = sa.dialects.postgresql.UUID


def upgrade() -> None:
    op.create_table(
        "site_forecasts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("gerado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kwh_previsto", sa.Numeric(12, 3), nullable=False),
        sa.Column("kwh_p10", sa.Numeric(12, 3), nullable=True),
        sa.Column("kwh_p90", sa.Numeric(12, 3), nullable=True),
        sa.Column("faturamento_previsto_brl", sa.Numeric(12, 2), nullable=True),
        sa.Column("fat_p10_brl", sa.Numeric(12, 2), nullable=True),
        sa.Column("fat_p90_brl", sa.Numeric(12, 2), nullable=True),
        sa.Column("media_diaria_28d", sa.Numeric(12, 3), nullable=True),
        sa.Column("modelo_aplicavel", sa.Boolean(), nullable=False),
        sa.Column("modelo_versao", sa.String(40), nullable=True),
        sa.Column("dias_de_historico", sa.Integer(), nullable=True),
        sa.Column("cobertura_declarada_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("cobertura_medida_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        # A previsao vigente de um mes e' uma so'; reexecutar o job atualiza em
        # vez de empilhar versoes que ninguem sabe qual vale.
        sa.UniqueConstraint("site_id", "competencia", name="uq_site_forecasts_site_competencia"),
    )
    # Banda sem os dois extremos nao e' banda: meio intervalo na tela mente sobre
    # a incerteza que o modelo declarou.
    op.create_check_constraint(
        "ck_site_forecasts_banda_completa",
        "site_forecasts",
        "(kwh_p10 IS NULL AND kwh_p90 IS NULL) OR (kwh_p10 IS NOT NULL AND kwh_p90 IS NOT NULL)",
    )
    # Fallback nao tem banda. Quando o modelo nao se aplica o numero e' a media
    # dos ultimos 28 dias, e desenhar incerteza em volta dela daria ares de
    # previsao a uma conta de padaria.
    op.create_check_constraint(
        "ck_site_forecasts_fallback_sem_banda",
        "site_forecasts",
        "modelo_aplicavel OR kwh_p10 IS NULL",
    )
    op.create_check_constraint(
        "ck_site_forecasts_kwh_nao_negativo", "site_forecasts", "kwh_previsto >= 0"
    )
    op.create_index("ix_site_forecasts_competencia", "site_forecasts", ["competencia"])


def downgrade() -> None:
    op.drop_index("ix_site_forecasts_competencia", table_name="site_forecasts")
    op.drop_table("site_forecasts")
