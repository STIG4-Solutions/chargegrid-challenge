"""Plano de recarga assinado pelo motorista.

Quem assina paga uma mensalidade e recebe, em toda recarga, o que o plano
promete. O beneficio entra no motor de tarifacao pelo MESMO `Beneficio` que as
campanhas usam - `rate_session` continua puro e nao sabe que assinatura existe.

NAO HA ISENCAO DE OCIOSIDADE, e a ausencia e' deliberada. A taxa de ociosidade
nao e' receita: e' o mecanismo que libera a vaga, e o proprio `tariff_engine`
comenta isso. Isentar o assinante transformaria o melhor cliente naquele que mais
trava o conector. Uma coluna para isso ja seria um convite, entao ela nao existe.
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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

ESTADOS_DA_ASSINATURA = ("ativa", "cancelada", "inadimplente")


class DriverPlan(UUIDMixin, TimestampMixin, Base):
    """O catalogo. Escopo de rede: um plano nao pertence a uma praca."""

    __tablename__ = "driver_plans"
    __table_args__ = (
        UniqueConstraint("codigo", name="uq_driver_plans_codigo"),
        CheckConstraint(
            "desconto_pct >= 0 AND desconto_pct <= 100", name="ck_driver_plans_desconto"
        ),
        CheckConstraint("kwh_inclusos >= 0", name="ck_driver_plans_kwh"),
        CheckConstraint("preco_mensal_brl >= 0", name="ck_driver_plans_preco"),
        # Plano que nao entrega nada e' mensalidade sem contrapartida. Barrar
        # aqui evita que ele exista; descobrir depois exigiria estornar quem
        # ja assinou.
        CheckConstraint(
            "desconto_pct > 0 OR kwh_inclusos > 0 OR isenta_taxa_de_conexao",
            name="ck_driver_plans_entrega_algo",
        ),
    )

    codigo: Mapped[str] = mapped_column(String(24), nullable=False)
    nome: Mapped[str] = mapped_column(String(80), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    preco_mensal_brl: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    desconto_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    kwh_inclusos: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=0, nullable=False)
    isenta_taxa_de_conexao: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DriverSubscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "driver_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('ativa', 'cancelada', 'inadimplente')",
            name="ck_driver_subscriptions_estado",
        ),
        CheckConstraint(
            "current_period_end > current_period_start", name="ck_driver_subscriptions_periodo"
        ),
        # Cancelar exige dizer QUANDO. Sem a marca, a pergunta "esta recarga
        # tinha desconto?" fica sem resposta depois do fato.
        CheckConstraint(
            "estado <> 'cancelada' OR canceled_at IS NOT NULL",
            # Sem o prefixo `ck_<tabela>_`: a NAMING_CONVENTION o acrescenta.
            # Escrevendo o nome completo aqui, ele sai duplicado - e neste caso
            # passava de 63 caracteres, o limite de identificador do Postgres,
            # que truncava e acrescentava um hash. O nome no banco deixava de
            # bater com o do metadata e `alembic check` acusava deriva.
            name="cancelamento_completo",
        ),
        # Uma pessoa, uma assinatura ativa. Mesmo desenho de
        # `uq_active_session_per_driver`: a checagem da aplicacao e' um SELECT
        # seguido de INSERT, e dois toques simultaneos a atravessam juntos.
        Index(
            "uq_driver_subscription_ativa",
            "user_id",
            unique=True,
            postgresql_where=text("estado = 'ativa'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # RESTRICT: nao se apaga plano que alguem assinou. O preco e as regras dele
    # explicam faturas ja emitidas.
    plan_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("driver_plans.id", ondelete="RESTRICT"), nullable=False
    )

    estado: Mapped[str] = mapped_column(String(14), default="ativa", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    current_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Quanto da franquia ja foi usado no periodo corrente. Recalculado a cada
    # faturamento a partir das sessoes - valor absoluto, nao incremento, pelo
    # mesmo motivo de `mission_progress`: reprocessar nao pode dobrar a conta.
    kwh_consumidos_no_periodo: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), default=0, nullable=False
    )

    plan = relationship("DriverPlan", lazy="joined")

    @property
    def vigente(self) -> bool:
        return self.estado == "ativa"
