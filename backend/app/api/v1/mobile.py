"""API do app do motorista.

O dashboard e o app compartilham dominio, servicos e banco - o que muda e o
escopo: aqui o usuario so enxerga o que e dele. Rotas prontas para o app que
vem depois (mapa, agendamento, sessao, pagamento, carteira).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, DriverUser
from app.db.base import RESERVATION_CODE_SEQ
from app.models.billing import Invoice
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
from app.models.session import ChargingSession
from app.models.site import Site
from app.models.tariff import Tariff
from app.models.user import Vehicle
from app.schemas.auth import VehicleCreate, VehicleOut, VehicleUpdate, WalletTopUpIn
from app.schemas.ev import (
    InvoiceOut,
    RatingOut,
    ReservationCreate,
    ReservationOut,
    ScannedChargePointOut,
    SessionDetail,
    SessionOut,
    StationOut,
    StationPointOut,
)
from app.services import billing_service, payment_service, session_service

# Teto de agendamentos simultaneos por motorista. Nao e' regra de negocio
# fechada - e' um limite de sanidade para uma conta nao drenar o orcamento do
# site inteiro, que era possivel sem ele.
MAX_RESERVAS_POR_MOTORISTA = 5

router = APIRouter(prefix="/app", tags=["app mobile"])


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    d_lat, d_lon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return round(2 * r * asin(sqrt(a)), 2)


@router.get("/stations", response_model=list[StationOut])
async def nearby_stations(
    db: DbSession,
    _: DriverUser,
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float = Query(default=25, gt=0, le=500),
    only_available: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[StationOut]:
    """Mapa de estacoes com disponibilidade e preco - primeira tela do app."""
    sites = (
        (await db.execute(select(Site).options(selectinload(Site.charge_points))))
        .scalars()
        .unique()
        .all()
    )

    # Preco de todas as estacoes numa consulta so.
    #
    # Antes a tarifa era buscada dentro do laco: com um site nao se nota, com
    # cinquenta sao cinquenta e uma consultas para montar a primeira tela do app.
    ids_de_tarifa = {s.default_tariff_id for s in sites if s.default_tariff_id}
    precos: dict[uuid.UUID, float] = {}
    if ids_de_tarifa:
        precos = {
            t.id: float(t.price_per_kwh)
            for t in (
                await db.execute(select(Tariff).where(Tariff.id.in_(ids_de_tarifa)))
            )
            .scalars()
            .all()
        }

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

        price = precos.get(site.default_tariff_id) if site.default_tariff_id else None

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

    # Ordena antes de cortar: com coordenada, o corte tem de deixar as mais
    # proximas, nao as primeiras que sairam do banco.
    out.sort(key=lambda s: (s.distance_km is None, s.distance_km or 0))
    return out[:limit]


@router.get("/stations/{site_id}/charge-points")
async def station_points(
    site_id: uuid.UUID, db: DbSession, _: DriverUser
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


@router.get("/charge-points/by-code/{codigo}", response_model=ScannedChargePointOut)
async def charge_point_by_code(codigo: str, db: DbSession, _: DriverUser):
    """Resolve o ponto pelo codigo do QR colado no carregador.

    O QR pode trazer o codigo puro (CP-01) ou uma URL que termina nele
    (chargegrid://cp/CP-01, https://.../cp/CP-01) - quem normaliza e' o app.
    Aqui a comparacao ignora caixa e espacos, porque codigo digitado a mao
    chega de todo jeito.
    """
    limpo = codigo.strip()
    if not limpo:
        raise HTTPException(status_code=422, detail="código vazio")

    linha = (
        await db.execute(
            select(ChargePoint, Site)
            .join(Site, Site.id == ChargePoint.site_id)
            .where(func.upper(ChargePoint.code) == limpo.upper())
        )
    ).first()
    if linha is None:
        raise HTTPException(status_code=404, detail=f"nenhum ponto com o código {limpo}")

    cp, site = linha
    if not cp.enabled:
        raise HTTPException(status_code=409, detail=f"{cp.code} está fora de operação")

    return ScannedChargePointOut(
        id=cp.id,
        code=cp.code,
        name=cp.name,
        connector=str(cp.connector),
        rated_kw=float(cp.rated_kw),
        status=str(cp.status),
        available=cp.status == ChargePointStatus.AVAILABLE,
        site_id=site.id,
        site_name=site.name,
        site_address=site.address,
    )


@router.post("/sessions", response_model=SessionDetail, status_code=201)
async def start_from_app(
    charge_point_id: uuid.UUID,
    db: DbSession,
    user: DriverUser,
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
    # Esta e' a chamada em que o motorista PODE cair na fila: se ela devolver
    # queue_position nulo, a tela nao tem como mostrar a posicao no momento
    # exato em que ela importa.
    return await _com_posicao_na_fila(
        db, await session_service.get_session(db, session.id, with_events=True)
    )


@router.get("/sessions", response_model=list[SessionOut])
async def my_sessions(
    db: DbSession, user: DriverUser, limit: int = Query(default=20, ge=1, le=100)
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
async def my_active_session(db: DbSession, user: DriverUser):
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
    return await _com_posicao_na_fila(db, session)


async def _com_posicao_na_fila(db, session: ChargingSession | None) -> SessionDetail | None:
    """Preenche queue_position, que so a rota do operador preenchia.

    A tela de recarga do app ja tratava o campo - mostra "posicao 3 na fila" em
    vez do texto generico -, mas nenhuma rota /app/* o populava, entao ele vinha
    sempre com o default None do schema. Quem estava na fila nunca via seu
    lugar, justamente na hora em que a informacao importa.
    """
    if session is None:
        return None
    detalhe = SessionDetail.model_validate(session)
    if session.state == SessionState.QUEUED:
        detalhe.queue_position = await session_service.queue_position(db, session)
    return detalhe


@router.get("/sessions/{session_id}/preview", response_model=RatingOut)
async def my_session_cost(session_id: uuid.UUID, db: DbSession, user: DriverUser) -> dict:
    session = await _own_session(db, session_id, user)
    return await billing_service.preview_session(db, session)


@router.post("/sessions/{session_id}/stop", response_model=SessionDetail)
async def stop_from_app(session_id: uuid.UUID, db: DbSession, user: DriverUser):
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
async def create_reservation(payload: ReservationCreate, db: DbSession, user: DriverUser):
    """Agendamento com checagem de conflito na janela pedida."""
    agora = datetime.now(UTC)

    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="janela de reserva inválida")

    # Janela no passado nao reserva nada e ainda entra no orcamento: load_budget
    # soma as CONFIRMED cuja janela ja comecou, e uma que comecou ontem continua
    # "corrente" ate acabar.
    if payload.ends_at <= agora:
        raise HTTPException(status_code=422, detail="não dá para agendar no passado")

    # Um motorista nao pode segurar o site inteiro. Cada reserva confirmada
    # desconta reserved_kw do orcamento durante a janela; sem teto, uma conta
    # zerava a potencia disponivel e empurrava todas as recargas reais para a
    # fila.
    em_aberto = (
        await db.execute(
            select(func.count(Reservation.id)).where(
                Reservation.user_id == user.id,
                Reservation.status.in_(
                    [ReservationStatus.PENDING, ReservationStatus.CONFIRMED]
                ),
                Reservation.ends_at > agora,
            )
        )
    ).scalar_one()
    if em_aberto >= MAX_RESERVAS_POR_MOTORISTA:
        raise HTTPException(
            status_code=409,
            detail=(
                f"você já tem {em_aberto} agendamentos em aberto "
                f"(máximo {MAX_RESERVAS_POR_MOTORISTA}); cancele um para criar outro"
            ),
        )

    # O veiculo entra na reserva e o rateio usa a potencia que ele aceita:
    # aceitar o carro de outra pessoa deixaria o agendamento reservar com base
    # num dado que nao e' do motorista.
    if payload.vehicle_id is not None:
        dono = (
            await db.execute(
                select(Vehicle.id).where(
                    Vehicle.id == payload.vehicle_id, Vehicle.user_id == user.id
                )
            )
        ).scalar_one_or_none()
        if dono is None:
            raise HTTPException(status_code=404, detail="veículo não encontrado")

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
    ponto = await db.get(ChargePoint, reservation.charge_point_id)
    site = await db.get(Site, ponto.site_id) if ponto else None
    return _reserva_com_contexto(reservation, ponto, site)


def _reserva_com_contexto(reserva, ponto, site) -> ReservationOut:
    """Preenche o contexto do ponto na resposta da reserva.

    O app precisa dizer *onde* a reserva e'; sem estes campos ele teria que
    fazer uma chamada por reserva so' para traduzir o UUID em nome.
    """
    saida = ReservationOut.model_validate(reserva)
    saida.charge_point_code = ponto.code if ponto else None
    saida.charge_point_name = ponto.name if ponto else None
    saida.site_name = site.name if site else None
    return saida


@router.get("/reservations", response_model=list[ReservationOut])
async def my_reservations(
    db: DbSession,
    user: DriverUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    linhas = (
        await db.execute(
            select(Reservation, ChargePoint, Site)
            .join(ChargePoint, ChargePoint.id == Reservation.charge_point_id, isouter=True)
            .join(Site, Site.id == ChargePoint.site_id, isouter=True)
            .where(Reservation.user_id == user.id)
            .order_by(Reservation.starts_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [_reserva_com_contexto(r, cp, st) for r, cp, st in linhas]


@router.delete("/reservations/{reservation_id}", response_model=ReservationOut)
async def cancel_reservation(reservation_id: uuid.UUID, db: DbSession, user: DriverUser):
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
    ponto = await db.get(ChargePoint, reservation.charge_point_id)
    site = await db.get(Site, ponto.site_id) if ponto else None
    return _reserva_com_contexto(reservation, ponto, site)


# ----------------------------------------------------- veiculos, faturas, carteira
@router.get("/vehicles", response_model=list[VehicleOut])
async def my_vehicles(
    db: DbSession, user: DriverUser, limit: int = Query(default=50, ge=1, le=200)
):
    # Teto, nao paginacao: sao os carros de uma pessoa. O limite existe para a
    # resposta nao poder crescer sem fim, nao para o app folhear.
    return (
        (await db.execute(select(Vehicle).where(Vehicle.user_id == user.id).limit(limit)))
        .scalars()
        .all()
    )


@router.post("/vehicles", response_model=VehicleOut, status_code=201)
async def add_vehicle(payload: VehicleCreate, db: DbSession, user: DriverUser):
    vehicle = Vehicle(user_id=user.id, **payload.model_dump())
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    return vehicle


async def _veiculo_do_motorista(db, vehicle_id: uuid.UUID, user) -> Vehicle:
    """Busca o veiculo garantindo que ele e' de quem pediu.

    O 404 para carro de outra pessoa e' deliberado: um 403 confirmaria que o
    identificador existe.
    """
    veiculo = (
        await db.execute(
            select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.user_id == user.id)
        )
    ).scalar_one_or_none()
    if veiculo is None:
        raise HTTPException(status_code=404, detail="veículo não encontrado")
    return veiculo


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleOut)
async def update_vehicle(
    vehicle_id: uuid.UUID, payload: VehicleUpdate, db: DbSession, user: DriverUser
):
    """Corrige o cadastro do carro - placa digitada errada, bateria trocada."""
    veiculo = await _veiculo_do_motorista(db, vehicle_id, user)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(veiculo, campo, valor)
    await db.commit()
    await db.refresh(veiculo)
    return veiculo


@router.delete("/vehicles/{vehicle_id}", status_code=204, response_class=Response)
async def delete_vehicle(vehicle_id: uuid.UUID, db: DbSession, user: DriverUser) -> Response:
    """Remove o carro do cadastro.

    As sessoes passadas ficam: a coluna e' ON DELETE SET NULL, entao o historico
    e as faturas continuam intactos, so perdem o vinculo com o carro vendido.

    Um carro em recarga nao pode sair - a sessao em curso passaria a nao ter
    carro nenhum, e o rateio usa a potencia que ele aceita.
    """
    veiculo = await _veiculo_do_motorista(db, vehicle_id, user)

    em_uso = (
        await db.execute(
            select(ChargingSession.id).where(
                ChargingSession.vehicle_id == veiculo.id,
                ChargingSession.state.in_(ACTIVE_SESSION_STATES),
            )
        )
    ).first()
    if em_uso is not None:
        raise HTTPException(
            status_code=409, detail="este veículo está em uma recarga em andamento"
        )

    await db.delete(veiculo)
    await db.commit()
    return Response(status_code=204)

@router.get("/invoices", response_model=list[InvoiceOut])
async def my_invoices(
    db: DbSession, user: DriverUser, limit: int = Query(default=20, ge=1, le=100)
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
async def topup(payload: WalletTopUpIn, db: DbSession, user: DriverUser) -> dict:
    """Credito na carteira pre-paga.

    Na integracao real, o credito so entra depois do webhook do PSP confirmar -
    esta rota representa o passo final desse fluxo.

    A chave de idempotencia e' opcional no contrato, mas o app sempre manda: sem
    ela, dois toques no botao viram dois creditos.
    """
    updated = await payment_service.topup_wallet(
        db, user, payload.amount, idempotency_key=payload.idempotency_key
    )
    return {"wallet_balance": float(updated.wallet_balance)}
