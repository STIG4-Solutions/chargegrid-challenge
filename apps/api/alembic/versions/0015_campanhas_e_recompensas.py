"""Campanha, missao, progresso e recompensa.

O produto cobrava recarga e administrava potencia, e nao tinha nenhum mecanismo
de retencao: o motorista nao tinha motivo para voltar ao mesmo eletroposto, e o
estabelecimento nao tinha ferramenta para influenciar isso.

Quatro tabelas, quatro perguntas. `campaigns` diz QUEM PAGA - e' a unidade
comercial, com patrocinador, periodo, orcamento e um unico tipo de beneficio.
`missions` diz O QUE PRECISA ACONTECER. `mission_progress` diz ONDE CADA UM
ESTA, materializado e nao derivado. `rewards` diz O QUE FOI CONCEDIDO, e e' a
unica que sobrevive a campanha que a originou, porque e' dinheiro.

DOIS BOLSOS. Desconto na fatura sai do estabelecimento - e' a margem dele
naquela sessao, cedida onde nasce. Cashback na carteira sai da rede: credito em
carteira so' vale dentro da plataforma e e' resgatavel em qualquer lugar, entao
um estabelecimento que o pagasse estaria financiando uma recarga que amanha
acontece no concorrente ao lado.

CARTEIRA. `wallet_topups` ganha `origem`. A tabela ja existia para responder "de
onde veio esse dinheiro" e nao conseguia: `provider` diz por qual MEIO o credito
entrou, nunca por que.

Revision ID: 0015_campanhas_e_recompensas
Revises: 0014_slug_do_site
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_campanhas_e_recompensas"
down_revision: str | None = "0014_slug_do_site"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = sa.dialects.postgresql.UUID

PATROCINADORES = ("rede", "site", "frota")
BENEFICIOS = ("desconto_pct", "desconto_fixo", "cashback_pct", "cashback_fixo")
METRICAS = (
    "sessoes",
    "energia_kwh",
    "energia_verde_kwh",
    "valor_brl",
    "dias_distintos",
    "sessoes_fora_de_ponta",
)
JANELAS = ("campanha", "mensal", "semanal")
ESTADOS = ("pendente", "creditada", "aplicada", "expirada", "cancelada")
ORIGENS = ("topup", "cashback", "estorno", "ajuste")


def _em(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def _carimbo() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade() -> None:
    # ------------------------------------------------------------- campanhas
    op.create_table(
        "campaigns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("patrocinador", sa.String(16), nullable=False),
        # CASCADE nos dois: a campanha nao sobrevive a quem a financiava. Sem o
        # patrocinador nao ha orcamento nem a quem cobrar o que ja foi concedido.
        sa.Column(
            "site_id", UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column(
            "fleet_id",
            UUID(as_uuid=True),
            sa.ForeignKey("fleets.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("beneficio_tipo", sa.String(16), nullable=False),
        sa.Column("beneficio_valor", sa.Numeric(10, 4), nullable=False),
        sa.Column("teto_por_recompensa", sa.Numeric(10, 2), nullable=True),
        sa.Column("orcamento_brl", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("consumido_brl", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("limite_por_motorista", sa.Integer(), nullable=True),
        *_carimbo(),
    )
    # Patrocinador e escopo nao podem divergir: "campanha de rede com site_id"
    # deixaria o banco sem saber de qual bolso saiu o dinheiro.
    op.create_check_constraint(
        "ck_campaigns_escopo_coerente",
        "campaigns",
        "(patrocinador = 'site' AND site_id IS NOT NULL AND fleet_id IS NULL)"
        " OR (patrocinador = 'frota' AND fleet_id IS NOT NULL AND site_id IS NULL)"
        " OR (patrocinador = 'rede' AND site_id IS NULL AND fleet_id IS NULL)",
    )
    op.create_check_constraint(
        "ck_campaigns_patrocinador", "campaigns", f"patrocinador IN ({_em(PATROCINADORES)})"
    )
    op.create_check_constraint(
        "ck_campaigns_beneficio", "campaigns", f"beneficio_tipo IN ({_em(BENEFICIOS)})"
    )
    op.create_check_constraint("ck_campaigns_beneficio_valor", "campaigns", "beneficio_valor > 0")
    op.create_check_constraint("ck_campaigns_periodo_valido", "campaigns", "ends_at > starts_at")
    op.create_check_constraint(
        "ck_campaigns_consumido_nao_negativo", "campaigns", "consumido_brl >= 0"
    )
    op.create_index(
        "ix_campaigns_vigentes",
        "campaigns",
        ["starts_at", "ends_at"],
        postgresql_where=sa.text("ativa"),
    )
    op.create_index("ix_campaigns_site_id", "campaigns", ["site_id"])

    # --------------------------------------------------------------- missoes
    op.create_table(
        "missions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_id",
            UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("codigo", sa.String(40), nullable=False),
        sa.Column("titulo", sa.String(120), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metrica", sa.String(24), nullable=False),
        sa.Column("alvo", sa.Numeric(12, 3), nullable=False),
        sa.Column("janela", sa.String(12), nullable=False),
        sa.Column("repetivel", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_carimbo(),
        sa.UniqueConstraint("campaign_id", "codigo", name="uq_missions_campaign_id_codigo"),
    )
    op.create_check_constraint("ck_missions_metrica", "missions", f"metrica IN ({_em(METRICAS)})")
    op.create_check_constraint("ck_missions_janela", "missions", f"janela IN ({_em(JANELAS)})")
    op.create_check_constraint("ck_missions_alvo", "missions", "alvo > 0")

    # -------------------------------------------------------------- progresso
    op.create_table(
        "mission_progress",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "mission_id",
            UUID(as_uuid=True),
            sa.ForeignKey("missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # CASCADE: progresso e' dado pessoal e nao significa nada sem a pessoa.
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Nunca nulo: no Postgres, dois NULL sao distintos, e a chave unica
        # abaixo deixaria de impedir duas linhas para o mesmo periodo.
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("valor", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("concluida_em", sa.DateTime(timezone=True), nullable=True),
        # SET NULL, nao CASCADE: apagar a sessao nao pode apagar a conquista.
        sa.Column(
            "ultima_sessao_id",
            UUID(as_uuid=True),
            sa.ForeignKey("charging_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_carimbo(),
        # Permite `INSERT ... ON CONFLICT DO UPDATE`: progresso sem corrida entre
        # dois faturamentos simultaneos do mesmo motorista.
        sa.UniqueConstraint(
            "mission_id", "user_id", "periodo", name="uq_mission_progress_missao_motorista_periodo"
        ),
    )
    op.create_index(
        "ix_mission_progress_concluidas",
        "mission_progress",
        ["user_id"],
        postgresql_where=sa.text("concluida_em IS NOT NULL"),
    )

    # ------------------------------------------------------------ recompensas
    op.create_table(
        "rewards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # RESTRICT, divergindo das demais de proposito: recompensa e' dinheiro
        # concedido, e apagar a campanha nao pode apagar o rastro de quem ganhou.
        sa.Column(
            "campaign_id",
            UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "mission_progress_id",
            UUID(as_uuid=True),
            sa.ForeignKey("mission_progress.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("tipo", sa.String(16), nullable=False),
        sa.Column("valor_brl", sa.Numeric(12, 2), nullable=False),
        sa.Column("estado", sa.String(12), nullable=False, server_default="pendente"),
        sa.Column(
            "wallet_topup_id",
            UUID(as_uuid=True),
            sa.ForeignKey("wallet_topups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "invoice_id",
            UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        *_carimbo(),
    )
    op.create_check_constraint("ck_rewards_estado", "rewards", f"estado IN ({_em(ESTADOS)})")
    op.create_check_constraint("ck_rewards_tipo", "rewards", f"tipo IN ({_em(BENEFICIOS)})")
    op.create_check_constraint("ck_rewards_valor_nao_negativo", "rewards", "valor_brl >= 0")
    # Creditar exige dizer ONDE. Sem isto uma recompensa pode se declarar paga
    # sem que exista credito nenhum na carteira do motorista.
    op.create_check_constraint(
        "ck_rewards_credito_completo",
        "rewards",
        "estado <> 'creditada' OR wallet_topup_id IS NOT NULL",
    )
    # Uma missao concluida gera no maximo UMA recompensa viva. Dois workers
    # simultaneos: o segundo leva IntegrityError e desiste. Cancelar libera o
    # lugar para reconceder, sem apagar o historico.
    op.create_index(
        "uq_rewards_por_progresso",
        "rewards",
        ["mission_progress_id"],
        unique=True,
        postgresql_where=sa.text("mission_progress_id IS NOT NULL AND estado <> 'cancelada'"),
    )
    op.create_index(
        "ix_rewards_a_notificar",
        "rewards",
        ["user_id"],
        postgresql_where=sa.text("notified_at IS NULL"),
    )

    # ---------------------------------------------------------------- carteira
    op.add_column(
        "wallet_topups",
        sa.Column("origem", sa.String(16), nullable=False, server_default="topup"),
    )
    # Sem FK: `rewards.wallet_topup_id` ja aponta para ca', e uma segunda FK no
    # sentido inverso criaria ciclo entre as duas tabelas na criacao do schema.
    op.add_column("wallet_topups", sa.Column("origem_ref", UUID(as_uuid=True), nullable=True))
    op.create_check_constraint(
        "ck_wallet_topups_origem", "wallet_topups", f"origem IN ({_em(ORIGENS)})"
    )


def downgrade() -> None:
    op.drop_constraint("ck_wallet_topups_origem", "wallet_topups", type_="check")
    op.drop_column("wallet_topups", "origem_ref")
    op.drop_column("wallet_topups", "origem")

    op.drop_index("ix_rewards_a_notificar", table_name="rewards")
    op.drop_index("uq_rewards_por_progresso", table_name="rewards")
    op.drop_table("rewards")

    op.drop_index("ix_mission_progress_concluidas", table_name="mission_progress")
    op.drop_table("mission_progress")

    op.drop_table("missions")

    op.drop_index("ix_campaigns_site_id", table_name="campaigns")
    op.drop_index("ix_campaigns_vigentes", table_name="campaigns")
    op.drop_table("campaigns")
