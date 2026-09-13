"""Mapa Modbus do GoodWe HCA G2 (docs/Mapa MODBUS_HCA G2.md, protocolo V1.0.15).

Fonte unica de verdade dos registradores. Nenhum endereco magico espalhado pelo
codigo: o driver le e escreve sempre atraves das definicoes abaixo.

Convencoes do fabricante:
  - SF (scale factor / ganho): valor_fisico = valor_bruto / SF
  - U32 ocupa 2 registradores, big-endian (registrador alto primeiro)
  - STR e ASCII empacotado em 2 bytes por registrador, preenchido com nulos
"""

from dataclasses import dataclass
from enum import IntEnum


class RegType(IntEnum):
    U16 = 1
    S16 = 2
    U32 = 3
    STR = 4


@dataclass(frozen=True, slots=True)
class Reg:
    address: int
    name: str
    type: RegType
    size: int = 1
    scale: int = 1
    unit: str = ""
    writable: bool = False


# ---------------------------------------------------------------- despacho / falhas
EMS_ENERGY_DISPATCH = Reg(10000, "ems_energy_dispatch", RegType.U16, writable=True)
"""1 = forca o ponto para a potencia minima; 0 = operacao normal.

Alavanca mais rapida do controle de demanda: corta a carga EV do site inteiro em
uma escrita, sem derrubar as sessoes.
"""

AC_FAULT_BYTES = [Reg(10000 + i, f"ac_fault_bytes_{i:02d}", RegType.U16) for i in range(1, 9)]

# Bits dos registradores 10001-10008 (coluna Note(English) da planilha do fabricante).
FAULT_BITS: dict[int, dict[int, str]] = {
    10001: {
        0: "Parada de emergencia acionada",
        1: "Protecao de sobretensao",
        2: "Protecao de sobrecorrente",
        3: "Protecao de subtensao",
        4: "Falha no conector",
        5: "S2 desconectado",
        6: "Sobretemperatura ambiente",
        7: "Sobretemperatura no cabo de recarga",
    },
    10002: {
        0: "Falha de controle de acesso",
        1: "Falha de aterramento",
        2: "Timeout de handshake",
        3: "Falha de comunicacao do leitor RFID",
        4: "Falha de comunicacao do display",
        5: "Falha do CI de medicao embarcado",
        6: "Falha do rele de saida",
        7: "Falha da trava do conector",
    },
    10003: {
        0: "Curto-circuito na saida",
        1: "Corrente de fuga",
        2: "Carga pausada por mais de 10 min",
        3: "Leitura do medidor inconsistente",
        4: "Ponto offline durante carga por PV/bateria",
        5: "Potencia insuficiente de PV/bateria",
    },
    10005: {
        0: "Alarme de sobretemperatura no cabo",
        1: "Alarme de aterramento",
        2: "Alarme de timeout de handshake",
        3: "Alarme de comunicacao RFID",
        4: "Alarme de comunicacao do display",
        5: "Alarme do CI de medicao",
        6: "Alarme de parada de carga",
        7: "Leitura do medidor inconsistente",
    },
    10006: {0: "Alarme de sobretemperatura ambiente"},
    10007: {
        0: "Falha da flash externa",
        1: "Falha da EEPROM",
        2: "Falha do dispositivo de deteccao de fuga",
        3: "Alimentacao de entrada anormal",
        4: "SN nao cadastrado",
        5: "Parametros de fabrica inconsistentes",
        6: "Firmware nao autorizado",
    },
}

# ------------------------------------------------------------------- medicao ao vivo
VOLTAGE_A = Reg(10009, "voltage_a", RegType.U16, scale=10, unit="V")
VOLTAGE_B = Reg(10010, "voltage_b", RegType.U16, scale=10, unit="V")
VOLTAGE_C = Reg(10011, "voltage_c", RegType.U16, scale=10, unit="V")
CURRENT_A = Reg(10012, "current_a", RegType.U16, scale=10, unit="A")
CURRENT_B = Reg(10013, "current_b", RegType.U16, scale=10, unit="A")
CURRENT_C = Reg(10014, "current_c", RegType.U16, scale=10, unit="A")
CHARGING_POWER = Reg(10015, "charging_power", RegType.U16, scale=10, unit="kW")
CHARGING_CAPACITY = Reg(10016, "charging_capacity", RegType.U16, scale=10, unit="kWh")
STATION_STATUS = Reg(10017, "station_status", RegType.U16)
COMM_STATUS = Reg(10018, "comm_status", RegType.U16)

# 10017 - estado do ponto conforme o fabricante.
HW_STATUS = {
    0: "idle_unplugged",
    1: "idle_plugged",
    2: "handshaking",
    3: "charging",
    4: "charge_complete",
    5: "alarm",
    6: "scheduled_start",
    7: "maintenance",
    8: "start_failed",
    9: "firmware_upgrade",
    10: "interrupted_low_power",
}

# 10018 - bitfield de conectividade.
COMM_BITS = {
    0: "wifi_router",
    1: "iot_cloud",
    2: "inverter",
    3: "mid_meter",
    4: "gw_meter",
    5: "ems",
}

# -------------------------------------------------------------- politicas de recarga
PLUG_AND_CHARGE = Reg(10019, "plug_and_charge", RegType.U16, writable=True)
RESERVATION_STATUS = Reg(10020, "reservation_status", RegType.U16, writable=True)
RESERVATION_START = Reg(10021, "reservation_start", RegType.U16, writable=True)
RESERVATION_DURATION = Reg(10022, "reservation_duration", RegType.U16, unit="min", writable=True)
PHASE_SWITCH_ENABLE = Reg(10023, "phase_switch_enable", RegType.U16, writable=True)
KEEP_MIN_POWER = Reg(10024, "keep_min_power", RegType.U16, writable=True)
DYNAMIC_LOAD_MGMT = Reg(10025, "dynamic_load_mgmt", RegType.U16, writable=True)
"""Controle Dinamico de Carga do proprio ponto (protecao local do disjuntor).

Mantemos ligado como rede de seguranca: se a plataforma cair, o hardware ainda
evita o disparo do disjuntor principal. Nosso alocador atua uma camada acima.
"""
MAIN_BREAKER_CURRENT = Reg(10026, "main_breaker_current", RegType.U16, unit="A", writable=True)
MAX_CHARGING_CAPACITY = Reg(
    10027, "max_charging_capacity", RegType.U16, scale=10, unit="kWh", writable=True
)
MIN_CHARGING_CAPACITY = Reg(
    10028, "min_charging_capacity", RegType.U16, scale=10, unit="kWh", writable=True
)
MAX_CHARGING_POWER = Reg(
    10029, "max_charging_power", RegType.U16, scale=10, unit="kW", writable=True
)
"""Faixa valida [14, 220] em decimos de kW: 1,4-7 kW mono, 4,2-11/22 kW trifasico.

Registrador central do Gerenciamento de Potencia - o alocador escreve aqui.
"""
BATTERY_DISCHARGE_SOC = Reg(10030, "battery_discharge_soc", RegType.U16, unit="%", writable=True)
COMPLETION_TIME = Reg(10031, "completion_time", RegType.U16, unit="h", writable=True)
ADVANCED_MODE = Reg(10032, "advanced_mode", RegType.U16, writable=True)
GRID_POWER_LIMIT = Reg(10039, "grid_power_limit", RegType.U16, scale=10, unit="kW", writable=True)

ADVANCED_MODES = {0: "fast", 1: "pv_only", 2: "pv_battery"}

# Daqui para baixo, alguns registradores estao mapeados para completar a
# documentacao do protocolo e nao sao lidos pelo driver hoje: SEMS_ACCOUNT,
# SAFETY_VERSION, CP_VOLTAGE_STATE, RECORD_INDEX, TERMINATION_REASON, COMM_BITS,
# ADVANCED_MODES e AC_FAULT_BYTES. Estao aqui de proposito - o mapa e a fonte
# unica de verdade do HCA G2, e ligar qualquer um deles depois nao exige
# reabrir a planilha do fabricante. O que o driver realmente le esta em
# POLL_BLOCKS, no fim do arquivo.

# ----------------------------------------------------------------------- identidade
SERIAL_NUMBER = Reg(10040, "serial_number", RegType.STR, size=8)
SOFTWARE_VERSION = Reg(10048, "software_version", RegType.STR, size=2)
HARDWARE_VERSION = Reg(10056, "hardware_version", RegType.STR, size=2)
POWER_SPEC = Reg(10058, "power_spec", RegType.U16)
STATION_TYPE = Reg(10059, "station_type", RegType.U16)
SEMS_ACCOUNT = Reg(10085, "sems_account", RegType.STR, size=18)
SAFETY_VERSION = Reg(10592, "safety_version", RegType.STR, size=2)

POWER_SPECS = {0: 7.0, 1: 11.0, 2: 22.0}
STATION_TYPES = {0: "three_phase", 1: "single_phase"}

# ---------------------------------------------------------------- comando de sessao
CHARGE_SWITCH = Reg(10060, "charge_switch", RegType.U16, writable=True)
CHARGE_OFF, CHARGE_ON = 1, 2

CHARGE_AMOUNT = Reg(10061, "charge_amount", RegType.U32, size=2, scale=100)
CHARGE_DURATION = Reg(10063, "charge_duration", RegType.U32, size=2, unit="s")
ACCUMULATED_ENERGY = Reg(10065, "accumulated_energy", RegType.U32, size=2, scale=10, unit="kWh")

CAR_CONNECTION = Reg(10075, "car_connection", RegType.U16)
START_MODE = Reg(10076, "start_mode", RegType.U16)
CHARGE_STRATEGY = Reg(10077, "charge_strategy", RegType.U16)
APPOINTMENT_FLAG = Reg(10079, "appointment_flag", RegType.U16)
CP_VOLTAGE_STATE = Reg(10084, "cp_voltage_state", RegType.U16)

CAR_CONNECTION_STATES = {0: "disconnected", 1: "half_connected", 2: "connected"}
START_MODES = {
    0: "auth_card",
    1: "backend",
    2: "local_admin",
    3: "vin",
    4: "wallet_card",
    5: "plug_and_charge",
    6: "reservation",
    7: "bluetooth_app",
}

# --------------------------------------------------------------- energia e registro
GREEN_ENERGY = Reg(10103, "green_energy", RegType.U32, size=2, scale=10, unit="kWh")
GRID_BOUGHT_ENERGY = Reg(10105, "grid_bought_energy", RegType.U32, size=2, scale=10, unit="kWh")
PROJECT_TYPE = Reg(10107, "project_type", RegType.U16)
POWER_SOURCE_BITS = Reg(10108, "power_source_bits", RegType.U16)
TRANSPARENT_MODE = Reg(10157, "transparent_mode", RegType.U16, writable=True)

# 10108 - bitfield da origem da energia entregue.
POWER_SOURCE_BIT_MAP = {0: "grid", 1: "pv", 2: "battery"}

CHARGE_START_YM = Reg(10158, "charge_start_ym", RegType.U16)
CHARGE_START_DH = Reg(10159, "charge_start_dh", RegType.U16)
CHARGE_START_MS = Reg(10160, "charge_start_ms", RegType.U16)
CHARGE_END_YM = Reg(10162, "charge_end_ym", RegType.U16)
CHARGE_END_DH = Reg(10163, "charge_end_dh", RegType.U16)
CHARGE_END_MS = Reg(10164, "charge_end_ms", RegType.U16)
RECORD_DURATION = Reg(10166, "record_duration", RegType.U32, size=2, unit="s")
TERMINATION_REASON = Reg(10168, "termination_reason", RegType.U32, size=2)
METER_BEFORE = Reg(10170, "meter_before", RegType.U32, size=2, scale=100, unit="kWh")
METER_AFTER = Reg(10172, "meter_after", RegType.U32, size=2, scale=100, unit="kWh")
RECORD_INDEX = Reg(10174, "record_index", RegType.U32, size=2)
CLEAR_SESSION_ENERGY = Reg(10176, "clear_session_energy", RegType.U16, writable=True)

# ----------------------------------------------------------------------- cartao RFID
RFID_LAST_CARD = Reg(10500, "rfid_last_card", RegType.STR, size=7)
RFID_ADD = Reg(10507, "rfid_add", RegType.STR, size=7, writable=True)
RFID_DELETE = Reg(10514, "rfid_delete", RegType.STR, size=7, writable=True)
RFID_LIST = Reg(10521, "rfid_list", RegType.STR, size=70)

IOT_ALARM = Reg(30000, "iot_alarm", RegType.U16)

# --------------------------------------------------------------- blocos de varredura
# Uma varredura completa em poucas transacoes: leituras unitarias em rajada sao
# lentas no HCA G2, e cada bloco cabe no limite de 125 registradores do Modbus.
POLL_BLOCKS: list[tuple[int, int]] = [
    (10001, 18),  # falhas + medicao + status + comunicacao
    (10019, 21),  # politicas, limites, orcamento local
    (10058, 8),  # specs, liga/desliga, valor e duracao da sessao
    (10065, 2),  # energia acumulada
    (10075, 10),  # conexao do carro, modo de inicio, estrategia, CP
    (10103, 6),  # energia verde, energia da rede, tipo, origem
    (10158, 18),  # registro da ultima sessao (inicio, fim, medidor)
]


# Nem tudo que acende bit e' motivo para encerrar a recarga.
#
# O registrador 10005 e' de ALARME, nao de falha - os proprios rotulos dizem
# "Alarme de ...". E no 10003 so os dois primeiros bits sao defeito eletrico; os
# demais descrevem condicao de operacao. "Potencia insuficiente de PV/bateria" e
# "Ponto offline durante carga por PV/bateria" sao rotina numa instalacao
# alimentada por solar - que e' a premissa deste projeto.
#
# Tratar tudo como terminal derrubava a sessao por causa de uma nuvem.
NAO_TERMINAIS: frozenset[tuple[int, int]] = frozenset(
    {(10003, 2), (10003, 3), (10003, 4), (10003, 5)} | {(10005, bit) for bit in FAULT_BITS[10005]}
)


def _classificar(values: dict[int, int]) -> tuple[list[str], list[str]]:
    terminais: list[str] = []
    operacionais: list[str] = []
    for address, bit_map in FAULT_BITS.items():
        raw = values.get(address)
        if not raw:
            continue
        for bit, label in bit_map.items():
            if not raw >> bit & 1:
                continue
            alvo = operacionais if (address, bit) in NAO_TERMINAIS else terminais
            alvo.append(label)
    return terminais, operacionais


def decode_terminal_faults(values: dict[int, int]) -> list[str]:
    """So o que obriga a encerrar a sessao."""
    return _classificar(values)[0]


def decode_operational_flags(values: dict[int, int]) -> list[str]:
    """Condicoes que o operador deve ver, mas que nao encerram a recarga."""
    return _classificar(values)[1]


def decode_faults(values: dict[int, int]) -> list[str]:
    """Recebe {endereco: valor_bruto} e devolve a lista legivel de falhas ativas."""
    faults: list[str] = []
    for address, bit_map in FAULT_BITS.items():
        raw = values.get(address)
        if not raw:
            continue
        faults.extend(label for bit, label in bit_map.items() if raw >> bit & 1)
    return faults


def decode_power_sources(raw: int | None) -> list[str]:
    if not raw:
        return []
    return [name for bit, name in POWER_SOURCE_BIT_MAP.items() if raw >> bit & 1]


def encode_hhmm(hour: int, minute: int) -> int:
    """Reg 10021: byte alto = hora, byte baixo = minuto (0x0C1E = 12:30)."""
    return (hour & 0xFF) << 8 | (minute & 0xFF)


def decode_hhmm(raw: int) -> tuple[int, int]:
    return raw >> 8 & 0xFF, raw & 0xFF


def clamp_power_kw(kw: float, rated_kw: float, min_kw: float) -> float:
    """Ajusta um alvo de potencia a faixa aceita pelo reg 10029 daquele ponto."""
    return round(max(min_kw, min(kw, rated_kw)), 1)
