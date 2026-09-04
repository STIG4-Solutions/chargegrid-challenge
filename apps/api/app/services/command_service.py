"""Ponte unica entre servicos e hardware, com auditoria de todo comando enviado."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.drivers.base import CommandResult
from app.drivers.registry import registry
from app.models.audit import CommandLog
from app.models.charge_point import ChargePoint

log = get_logger(__name__)

# Assinatura de cada comando exposto pelo driver.
COMMANDS = {
    "set_power_limit": lambda d, kw, **_: d.set_power_limit(kw),
    "start_charging": lambda d, **_: d.start_charging(),
    "stop_charging": lambda d, **_: d.stop_charging(),
    "set_dispatch_throttle": lambda d, throttled, **_: d.set_dispatch_throttle(throttled),
    "set_dynamic_load_management": lambda d, enabled, **_: d.set_dynamic_load_management(enabled),
    "set_grid_power_limit": lambda d, kw, **_: d.set_grid_power_limit(kw),
    "add_rfid_card": lambda d, uid, **_: d.add_rfid_card(uid),
    "remove_rfid_card": lambda d, uid, **_: d.remove_rfid_card(uid),
    "push_reservation": lambda d, hour, minute, duration_min, **_: d.push_reservation(
        hour, minute, duration_min
    ),
}


async def send_command(
    db: AsyncSession,
    charge_point: ChargePoint,
    command: str,
    *,
    triggered_by: str = "system",
    **kwargs,
) -> CommandResult:
    """Executa o comando e grava CommandLog - sucesso ou falha.

    Nao levanta excecao: o chamador decide o que fazer com result.ok, e o log
    permanece como prova do que foi enviado ao equipamento.
    """
    if command not in COMMANDS:
        raise ValueError(f"comando desconhecido: {command}")

    driver = await registry.get(charge_point)
    try:
        result = await COMMANDS[command](driver, **kwargs)
    except Exception as exc:  # noqa: BLE001
        result = CommandResult(ok=False, command=command, error=str(exc), payload=kwargs)

    db.add(
        CommandLog(
            charge_point_id=charge_point.id,
            sent_at=datetime.now(UTC),
            command=command,
            register=result.register,
            raw_value=result.raw_value,
            payload={**kwargs, **result.payload},
            success=result.ok,
            error=result.error,
            latency_ms=result.latency_ms,
            triggered_by=triggered_by,
        )
    )
    if not result.ok:
        log.warning("command.failed", cp=charge_point.code, command=command, error=result.error)
    return result
