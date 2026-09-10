"""Ciclo da sessao de recarga: a unidade de negocio da plataforma."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import AuthMethod, SessionState, StopReason

_ATIVOS_SQL = (
    "state IN ('AUTHORIZING', 'QUEUED', 'STARTING', 'CHARGING', 'SUSPENDED', 'FINISHING')"
)


class ChargingSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "charging_sessions"
    # Os indices parciais ficam declarados aqui, e nao so na migration.
    #
    # O que existe apenas na migration some de um banco criado por
    # `create_all` - foi assim que oito indices, entre eles a unica garantia de
    # unicidade, deixaram de existir em desenvolvimento sem que `alembic check`
    # percebesse: ele compara modelos com migrations, e nao havia o que comparar.
    #
    # O predicado usa os NOMES dos membros porque e' o que
    # Enum(..., native_enum=False) grava na coluna. Escrever os valores em
    # minusculas - como a migration original fazia - cria um indice que casa com
    # zero linhas e nao exige nada.
    __table_args__ = (
        Index("ix_charging_sessions_cp_state", "charge_point_id", "state"),
        Index("ix_charging_sessions_started_at", "started_at"),
        Index(
            "uq_active_session_per_charge_point",
            "charge_point_id",
            unique=True,
            postgresql_where=text(_ATIVOS_SQL),
        ),
        Index(
            "uq_active_session_per_driver",
            "user_id",
            unique=True,
            postgresql_where=text(f"user_id IS NOT NULL AND {_ATIVOS_SQL}"),
        ),
    )

    code: Mapped[str] = mapped_column(
        String(24), unique=True, index=True, nullable=False, doc="ex.: SES-20483"
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    charge_point_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("charge_points.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL")
    )
    rfid_card_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("rfid_cards.id", ondelete="SET NULL")
    )
    tariff_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tariffs.id", ondelete="SET NULL")
    )
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("reservations.id", ondelete="SET NULL")
    )

    state: Mapped[SessionState] = mapped_column(
        Enum(SessionState, name="session_state", native_enum=False),
        default=SessionState.AUTHORIZING,
        nullable=False,
        index=True,
    )
    auth_method: Mapped[AuthMethod] = mapped_column(
        Enum(AuthMethod, name="auth_method", native_enum=False),
        default=AuthMethod.APP,
        nullable=False,
    )
    stop_reason: Mapped[StopReason | None] = mapped_column(
        Enum(StopReason, name="stop_reason", native_enum=False)
    )

    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Entrada na fila de espera. Ordena a fila e mede quanto tempo o motorista
    # aguardou - insumo para dimensionar o site.
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    charging_stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    energy_kwh: Mapped[float] = mapped_column(Numeric(10, 3), default=0, nullable=False)
    green_energy_kwh: Mapped[float] = mapped_column(Numeric(10, 3), default=0, nullable=False)
    duration_s: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idle_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    peak_power_kw: Mapped[float] = mapped_column(Numeric(7, 3), default=0, nullable=False)

    meter_start_kwh: Mapped[float | None] = mapped_column(Numeric(12, 3))
    meter_stop_kwh: Mapped[float | None] = mapped_column(Numeric(12, 3))

    estimated_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    preauth_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    limit_kwh: Mapped[float | None] = mapped_column(Numeric(10, 3))
    limit_minutes: Mapped[int | None] = mapped_column(Integer)
    limit_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))

    error_message: Mapped[str | None] = mapped_column(Text)

    charge_point = relationship("ChargePoint", back_populates="sessions")
    events = relationship(
        "SessionEvent",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionEvent.occurred_at",
    )
    invoice = relationship("Invoice", back_populates="session", uselist=False)


class SessionEvent(UUIDMixin, Base):
    """Trilha de auditoria do ciclo - alimenta a timeline do dashboard."""

    __tablename__ = "session_events"
    # A fila do worker de push: eventos ainda nao notificados. Indice PARCIAL
    # porque essa fatia e' minuscula perto do historico inteiro - indexar a
    # tabela toda desperdicaria espaco proporcional a algo que nunca e' lido.
    #
    # Declarado aqui, e nao so' na migration, pelo mesmo motivo dos indices de
    # sessao ativa logo acima: o que so' existe na migration some de um banco
    # criado por `create_all`, e `alembic check` nao tem com o que comparar.
    __table_args__ = (
        Index(
            "ix_session_events_pendentes",
            "occurred_at",
            postgresql_where=text("notified_at IS NULL"),
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("charging_sessions.id", ondelete="CASCADE"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(24))
    to_state: Mapped[str | None] = mapped_column(String(24))
    message: Mapped[str | None] = mapped_column(Text)

    # Marca de envio da notificacao push. Nulo = ainda nao enviado.
    #
    # E' um outbox na propria tabela de eventos, em vez de uma fila separada: o
    # evento ja e' a fonte da verdade do que aconteceu, e duplicar isso criaria
    # duas historias que podem divergir. O worker so' olha os notificaveis com
    # esta coluna nula, entao um envio que falhou volta no ciclo seguinte -
    # e nenhum evento e' notificado duas vezes.
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    session = relationship("ChargingSession", back_populates="events")
