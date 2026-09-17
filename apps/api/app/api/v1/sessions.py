"""Modulo Ciclo da Sessao: autorizacao, inicio, acompanhamento e encerramento."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, OperatorUser, ScopedSiteId
from app.models.billing import Invoice
from app.models.charge_point import ChargePoint
from app.models.enums import InvoiceStatus, SessionState
from app.models.session import ChargingSession
from app.models.site import Site
from app.models.telemetry import TelemetrySample
from app.models.user import RfidCard, User
from app.schemas.common import Page
from app.schemas.ev import (
    RatingOut,
    SessionDetail,
    SessionKpis,
    SessionOut,
    SessionStartRequest,
    SessionStopRequest,
)
from app.services import billing_service, session_service

router = APIRouter(prefix="/sessions", tags=["recarga ev · sessões"])


@router.get("", response_model=Page[SessionOut])
async def list_sessions(
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    state: SessionState | None = None,
    charge_point_id: uuid.UUID | None = None,
    since: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[SessionOut]:
    filters = [ChargingSession.site_id == site_id]
    if state is not None:
        filters.append(ChargingSession.state == state)
    if charge_point_id is not None:
        filters.append(ChargingSession.charge_point_id == charge_point_id)
    if since is not None:
        filters.append(ChargingSession.created_at >= since)

    total = (await db.execute(select(func.count(ChargingSession.id)).where(*filters))).scalar_one()
    rows = (
        (
            await db.execute(
                select(ChargingSession)
                .where(*filters)
                .order_by(ChargingSession.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return Page(
        items=[SessionOut.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def inicio_do_dia(nome_do_fuso: str | None, agora: datetime | None = None) -> datetime:
    """Meia-noite de hoje no fuso do estabelecimento.

    Antes era meia-noite UTC, e em Sao Paulo (UTC-3) isso cai as 21h locais: os
    cartoes de "hoje" zeravam no meio da noite de um site comercial, dentro do
    horario de pico. O resto do sistema ja usava site.timezone.

    Recebe `agora` para poder ser testado sem depender da hora do relogio.
    """
    fuso = ZoneInfo(nome_do_fuso or "America/Sao_Paulo")
    referencia = (agora or datetime.now(UTC)).astimezone(fuso)
    return referencia.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/kpis", response_model=SessionKpis)
async def kpis(db: DbSession, site_id: ScopedSiteId, _: OperatorUser) -> SessionKpis:
    """Cartoes do topo da tela de sessoes."""
    # "Hoje" e' o dia do estabelecimento, nao o de Greenwich.
    #
    # Com meia-noite UTC os contadores zeravam as 21h em Sao Paulo - dentro do
    # horario de pico de um site comercial, e o operador via a energia do dia
    # sumir sem explicacao. O resto do sistema ja usa site.timezone; isto aqui
    # tinha ficado para tras.
    nome_do_fuso = (
        await db.execute(select(Site.timezone).where(Site.id == site_id))
    ).scalar_one_or_none()
    day_start = inicio_do_dia(nome_do_fuso)

    active = (
        await db.execute(
            select(func.count(ChargingSession.id)).where(
                ChargingSession.site_id == site_id,
                ChargingSession.state == SessionState.CHARGING,
            )
        )
    ).scalar_one()
    queued = (
        await db.execute(
            select(func.count(ChargingSession.id)).where(
                ChargingSession.site_id == site_id,
                ChargingSession.state == SessionState.QUEUED,
            )
        )
    ).scalar_one()
    today = (
        await db.execute(
            select(func.count(ChargingSession.id)).where(
                ChargingSession.site_id == site_id, ChargingSession.created_at >= day_start
            )
        )
    ).scalar_one()
    energy, green = (
        await db.execute(
            select(
                func.coalesce(func.sum(ChargingSession.energy_kwh), 0),
                func.coalesce(func.sum(ChargingSession.green_energy_kwh), 0),
            ).where(ChargingSession.site_id == site_id, ChargingSession.created_at >= day_start)
        )
    ).one()
    confirmed = (
        await db.execute(
            select(func.coalesce(func.sum(Invoice.total), 0)).where(
                Invoice.site_id == site_id, Invoice.status == InvoiceStatus.PAID
            )
        )
    ).scalar_one()
    pending = (
        await db.execute(
            select(func.coalesce(func.sum(Invoice.total), 0)).where(
                Invoice.site_id == site_id, Invoice.status == InvoiceStatus.OPEN
            )
        )
    ).scalar_one()

    return SessionKpis(
        active=active,
        queued=queued,
        today=today,
        energy_kwh=float(energy),
        green_energy_kwh=float(green),
        confirmed_revenue=float(confirmed),
        pending_revenue=float(pending),
    )


async def _sessao_do_site(db, session_id, site_id) -> ChargingSession:
    """Sessao do estabelecimento de quem pediu.

    O 404 e' proposital: um 403 confirmaria que a sessao existe em outro site.
    Vale para detalhe, previa, telemetria e faturamento - `list_sessions` e
    `stop_session` ja filtravam, mas as outras quatro liam qualquer sessao do
    sistema com um token de operador de qualquer estabelecimento.
    """
    session = await session_service.get_session(db, session_id, with_events=True)
    if session.site_id != site_id:
        raise HTTPException(status_code=404, detail="sessão não encontrada neste site")
    return session


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: uuid.UUID, db: DbSession, site_id: ScopedSiteId, _: OperatorUser
) -> SessionDetail:
    """Detalhe com a linha do tempo do ciclo e, se estiver na fila, a posição."""
    session = await _sessao_do_site(db, session_id, site_id)
    detalhe = SessionDetail.model_validate(session)
    if session.state == SessionState.QUEUED:
        detalhe.queue_position = await session_service.queue_position(db, session)
    return detalhe


@router.post("", response_model=SessionDetail, status_code=201)
async def start_session(
    payload: SessionStartRequest, db: DbSession, site_id: ScopedSiteId, operator: OperatorUser
) -> ChargingSession:
    """Autoriza e inicia em um passo - e o que o operador espera do botao Iniciar."""
    cp = (
        await db.execute(
            select(ChargePoint)
            .where(ChargePoint.id == payload.charge_point_id, ChargePoint.site_id == site_id)
            .options(selectinload(ChargePoint.connection))
        )
    ).scalar_one_or_none()
    if cp is None:
        raise HTTPException(status_code=404, detail="ponto de recarga não encontrado")

    card = None
    if payload.rfid_uid:
        card = (
            await db.execute(
                select(RfidCard)
                .where(RfidCard.uid == payload.rfid_uid, RfidCard.is_active.is_(True))
                .options(selectinload(RfidCard.user))
            )
        ).scalar_one_or_none()
        if card is None:
            raise HTTPException(status_code=404, detail="cartão RFID não cadastrado ou inativo")

    user = card.user if card else None
    if user is None and payload.user_id:
        user = (
            await db.execute(select(User).where(User.id == payload.user_id))
        ).scalar_one_or_none()

    session = await session_service.authorize(
        db,
        cp,
        user=user,
        rfid_card=card,
        vehicle_id=payload.vehicle_id,
        auth_method=payload.auth_method,
        preauth_amount=payload.preauth_amount,
        limit_kwh=payload.limit_kwh,
        limit_minutes=payload.limit_minutes,
        limit_amount=payload.limit_amount,
    )
    session = await session_service.start(
        db,
        session,
        cp,
        triggered_by=f"operator:{operator.email}",
        enqueue=payload.queue_if_unavailable,
    )
    return await session_service.get_session(db, session.id, with_events=True)


@router.post("/{session_id}/stop", response_model=SessionDetail)
async def stop_session(
    session_id: uuid.UUID,
    payload: SessionStopRequest,
    db: DbSession,
    site_id: ScopedSiteId,
    operator: OperatorUser,
) -> ChargingSession:
    session = await session_service.get_session(db, session_id)
    if session.site_id != site_id:
        raise HTTPException(status_code=404, detail="sessão não encontrada neste site")

    cp = (
        await db.execute(
            select(ChargePoint)
            .where(ChargePoint.id == session.charge_point_id)
            .options(selectinload(ChargePoint.connection))
        )
    ).scalar_one()
    await session_service.stop(
        db,
        session,
        cp,
        reason=payload.reason,
        triggered_by=f"operator:{operator.email}",
        auto_bill=payload.auto_bill,
    )
    return await session_service.get_session(db, session_id, with_events=True)


@router.get("/{session_id}/preview", response_model=RatingOut)
async def preview_cost(
    session_id: uuid.UUID, db: DbSession, site_id: ScopedSiteId, _: OperatorUser
) -> dict:
    """Quanto a sessao ja custa agora, com o rateio por janela tarifaria."""
    session = await _sessao_do_site(db, session_id, site_id)
    return await billing_service.preview_session(db, session)


@router.get("/{session_id}/telemetry")
async def session_telemetry(
    session_id: uuid.UUID,
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    minutes: int = Query(default=120, ge=1, le=1440),
    max_points: int = Query(default=600, ge=10, le=5000),
) -> list[dict]:
    """Serie de potencia e energia da sessao - alimenta o grafico do detalhe.

    A janela sozinha nao limitava a resposta: o poller grava a cada 5 s, entao
    24 h de sessao dao mais de 17 mil amostras - e o painel pede 4 h a cada 12 s.

    Cortar com LIMIT truncaria a serie e o grafico mentiria, mostrando o comeco
    da recarga como se fosse a recarga inteira. Entao em vez de cortar, reamostra:
    pega uma amostra a cada N, cobrindo a janela toda. O desenho da curva e' o
    mesmo; o que cai e' a resolucao, que o grafico nao usava de qualquer forma.
    """
    # A serie e' lida por session_id; sem esta checagem o site nao entrava na
    # consulta e um operador via a telemetria de outro estabelecimento.
    await _sessao_do_site(db, session_id, site_id)

    since = datetime.now(UTC) - timedelta(minutes=minutes)
    base = select(TelemetrySample).where(
        TelemetrySample.session_id == session_id,
        TelemetrySample.recorded_at >= since,
    )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    consulta = base.order_by(TelemetrySample.recorded_at)
    if total > max_points:
        # Um a cada N pela posicao na serie. O ultimo ponto entra sempre: e' o
        # estado atual da recarga, e some justamente quando o passo nao fecha.
        passo = -(-total // max_points)  # divisao para cima
        posicao = func.row_number().over(order_by=TelemetrySample.recorded_at).label("posicao")
        numeradas = base.add_columns(posicao).subquery()
        escolhidas = select(numeradas.c.id).where(
            (numeradas.c.posicao % passo == 1) | (numeradas.c.posicao == total)
        )
        consulta = (
            select(TelemetrySample)
            .where(TelemetrySample.id.in_(escolhidas))
            .order_by(TelemetrySample.recorded_at)
        )

    rows = (await db.execute(consulta)).scalars().all()
    return [
        {
            "recorded_at": row.recorded_at.isoformat(),
            "power_kw": float(row.power_kw),
            "energy_kwh": float(row.session_energy_kwh),
            "limit_kw": float(row.applied_limit_kw) if row.applied_limit_kw else None,
        }
        for row in rows
    ]


@router.post("/{session_id}/bill", response_model=dict)
async def bill(
    session_id: uuid.UUID, db: DbSession, site_id: ScopedSiteId, _: OperatorUser
) -> dict:
    """Fatura manualmente uma sessao encerrada sem cobranca (idempotente)."""
    session = await _sessao_do_site(db, session_id, site_id)
    invoice = await billing_service.bill_session(db, session)
    return {"invoice_id": str(invoice.id), "code": invoice.code, "total": float(invoice.total)}
