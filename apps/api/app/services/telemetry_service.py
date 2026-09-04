"""Ingestao de telemetria: traduz a varredura do hardware em estado de negocio."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.drivers import modbus_map
from app.drivers.base import ChargePointReading
from app.models.charge_point import ChargePoint
from app.models.enums import AuthMethod, ChargePointStatus, SessionState, StopReason
from app.models.tariff import Tariff
from app.models.telemetry import TelemetrySample
from app.models.user import RfidCard
from app.services import session_service

log = get_logger(__name__)

# Estado do hardware (reg 10017) mapeado para o estado de negocio do ponto.
# Codigo bruto do reg 10017, preservado para pericia de campo.
RAW_STATUS_CODE = {name: code for code, name in modbus_map.HW_STATUS.items()}

HW_TO_STATUS = {
    "idle_unplugged": ChargePointStatus.AVAILABLE,
    "idle_plugged": ChargePointStatus.PREPARING,
    "handshaking": ChargePointStatus.PREPARING,
    "charging": ChargePointStatus.CHARGING,
    "charge_complete": ChargePointStatus.FINISHING,
    "alarm": ChargePointStatus.FAULTED,
    "scheduled_start": ChargePointStatus.RESERVED,
    "maintenance": ChargePointStatus.MAINTENANCE,
    "start_failed": ChargePointStatus.FAULTED,
    "firmware_upgrade": ChargePointStatus.MAINTENANCE,
    "interrupted_low_power": ChargePointStatus.SUSPENDED,
}


async def ingest(db: AsyncSession, charge_point: ChargePoint, reading: ChargePointReading) -> None:
    """Persiste a amostra, sincroniza o ponto e avanca a sessao ativa.

    Chamada uma vez por ponto por ciclo do poller. Sem commit aqui: o worker
    fecha a transacao depois de varrer todos os pontos do site.
    """
    now = datetime.now(UTC)

    if not reading.online:
        charge_point.status = ChargePointStatus.OFFLINE
        charge_point.current_kw = 0
        charge_point.active_faults = reading.faults
        return

    charge_point.last_seen_at = now
    charge_point.current_kw = reading.power_kw
    # O painel mostra as duas coisas: o que derruba a sessao e o que so merece
    # atencao. So a falha terminal vira last_fault_code.
    charge_point.active_faults = [*reading.faults, *reading.operational_flags]
    charge_point.last_fault_code = reading.faults[0] if reading.faults else None
    if reading.serial_number and not charge_point.serial_number:
        charge_point.serial_number = reading.serial_number
    if reading.firmware_version:
        charge_point.firmware_version = reading.firmware_version
    if reading.applied_limit_kw:
        charge_point.limit_kw = reading.applied_limit_kw

    session = await session_service.active_session_for(db, charge_point.id)

    # O status calculado nao pode apagar uma suspensao que nos impusemos: o
    # hardware nao sabe que fomos nos que cortamos a potencia dele.
    new_status = HW_TO_STATUS.get(reading.hw_status, ChargePointStatus.AVAILABLE)
    if charge_point.operator_throttled:
        # Corte manual so sai por decisao do operador: nem a leitura do hardware
        # nem o rateio automatico podem reverter.
        charge_point.status = ChargePointStatus.SUSPENDED
    elif (
        charge_point.status != ChargePointStatus.SUSPENDED
        or new_status != ChargePointStatus.CHARGING
    ):
        charge_point.status = new_status

    db.add(
        TelemetrySample(
            charge_point_id=charge_point.id,
            session_id=session.id if session else None,
            recorded_at=reading.recorded_at,
            voltage_a=reading.voltage_a,
            voltage_b=reading.voltage_b,
            voltage_c=reading.voltage_c,
            current_a=reading.current_a,
            current_b=reading.current_b,
            current_c=reading.current_c,
            power_kw=reading.power_kw,
            session_energy_kwh=reading.session_energy_kwh,
            meter_kwh=reading.meter_kwh,
            green_kwh=reading.green_kwh,
            raw_status=RAW_STATUS_CODE.get(reading.hw_status),
            applied_limit_kw=charge_point.limit_kw,
        )
    )

    if session is None:
        # Carga iniciada localmente (RFID ou plug-and-charge): adota a sessao.
        if reading.hw_status == "charging":
            await _adopt_local_session(db, charge_point, reading)
        return

    tariff = None
    if session.tariff_id:
        tariff = (
            await db.execute(
                select(Tariff)
                .where(Tariff.id == session.tariff_id)
                .options(selectinload(Tariff.windows))
            )
        ).scalar_one_or_none()

    await session_service.apply_reading(db, session, reading, tariff=tariff)

    if reading.faults:
        # Encerra pelo caminho normal, nao com fail().
        #
        # fail() so marcava state = ERROR: nenhum comando de parada era enviado -
        # o carro continuava puxando energia - e bill_session nunca era chamado,
        # entao a energia entregue nao virava fatura. Pior, ERROR nao esta em
        # ACTIVE_SESSION_STATES, e no ciclo seguinte a leitura "charging" fazia o
        # poller adotar uma sessao nova: um laco adota-falha-adota.
        #
        # stop() manda parar, encerra e fatura. A causa fica no evento.
        await session_service.stop(
            db,
            session,
            charge_point,
            reason=StopReason.FAULT,
            triggered_by="hardware:" + "; ".join(reading.faults),
        )
        return

    stop_reason = session_service.reached_limit(session)
    if reading.car_connection == "disconnected" and session.started_at is not None:
        stop_reason = StopReason.EV_DISCONNECTED
    elif reading.hw_status == "charge_complete":
        stop_reason = stop_reason or StopReason.LOCAL

    if stop_reason is not None:
        await session_service.stop(
            db, session, charge_point, reason=stop_reason, triggered_by="system"
        )


async def _adopt_local_session(
    db: AsyncSession, charge_point: ChargePoint, reading: ChargePointReading
) -> None:
    """Carga iniciada no proprio ponto precisa virar sessao faturavel.

    Sem isso, energia sai do medidor sem nenhuma cobranca associada - o buraco
    exato que o desafio aponta nos eletropostos comerciais de hoje.
    """
    card = None
    if reading.last_rfid_uid:
        card = (
            await db.execute(
                select(RfidCard)
                .where(RfidCard.uid == reading.last_rfid_uid, RfidCard.is_active.is_(True))
                .options(selectinload(RfidCard.user))
            )
        ).scalar_one_or_none()

    method = AuthMethod.RFID if card else AuthMethod.PLUG_AND_CHARGE
    session = await session_service.authorize(
        db,
        charge_point,
        user=card.user if card else None,
        rfid_card=card,
        auth_method=method,
    )
    session.started_at = reading.recorded_at
    session.state = SessionState.STARTING
    session_service.transition(
        db,
        session,
        SessionState.CHARGING,
        message=f"Sessão adotada do hardware (início {reading.start_mode})",
    )
    log.info("session.adopted", code=session.code, cp=charge_point.code, method=str(method))


async def mark_stale_offline(db: AsyncSession) -> int:
    """Ponto sem leitura recente e ponto offline - nao pode aparecer como saudavel."""
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.stale_telemetry_seconds)
    stale = (
        (
            await db.execute(
                select(ChargePoint).where(
                    ChargePoint.last_seen_at.is_not(None),
                    ChargePoint.last_seen_at < cutoff,
                    ChargePoint.status != ChargePointStatus.OFFLINE,
                )
            )
        )
        .scalars()
        .all()
    )
    for cp in stale:
        cp.status = ChargePointStatus.OFFLINE
        cp.current_kw = 0
    return len(stale)
