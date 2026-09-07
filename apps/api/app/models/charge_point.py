"""Ponto de recarga (eletroposto) e sua configuração de conexão."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ChargePointStatus, ConnectorType, PhaseType


class ChargePoint(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "charge_points"
    __table_args__ = (UniqueConstraint("site_id", "code", name="uq_charge_points_site_id_code"),)

    site_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(24), nullable=False, doc="ex.: CP-01")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(32), index=True, doc="reg 10040")

    connector: Mapped[ConnectorType] = mapped_column(
        Enum(ConnectorType, name="connector_type", native_enum=False),
        default=ConnectorType.TYPE2,
        nullable=False,
    )
    phase_type: Mapped[PhaseType] = mapped_column(
        Enum(PhaseType, name="phase_type", native_enum=False),
        default=PhaseType.THREE,
        nullable=False,
    )
    rated_kw: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    min_kw: Mapped[float] = mapped_column(
        Numeric(6, 2),
        default=4.2,
        nullable=False,
        doc="Piso do reg 10029: 1,4 kW (7 kW mono) ou 4,2 kW (11/22 kW tri)",
    )
    # Limite atualmente aplicado no hardware (reg 10029) - saida do alocador.
    limit_kw: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    # Corte manual do operador (reg 10000). Precisa persistir: sem isso o poller
    # e o rateio automatico desfaziam o corte em segundos, e o botao do painel
    # parecia funcionar e revertia sozinho.
    operator_throttled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Teto definido pelo operador no dashboard. Nulo = usar o nominal.
    # Sem esse campo o rateio automatico sobrescreveria o ajuste manual no ciclo
    # seguinte, e o controle do painel nao controlaria nada.
    operator_max_kw: Mapped[float | None] = mapped_column(Numeric(6, 2))

    status: Mapped[ChargePointStatus] = mapped_column(
        Enum(ChargePointStatus, name="charge_point_status", native_enum=False),
        default=ChargePointStatus.OFFLINE,
        nullable=False,
        index=True,
    )
    current_kw: Mapped[float] = mapped_column(Numeric(6, 2), default=0, nullable=False)

    # Prioridade no rateio de potência: maior número = atendido primeiro.
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Tarifa específica do ponto (senão cai na tarifa padrão do site).
    tariff_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tariffs.id", ondelete="SET NULL")
    )

    firmware_version: Mapped[str | None] = mapped_column(String(32))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_fault_code: Mapped[str | None] = mapped_column(String(120))
    # Bits de falha/alarme decodificados dos registradores 10001–10008 e 30000.
    active_faults: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    site = relationship("Site", back_populates="charge_points")
    connection = relationship(
        "ChargePointConnection",
        back_populates="charge_point",
        uselist=False,
        cascade="all, delete-orphan",
    )
    sessions = relationship("ChargingSession", back_populates="charge_point")

    @property
    def effective_max_kw(self) -> float:
        """Teto de demanda: o menor entre o nominal e a politica do operador."""
        rated = float(self.rated_kw)
        if self.operator_max_kw is None:
            return rated
        return min(rated, float(self.operator_max_kw))

    @property
    def is_dispatchable(self) -> bool:
        """Pode receber potência do alocador?"""
        if self.operator_throttled:
            return False
        # PREPARING fica de fora de proposito: carro plugado que nao carrega nao
        # consome nada, e incluir esse estado faria um carro na fila reservar
        # exatamente a potencia que ele esta esperando. Quando a sessao comeca,
        # start() aloca o ponto explicitamente via starting_ids.
        return self.enabled and self.status in {
            ChargePointStatus.CHARGING,
            ChargePointStatus.SUSPENDED,
        }


class ChargePointConnection(UUIDMixin, TimestampMixin, Base):
    """Como falamos com o hardware. Hoje Modbus TCP; amanhã OCPP 1.6J/2.0.1."""

    __tablename__ = "charge_point_connections"

    charge_point_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("charge_points.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    protocol: Mapped[str] = mapped_column(String(24), default="modbus_tcp", nullable=False)
    host: Mapped[str | None] = mapped_column(String(120))
    port: Mapped[int] = mapped_column(Integer, default=502, nullable=False)
    unit_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, doc="slave id Modbus")
    # Espaço para credenciais OCPP, gateway GoodWe etc. sem nova migration.
    options: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    charge_point = relationship("ChargePoint", back_populates="connection")


class ChargePointFault(UUIDMixin, TimestampMixin, Base):
    """Um episodio de falha: da primeira leitura que a viu ate a que nao viu mais.

    `charge_points.active_faults` diz o que esta acontecendo agora. Esta tabela
    diz o que ja aconteceu - e e' so' com ela que da' para responder "este ponto
    tem falhado mais que os outros?", que e' a pergunta da manutencao.

    O indice unico parcial garante um episodio aberto por ponto e rotulo: o
    poller reencontra a mesma falha a cada ciclo de 5 segundos, e sem ele um
    minuto de falha viraria doze episodios.
    """

    __tablename__ = "charge_point_faults"
    __table_args__ = (
        Index("ix_charge_point_faults_cp_time", "charge_point_id", "first_seen_at"),
        Index(
            "uq_falha_aberta_por_ponto",
            "charge_point_id",
            "label",
            unique=True,
            postgresql_where=text("resolved_at IS NULL"),
        ),
    )

    charge_point_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("charge_points.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    terminal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ciclos: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
