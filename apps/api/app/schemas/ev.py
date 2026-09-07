"""Schemas dos tres modulos da secao Recarga EV."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import (
    AuthMethod,
    ChargePointStatus,
    ConnectorType,
    InvoiceStatus,
    PaymentMethodKind,
    PhaseType,
    ReservationStatus,
    SessionState,
    StopReason,
    TariffType,
)
from app.schemas.common import ORMModel


# ------------------------------------------------------- Gerenciamento de Potencia
class ChargePointOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    serial_number: str | None
    connector: ConnectorType
    phase_type: PhaseType
    rated_kw: float
    min_kw: float
    limit_kw: float
    operator_max_kw: float | None
    operator_throttled: bool
    current_kw: float
    status: ChargePointStatus
    priority: int
    enabled: bool
    tariff_id: uuid.UUID | None
    firmware_version: str | None
    last_seen_at: datetime | None
    active_faults: list[str]


class ChargePointCreate(BaseModel):
    code: str = Field(max_length=24)
    name: str = Field(max_length=120)
    connector: ConnectorType = ConnectorType.TYPE2
    phase_type: PhaseType = PhaseType.THREE
    rated_kw: float = Field(gt=0, le=350)
    min_kw: float = Field(default=4.2, ge=0)
    priority: int = Field(default=100, ge=0, le=1000)
    tariff_id: uuid.UUID | None = None
    host: str | None = None
    port: int = 502
    unit_id: int = 1
    protocol: str = "modbus_tcp"


class ChargePointUpdate(BaseModel):
    name: str | None = None
    priority: int | None = Field(default=None, ge=0, le=1000)
    enabled: bool | None = None
    tariff_id: uuid.UUID | None = None
    limit_kw: float | None = Field(default=None, ge=0)


class PowerBudgetOut(BaseModel):
    grid_limit_kw: float
    pv_kw: float
    battery_kw: float
    reserved_kw: float
    building_load_kw: float
    ev_load_kw: float
    # Potência segurada por agendamentos em curso, fora do rateio.
    booked_kw: float = 0.0
    available_kw: float
    # Frescor da leitura do medidor: obsoleta significa que PV e bateria sairam
    # do orcamento e so a rede sustenta os pontos.
    reading_at: datetime | None = None
    reading_stale: bool = True


class SiteSettingsOut(BaseModel):
    """Politica de demanda do site - o que o operador edita no painel."""

    grid_limit_kw: float
    reserved_kw: float
    allow_pv_kw: bool
    allow_battery_kw: bool
    battery_min_soc: float
    main_breaker_current_a: float | None


class PowerBudgetUpdate(BaseModel):
    grid_limit_kw: float | None = Field(default=None, ge=0)
    reserved_kw: float | None = Field(default=None, ge=0)
    allow_pv_kw: bool | None = None
    allow_battery_kw: bool | None = None
    battery_min_soc: float | None = Field(default=None, ge=0, le=100)
    main_breaker_current_a: float | None = Field(default=None, ge=0)


class AllocationOut(BaseModel):
    charge_point_id: str
    code: str
    priority: int
    requested_kw: float
    granted_kw: float
    suspended: bool
    reason: str
    # Nome da regra de prioridade que definiu a faixa; vazio quando nenhuma
    # casou e valeu o inteiro do proprio ponto.
    regra: str = ""


class PowerPlanOut(BaseModel):
    budget: PowerBudgetOut
    total_granted_kw: float
    over_budget: bool
    allocations: list[AllocationOut]


class PowerOverview(BaseModel):
    budget: PowerBudgetOut
    settings: SiteSettingsOut
    allocated_kw: float
    current_kw: float
    usage_percent: float
    over_budget: bool
    active_count: int
    total_count: int
    charge_points: list[ChargePointOut]


class SetLimitRequest(BaseModel):
    limit_kw: float = Field(ge=0, le=350)


class MeterReadingIn(BaseModel):
    """Leitura do smart meter do site (inversor GoodWe, medidor MID ou gateway)."""

    recorded_at: datetime | None = None
    grid_import_kw: float = 0
    pv_kw: float = 0
    battery_kw: float = 0
    battery_soc: float | None = Field(default=None, ge=0, le=100)
    building_load_kw: float = 0
    ev_load_kw: float = 0


# ------------------------------------------------------------- Ciclo da Sessao
class SessionEventOut(ORMModel):
    occurred_at: datetime
    event_type: str
    from_state: str | None
    to_state: str | None
    message: str | None
    payload: dict


class SessionOut(ORMModel):
    id: uuid.UUID
    code: str
    queued_at: datetime | None = None
    charge_point_id: uuid.UUID
    user_id: uuid.UUID | None
    tariff_id: uuid.UUID | None
    state: SessionState
    auth_method: AuthMethod
    stop_reason: StopReason | None
    authorized_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    energy_kwh: float
    green_energy_kwh: float
    duration_s: int
    idle_minutes: int
    peak_power_kw: float
    estimated_cost: float
    error_message: str | None

    # Tetos pedidos pelo motorista. Sem eles na resposta a tela nao tem como
    # mostrar "carregando ate 30 kWh" nem o quanto falta - e um limite que o
    # motorista nao ve em nenhum lugar depois de definir e' um limite em que
    # ele nao confia.
    limit_kwh: float | None = None
    limit_minutes: int | None = None
    limit_amount: float | None = None
    preauth_amount: float = 0.0


class SessionDetail(SessionOut):
    events: list[SessionEventOut] = []
    # Preenchido apenas enquanto a sessão está na fila.
    queue_position: int | None = None


class SessionStartRequest(BaseModel):
    charge_point_id: uuid.UUID
    # Sem potência disponível: entrar na fila (padrão) ou falhar na hora.
    queue_if_unavailable: bool = True
    user_id: uuid.UUID | None = None
    vehicle_id: uuid.UUID | None = None
    rfid_uid: str | None = None
    auth_method: AuthMethod = AuthMethod.OPERATOR
    preauth_amount: float = Field(default=0, ge=0)
    limit_kwh: float | None = Field(default=None, gt=0)
    limit_minutes: int | None = Field(default=None, gt=0)
    limit_amount: float | None = Field(default=None, gt=0)


class SessionStopRequest(BaseModel):
    reason: StopReason = StopReason.REMOTE
    auto_bill: bool = True


class SessionKpis(BaseModel):
    active: int
    queued: int
    today: int
    energy_kwh: float
    green_energy_kwh: float
    confirmed_revenue: float
    pending_revenue: float


# ---------------------------------------------------- Tarifacao e Pagamento
class TariffWindowIn(BaseModel):
    label: str = ""
    day_mask: int = Field(default=0b1111111, ge=0, le=127)
    starts_at: time
    ends_at: time
    price_per_kwh: float = Field(default=0, ge=0)
    price_per_min: float = Field(default=0, ge=0)
    idle_fee_per_min: float = Field(default=0, ge=0)


class TariffWindowOut(TariffWindowIn, ORMModel):
    id: uuid.UUID


class TariffCreate(BaseModel):
    name: str = Field(max_length=120)
    type: TariffType = TariffType.PER_KWH
    active: bool = True
    price_per_kwh: float = Field(default=0, ge=0)
    price_per_min: float = Field(default=0, ge=0)
    idle_fee_per_min: float = Field(default=0, ge=0)
    session_fee: float = Field(default=0, ge=0)
    min_charge: float = Field(default=0, ge=0)
    free_minutes: int = Field(default=0, ge=0)
    dynamic_enabled: bool = False
    dynamic_multiplier: float = Field(default=1.0, gt=0, le=5)
    windows: list[TariffWindowIn] = []


class TariffUpdate(BaseModel):
    name: str | None = None
    active: bool | None = None
    price_per_kwh: float | None = Field(default=None, ge=0)
    price_per_min: float | None = Field(default=None, ge=0)
    idle_fee_per_min: float | None = Field(default=None, ge=0)
    session_fee: float | None = Field(default=None, ge=0)
    min_charge: float | None = Field(default=None, ge=0)
    free_minutes: int | None = Field(default=None, ge=0)
    dynamic_enabled: bool | None = None
    dynamic_multiplier: float | None = Field(default=None, gt=0, le=5)


class TariffOut(ORMModel):
    id: uuid.UUID
    name: str
    type: TariffType
    currency: str
    active: bool
    price_per_kwh: float
    price_per_min: float
    idle_fee_per_min: float
    session_fee: float
    min_charge: float
    free_minutes: int
    dynamic_enabled: bool
    dynamic_multiplier: float
    windows: list[TariffWindowOut] = []


class SimulationRequest(BaseModel):
    tariff_id: uuid.UUID
    energy_kwh: float = Field(default=0, ge=0)
    minutes: int = Field(default=0, ge=0)
    idle_minutes: int = Field(default=0, ge=0)
    at: datetime | None = None


class RatedLineOut(BaseModel):
    kind: str
    description: str
    quantity: float
    unit: str
    unit_price: float
    amount: float


class RatingOut(BaseModel):
    subtotal: float
    total: float
    energy_kwh: float
    billable_minutes: int
    idle_minutes: int
    lines: list[RatedLineOut]
    tariff_snapshot: dict = {}


class PaymentMethodIn(BaseModel):
    kind: PaymentMethodKind
    label: str
    enabled: bool = True
    fee_percent: float = Field(default=0, ge=0, le=100)
    fee_fixed: float = Field(default=0, ge=0)
    provider: str = "mock"


class PaymentMethodOut(ORMModel):
    id: uuid.UUID
    kind: PaymentMethodKind
    label: str
    enabled: bool
    fee_percent: float
    fee_fixed: float
    provider: str


class InvoiceLineOut(ORMModel):
    position: int
    kind: str
    description: str
    quantity: float
    unit: str
    unit_price: float
    amount: float


class PaymentOut(ORMModel):
    id: uuid.UUID
    method: PaymentMethodKind
    status: str
    amount: float
    provider: str
    provider_ref: str | None
    qr_code: str | None
    failure_reason: str | None
    created_at: datetime


class InvoiceOut(ORMModel):
    id: uuid.UUID
    code: str
    session_id: uuid.UUID | None
    user_id: uuid.UUID | None
    status: InvoiceStatus
    currency: str
    subtotal: float
    total: float
    processing_fee: float
    net_amount: float
    issued_on: date
    paid_at: datetime | None
    lines: list[InvoiceLineOut] = []
    payments: list[PaymentOut] = []


class ChargeRequestIn(BaseModel):
    method: PaymentMethodKind
    idempotency_key: str | None = Field(default=None, max_length=80)


class RevenueSummary(BaseModel):
    gross: float
    net: float
    processing_fees: float
    paid_invoices: int
    open_invoices: int
    failed_invoices: int
    energy_kwh: float
    average_ticket: float


# --------------------------------------------------------------- Reservas (app)
class ReservationCreate(BaseModel):
    charge_point_id: uuid.UUID
    vehicle_id: uuid.UUID | None = None
    starts_at: datetime
    ends_at: datetime
    target_kwh: float | None = Field(default=None, gt=0)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def exige_fuso(cls, valor: datetime) -> datetime:
        """Recusa horario sem fuso, em vez de adivinhar.

        A rota compara a janela com datetime.now(UTC), e um valor ingenuo
        estourava TypeError - o cliente recebia 500 no lugar de 422.

        Assumir UTC seria pior que recusar: quem escrevesse "10:00" querendo
        10h da manha em Sao Paulo teria a vaga reservada para as 07h, sem
        nenhum aviso. Uma reserva errada em silencio e' pior que um erro claro.
        """
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError("informe o fuso horário (ex.: 2026-09-01T10:00:00-03:00)")
        return valor


class ReservationOut(ORMModel):
    id: uuid.UUID
    code: str
    charge_point_id: uuid.UUID
    # Contexto do ponto junto da reserva. Sem isto o app so' teria o UUID para
    # mostrar, e precisaria de uma chamada por reserva para descobrir onde ela e'.
    charge_point_code: str | None = None
    charge_point_name: str | None = None
    site_name: str | None = None
    user_id: uuid.UUID
    status: ReservationStatus
    starts_at: datetime
    ends_at: datetime
    target_kwh: float | None
    reserved_kw: float


class StationPointOut(BaseModel):
    """Ponto de recarga como o app do motorista o ve.

    Deliberadamente menor que ChargePointOut: o motorista escolhe uma vaga, nao
    opera o site. Limite de potencia, registrador Modbus e politica do operador
    ficam fora.
    """

    id: uuid.UUID
    code: str
    name: str
    connector: str
    rated_kw: float
    status: str
    available: bool


class ScannedChargePointOut(StationPointOut):
    """Ponto resolvido a partir do codigo lido no QR colado no carregador.

    Traz o contexto da estacao junto: quem chega por aqui tem so' o codigo na
    mao e precisa saber onde esta antes de decidir iniciar a recarga.
    """

    site_id: uuid.UUID
    site_name: str
    site_address: str | None = None


class StationOut(BaseModel):
    """Estacao vista pelo app mobile (mapa e disponibilidade)."""

    site_id: uuid.UUID
    name: str
    address: str | None
    latitude: float | None
    longitude: float | None
    distance_km: float | None = None
    total_points: int
    available_points: int
    max_kw: float
    connectors: list[str]
    price_per_kwh: float | None


class PriorityRuleIn(BaseModel):
    """Regra de prioridade nomeada.

    A validacao aqui existe porque o banco so consegue barrar o que e' local a
    uma linha. Ele garante que a janela tenha os dois lados e que o criterio
    tenha valor; o que ele nao ve e' se o texto do criterio faz sentido.
    """

    nome: str = Field(min_length=1, max_length=80)
    prioridade: int = Field(ge=0, le=1000)
    ordem: int = Field(default=100, ge=0, le=10000)
    ativo: bool = True
    criterio_tipo: Literal["sempre", "ponto", "conector"] = "sempre"
    criterio_valor: str | None = Field(default=None, max_length=400)
    janela_inicio: time | None = None
    janela_fim: time | None = None

    @model_validator(mode="after")
    def _coerente(self):
        if (self.janela_inicio is None) != (self.janela_fim is None):
            # Com um so lado nao da para saber se o outro extremo e' o inicio ou
            # o fim do dia, e a regra passaria a valer em horarios que ninguem
            # pediu - justamente numa regra que decide quem fica sem carregar.
            raise ValueError("janela precisa de inicio e fim, ou de nenhum dos dois")
        if self.criterio_tipo != "sempre" and not (self.criterio_valor or "").strip():
            raise ValueError(f"criterio '{self.criterio_tipo}' exige criterio_valor")
        if self.janela_inicio is not None and self.janela_inicio == self.janela_fim:
            # Nao e' "o dia inteiro" nem "instante nenhum": e' ambiguo. Recusar e'
            # melhor que escolher por conta - a escolha errada some no silencio.
            raise ValueError("janela de duracao zero: use nenhuma janela para valer o dia todo")
        return self


class PriorityRuleOut(BaseModel):
    id: str
    nome: str
    prioridade: int
    ordem: int
    ativo: bool
    criterio_tipo: str
    criterio_valor: str | None
    janela_inicio: str | None
    janela_fim: str | None
