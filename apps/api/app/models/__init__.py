"""Importa todos os modelos para que o Alembic enxergue o metadata completo."""

from app.db.base import Base
from app.models.audit import AuditLog, CommandLog
from app.models.billing import (
    Invoice,
    InvoiceLine,
    Payment,
    SitePaymentMethod,
    WalletTopUp,
)
from app.models.campaign import Campaign, Mission, MissionProgress, Reward
from app.models.charge_point import ChargePoint, ChargePointConnection, ChargePointFault
from app.models.charge_point_report import ChargePointReport
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
from app.models.fleet import Fleet
from app.models.forecast import SiteForecast
from app.models.platform import PlatformInvoice, PlatformPlan, SiteSubscription
from app.models.priority_rule import PriorityRule
from app.models.push_device import PushDevice
from app.models.reservation import Reservation
from app.models.session import ChargingSession, SessionEvent
from app.models.site import Site, SiteMeterReading
from app.models.subscription import DriverPlan, DriverSubscription
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
    "ChargePointReport",
    "ChargePointStatus",
    "ChargingSession",
    "DriverPlan",
    "DriverSubscription",
    "Campaign",
    "CommandLog",
    "ConnectorType",
    "Invoice",
    "InvoiceLine",
    "InvoiceStatus",
    "Mission",
    "MissionProgress",
    "Payment",
    "PaymentMethodKind",
    "PaymentStatus",
    "PhaseType",
    "PlatformInvoice",
    "PlatformPlan",
    "PowerSource",
    "Fleet",
    "PriorityRule",
    "PushDevice",
    "Reservation",
    "ReservationStatus",
    "Reward",
    "RfidCard",
    "SessionEvent",
    "SessionState",
    "Site",
    "SiteForecast",
    "SiteMeterReading",
    "SiteSubscription",
    "SitePaymentMethod",
    "StopReason",
    "Tariff",
    "TariffType",
    "TariffWindow",
    "TelemetrySample",
    "User",
    "UserRole",
    "Vehicle",
    "WalletTopUp",
]
