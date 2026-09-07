"""Importa todos os modelos para que o Alembic enxergue o metadata completo."""

from app.db.base import Base
from app.models.audit import AuditLog, CommandLog
from app.models.billing import Invoice, InvoiceLine, Payment, SitePaymentMethod
from app.models.charge_point import ChargePoint, ChargePointConnection, ChargePointFault
from app.models.enums import (
    ACTIVE_SESSION_STATES,
    TERMINAL_SESSION_STATES,
    AuthMethod,
    ChargePointStatus,
    ConnectorType,
    InvoiceStatus,
    PaymentMethodKind,
    PaymentStatus,
    PhaseType,
    PowerSource,
    ReservationStatus,
    SessionState,
    StopReason,
    TariffType,
    UserRole,
)
from app.models.priority_rule import PriorityRule
from app.models.push_device import PushDevice
from app.models.reservation import Reservation
from app.models.session import ChargingSession, SessionEvent
from app.models.site import Site, SiteMeterReading
from app.models.tariff import Tariff, TariffWindow
from app.models.telemetry import TelemetrySample
from app.models.user import RfidCard, User, Vehicle

__all__ = [
    "ACTIVE_SESSION_STATES",
    "TERMINAL_SESSION_STATES",
    "AuditLog",
    "AuthMethod",
    "Base",
    "ChargePoint",
    "ChargePointConnection",
    "ChargePointFault",
    "ChargePointStatus",
    "ChargingSession",
    "CommandLog",
    "ConnectorType",
    "Invoice",
    "InvoiceLine",
    "InvoiceStatus",
    "Payment",
    "PaymentMethodKind",
    "PaymentStatus",
    "PhaseType",
    "PowerSource",
    "PriorityRule",
    "PushDevice",
    "Reservation",
    "ReservationStatus",
    "RfidCard",
    "SessionEvent",
    "SessionState",
    "Site",
    "SiteMeterReading",
    "SitePaymentMethod",
    "StopReason",
    "Tariff",
    "TariffType",
    "TariffWindow",
    "TelemetrySample",
    "User",
    "UserRole",
    "Vehicle",
]
