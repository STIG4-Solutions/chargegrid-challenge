"""Ciclo da Sessao: maquina de estados unica para dashboard, app e hardware.

    AUTHORIZING -> STARTING -> CHARGING -> FINISHING -> FINISHED -> BILLED
                                  |
                                  +-> SUSPENDED (corte do controle de demanda)

Qualquer estado pode cair em ERROR. Toda transicao grava um SessionEvent, que e
exatamente o que a timeline do dashboard renderiza.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import Conflict, InsufficientPower, InvalidTransition, NotFound
from app.core.logging import get_logger
from app.db.base import SESSION_CODE_SEQ
from app.models.charge_point import ChargePoint
from app.models.enums import (
    ACTIVE_SESSION_STATES,
    AuthMethod,
    ChargePointStatus,
    ReservationStatus,
    SessionState,
    StopReason,
)
from app.models.reservation import Reservation
from app.models.session import ChargingSession, SessionEvent
from app.models.site import Site
from app.models.tariff import Tariff
from app.models.user import RfidCard, User
from app.services.command_service import send_command

log = get_logger(__name__)

ALLOWED: dict[SessionState, set[SessionState]] = {
    # FINISHING a partir de AUTHORIZING permite cancelar uma autorizacao antes de
    # a energia fluir. Sem ela, uma sessao interrompida entre authorize() e
    # start() ficava presa nesse estado - e como AUTHORIZING bloqueia o ponto,
    # o eletroposto ficava inutilizavel sem nenhuma saida pela API.
    SessionState.AUTHORIZING: {
        SessionState.QUEUED,
        SessionState.STARTING,
        SessionState.FINISHING,
        SessionState.FINISHED,
        SessionState.ERROR,
    },
    # Da fila so se sai para energizar ou para desistir.
    SessionState.QUEUED: {
        SessionState.STARTING,
        SessionState.FINISHING,
        SessionState.ERROR,
    },
    SessionState.STARTING: {SessionState.CHARGING, SessionState.ERROR, SessionState.FINISHING},
    SessionState.CHARGING: {
        SessionState.SUSPENDED,
        SessionState.FINISHING,
        SessionState.ERROR,
    },
    SessionState.SUSPENDED: {SessionState.CHARGING, SessionState.FINISHING, SessionState.ERROR},
    SessionState.FINISHING: {SessionState.FINISHED, SessionState.ERROR},
    SessionState.FINISHED: {SessionState.BILLED, SessionState.ERROR},
    SessionState.BILLED: set(),
    SessionState.ERROR: set(),
}


async def _next_code(db: AsyncSession) -> str:
    """Codigo curto e legivel para operador e recibo (SES-20483).

    Sequencia do Postgres: contagem + random colide quando duas sessoes comecam
    no mesmo instante, e o codigo tem unique constraint.
    """
    number = (await db.execute(select(SESSION_CODE_SEQ.next_value()))).scalar_one()
    return f"SES-{number}"


def record_event(
    db: AsyncSession,
    session: ChargingSession,
    event_type: str,
    *,
    message: str | None = None,
    from_state: SessionState | None = None,
    to_state: SessionState | None = None,
    **payload,
) -> SessionEvent:
    """Registra um evento do ciclo.

    Insere pela sessao do banco em vez de usar session.events.append(): tocar a
    colecao de um objeto ja persistido dispara lazy load sincrono, que levanta
    MissingGreenlet dentro do contexto async.
    """
    event = SessionEvent(
        session_id=session.id,
        occurred_at=datetime.now(UTC),
        event_type=event_type,
        from_state=str(from_state) if from_state else None,
        to_state=str(to_state) if to_state else None,
        message=message,
        payload=payload,
    )
    db.add(event)
    return event


def transition(
    db: AsyncSession,
    session: ChargingSession,
    target: SessionState,
    *,
    message: str | None = None,
    **payload,
) -> None:
    current = session.state
    if target == current:
        return
    if target not in ALLOWED.get(current, set()):
        raise InvalidTransition(f"transição inválida: {current} → {target}")
    session.state = target
    record_event(
        db, session, "state_change", message=message, from_state=current, to_state=target, **payload
    )
    log.info("session.transition", code=session.code, from_state=str(current), to_state=str(target))


async def get_session(
    db: AsyncSession, session_id, *, with_events: bool = False
) -> ChargingSession:
    stmt = select(ChargingSession).where(ChargingSession.id == session_id)
    if with_events:
        stmt = stmt.options(selectinload(ChargingSession.events))
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise NotFound("sessão não encontrada")
    return session


async def active_session_for(db: AsyncSession, charge_point_id) -> ChargingSession | None:
    return (
        await db.execute(
            select(ChargingSession)
            .where(
                ChargingSession.charge_point_id == charge_point_id,
                ChargingSession.state.in_(ACTIVE_SESSION_STATES),
            )
            .order_by(ChargingSession.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def active_session_of_user(db: AsyncSession, user_id) -> ChargingSession | None:
    """Sessao em aberto do motorista, em qualquer ponto."""
    return (
        await db.execute(
            select(ChargingSession)
            .where(
                ChargingSession.user_id == user_id,
                ChargingSession.state.in_(ACTIVE_SESSION_STATES),
            )
            .order_by(ChargingSession.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def resolve_tariff(
    db: AsyncSession, charge_point: ChargePoint, card: RfidCard | None
) -> Tariff | None:
    """Precedencia: tarifa do cartao > tarifa do ponto > tarifa padrao do site."""
    tariff_id = None
    if card is not None and card.tariff_id:
        tariff_id = card.tariff_id
    elif charge_point.tariff_id:
        tariff_id = charge_point.tariff_id
    else:
        site = (await db.execute(select(Site).where(Site.id == charge_point.site_id))).scalar_one()
        tariff_id = site.default_tariff_id
    if tariff_id is None:
        return None
    return (
        await db.execute(
            select(Tariff).where(Tariff.id == tariff_id).options(selectinload(Tariff.windows))
        )
    ).scalar_one_or_none()


async def consumir_reserva(
    db: AsyncSession, charge_point: ChargePoint, user: User | None, auth_method: AuthMethod
) -> Reservation | None:
    """Casa a sessao que esta comecando com um agendamento em curso, se houver.

    Sem isso a reserva seguiria segurando potencia no orcamento durante a propria
    recarga que ela reservou - capacidade contada duas vezes. Marcar CONSUMED
    devolve essa potencia ao rateio no mesmo instante em que a sessao passa a
    consumi-la de verdade.
    """
    agora = datetime.now(UTC)
    reserva = (
        await db.execute(
            select(Reservation)
            .where(
                Reservation.charge_point_id == charge_point.id,
                Reservation.status == ReservationStatus.CONFIRMED,
                Reservation.starts_at <= agora,
                Reservation.ends_at > agora,
            )
            .order_by(Reservation.starts_at)
            .limit(1)
        )
    ).scalar_one_or_none()

    if reserva is None:
        return None

    # O ponto esta reservado para outra pessoa. O operador no site pode assumir
    # o controle; um motorista pelo app, nao.
    de_outro = user is None or reserva.user_id != user.id
    if de_outro and auth_method != AuthMethod.OPERATOR:
        raise Conflict(f"ponto reservado ate {reserva.ends_at:%H:%M} por outro motorista")

    reserva.status = ReservationStatus.CONSUMED
    return reserva


async def expirar_reservas_vencidas(db: AsyncSession) -> int:
    """Agendamento cuja janela passou sem uso para de segurar potencia."""
    vencidas = (
        (
            await db.execute(
                select(Reservation).where(
                    Reservation.status == ReservationStatus.CONFIRMED,
                    Reservation.ends_at <= datetime.now(UTC),
                )
            )
        )
        .scalars()
        .all()
    )
    for reserva in vencidas:
        reserva.status = ReservationStatus.EXPIRED
    return len(vencidas)


async def authorize(
    db: AsyncSession,
    charge_point: ChargePoint,
    *,
    user: User | None = None,
    rfid_card: RfidCard | None = None,
    vehicle_id=None,
    reservation_id=None,
    auth_method: AuthMethod = AuthMethod.APP,
    preauth_amount: float = 0.0,
    limit_kwh: float | None = None,
    limit_minutes: int | None = None,
    limit_amount: float | None = None,
) -> ChargingSession:
    """Cria a sessao em AUTHORIZING. Ainda nao ha energia fluindo."""
    if charge_point.status in {ChargePointStatus.FAULTED, ChargePointStatus.OFFLINE}:
        raise Conflict(f"ponto indisponível ({charge_point.status})")
    if await active_session_for(db, charge_point.id) is not None:
        raise Conflict("já existe uma sessão ativa neste ponto")

    # Uma vaga por motorista de cada vez.
    #
    # A guarda acima e' do ponto; sozinha, ela deixava o mesmo motorista ocupar
    # varias vagas ao mesmo tempo - cada uma com sua pre-autorizacao, e cada uma
    # negando vaga a outra pessoa. O app so mostra uma recarga em andamento,
    # entao as demais ficariam invisiveis para quem as abriu.
    #
    # Vale so para quem se identifica como usuario. Cartao RFID sem usuario
    # vinculado nao tem como ser agrupado, e a guarda do ponto ja cobre o caso.
    if user is not None:
        em_aberto = await active_session_of_user(db, user.id)
        if em_aberto is not None:
            raise Conflict(
                f"você já tem uma recarga em andamento ({em_aberto.code}); "
                "encerre antes de iniciar outra"
            )

    reserva = await consumir_reserva(db, charge_point, user, auth_method)
    if reserva is not None and reservation_id is None:
        reservation_id = reserva.id

    tariff = await resolve_tariff(db, charge_point, rfid_card)
    now = datetime.now(UTC)
    session = ChargingSession(
        code=await _next_code(db),
        site_id=charge_point.site_id,
        charge_point_id=charge_point.id,
        user_id=user.id if user else None,
        vehicle_id=vehicle_id,
        rfid_card_id=rfid_card.id if rfid_card else None,
        tariff_id=tariff.id if tariff else None,
        reservation_id=reservation_id,
        state=SessionState.AUTHORIZING,
        auth_method=auth_method,
        authorized_at=now,
        preauth_amount=preauth_amount,
        limit_kwh=limit_kwh,
        limit_minutes=limit_minutes,
        limit_amount=limit_amount,
    )
    db.add(session)
    await db.flush()
    record_event(
        db,
        session,
        "authorized",
        message=f"Autorizado via {auth_method}",
        tariff=tariff.name if tariff else None,
        preauth_amount=preauth_amount,
    )
    await db.commit()
    await db.refresh(session)
    return session


async def start(
    db: AsyncSession,
    session: ChargingSession,
    charge_point: ChargePoint,
    *,
    triggered_by: str = "operator",
    enqueue: bool = True,
) -> ChargingSession:
    """Manda o ponto energizar e ja aplica o teto vindo do controle de demanda.

    Sem folga no site a sessao entra na fila (enqueue=True, o padrao) e o
    rebalanceador a promove quando o orcamento abre. Com enqueue=False falha
    na hora e libera o ponto.
    """
    from app.services import power_manager

    # Consulta o rateio ANTES de mudar de estado: sem potencia a sessao vai para
    # a fila, e ela nunca chegou a iniciar. Transicionar para STARTING primeiro
    # deixava a sessao num estado de onde nao ha caminho para QUEUED.
    plan = await power_manager.plan_for_site(
        db, charge_point.site_id, starting_ids={str(charge_point.id)}
    )
    allocation = next(
        (a for a in plan.allocations if a.charge_point_id == str(charge_point.id)), None
    )
    granted = allocation.granted_kw if allocation and not allocation.suspended else 0.0

    if granted <= 0:
        disponivel = plan.budget.available_kw
        if not enqueue:
            # Sem fila, a sessao termina aqui e libera o ponto. Deixa-la parada
            # em STARTING bloquearia o eletroposto para sempre.
            mensagem = (
                f"Sem potência disponível no site (livre: {disponivel:.1f} kW). "
                "Tente novamente quando outra sessão liberar capacidade."
            )
            session.error_message = mensagem
            transition(db, session, SessionState.ERROR, message=mensagem, available_kw=disponivel)
            charge_point.status = ChargePointStatus.AVAILABLE
            await db.commit()
            raise InsufficientPower(mensagem)

        session.queued_at = session.queued_at or datetime.now(UTC)
        posicao = await queue_position(db, session)
        transition(
            db,
            session,
            SessionState.QUEUED,
            message=f"Na fila, posição {posicao} — aguardando potência no site",
            available_kw=disponivel,
            position=posicao,
        )
        await db.commit()
        await db.refresh(session)
        return session

    transition(db, session, SessionState.STARTING, message="Comando de início enviado ao ponto")

    limit_result = await send_command(
        db, charge_point, "set_power_limit", triggered_by=triggered_by, kw=granted
    )
    if limit_result.ok:
        charge_point.limit_kw = granted

    # Libera o corte do reg 10000 antes de energizar - sempre, sem olhar o
    # status no banco: o corte vive no hardware e nosso estado pode ter
    # divergido. O ponto pode ter sido cortado num congestionamento anterior; ai
    # ele carregaria na potencia minima a sessao inteira, porque logo abaixo o
    # status vira CHARGING e a retomada do rebalanceador (que so age sobre
    # SUSPENDED) nunca dispararia. E uma escrita por sessao, nao por ciclo.
    await send_command(
        db, charge_point, "set_dispatch_throttle", triggered_by=triggered_by, throttled=False
    )

    start_result = await send_command(db, charge_point, "start_charging", triggered_by=triggered_by)
    now = datetime.now(UTC)
    if not start_result.ok:
        session.error_message = start_result.error
        transition(
            db, session, SessionState.ERROR, message=f"Falha ao iniciar: {start_result.error}"
        )
        charge_point.status = ChargePointStatus.FAULTED
        await db.commit()
        return session

    session.started_at = now
    transition(db, session, SessionState.CHARGING, message="Recarga iniciada", limit_kw=granted)
    charge_point.status = ChargePointStatus.CHARGING
    await db.commit()
    await db.refresh(session)
    return session


async def stop(
    db: AsyncSession,
    session: ChargingSession,
    charge_point: ChargePoint,
    *,
    reason: StopReason = StopReason.REMOTE,
    triggered_by: str = "operator",
    auto_bill: bool = True,
) -> ChargingSession:
    """Encerra a sessao e, por padrao, ja emite a fatura."""
    from app.services import billing_service

    if session.state not in ACTIVE_SESSION_STATES:
        raise InvalidTransition(f"sessão já encerrada ({session.state})")

    transition(db, session, SessionState.FINISHING, message=f"Encerramento solicitado ({reason})")
    result = await send_command(db, charge_point, "stop_charging", triggered_by=triggered_by)
    if not result.ok:
        # O comando falhou, mas a sessao precisa fechar do lado comercial:
        # registramos a falha e seguimos para o faturamento do que foi medido.
        record_event(db, session, "stop_command_failed", message=result.error)

    now = datetime.now(UTC)
    session.ended_at = now
    session.stop_reason = reason
    if session.started_at:
        session.duration_s = int((now - session.started_at).total_seconds())
    if session.charging_stopped_at is None:
        session.charging_stopped_at = now

    transition(db, session, SessionState.FINISHED, message="Sessão encerrada")
    charge_point.status = ChargePointStatus.AVAILABLE
    charge_point.current_kw = 0
    await db.commit()

    if auto_bill:
        await billing_service.bill_session(db, session)
    await db.refresh(session)
    return session


async def apply_reading(
    db: AsyncSession, session: ChargingSession, reading, *, tariff: Tariff | None = None
) -> None:
    """Atualiza os contadores da sessao com uma varredura do ponto.

    Nao faz commit: quem chama (o poller) fecha a transacao do ciclo inteiro.
    """
    now = reading.recorded_at

    # Sessao que ainda nao energizou nao acumula nada. AUTHORIZING e QUEUED
    # contam como ativas (ocupam o ponto), entao sem esta guarda o poller copiava
    # o contador do carregador para uma sessao que nunca comecou - e o motorista
    # via energia e custo de uma recarga que nao aconteceu.
    if session.started_at is None:
        return

    if reading.session_energy_kwh and reading.session_energy_kwh >= float(session.energy_kwh):
        session.energy_kwh = reading.session_energy_kwh
    if reading.green_kwh is not None:
        session.green_energy_kwh = reading.green_kwh
    if reading.power_kw > float(session.peak_power_kw):
        session.peak_power_kw = reading.power_kw
    if session.started_at:
        session.duration_s = int((now - session.started_at).total_seconds())
    if session.meter_start_kwh is None and reading.meter_kwh is not None:
        session.meter_start_kwh = reading.meter_kwh - (reading.session_energy_kwh or 0)
    if reading.meter_kwh is not None:
        session.meter_stop_kwh = reading.meter_kwh

    # Carro parou de puxar energia mas continua plugado: comeca a contar ociosidade.
    if reading.power_kw <= 0.1 and session.state == SessionState.CHARGING:
        if session.charging_stopped_at is None:
            session.charging_stopped_at = now
            record_event(
                db, session, "charging_stopped", message="Potência zerada — início da ociosidade"
            )
    elif reading.power_kw > 0.1 and session.charging_stopped_at is not None:
        # Carro voltou a puxar energia: o contador precisa zerar junto. Sem isso
        # o painel seguia exibindo os minutos do periodo ocioso anterior,
        # contradizendo a fatura - que rateia a ociosidade a partir de
        # charging_stopped_at e portanto nao cobra nada.
        session.charging_stopped_at = None
        session.idle_minutes = 0

    if session.charging_stopped_at is not None:
        session.idle_minutes = int((now - session.charging_stopped_at).total_seconds() // 60)

    if tariff is not None:
        from app.services.tariff_engine import rate_session

        # Previa barata: sem amostras, o motor usa o total acumulado da sessao.
        session.estimated_cost = float(rate_session(session, tariff, [], now=now).total)


def reached_limit(session: ChargingSession) -> StopReason | None:
    """Teto pedido pelo motorista no app (kWh, minutos ou valor)."""
    if session.limit_kwh and float(session.energy_kwh) >= float(session.limit_kwh):
        return StopReason.ENERGY_LIMIT
    if session.limit_minutes and session.duration_s >= session.limit_minutes * 60:
        return StopReason.TIME_LIMIT
    if session.limit_amount and float(session.estimated_cost) >= float(session.limit_amount):
        return StopReason.AMOUNT_LIMIT
    if float(session.preauth_amount) > 0 and float(session.estimated_cost) >= float(
        session.preauth_amount
    ):
        return StopReason.AMOUNT_LIMIT
    return None


async def fail(db: AsyncSession, session: ChargingSession, message: str) -> None:
    session.error_message = message
    if session.state not in {SessionState.ERROR, SessionState.BILLED}:
        session.state = SessionState.ERROR
        record_event(db, session, "error", message=message, to_state=SessionState.ERROR)
    if session.ended_at is None:
        session.ended_at = datetime.now(UTC)
    await db.commit()


async def queue_position(db: AsyncSession, session: ChargingSession) -> int:
    """Posicao da sessao na fila do site, comecando em 1.

    A ordem combina a prioridade do ponto com a hora de chegada: uma vaga VIP
    e servida antes, e dentro da mesma faixa vale quem chegou primeiro. Ambos os
    criterios ja existem na configuracao do site, entao a fila nao inventa
    politica nova.
    """
    referencia = session.queued_at or datetime.now(UTC)
    prioridade = (
        await db.execute(
            select(ChargePoint.priority).where(ChargePoint.id == session.charge_point_id)
        )
    ).scalar_one()

    a_frente = (
        await db.execute(
            select(func.count(ChargingSession.id))
            .join(ChargePoint, ChargePoint.id == ChargingSession.charge_point_id)
            .where(
                ChargingSession.site_id == session.site_id,
                ChargingSession.state == SessionState.QUEUED,
                ChargingSession.id != session.id,
                or_(
                    ChargePoint.priority > prioridade,
                    and_(
                        ChargePoint.priority == prioridade,
                        ChargingSession.queued_at < referencia,
                    ),
                ),
            )
        )
    ).scalar_one()
    return int(a_frente) + 1


async def _fila_do_site(db: AsyncSession, site_id) -> list[ChargingSession]:
    return list(
        (
            await db.execute(
                select(ChargingSession)
                .join(ChargePoint, ChargePoint.id == ChargingSession.charge_point_id)
                .where(
                    ChargingSession.site_id == site_id,
                    ChargingSession.state == SessionState.QUEUED,
                )
                .order_by(ChargePoint.priority.desc(), ChargingSession.queued_at)
            )
        )
        .scalars()
        .all()
    )


async def promote_queue(db: AsyncSession, site_id, *, triggered_by: str = "system") -> int:
    """Energiza quem esta na fila, na ordem, enquanto houver orcamento.

    Chamada pelo rebalanceador. Promove uma sessao por vez porque cada uma
    consome parte do orcamento: o calculo da proxima ja precisa enxergar a
    anterior carregando.
    """
    promovidas = 0
    for session in await _fila_do_site(db, site_id):
        charge_point = (
            await db.execute(
                select(ChargePoint)
                .where(ChargePoint.id == session.charge_point_id)
                .options(selectinload(ChargePoint.connection))
            )
        ).scalar_one()

        if not charge_point.enabled or charge_point.operator_throttled:
            continue

        espera = (
            int((datetime.now(UTC) - session.queued_at).total_seconds() // 60)
            if session.queued_at
            else 0
        )

        # start() decide sozinho: energiza (QUEUED -> STARTING -> CHARGING) ou
        # deixa onde esta (QUEUED -> QUEUED e um no-op). Nao adianta forcar
        # STARTING antes de chamar: dali nao ha caminho de volta para a fila.
        atualizada = await start(db, session, charge_point, triggered_by=triggered_by)
        if atualizada.state != SessionState.CHARGING:
            # Nao coube. A fila esta ordenada, entao ninguem atras cabe tambem.
            break

        record_event(db, atualizada, "queue_promoted", message=f"Esperou {espera} min na fila")
        await db.commit()
        promovidas += 1
    return promovidas


async def expire_queue(db: AsyncSession) -> int:
    """Libera quem esperou demais - o ponto nao pode ficar preso indefinidamente."""
    limite = datetime.now(UTC) - timedelta(minutes=settings.queue_timeout_minutes)
    vencidas = (
        (
            await db.execute(
                select(ChargingSession).where(
                    ChargingSession.state == SessionState.QUEUED,
                    ChargingSession.queued_at < limite,
                )
            )
        )
        .scalars()
        .all()
    )
    for session in vencidas:
        session.stop_reason = StopReason.QUEUE_TIMEOUT
        session.ended_at = datetime.now(UTC)
        session.error_message = (
            f"Saiu da fila após {settings.queue_timeout_minutes} min sem potência disponível."
        )
        transition(
            db,
            session,
            SessionState.ERROR,
            message=session.error_message,
        )
    return len(vencidas)
