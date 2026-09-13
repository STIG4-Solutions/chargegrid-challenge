"""Contrato do driver de hardware.

Toda a aplicacao fala com o eletroposto por esta interface. Hoje existe uma
implementacao Modbus TCP e um simulador; quando a linha HCA ganhar OCPP 1.6J,
basta uma terceira implementacao - nenhum servico muda.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class ChargePointReading:
    """Fotografia normalizada de uma varredura, independente do protocolo."""

    recorded_at: datetime
    online: bool = True

    hw_status: str = "idle_unplugged"  # ver modbus_map.HW_STATUS
    car_connection: str = "disconnected"
    power_kw: float = 0.0
    session_energy_kwh: float = 0.0
    meter_kwh: float | None = None
    green_kwh: float | None = None

    voltage_a: float | None = None
    voltage_b: float | None = None
    voltage_c: float | None = None
    current_a: float | None = None
    current_b: float | None = None
    current_c: float | None = None

    applied_limit_kw: float | None = None
    session_duration_s: int = 0
    power_sources: list[str] = field(default_factory=list)
    faults: list[str] = field(default_factory=list)
    # Condicoes ativas que NAO encerram a recarga - alarmes e estados de
    # operacao. Ficam visiveis para o operador, mas a sessao segue.
    operational_flags: list[str] = field(default_factory=list)
    start_mode: str | None = None
    last_rfid_uid: str | None = None

    serial_number: str | None = None
    firmware_version: str | None = None
    rated_kw: float | None = None
    phase_type: str | None = None

    raw: dict[int, int] = field(default_factory=dict)


@dataclass(slots=True)
class CommandResult:
    ok: bool
    command: str
    register: int | None = None
    raw_value: int | None = None
    latency_ms: int | None = None
    error: str | None = None
    payload: dict = field(default_factory=dict)


class ChargePointDriver(ABC):
    """Um driver por ponto de recarga; instancias sao mantidas no DriverRegistry."""

    protocol: str = "abstract"

    def __init__(self, charge_point_id: str, host: str | None, port: int, unit_id: int, **options):
        self.charge_point_id = charge_point_id
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.options = options

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def read(self) -> ChargePointReading:
        """Varredura completa do ponto."""

    @abstractmethod
    async def set_power_limit(self, kw: float) -> CommandResult:
        """Aplica o teto de potencia (reg 10029). Coracao do controle de demanda."""

    @abstractmethod
    async def start_charging(self) -> CommandResult: ...

    @abstractmethod
    async def stop_charging(self) -> CommandResult: ...

    @abstractmethod
    async def set_dispatch_throttle(self, throttled: bool) -> CommandResult:
        """Reg 10000: corta o ponto para a potencia minima sem encerrar a sessao."""

    async def set_dynamic_load_management(self, enabled: bool) -> CommandResult:
        return CommandResult(
            ok=True, command="set_dynamic_load_management", payload={"skipped": True}
        )

    async def set_grid_power_limit(self, kw: float) -> CommandResult:
        return CommandResult(ok=True, command="set_grid_power_limit", payload={"skipped": True})

    async def add_rfid_card(self, uid: str) -> CommandResult:
        return CommandResult(
            ok=False, command="add_rfid_card", error="nao suportado por este driver"
        )

    async def remove_rfid_card(self, uid: str) -> CommandResult:
        return CommandResult(ok=False, command="remove_rfid_card", error="nao suportado")

    async def push_reservation(self, hour: int, minute: int, duration_min: int) -> CommandResult:
        return CommandResult(ok=False, command="push_reservation", error="nao suportado")

    async def clear_reservation(self) -> CommandResult:
        return CommandResult(ok=False, command="clear_reservation", error="nao suportado")
