"""Nem todo bit aceso encerra a recarga.

O servico tratava qualquer entrada de `decode_faults` como terminal e chamava
`fail()`, que so marcava state = ERROR: nenhum comando de parada era enviado - o
carro continuava puxando energia - e a energia entregue nunca virava fatura.

O registrador 10005 e' de alarme, e no 10003 so os dois primeiros bits sao
defeito eletrico. "Potencia insuficiente de PV/bateria" e' rotina numa
instalacao solar, que e' a premissa deste projeto.
"""

from app.drivers import modbus_map as M

# 10001 bit 0 = parada de emergencia; 10003 bit 5 = potencia insuficiente de PV
EMERGENCIA = {10001: 1 << 0}
PV_INSUFICIENTE = {10003: 1 << 5}
PAUSA_LONGA = {10003: 1 << 2}
ALARME_CABO = {10005: 1 << 0}
CURTO = {10003: 1 << 0}


def test_falha_eletrica_e_terminal():
    assert M.decode_terminal_faults(EMERGENCIA) == ["Parada de emergencia acionada"]
    assert M.decode_operational_flags(EMERGENCIA) == []


def test_curto_circuito_e_terminal_mesmo_no_10003():
    assert M.decode_terminal_faults(CURTO) == ["Curto-circuito na saida"]


def test_potencia_insuficiente_de_pv_nao_encerra():
    """Numa instalacao solar isso e' uma nuvem passando."""
    assert M.decode_terminal_faults(PV_INSUFICIENTE) == []
    assert M.decode_operational_flags(PV_INSUFICIENTE) == ["Potencia insuficiente de PV/bateria"]


def test_pausa_longa_nao_encerra():
    assert M.decode_terminal_faults(PAUSA_LONGA) == []
    assert M.decode_operational_flags(PAUSA_LONGA)


def test_registrador_de_alarme_nunca_e_terminal():
    assert M.decode_terminal_faults(ALARME_CABO) == []
    assert M.decode_operational_flags(ALARME_CABO) == ["Alarme de sobretemperatura no cabo"]


def test_todos_os_bits_do_10005_sao_alarme():
    for bit in M.FAULT_BITS[10005]:
        assert M.decode_terminal_faults({10005: 1 << bit}) == [], f"bit {bit} tratado como falha"


def test_decode_faults_antigo_continua_devolvendo_tudo():
    """A lista completa segue existindo: o painel mostra as duas coisas."""
    tudo = M.decode_faults({**EMERGENCIA, **PV_INSUFICIENTE})
    assert len(tudo) == 2


async def test_condicao_operacional_nao_derruba_a_sessao(db, ponto, motorista):
    """O teste que representa o prejuizo: a sessao seguia viva ou nao."""
    from datetime import UTC, datetime

    from app.drivers.base import ChargePointReading
    from app.models.enums import SessionState
    from app.services import session_service, telemetry_service

    sessao = await session_service.authorize(db, ponto, user=motorista)
    sessao = await session_service.start(db, sessao, ponto)

    leitura = ChargePointReading(
        recorded_at=datetime.now(UTC),
        hw_status="charging",
        car_connection="charging",
        power_kw=7.0,
        session_energy_kwh=1.5,
        faults=[],
        operational_flags=["Potencia insuficiente de PV/bateria"],
    )
    await telemetry_service.ingest(db, ponto, leitura)
    await db.refresh(sessao)

    assert sessao.state != SessionState.ERROR, "uma nuvem encerrou a recarga"


async def test_falha_terminal_encerra_e_fatura(db, ponto, motorista, tarifa):
    """fail() nao faturava; stop() fatura."""
    from datetime import UTC, datetime

    from app.drivers.base import ChargePointReading
    from app.models.enums import SessionState
    from app.services import session_service, telemetry_service

    sessao = await session_service.authorize(db, ponto, user=motorista)
    sessao = await session_service.start(db, sessao, ponto)

    leitura = ChargePointReading(
        recorded_at=datetime.now(UTC),
        hw_status="fault",
        car_connection="charging",
        power_kw=0.0,
        session_energy_kwh=2.0,
        faults=["Parada de emergencia acionada"],
    )
    await telemetry_service.ingest(db, ponto, leitura)
    await db.refresh(sessao)

    assert sessao.state in {SessionState.FINISHED, SessionState.BILLED}, (
        f"a sessão ficou em {sessao.state} em vez de encerrar"
    )
    assert sessao.ended_at is not None
