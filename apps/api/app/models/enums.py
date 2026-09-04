"""Enumerações do domínio.

Os valores de ChargePointStatus e SessionState espelham exatamente os rótulos
já usados pelo front (src/views/ev/*.jsx), para o React consumir sem tradução.
"""

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"  # dono do estabelecimento / plataforma
    OPERATOR = "operator"  # operação do site (dashboard comercial)
    DRIVER = "driver"  # end user do app mobile


class ConnectorType(StrEnum):
    TYPE2 = "Type 2"
    CCS2 = "CCS2"
    CHADEMO = "CHAdeMO"


class PhaseType(StrEnum):
    SINGLE = "single_phase"
    THREE = "three_phase"


class ChargePointStatus(StrEnum):
    AVAILABLE = "available"
    PREPARING = "preparing"
    CHARGING = "charging"
    SUSPENDED = "suspended"  # pausado pelo controle de demanda
    FINISHING = "finishing"
    RESERVED = "reserved"
    FAULTED = "faulted"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class SessionState(StrEnum):
    AUTHORIZING = "authorizing"
    QUEUED = "queued"
    STARTING = "starting"
    CHARGING = "charging"
    SUSPENDED = "suspended"
    FINISHING = "finishing"
    FINISHED = "finished"
    BILLED = "billed"
    ERROR = "error"


# Estados a partir dos quais a sessão não muda mais.
TERMINAL_SESSION_STATES = {SessionState.BILLED, SessionState.ERROR}
ACTIVE_SESSION_STATES = {
    SessionState.AUTHORIZING,
    # Na fila o motorista ja esta na vaga esperando: o ponto continua ocupado.
    SessionState.QUEUED,
    SessionState.STARTING,
    SessionState.CHARGING,
    SessionState.SUSPENDED,
    SessionState.FINISHING,
}


class StopReason(StrEnum):
    QUEUE_TIMEOUT = "queue_timeout"
    LOCAL = "local"  # botão no ponto / RFID
    REMOTE = "remote"  # dashboard ou app
    EV_DISCONNECTED = "ev_disconnected"
    ENERGY_LIMIT = "energy_limit"
    TIME_LIMIT = "time_limit"
    AMOUNT_LIMIT = "amount_limit"
    POWER_SHORTAGE = "power_shortage"
    FAULT = "fault"
    DEAUTHORIZED = "deauthorized"


class AuthMethod(StrEnum):
    RFID = "rfid"
    APP = "app"
    PLUG_AND_CHARGE = "plug_and_charge"
    RESERVATION = "reservation"
    OPERATOR = "operator"


class TariffType(StrEnum):
    PER_KWH = "per_kwh"
    PER_TIME = "per_time"
    TIME_OF_USE = "time_of_use"
    FLAT = "flat"


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"  # aguardando pagamento
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    VOID = "void"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethodKind(StrEnum):
    PIX = "pix"
    CREDIT_CARD = "credit_card"
    RFID_SUBSCRIPTION = "rfid_subscription"
    WALLET = "wallet"


class ReservationStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CONSUMED = "consumed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PowerSource(StrEnum):
    GRID = "grid"
    PV = "pv"
    BATTERY = "battery"
