"""API do app do motorista.

O dashboard e o app compartilham dominio, servicos e banco - o que muda e o
escopo: aqui o usuario so enxerga o que e dele. Rotas prontas para o app que
vem depois (mapa, agendamento, sessao, pagamento, carteira).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession
from app.db.base import RESERVATION_CODE_SEQ
from app.models.billing import Invoice
from app.models.charge_point import ChargePoint
from app.models.enums import (
    ACTIVE_SESSION_STATES,
    AuthMethod,
    ChargePointStatus,
    ReservationStatus,
    StopReason,
)
from app.models.reservation import Reservation
from app.models.session import ChargingSession
from app.models.site import Site
from app.models.tariff import Tariff
from app.models.user import Vehicle
from app.schemas.auth import VehicleCreate, VehicleOut
from app.schemas.ev import (
    InvoiceOut,
    RatingOut,
    ReservationCreate,
    ReservationOut,
    SessionDetail,
    SessionOut,
    StationOut,
    StationPointOut,
)
from app.services import billing_service, payment_service, session_service

router = APIRouter(prefix="/app", tags=["app mobile"])


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    d_lat, d_lon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return round(2 * r * asin(sqrt(a)), 2)


@router.get("/stations", response_model=list[StationOut])
async def nearby_stations(
    db: DbSession,
    _: CurrentUser,
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float = Query(default=25, gt=0, le=500),
    only_available: bool = False,
) -> list[StationOut]:
    """Mapa de estacoes com disponibilidade e preco - primeira tela do app."""
    sites = (
        (await db.execute(select(Site).options(selectinload(Site.charge_points))))
        .scalars()
        .unique()
        .all()
    )

    out: list[StationOut] = []
    for site in sites:
        points = [cp for cp in site.charge_points if cp.enabled]
        if not points:
            continue
        available = sum(1 for cp in points if cp.status == ChargePointStatus.AVAILABLE)
        if only_available and available == 0:
            continue

        distance = None
        if latitude is not None and longitude is not None:
            if site.latitude is None or site.longitude is None:
                continue
            distance = _haversine_km(
                latitude, longitude, float(site.latitude), float(site.longitude)
            )
            if distance > radius_km:
                continue

        price = None
        if site.default_tariff_id:
            tariff = (
                await db.execute(select(Tariff).where(Tariff.id == site.default_tariff_id))
            ).scalar_one_or_none()
            price = float(tariff.price_per_kwh) if tariff else None

        out.append(
            StationOut(
                site_id=site.id,
                name=site.name,
                address=site.address,
                latitude=float(site.latitude) if site.latitude is not None else None,
                longitude=float(site.longitude) if site.longitude is not None else None,
                distance_km=distance,
                total_points=len(points),
                available_points=available,
                max_kw=max(float(cp.rated_kw) for cp in points),
                connectors=sorted({str(cp.connector) for cp in points}),
                price_per_kwh=price,
            )
        )

    out.sort(key=lambda s: (s.distance_km is None, s.distance_km or 0))
    return out


@router.get("/stations/{site_id}/charge-points")
async def station_points(
    site_id: uuid.UUID, db: DbSession, _: CurrentUser
) -> list[StationPointOut]:
    points = (
        (
            await db.execute(
                select(ChargePoint)
                .where(ChargePoint.site_id == site_id, ChargePoint.enabled.is_(True))
                .order_by(ChargePoint.code)
            )
        )
        .scalars()
        .all()
    )
    return [
        StationPointOut(
            id=cp.id,
            code=cp.code,
            name=cp.name,
            connector=str(cp.connector),
            rated_kw=float(cp.rated_kw),
            status=str(cp.status),
            available=cp.status == ChargePointStatus.AVAILABLE,
        )
        for cp in points
    ]


@router.post("/sessions", response_model=SessionDetail, status_code=201)
async def start_from_app(
    charge_point_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    vehicle_id: uuid.UUID | None = None,
    preauth_amount: float = Query(default=50.0, ge=0),
    limit_kwh: float | None = Query(default=None, gt=0),
) -> ChargingSession:
    """Iniciar recarga pelo app.

    A pre-autorizacao existe para o estabelecimento nao ficar com energia
    entregue e sem lastro de pagamento: a sessao para sozinha ao atingir o valor.
    """
    cp = (
        await db.execute(
            select(ChargePoint)
            .where(ChargePoint.id == charge_point_id)
            .options(selectinload(ChargePoint.connection))
        )
    ).scalar_one_or_none()
    if cp is None:
        raise HTTPException(status_code=404, detail="ponto de recarga não encontrado")

    session = await session_service.authorize(
        db,
        cp,
        user=user,
        vehicle_id=vehicle_id,
        auth_method=AuthMethod.APP,
        preauth_amount=preauth_amount,
        limit_kwh=limit_kwh,
    )
    session = await session_service.start(db, session, cp, triggered_by=f"driver:{user.email}")
    return await session_service.get_session(db, session.id, with_events=True)


@router.get("/sessions", response_model=list[SessionOut])
async def my_sessions(
    db: DbSession, user: CurrentUser, limit: int = Query(default=20, ge=1, le=100)
):
    return (
        (
            await db.execute(
                select(ChargingSession)
                .where(ChargingSession.user_id == user.id)
                .order_by(ChargingSession.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


@router.get("/sessions/active", response_model=SessionDetail | None)
async def my_active_session(db: DbSession, user: CurrentUser):
    session = (
        await db.execute(
            select(ChargingSession)
            .where(
                ChargingSession.user_id == user.id,
                ChargingSession.state.in_(ACTIVE_SESSION_STATES),
            )
            .options(selectinload(ChargingSession.events))
            .order_by(ChargingSession.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return session


@router.get("/sessions/{session_id}/preview", response_model=RatingOut)
async def my_session_cost(session_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict:
    session = await _own_session(db, session_id, user)
    return await billing_service.preview_session(db, session)


@router.post("/sessions/{session_id}/stop", response_model=SessionDetail)
async def stop_from_app(session_id: uuid.UUID, db: DbSession, user: CurrentUser):
    session = await _own_session(db, session_id, user)
    cp = (
        await db.execute(
            select(ChargePoint)
            .where(ChargePoint.id == session.charge_point_id)
            .options(selectinload(ChargePoint.connection))
        )
    ).scalar_one()
    await session_service.stop(
        db, session, cp, reason=StopReason.REMOTE, triggered_by=f"driver:{user.email}"
    )
    return await session_service.get_session(db, session_id, with_events=True)


async def _own_session(db, session_id, user) -> ChargingSession:
    session = await session_service.get_session(db, session_id)
    if session.user_id != user.id:
        raise HTTPException(status_code=403, detail="sessão de outro usuário")
    return session


# ------------------------------------------------------------------- reservas
@router.post("/reservations", response_model=ReservationOut, status_code=201)
async def create_reservation(payload: ReservationCreate, db: DbSession, user: CurrentUser):
    """Agendamento com checagem de conflito na janela pedida."""
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="janela de reserva inválida")

    cp = (
        await db.execute(select(ChargePoint).where(ChargePoint.id == payload.charge_point_id))
    ).scalar_one_or_none()
    if cp is None or not cp.enabled:
        raise HTTPException(status_code=404, detail="ponto de recarga indisponível")

    conflict = (
        await db.execute(
            select(func.count(Reservation.id)).where(
                Reservation.charge_point_id == cp.id,
                Reservation.status.in_([ReservationStatus.PENDING, ReservationStatus.CONFIRMED]),
                Reservation.starts_at < payload.ends_at,
                Reservation.ends_at > payload.starts_at,
            )
        )
    ).scalar_one()
    if conflict:
        raise HTTPException(status_code=409, detail="já existe reserva nessa janela")

    number = (await db.execute(select(RESERVATION_CODE_SEQ.next_value()))).scalar_one()
    reservation = Reservation(
        code=f"RES-{number}",
        site_id=cp.site_id,
        charge_point_id=cp.id,
        user_id=user.id,
        vehicle_id=payload.vehicle_id,
        status=ReservationStatus.CONFIRMED,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        target_kwh=payload.target_kwh,
        # Reserva potencia no orcamento do site durante a janela agendada.
        reserved_kw=float(cp.rated_kw),
    )
    db.add(reservation)
    await db.commit()
    await db.refresh(reservation)
    return reservation


@router.get("/reservations", response_model=list[ReservationOut])
async def my_reservations(db: DbSession, user: CurrentUser):
    return (
        (
            await db.execute(
                select(Reservation)
                .where(Reservation.user_id == user.id)
                .order_by(Reservation.starts_at.desc())
            )
        )
        .scalars()
        .all()
    )


@router.delete("/reservations/{reservation_id}", response_model=ReservationOut)
async def cancel_reservation(reservation_id: uuid.UUID, db: DbSession, user: CurrentUser):
    reservation = (
        await db.execute(
            select(Reservation).where(
                Reservation.id == reservation_id, Reservation.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if reservation is None:
        raise HTTPException(status_code=404, detail="reserva não encontrada")
    if reservation.status == ReservationStatus.CONSUMED:
        raise HTTPException(status_code=409, detail="reserva já utilizada")
    reservation.status = ReservationStatus.CANCELLED
    reservation.cancelled_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(reservation)
    return reservation


# ----------------------------------------------------- veiculos, faturas, carteira
@router.get("/vehicles", response_model=list[VehicleOut])
async def my_vehicles(db: DbSession, user: CurrentUser):
    return (await db.execute(select(Vehicle).where(Vehicle.user_id == user.id))).scalars().all()


@router.post("/vehicles", response_model=VehicleOut, status_code=201)
async def add_vehicle(payload: VehicleCreate, db: DbSession, user: CurrentUser):
    vehicle = Vehicle(user_id=user.id, **payload.model_dump())
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    return vehicle


@router.get("/invoices", response_model=list[InvoiceOut])
async def my_invoices(
    db: DbSession, user: CurrentUser, limit: int = Query(default=20, ge=1, le=100)
):
    return (
        (
            await db.execute(
                select(Invoice)
                .where(Invoice.user_id == user.id)
                .options(selectinload(Invoice.lines), selectinload(Invoice.payments))
                .order_by(Invoice.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


@router.post("/wallet/topup")
async def topup(amount: float, db: DbSession, user: CurrentUser) -> dict:
    """Credito na carteira pre-paga.

    Na integracao real, o credito so entra depois do webhook do PSP confirmar -
    esta rota representa o passo final desse fluxo.
    """
    updated = await payment_service.topup_wallet(db, user, Decimal(str(amount)))
    return {"wallet_balance": float(updated.wallet_balance)}
