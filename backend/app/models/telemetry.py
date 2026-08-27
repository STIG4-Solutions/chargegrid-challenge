"""Amostras de telemetria por ponto — base para tarifação por janela e para a IA."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, SmallInteger
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDMixin


class TelemetrySample(UUIDMixin, Base):
    """Snapshot de uma varredura Modbus.

    Tabela append-only e volumosa: a migration cria índice BRIN em recorded_at
    (barato para série temporal) além do B-tree composto de consulta.
    """

    __tablename__ = "telemetry_samples"

    charge_point_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("charge_points.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("charging_sessions.id", ondelete="SET NULL")
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # 10009–10015
    voltage_a: Mapped[float | None] = mapped_column(Numeric(7, 2))
    voltage_b: Mapped[float | None] = mapped_column(Numeric(7, 2))
    voltage_c: Mapped[float | None] = mapped_column(Numeric(7, 2))
    current_a: Mapped[float | None] = mapped_column(Numeric(7, 2))
    current_b: Mapped[float | None] = mapped_column(Numeric(7, 2))
    current_c: Mapped[float | None] = mapped_column(Numeric(7, 2))
    power_kw: Mapped[float] = mapped_column(Numeric(7, 3), default=0, nullable=False)

    # 10016 (energia da sessão) e 10065 (acumulado do medidor)
    session_energy_kwh: Mapped[float] = mapped_column(Numeric(10, 3), default=0, nullable=False)
    meter_kwh: Mapped[float | None] = mapped_column(Numeric(12, 3))

    # 10017 bruto e 10108 (bitfield da fonte de energia)
    raw_status: Mapped[int | None] = mapped_column(SmallInteger)
    power_source_bits: Mapped[int | None] = mapped_column(SmallInteger)
    # Fatia verde da amostra (reg 10103) — insumo do relatório de sustentabilidade.
    green_kwh: Mapped[float | None] = mapped_column(Numeric(10, 3))

    # Limite que o alocador tinha aplicado nesse instante (auditoria do controle de demanda).
    applied_limit_kw: Mapped[float | None] = mapped_column(Numeric(6, 2))
