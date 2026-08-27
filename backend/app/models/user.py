"""Usuários da plataforma (dashboard comercial) e motoristas (app mobile)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import UserRole


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False), default=UserRole.DRIVER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    document: Mapped[str | None] = mapped_column(String(32), doc="CPF/CNPJ para nota fiscal")

    # Operadores/admins pertencem a um site; motoristas não.
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="SET NULL")
    )

    # Saldo pré-pago da carteira do app (BRL).
    wallet_balance: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    site = relationship("Site", back_populates="users")
    rfid_cards = relationship("RfidCard", back_populates="user", cascade="all, delete-orphan")
    vehicles = relationship("Vehicle", back_populates="user", cascade="all, delete-orphan")


class RfidCard(UUIDMixin, TimestampMixin, Base):
    """Cartão RFID — a linha HCA G2 suporta até 10 cartões por ponto (regs 10500/10507/10514)."""

    __tablename__ = "rfid_cards"
    __table_args__ = (UniqueConstraint("uid", name="uq_rfid_cards_uid"),)

    uid: Mapped[str] = mapped_column(String(14), index=True, nullable=False, doc="UID de 14 bytes")
    label: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    # Cartão pode estar amarrado a uma tarifa específica (ex.: funcionário paga menos).
    tariff_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tariffs.id", ondelete="SET NULL")
    )
    # Sincronizado no hardware via Modbus (10507)?
    synced_to_hardware: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="rfid_cards")
    site = relationship("Site")


class Vehicle(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "vehicles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    plate: Mapped[str | None] = mapped_column(String(16), index=True)
    vin: Mapped[str | None] = mapped_column(String(24), index=True, doc="usado no VIN charging")
    battery_kwh: Mapped[float | None] = mapped_column(Numeric(6, 2))
    max_ac_kw: Mapped[float | None] = mapped_column(Numeric(6, 2))

    user = relationship("User", back_populates="vehicles")
