"""Simulador de eletroposto.

Permite rodar a plataforma inteira sem hardware - util para desenvolver o app
mobile e para a banca avaliar o fluxo. Ele respeita as mesmas regras do HCA G2:
teto de potencia do reg 10029, curva de carga que cai no fim da bateria e
transicao para ocioso quando o carro para de puxar energia.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from app.drivers.base import ChargePointDriver, ChargePointReading, CommandResult

# Estado global do simulador, indexado por ponto de recarga.
_STATE: dict[str, dict] = {}


class SimulatedChargePointDriver(ChargePointDriver):
    protocol = "simulator"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rated = float(self.options.get("rated_kw", 22.0))
        self.state = _STATE.setdefault(
            self.charge_point_id,
            {
                "charging": False,
                "throttled": False,
                "limit_kw": rated,
                "rated_kw": rated,
                "min_kw": float(self.options.get("min_kw", 4.2)),
                "session_kwh": 0.0,
                "meter_kwh": float(self.options.get("meter_kwh", 1000.0)),
                "green_kwh": 0.0,
                "duration_s": 0,
                "battery_kwh": 60.0,
                "soc": 0.25,
                "last_read": None,
                "faults": [],
                "plugged": False,
            },
        )

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def _target_power(self) -> float:
        """Potencia instantanea: teto aplicado, com taper acima de 80 por cento de SOC."""
        s = self.state
        if not s["charging"] or s["soc"] >= 0.995:
            return 0.0
        ceiling = s["min_kw"] if s["throttled"] else s["limit_kw"]
        taper = 1.0 if s["soc"] < 0.8 else max(0.15, math.cos((s["soc"] - 0.8) * math.pi / 0.4))
        return round(min(ceiling, s["rated_kw"]) * taper, 2)

    async def read(self) -> ChargePointReading:
        s = self.state
        now = datetime.now(UTC)

        # Integra energia desde a leitura anterior.
        elapsed_s = 0.0
        if s["last_read"] is not None:
            elapsed_s = (now - s["last_read"]).total_seconds()
        s["last_read"] = now

        power = self._target_power()
        if elapsed_s > 0 and power > 0:
            delta_kwh = power * elapsed_s / 3600
            s["session_kwh"] = round(s["session_kwh"] + delta_kwh, 4)
            s["meter_kwh"] = round(s["meter_kwh"] + delta_kwh, 4)
            # Fatia verde: metade da energia vem de PV/bateria no cenario simulado.
            s["green_kwh"] = round(s["green_kwh"] + delta_kwh * 0.5, 4)
            s["soc"] = min(1.0, s["soc"] + delta_kwh / s["battery_kwh"])
            s["duration_s"] = int(s["duration_s"] + elapsed_s)
        elif s["charging"]:
            s["duration_s"] = int(s["duration_s"] + elapsed_s)

        if s["charging"] and s["soc"] >= 0.995:
            hw_status = "charge_complete"
        elif s["charging"]:
            hw_status = "charging"
        elif s["plugged"]:
            hw_status = "idle_plugged"
        else:
            hw_status = "idle_unplugged"

        phase_v = 220.0 if s["rated_kw"] <= 7.5 else 380.0
        current = round(power * 1000 / (phase_v * (1 if s["rated_kw"] <= 7.5 else 1.732)), 1)

        return ChargePointReading(
            recorded_at=now,
            online=True,
            hw_status=hw_status,
            car_connection="connected" if s["plugged"] or s["charging"] else "disconnected",
            power_kw=power,
            session_energy_kwh=round(s["session_kwh"], 3),
            meter_kwh=round(s["meter_kwh"], 3),
            green_kwh=round(s["green_kwh"], 3),
            voltage_a=phase_v,
            voltage_b=phase_v if s["rated_kw"] > 7.5 else None,
            voltage_c=phase_v if s["rated_kw"] > 7.5 else None,
            current_a=current,
            applied_limit_kw=s["limit_kw"],
            session_duration_s=s["duration_s"],
            power_sources=["grid", "pv"] if power > 0 else [],
            faults=list(s["faults"]),
            operational_flags=self._alarmes_simulados(now),
            start_mode="backend" if s["charging"] else None,
            serial_number=f"SIM{self.charge_point_id[:8].upper()}",
            firmware_version="1.00.00",
            rated_kw=s["rated_kw"],
            phase_type="single_phase" if s["rated_kw"] <= 7.5 else "three_phase",
        )

    def _alarmes_simulados(self, now: datetime) -> list[str]:
        """Alarmes intermitentes, para o simulador exercitar a manutencao.

        O medidor virtual ja sintetiza a curva do dia; isto e' o equivalente do
        lado do carregador. Sao ALARMES do registrador 10005 - nao encerram
        sessao, exatamente como o hardware real -, entao o simulador continua
        entregando energia normalmente.

        Deterministico pela hora e pelo ponto, nao aleatorio: um alarme que
        aparece e some sozinho a cada leitura viraria ruido e nao serie. Assim
        um ponto especifico "esquenta" em janelas previsiveis, que e' o padrao
        que a manutencao preditiva existe para encontrar.

        Some inteiro com CHARGER_DRIVER=modbus: la' os bits vem do equipamento.
        """
        if not self.state["charging"]:
            return []
        # Um ponto entre quatro, em ~10 min de cada hora carregando.
        semente = sum(ord(c) for c in self.charge_point_id[:8])
        if semente % 4 != now.hour % 4:
            return []
        if not 20 <= now.minute < 30:
            return []
        return ["Alarme de sobretemperatura no cabo"]

    async def set_power_limit(self, kw: float) -> CommandResult:
        self.state["limit_kw"] = round(
            max(self.state["min_kw"], min(kw, self.state["rated_kw"])), 1
        )
        return CommandResult(
            ok=True, command="set_power_limit", payload={"kw": self.state["limit_kw"]}
        )

    async def start_charging(self) -> CommandResult:
        self.state.update(charging=True, plugged=True, session_kwh=0.0, duration_s=0, green_kwh=0.0)
        return CommandResult(ok=True, command="start_charging")

    async def stop_charging(self) -> CommandResult:
        self.state["charging"] = False
        return CommandResult(ok=True, command="stop_charging")

    async def set_dispatch_throttle(self, throttled: bool) -> CommandResult:
        self.state["throttled"] = throttled
        return CommandResult(
            ok=True, command="set_dispatch_throttle", payload={"throttled": throttled}
        )

    async def set_dynamic_load_management(self, enabled: bool) -> CommandResult:
        return CommandResult(ok=True, command="set_dynamic_load_management")

    async def set_grid_power_limit(self, kw: float) -> CommandResult:
        return CommandResult(ok=True, command="set_grid_power_limit", payload={"kw": kw})

    async def add_rfid_card(self, uid: str) -> CommandResult:
        return CommandResult(ok=True, command="add_rfid_card", payload={"uid": uid})

    async def remove_rfid_card(self, uid: str) -> CommandResult:
        return CommandResult(ok=True, command="remove_rfid_card", payload={"uid": uid})

    async def push_reservation(self, hour: int, minute: int, duration_min: int) -> CommandResult:
        self.state["reservation"] = {"hour": hour, "minute": minute, "duration_min": duration_min}
        return CommandResult(ok=True, command="push_reservation")

    async def clear_reservation(self) -> CommandResult:
        self.state.pop("reservation", None)
        return CommandResult(ok=True, command="clear_reservation")

    # ---- gatilhos usados pelos testes e pela rota /simulator do ambiente dev ----
    def plug_in(self, battery_kwh: float = 60.0, soc: float = 0.25) -> None:
        self.state.update(plugged=True, battery_kwh=battery_kwh, soc=soc)

    def unplug(self) -> None:
        self.state.update(plugged=False, charging=False)

    def inject_fault(self, label: str) -> None:
        self.state["faults"].append(label)
