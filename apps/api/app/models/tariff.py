"""Politicas de tarifacao. Uma tarifa = componentes fixos + janelas horarias opcionais."""

import uuid
from datetime import time

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, SmallInteger, String, Time
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import TariffType

# Mascara de dias da semana: bit0 = segunda ... bit6 = domingo.
ALL_DAYS = 0b1111111
WEEKDAYS = 0b0011111
WEEKEND = 0b1100000


class Tariff(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tariffs"

    site_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[TariffType] = mapped_column(
        Enum(TariffType, name="tariff_type", native_enum=False),
        default=TariffType.PER_KWH,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), default="BRL", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Componentes base (usados quando nenhuma janela casa com o horario).
    price_per_kwh: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=False)
    price_per_min: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=False)
    idle_fee_per_min: Mapped[float] = mapped_column(
        Numeric(10, 4), default=0, nullable=False, doc="Cobrada apos o carro parar de puxar energia"
    )
    session_fee: Mapped[float] = mapped_column(
        Numeric(10, 4), default=0, nullable=False, doc="Taxa fixa de conexao"
    )
    min_charge: Mapped[float] = mapped_column(
        Numeric(10, 4), default=0, nullable=False, doc="Valor minimo faturado"
    )
    free_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Multiplicador digitado pelo operador (1.0 = neutro). E' o caminho LEGADO: com a
    # precificacao dinamica ligada, o multiplicador vem da bandeira do site (folga de
    # potencia) e fica travado na sessao; este so' vale para sessao sem travado.
    dynamic_multiplier: Mapped[float] = mapped_column(Numeric(5, 3), default=1.0, nullable=False)
    dynamic_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    site = relationship("Site", back_populates="tariffs", foreign_keys=[site_id])
    windows = relationship(
        "TariffWindow",
        back_populates="tariff",
        cascade="all, delete-orphan",
        order_by="TariffWindow.starts_at",
    )


class TariffWindow(UUIDMixin, Base):
    """Faixa horaria (ponta / fora de ponta). Janela que cruza a meia-noite e suportada."""

    __tablename__ = "tariff_windows"

    tariff_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tariffs.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    day_mask: Mapped[int] = mapped_column(SmallInteger, default=ALL_DAYS, nullable=False)
    starts_at: Mapped[time] = mapped_column(Time, nullable=False)
    ends_at: Mapped[time] = mapped_column(Time, nullable=False)

    price_per_kwh: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=False)
    price_per_min: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=False)
    idle_fee_per_min: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=False)

    tariff = relationship("Tariff", back_populates="windows")

    def matches(self, moment) -> bool:
        """O argumento moment e um datetime ja convertido para o fuso do site."""
        if not (self.day_mask >> moment.weekday()) & 1:
            return False
        t = moment.time()
        if self.starts_at <= self.ends_at:
            return self.starts_at <= t < self.ends_at
        # Janela que atravessa a meia-noite, ex.: 21:00 ate 18:00.
        return t >= self.starts_at or t < self.ends_at
