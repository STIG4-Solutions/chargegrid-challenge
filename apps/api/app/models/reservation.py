"""Agendamento de recarga - requisito do app mobile e do reg 10020/10021 do HCA G2."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ReservationStatus


class Reservation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reservations"
    __table_args__ = (
        Index("ix_reservations_cp_window", "charge_point_id", "starts_at", "ends_at"),
    )

    code: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    charge_point_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("charge_points.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL")
    )

    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status", native_enum=False),
        default=ReservationStatus.PENDING,
        nullable=False,
        index=True,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_kwh: Mapped[float | None] = mapped_column(Numeric(10, 3))
    # Potencia reservada no orcamento do site durante a janela.
    reserved_kw: Mapped[float] = mapped_column(Numeric(6, 2), default=0, nullable=False)
    # Escrita nos registradores 10020-10022 do ponto?
    pushed_to_hardware: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    charge_point = relationship("ChargePoint")
    user = relationship("User")
