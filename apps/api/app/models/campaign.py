"""Campanha, missao, progresso e recompensa.

Sao quatro tabelas porque sao quatro perguntas diferentes, e junta-las perde a
resposta de alguma delas:

- `campaigns` responde QUEM PAGA. E' a unidade comercial: tem patrocinador,
  periodo, orcamento e um unico tipo de beneficio.
- `missions` responde O QUE PRECISA ACONTECER. E' a regra mensuravel que o
  motorista le na tela.
- `mission_progress` responde ONDE CADA UM ESTA. Materializado, nao derivado -
  ver o docstring da propria classe.
- `rewards` responde O QUE FOI CONCEDIDO. E' dinheiro, e por isso e' a unica
  que nao some junto com a campanha que a originou.

QUEM PAGA O QUE. Ha dois mecanismos, e trocar o bolso de qualquer um dos dois
produz um modelo que ninguem consegue sustentar:

- Desconto na fatura sai do ESTABELECIMENTO. E' a margem dele naquela sessao,
  cedida onde nasce, e o motorista ve o beneficio no momento de decidir onde
  carregar - que e' quando o comportamento muda.
- Cashback na carteira sai da REDE. Credito em carteira so' vale dentro da
  plataforma e e' resgatavel em qualquer lugar; se o estabelecimento A o
  pagasse, estaria financiando uma recarga que amanha acontece no B.

Uma campanha declara UM tipo de beneficio, garantido por check constraint.
"20% de desconto E 5% de cashback" e' o caminho para ninguem conseguir dizer
quanto a campanha custou.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

# Quem banca. Nao e' o mesmo que "para quem vale": uma campanha de rede pode
# valer so' para quem carrega num site, mas quem paga continua sendo a rede.
PATROCINADORES = ("rede", "site", "frota")

# O que o motorista leva. Desconto abate na hora, na propria fatura; cashback
# vira credito na carteira e so' se realiza na proxima recarga.
BENEFICIOS = ("desconto_pct", "desconto_fixo", "cashback_pct", "cashback_fixo")

# O que da' para medir. Toda metrica desta lista sai de coluna que JA existe em
# `charging_sessions` ou em `invoices` - nenhuma exige instrumentacao nova, e e'
# por isso que a lista termina aqui em vez de tentar cobrir tudo.
METRICAS = (
    "sessoes",
    "energia_kwh",
    "energia_verde_kwh",
    "valor_brl",
    "dias_distintos",
    "sessoes_fora_de_ponta",
)

# Em que periodo a conta zera.
JANELAS = ("campanha", "mensal", "semanal")

# Ciclo de vida da recompensa. `pendente` e' o que o worker procura; `creditada`
# exige dizer em qual credito ela virou dinheiro.
ESTADOS_DA_RECOMPENSA = ("pendente", "creditada", "aplicada", "expirada", "cancelada")


def _em(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


class Campaign(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        # Patrocinador e escopo nao podem divergir. Sem isto existe "campanha de
        # rede com site_id" no banco, e ninguem consegue dizer de qual bolso
        # saiu o dinheiro depois que ela acabou.
        CheckConstraint(
            "(patrocinador = 'site' AND site_id IS NOT NULL AND fleet_id IS NULL)"
            " OR (patrocinador = 'frota' AND fleet_id IS NOT NULL AND site_id IS NULL)"
            " OR (patrocinador = 'rede' AND site_id IS NULL AND fleet_id IS NULL)",
            name="ck_campaigns_escopo_coerente",
        ),
        CheckConstraint(
            f"patrocinador IN ({_em(PATROCINADORES)})", name="ck_campaigns_patrocinador"
        ),
        CheckConstraint(f"beneficio_tipo IN ({_em(BENEFICIOS)})", name="ck_campaigns_beneficio"),
        CheckConstraint("beneficio_valor > 0", name="ck_campaigns_beneficio_valor"),
        CheckConstraint("ends_at > starts_at", name="ck_campaigns_periodo_valido"),
        CheckConstraint("consumido_brl >= 0", name="ck_campaigns_consumido_nao_negativo"),
        # A consulta quente e' "quais valem agora". A maioria das linhas envelhece
        # para inativa e nunca mais e' lida.
        Index(
            "ix_campaigns_vigentes",
            "starts_at",
            "ends_at",
            postgresql_where=text("ativa"),
        ),
        Index("ix_campaigns_site_id", "site_id"),
    )

    patrocinador: Mapped[str] = mapped_column(String(16), nullable=False)
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE")
    )
    # CASCADE nos dois: a campanha nao sobrevive a quem a financiava. Apagado o
    # patrocinador, nao ha mais orcamento nem a quem cobrar.
    fleet_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fleets.id", ondelete="CASCADE")
    )

    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    beneficio_tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    beneficio_valor: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    # Trava o valor de UMA concessao. Percentual sem teto numa recarga grande
    # gasta o orcamento inteiro numa pessoa so'.
    teto_por_recompensa: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    orcamento_brl: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    consumido_brl: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    limite_por_motorista: Mapped[int | None] = mapped_column(Integer)

    missions = relationship(
        "Mission", back_populates="campaign", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def orcamento_disponivel(self) -> Decimal:
        return Decimal(str(self.orcamento_brl)) - Decimal(str(self.consumido_brl))


class Mission(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "missions"
    __table_args__ = (
        UniqueConstraint("campaign_id", "codigo", name="uq_missions_campaign_id_codigo"),
        CheckConstraint(f"metrica IN ({_em(METRICAS)})", name="ck_missions_metrica"),
        CheckConstraint(f"janela IN ({_em(JANELAS)})", name="ck_missions_janela"),
        CheckConstraint("alvo > 0", name="ck_missions_alvo"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    codigo: Mapped[str] = mapped_column(String(40), nullable=False)
    titulo: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    ordem: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    metrica: Mapped[str] = mapped_column(String(24), nullable=False)
    alvo: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    janela: Mapped[str] = mapped_column(String(12), nullable=False)
    repetivel: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    campaign = relationship("Campaign", back_populates="missions")


class MissionProgress(UUIDMixin, TimestampMixin, Base):
    """Onde cada motorista esta em cada missao.

    MATERIALIZADO, e nao derivado por consulta. Derivar seria barato de ler - um
    GROUP BY sobre `charging_sessions` filtrado pela janela. O que quebra e'
    outra coisa:

    1. Valor derivado nao tem INSTANTE. A recompensa precisa de um "quando isto
       foi concluido" para ser paga uma unica vez, e sem linha nao ha onde
       pendurar o indice unico que impede o credito duplo.

    2. A regra pode mudar depois que alguem cumpriu. Derivado, mudar o alvo de 5
       para 6 RETIRA uma conclusao que o app ja comemorou. Materializado,
       `concluida_em` e' fato consumado - a unica forma defensavel de tratar
       dinheiro.

    O custo aceito e' recomputacao. Como a coluna guarda valor absoluto e nao
    incremento, reprocessar e' idempotente.
    """

    __tablename__ = "mission_progress"
    __table_args__ = (
        # E' ela que permite `INSERT ... ON CONFLICT DO UPDATE`, isto e',
        # progresso sem corrida entre dois faturamentos simultaneos.
        UniqueConstraint(
            "mission_id", "user_id", "periodo", name="uq_mission_progress_missao_motorista_periodo"
        ),
        # A fila do worker de recompensa: a fatia pequena da tabela.
        Index(
            "ix_mission_progress_concluidas",
            "user_id",
            postgresql_where=text("concluida_em IS NOT NULL"),
        ),
    )

    mission_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False
    )
    # CASCADE: progresso e' dado pessoal e nao faz sentido sem a pessoa.
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Primeiro dia da janela. Para `janela='campanha'` recebe a data de inicio da
    # campanha - assim a chave unica nunca tem NULL, que no Postgres seria
    # tratado como distinto e permitiria duas linhas para o mesmo periodo.
    periodo: Mapped[date] = mapped_column(Date, nullable=False)

    valor: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # SET NULL, nao CASCADE: apagar a sessao nao pode apagar a conquista. Serve
    # para auditoria - qual recarga fechou a missao.
    ultima_sessao_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("charging_sessions.id", ondelete="SET NULL")
    )

    mission = relationship("Mission", lazy="joined")


class Reward(UUIDMixin, TimestampMixin, Base):
    """O "eu te devo", separado do progresso.

    Progresso e' medicao; recompensa e' divida. Separar as duas e' o que permite
    recomputar a primeira sem tocar na segunda.
    """

    __tablename__ = "rewards"
    __table_args__ = (
        # O coracao da tabela. Uma missao concluida gera no maximo UMA recompensa
        # viva; duas instancias do worker rodando juntas fazem a segunda levar
        # IntegrityError e desistir, do mesmo jeito que `topup_wallet` faz.
        # Cancelar libera o lugar para reconceder, sem apagar o historico.
        Index(
            "uq_rewards_por_progresso",
            "mission_progress_id",
            unique=True,
            postgresql_where=text("mission_progress_id IS NOT NULL AND estado <> 'cancelada'"),
        ),
        # Creditar exige dizer ONDE. Sem isto, uma recompensa pode se declarar
        # paga sem que exista credito nenhum na carteira do motorista.
        CheckConstraint(
            "estado <> 'creditada' OR wallet_topup_id IS NOT NULL",
            name="ck_rewards_credito_completo",
        ),
        CheckConstraint(f"estado IN ({_em(ESTADOS_DA_RECOMPENSA)})", name="ck_rewards_estado"),
        CheckConstraint(f"tipo IN ({_em(BENEFICIOS)})", name="ck_rewards_tipo"),
        CheckConstraint("valor_brl >= 0", name="ck_rewards_valor_nao_negativo"),
        # Outbox proprio: a fila do push de recompensa.
        Index("ix_rewards_a_notificar", "user_id", postgresql_where=text("notified_at IS NULL")),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # RESTRICT, e aqui a divergencia das demais e' proposital: recompensa e'
    # dinheiro concedido. Apagar a campanha nao pode apagar o rastro de quem ja
    # ganhou - o registro sobrevive a quem o originou.
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="RESTRICT"), nullable=False
    )
    # Nulo = concessao avulsa do operador, sem missao por tras.
    mission_progress_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("mission_progress.id", ondelete="CASCADE")
    )

    tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    valor_brl: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    estado: Mapped[str] = mapped_column(String(12), default="pendente", nullable=False)

    wallet_topup_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("wallet_topups.id", ondelete="SET NULL")
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL")
    )

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Marca de envio do push. Mesmo desenho do `session_events.notified_at`, mas
    # em tabela propria: o outbox de sessao exige `session_id`, e uma missao do
    # tipo "cadastre dois veiculos" nao nasce de sessao nenhuma.
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    campaign = relationship("Campaign", lazy="joined")
    progresso = relationship("MissionProgress", lazy="joined")
