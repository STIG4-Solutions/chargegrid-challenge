"""Faturamento: fatura, linhas de cobranca, pagamentos e metodos aceitos no site."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import InvoiceStatus, PaymentMethodKind, PaymentStatus


class SitePaymentMethod(UUIDMixin, TimestampMixin, Base):
    """Metodos habilitados pelo estabelecimento, com a taxa do adquirente."""

    __tablename__ = "site_payment_methods"
    __table_args__ = (
        UniqueConstraint("site_id", "kind", name="uq_site_payment_methods_site_id_kind"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[PaymentMethodKind] = mapped_column(
        Enum(PaymentMethodKind, name="payment_method_kind", native_enum=False), nullable=False
    )
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fee_percent: Mapped[float] = mapped_column(Numeric(6, 3), default=0, nullable=False)
    fee_fixed: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), default="mock", nullable=False)
    provider_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class Invoice(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    code: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("charging_sessions.id", ondelete="SET NULL"), unique=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status", native_enum=False),
        default=InvoiceStatus.DRAFT,
        nullable=False,
        index=True,
    )
    currency: Mapped[str] = mapped_column(String(3), default="BRL", nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    discount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    processing_fee: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    net_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    issued_on: Mapped[date] = mapped_column(Date, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tariff_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    session = relationship("ChargingSession", back_populates="invoice")
    lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceLine(UUIDMixin, Base):
    __tablename__ = "invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 4), default=0, nullable=False)
    unit: Mapped[str] = mapped_column(String(12), default="kWh", nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 4), default=0, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    invoice = relationship("Invoice", back_populates="lines")


class Payment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    method: Mapped[PaymentMethodKind] = mapped_column(
        Enum(PaymentMethodKind, name="payment_method_kind", native_enum=False), nullable=False
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", native_enum=False),
        default=PaymentStatus.PENDING,
        nullable=False,
        index=True,
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    provider: Mapped[str] = mapped_column(String(40), default="mock", nullable=False)
    provider_ref: Mapped[str | None] = mapped_column(String(120), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    qr_code: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_response: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    invoice = relationship("Invoice", back_populates="payments")


class WalletTopUp(UUIDMixin, TimestampMixin, Base):
    """Cada credito na carteira pre-paga, com a chave que impede o duplicado.

    Existe por duas razoes que se resolvem na mesma tabela.

    A primeira e' auditoria: ate aqui um credito so alterava users.wallet_balance
    e nao deixava rastro nenhum - nao dava para reconciliar um saldo nem
    responder "de onde veio esse dinheiro".

    A segunda e' idempotencia. O app manda a chave; o UNIQUE do banco e' quem
    garante, nao um SELECT antes do INSERT: dois toques simultaneos passariam
    pelos dois SELECTs antes de qualquer INSERT, e o motorista seria creditado
    duas vezes.
    """

    __tablename__ = "wallet_topups"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    balance_after: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), default="mock", nullable=False)
    provider_ref: Mapped[str | None] = mapped_column(String(120), index=True)
