"""Driver Modbus TCP para a linha GoodWe HCA G2."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

from app.core.config import settings
from app.core.logging import get_logger
from app.drivers import modbus_map as M
from app.drivers.base import ChargePointDriver, ChargePointReading, CommandResult

log = get_logger(__name__)


def _u32(high: int, low: int) -> int:
    """Big-endian: registrador alto primeiro, conforme a planilha do fabricante."""
    return (high << 16) | low


def _decode_str(words: list[int]) -> str:
    raw = bytearray()
    for w in words:
        raw += bytes([(w >> 8) & 0xFF, w & 0xFF])
    return raw.split(b"\x00")[0].decode("ascii", errors="ignore").strip()


def _scaled(raw: int | None, scale: int) -> float | None:
    if raw is None or raw in (0xFFFF, 0x8000):  # NAN definido pelo fabricante
        return None
    return raw / scale


class ModbusChargePointDriver(ChargePointDriver):
    protocol = "modbus_tcp"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = None
        # Uma transacao por vez: o HCA G2 aceita poucas conexoes simultaneas.
        self._lock = asyncio.Lock()
        self._offset = settings.modbus_register_offset

    # ------------------------------------------------------------------ conexao
    async def connect(self) -> None:
        from pymodbus.client import AsyncModbusTcpClient

        if self._client is not None and self._client.connected:
            return
        self._client = AsyncModbusTcpClient(
            host=self.host, port=self.port, timeout=settings.modbus_timeout_s
        )
        await self._client.connect()
        if not self._client.connected:
            raise ConnectionError(f"sem conexao Modbus com {self.host}:{self.port}")

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # ------------------------------------------- primitivas de leitura e escrita
    async def _read_block(self, address: int, count: int) -> dict[int, int]:
        await self.connect()
        rr = await self._client.read_holding_registers(
            address + self._offset, count=count, slave=self.unit_id
        )
        if rr.isError():
            raise OSError(f"erro Modbus lendo {address}+{count}: {rr}")
        return {address + i: value for i, value in enumerate(rr.registers)}

    async def _write(self, reg: M.Reg, value: int) -> None:
        if not reg.writable:
            raise ValueError(f"registrador {reg.address} ({reg.name}) e somente leitura")
        await self.connect()
        rq = await self._client.write_register(
            reg.address + self._offset, value, slave=self.unit_id
        )
        if rq.isError():
            raise OSError(f"erro Modbus escrevendo {reg.address}={value}: {rq}")

    async def _command(self, name: str, reg: M.Reg, value: int, **payload) -> CommandResult:
        started = time.perf_counter()
        try:
            async with self._lock:
                await self._write(reg, value)
            return CommandResult(
                ok=True,
                command=name,
                register=reg.address,
                raw_value=value,
                latency_ms=int((time.perf_counter() - started) * 1000),
                payload=payload,
            )
        except Exception as exc:  # noqa: BLE001 - a falha vira CommandResult auditavel
            log.warning(
                "modbus.command_failed", command=name, cp=self.charge_point_id, error=str(exc)
            )
            return CommandResult(
                ok=False,
                command=name,
                register=reg.address,
                raw_value=value,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=str(exc),
                payload=payload,
            )

    # ------------------------------------------------------------------ varredura
    async def read(self) -> ChargePointReading:
        now = datetime.now(UTC)
        values: dict[int, int] = {}
        try:
            async with self._lock:
                for address, count in M.POLL_BLOCKS:
                    values |= await self._read_block(address, count)
                values |= await self._read_block(M.SERIAL_NUMBER.address, 8)
                values |= await self._read_block(M.SOFTWARE_VERSION.address, 2)
                values |= await self._read_block(M.RFID_LAST_CARD.address, 7)
        except Exception as exc:  # noqa: BLE001
            log.warning("modbus.read_failed", cp=self.charge_point_id, error=str(exc))
            await self.close()
            return ChargePointReading(
                recorded_at=now, online=False, faults=[f"Sem comunicacao: {exc}"]
            )

        def g(address: int) -> int | None:
            return values.get(address)

        def u32_at(reg: M.Reg, divisor: int = 1) -> float | None:
            high, low = g(reg.address), g(reg.address + 1)
            if high is None or low is None:
                return None
            return _u32(high, low) / divisor

        power_spec = g(M.POWER_SPEC.address)
        station_type = g(M.STATION_TYPE.address)

        return ChargePointReading(
            recorded_at=now,
            online=True,
            hw_status=M.HW_STATUS.get(g(M.STATION_STATUS.address) or 0, "unknown"),
            car_connection=M.CAR_CONNECTION_STATES.get(g(M.CAR_CONNECTION.address) or 0, "unknown"),
            power_kw=_scaled(g(M.CHARGING_POWER.address), M.CHARGING_POWER.scale) or 0.0,
            session_energy_kwh=_scaled(g(M.CHARGING_CAPACITY.address), 10) or 0.0,
            meter_kwh=u32_at(M.ACCUMULATED_ENERGY, 10),
            green_kwh=u32_at(M.GREEN_ENERGY, 10),
            voltage_a=_scaled(g(M.VOLTAGE_A.address), 10),
            voltage_b=_scaled(g(M.VOLTAGE_B.address), 10),
            voltage_c=_scaled(g(M.VOLTAGE_C.address), 10),
            current_a=_scaled(g(M.CURRENT_A.address), 10),
            current_b=_scaled(g(M.CURRENT_B.address), 10),
            current_c=_scaled(g(M.CURRENT_C.address), 10),
            applied_limit_kw=_scaled(g(M.MAX_CHARGING_POWER.address), 10),
            session_duration_s=int(u32_at(M.CHARGE_DURATION) or 0),
            power_sources=M.decode_power_sources(g(M.POWER_SOURCE_BITS.address)),
            faults=M.decode_terminal_faults(values),
            operational_flags=M.decode_operational_flags(values),
            start_mode=M.START_MODES.get(g(M.START_MODE.address) or -1),
            last_rfid_uid=_decode_str(
                [values.get(M.RFID_LAST_CARD.address + i, 0) for i in range(7)]
            )
            or None,
            serial_number=_decode_str(
                [values.get(M.SERIAL_NUMBER.address + i, 0) for i in range(8)]
            )
            or None,
            firmware_version=_decode_str(
                [values.get(M.SOFTWARE_VERSION.address + i, 0) for i in range(2)]
            )
            or None,
            rated_kw=M.POWER_SPECS.get(power_spec) if power_spec is not None else None,
            phase_type=M.STATION_TYPES.get(station_type) if station_type is not None else None,
            raw=values,
        )

    # -------------------------------------------------------------------- comandos
    def _faixa_decimos(self) -> tuple[int, int]:
        """Faixa aceita pelos regs 10029/10039 NESTE equipamento, em decimos de kW.

        A planilha lista [14, 220], mas isso e o envelope da linha HCA inteira.
        Por modelo o fabricante especifica 1,4-7 kW no monofasico e 4,2-11 ou
        4,2-22 kW no trifasico. Escrever fora da faixa do modelo faz o
        carregador recusar com Illegal Data Value - ou pior, num equipamento de
        7 kW aceitar um teto de 22 kW que o circuito nao suporta.
        """
        rated = float(self.options.get("rated_kw") or 22.0)
        minimo = float(self.options.get("min_kw") or 1.4)
        return max(14, int(round(minimo * 10))), min(220, int(round(rated * 10)))

    async def set_power_limit(self, kw: float) -> CommandResult:
        piso, teto = self._faixa_decimos()
        raw = max(piso, min(teto, int(round(kw * 10))))
        return await self._command("set_power_limit", M.MAX_CHARGING_POWER, raw, kw=raw / 10)

    async def start_charging(self) -> CommandResult:
        return await self._command("start_charging", M.CHARGE_SWITCH, M.CHARGE_ON)

    async def stop_charging(self) -> CommandResult:
        return await self._command("stop_charging", M.CHARGE_SWITCH, M.CHARGE_OFF)

    async def set_dispatch_throttle(self, throttled: bool) -> CommandResult:
        return await self._command(
            "set_dispatch_throttle", M.EMS_ENERGY_DISPATCH, 1 if throttled else 0
        )

    async def set_dynamic_load_management(self, enabled: bool) -> CommandResult:
        return await self._command(
            "set_dynamic_load_management", M.DYNAMIC_LOAD_MGMT, 1 if enabled else 0
        )

    async def set_grid_power_limit(self, kw: float) -> CommandResult:
        piso, teto = self._faixa_decimos()
        raw = max(piso, min(teto, int(round(kw * 10))))
        return await self._command("set_grid_power_limit", M.GRID_POWER_LIMIT, raw, kw=raw / 10)

    async def _write_str(self, reg: M.Reg, text: str, name: str) -> CommandResult:
        """STR ocupa varios registradores: exige write_registers em bloco."""
        started = time.perf_counter()
        padded = text.ljust(reg.size * 2, "\x00").encode("ascii")[: reg.size * 2]
        words = [(padded[i] << 8) | padded[i + 1] for i in range(0, len(padded), 2)]
        try:
            async with self._lock:
                await self.connect()
                rq = await self._client.write_registers(
                    reg.address + self._offset, words, slave=self.unit_id
                )
                if rq.isError():
                    raise OSError(str(rq))
            return CommandResult(
                ok=True,
                command=name,
                register=reg.address,
                latency_ms=int((time.perf_counter() - started) * 1000),
                payload={"value": text},
            )
        except Exception as exc:  # noqa: BLE001
            return CommandResult(ok=False, command=name, register=reg.address, error=str(exc))

    async def add_rfid_card(self, uid: str) -> CommandResult:
        return await self._write_str(M.RFID_ADD, uid, "add_rfid_card")

    async def remove_rfid_card(self, uid: str) -> CommandResult:
        return await self._write_str(M.RFID_DELETE, uid, "remove_rfid_card")

    async def push_reservation(self, hour: int, minute: int, duration_min: int) -> CommandResult:
        result = await self._command(
            "push_reservation", M.RESERVATION_START, M.encode_hhmm(hour, minute)
        )
        if not result.ok:
            return result
        await self._command("push_reservation_duration", M.RESERVATION_DURATION, duration_min)
        # 1 = valida uma unica vez (reg 10020).
        return await self._command("push_reservation_enable", M.RESERVATION_STATUS, 1)

    async def clear_reservation(self) -> CommandResult:
        """Zera o reg 10020 e devolve a vaga.

        Sem isto, cancelar no app deixaria o equipamento recusando cartao alheio
        ate' a janela passar - o motorista desiste da reserva e o ponto continua
        bloqueado para quem chegasse na frente.
        """
        return await self._command("clear_reservation", M.RESERVATION_STATUS, 0)
