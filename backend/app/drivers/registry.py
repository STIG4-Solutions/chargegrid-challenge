"""Pool de drivers: uma instancia viva por ponto de recarga.

Conexoes Modbus sao caras e o HCA G2 tolera poucas simultaneas - por isso o
driver e criado uma vez e reaproveitado por poller, alocador e API.
"""

from __future__ import annotations

import asyncio

from app.core.config import settings
from app.drivers.base import ChargePointDriver
from app.drivers.modbus_driver import ModbusChargePointDriver
from app.drivers.simulator import SimulatedChargePointDriver
from app.models.charge_point import ChargePoint

DRIVERS: dict[str, type[ChargePointDriver]] = {
    "modbus_tcp": ModbusChargePointDriver,
    "simulator": SimulatedChargePointDriver,
}


class DriverRegistry:
    def __init__(self) -> None:
        self._drivers: dict[str, ChargePointDriver] = {}
        self._lock = asyncio.Lock()

    async def get(self, charge_point: ChargePoint) -> ChargePointDriver:
        cp_id = str(charge_point.id)
        if cp_id in self._drivers:
            return self._drivers[cp_id]

        async with self._lock:
            if cp_id in self._drivers:  # outra corrotina criou enquanto esperavamos
                return self._drivers[cp_id]

            conn = charge_point.connection
            # CHARGER_DRIVER=simulator forca o modo offline, mesmo com conexao cadastrada.
            protocol = (
                "simulator"
                if settings.charger_driver == "simulator"
                else (conn.protocol if conn else "simulator")
            )
            driver_cls = DRIVERS.get(protocol, SimulatedChargePointDriver)
            driver = driver_cls(
                charge_point_id=cp_id,
                host=conn.host if conn else None,
                port=conn.port if conn else 502,
                unit_id=conn.unit_id if conn else 1,
                rated_kw=float(charge_point.rated_kw),
                min_kw=float(charge_point.min_kw),
                **(conn.options if conn else {}),
            )
            self._drivers[cp_id] = driver
            return driver

    async def drop(self, charge_point_id: str) -> None:
        driver = self._drivers.pop(charge_point_id, None)
        if driver is not None:
            await driver.close()

    async def close_all(self) -> None:
        for driver in list(self._drivers.values()):
            await driver.close()
        self._drivers.clear()


registry = DriverRegistry()
