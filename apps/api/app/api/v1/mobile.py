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
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, DriverUser, FleetManager
from app.core.errors import PaymentError
from app.db.base import RESERVATION_CODE_SEQ
from app.models.billing import Invoice
from app.models.charge_point import ChargePoint
from app.models.charge_point_report import ChargePointReport
from app.models.enums import (
    ACTIVE_SESSION_STATES,
    AuthMethod,
    ChargePointStatus,
    ReservationStatus,
    SessionState,
    StopReason,
)
from app.models.push_device import PushDevice
from app.models.reservation import Reservation
from app.models.session import ChargingSession
from app.models.site import Site
from app.models.tariff import Tariff
from app.models.user import Vehicle
from app.schemas.auth import (
    CentroDeCustoIn,
    PushDeviceIn,
    ReporteIn,
    VehicleCreate,
    VehicleOut,
    VehicleUpdate,
    WalletTopUpIn,
)
from app.schemas.campanha import MissaoDoMotoristaOut, RecompensaOut
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
from app.services import (
    billing_service,
    campaign_service,
    fleet_service,
    payment_service,
    receipt_service,
    session_service,
    start_advice_service,
    subscription_service,
)

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
    limit_minutes: int | None = Query(default=None, gt=0, le=24 * 60),
    limit_amount: float | None = Query(default=None, gt=0),
) -> SessionDetail:
    """Iniciar recarga pelo app, opcionalmente com um teto.

    A pre-autorizacao existe para o estabelecimento nao ficar com energia
    entregue e sem lastro de pagamento: a sessao para sozinha ao atingir o valor.

    Os tres limites sao tetos que o motorista escolhe - "carregue ate 30 kWh",
    "ate 40 minutos", "ate R$ 50". Quem os aplica e a ingestao de telemetria,
    que encerra a sessao no primeiro que for atingido; a rota so' os registra.
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

    # A pre-autorizacao TAMBEM encerra a sessao ao ser atingida. Sem esta
    # reconciliacao, um teto de R$ 80 sobre a pre-autorizacao padrao de R$ 50
    # nunca seria alcancado: a recarga pararia nos 50 e o motorista veria o
    # proprio limite ignorado, sem erro nenhum. Nao da' para gastar mais do que
    # se autorizou, entao autorizar ao menos o que se pretende gastar.
    if limit_amount is not None and limit_amount > preauth_amount:
        preauth_amount = limit_amount

    session = await session_service.authorize(
        db,
        cp,
        user=user,
        vehicle_id=vehicle_id,
        auth_method=AuthMethod.APP,
        preauth_amount=preauth_amount,
        limit_kwh=limit_kwh,
        limit_minutes=limit_minutes,
        limit_amount=limit_amount,
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


@router.get("/charge-points/{charge_point_id}/when-to-start")
async def when_to_start(
    charge_point_id: uuid.UUID,
    db: DbSession,
    _: DriverUser,
    kwh: float = Query(default=30.0, gt=0, le=200),
    horas: int = Query(default=12, ge=1, le=24),
) -> dict:
    """Quando compensa começar a recarga neste ponto.

    O motorista vê o preço de agora; o que ele não vê é que daqui a duas horas
    o mesmo kWh custa 30% menos. A conta usa o mesmo motor de tarifação que vai
    faturar depois, caminhando a sessão pelas janelas — uma recarga longa
    atravessa a virada no meio, e o preço médio que ela paga não é o de
    nenhuma das duas pontas.
    """
    return await start_advice_service.quando_comecar(
        db, charge_point_id, kwh=kwh, horas=horas
    )


# ------------------------------------------------------------------ push


@router.post("/push-devices", status_code=204, response_class=Response, response_model=None)
async def register_push_device(
    payload: PushDeviceIn, db: DbSession, user: DriverUser
) -> Response:
    """Registra (ou reaponta) o aparelho deste motorista.

    O token pertence ao aparelho, não à pessoa. Dois motoristas usando o mesmo
    celular emprestado: sem o reaponte, o segundo receberia as notificações do
    primeiro — com o código da recarga e o valor. Por isso o registro sempre
    sobrescreve o dono em vez de criar uma segunda linha.
    """
    existente = (
        await db.execute(select(PushDevice).where(PushDevice.token == payload.token))
    ).scalar_one_or_none()

    agora = datetime.now(UTC)
    if existente is not None:
        existente.user_id = user.id
        existente.platform = payload.platform
        existente.last_seen_at = agora
    else:
        db.add(
            PushDevice(
                id=uuid.uuid4(),
                user_id=user.id,
                token=payload.token,
                platform=payload.platform,
                last_seen_at=agora,
            )
        )
    await db.commit()
    return Response(status_code=204)


@router.delete(
    "/push-devices/{token}", status_code=204, response_class=Response, response_model=None
)
async def unregister_push_device(token: str, db: DbSession, user: DriverUser) -> Response:
    """Remove o aparelho ao sair da conta.

    Filtra pelo dono: sem isso, saber o token de outra pessoa bastaria para
    silenciar as notificações dela.
    """
    aparelho = (
        await db.execute(
            select(PushDevice).where(PushDevice.token == token, PushDevice.user_id == user.id)
        )
    ).scalar_one_or_none()
    if aparelho is not None:
        await db.delete(aparelho)
        await db.commit()
    # 204 mesmo quando não existe: sair da conta não pode falhar por causa de
    # um token que o servidor já não tinha.
    return Response(status_code=204)


# ----------------------------------------------------------------- recibo


@router.get("/invoices/{invoice_id}/receipt")
async def invoice_receipt(invoice_id: uuid.UUID, db: DbSession, user: DriverUser) -> dict:
    """Dados do recibo, para a tela montar o resumo."""
    recibo = await receipt_service.montar(db, invoice_id, user)
    if recibo is None:
        raise HTTPException(status_code=404, detail="fatura não encontrada")
    return recibo


@router.get("/invoices/{invoice_id}/receipt.html", response_class=HTMLResponse)
async def invoice_receipt_html(
    invoice_id: uuid.UUID, db: DbSession, user: DriverUser
) -> HTMLResponse:
    """O documento em si, pronto para virar PDF no aparelho.

    Renderizado no servidor de propósito: um recibo montado no cliente teria
    números dependentes da versão instalada, e dois motoristas com builds
    diferentes gerariam documentos diferentes para a mesma fatura.
    """
    recibo = await receipt_service.montar(db, invoice_id, user)
    if recibo is None:
        raise HTTPException(status_code=404, detail="fatura não encontrada")
    return HTMLResponse(receipt_service.como_html(recibo))


# --------------------------------------------------- reportar problema no ponto


@router.post("/charge-points/{charge_point_id}/reports", status_code=201)
async def report_problem(
    charge_point_id: uuid.UUID, payload: ReporteIn, db: DbSession, user: DriverUser
) -> dict:
    """Reportar um problema neste ponto.

    Fecha o ciclo com a manutenção preditiva do painel. O registrador cobre o
    que o equipamento sabe de si — sobretemperatura, falha de trava, perda de
    comunicação. Não cobre cabo cortado, tela apagada nem vaga tomada por um
    carro a combustão: nesses casos o ponto reporta "disponível" com toda a
    sinceridade, e quem vê é a pessoa que chegou ali. O motorista vê antes do
    sensor, e às vezes é o único que vê.
    """
    cp = (
        await db.execute(select(ChargePoint).where(ChargePoint.id == charge_point_id))
    ).scalar_one_or_none()
    if cp is None:
        raise HTTPException(status_code=404, detail="ponto de recarga não encontrado")

    if payload.session_id is not None:
        # Amarrar o reporte a uma sessão de outra pessoa daria ao operador uma
        # pista falsa sobre quando o problema aconteceu.
        dono = (
            await db.execute(
                select(ChargingSession.id).where(
                    ChargingSession.id == payload.session_id,
                    ChargingSession.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if dono is None:
            raise HTTPException(status_code=404, detail="sessão não encontrada")

    reporte = ChargePointReport(
        id=uuid.uuid4(),
        charge_point_id=charge_point_id,
        user_id=user.id,
        session_id=payload.session_id,
        categoria=payload.categoria,
        descricao=(payload.descricao or "").strip() or None,
    )
    db.add(reporte)
    await db.commit()
    return {
        "id": str(reporte.id),
        "categoria": reporte.categoria,
        "ponto": cp.code,
        "registrado": True,
    }


@router.get("/charge-points/{charge_point_id}/reports")
async def my_reports_for_point(
    charge_point_id: uuid.UUID, db: DbSession, user: DriverUser
) -> list[dict]:
    """Os reportes que ESTE motorista fez neste ponto.

    Só os próprios: a lista de reclamações de um ponto é informação do
    operador, e devolvê-la ao público entregaria quem reclamou de quê.
    """
    linhas = (
        (
            await db.execute(
                select(ChargePointReport)
                .where(
                    ChargePointReport.charge_point_id == charge_point_id,
                    ChargePointReport.user_id == user.id,
                )
                .order_by(ChargePointReport.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "categoria": r.categoria,
            "descricao": r.descricao,
            "criado_em": r.created_at.isoformat(),
            "resolvido": r.resolved_at is not None,
            "resolucao": r.resolucao,
        }
        for r in linhas
    ]


# ------------------------------------------------------------------- frota


@router.get("/fleet/report")
async def fleet_report(
    db: DbSession,
    gestor: FleetManager,
    mes: str = Query(description="AAAA-MM", pattern=r"^\d{4}-\d{2}$"),
) -> dict:
    """Relatório mensal da frota, por centro de custo.

    Fecha pela data de emissão da fatura, não pelo início da recarga: uma
    sessão que começa 31/03 às 23h e termina 01/04 às 2h pertence à fatura de
    abril — e é a fatura que o financeiro concilia.
    """
    try:
        return await fleet_service.relatorio_mensal(db, gestor, mes=mes)
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro


@router.get("/fleet/vehicles")
async def fleet_vehicles(db: DbSession, gestor: FleetManager) -> list[dict]:
    """Carros da frota e seus centros de custo."""
    return await fleet_service.veiculos_da_frota(db, gestor)


@router.put("/fleet/vehicles/{vehicle_id}/cost-center")
async def set_cost_center(
    vehicle_id: uuid.UUID, payload: CentroDeCustoIn, db: DbSession, gestor: FleetManager
) -> dict:
    """Define o centro de custo de um carro da própria frota."""
    veiculo = await fleet_service.definir_centro_de_custo(
        db, gestor, vehicle_id, payload.centro_de_custo
    )
    if veiculo is None:
        raise HTTPException(status_code=404, detail="veículo não encontrado")
    return veiculo


# --------------------------------------------------------------------- missoes


@router.get("/missions", response_model=list[MissaoDoMotoristaOut])
async def minhas_missoes(db: DbSession, user: DriverUser) -> list[dict]:
    """Missoes vigentes com o progresso DESTE motorista.

    Seguranca: o progresso e' filtrado por `user.id` do token, nunca por
    parametro - senao qualquer um leria o desempenho de qualquer outro.
    """
    return await campaign_service.missoes_do_motorista(db, user)


@router.get("/rewards", response_model=list[RecompensaOut])
async def minhas_recompensas(db: DbSession, user: DriverUser) -> list[dict]:
    """Historico de recompensas, so' as de quem esta pedindo."""
    return await campaign_service.recompensas_do_motorista(db, user)


# ----------------------------------------------------------------- assinatura


@router.get("/plans")
async def planos_de_recarga(db: DbSession, _: DriverUser) -> list[dict]:
    """Catalogo de planos. Escopo de rede: nao pertencem a praca nenhuma."""
    return [
        {
            "codigo": p.codigo,
            "nome": p.nome,
            "descricao": p.descricao,
            "preco_mensal_brl": float(p.preco_mensal_brl),
            "desconto_pct": float(p.desconto_pct),
            "kwh_inclusos": float(p.kwh_inclusos),
            "isenta_taxa_de_conexao": p.isenta_taxa_de_conexao,
        }
        for p in await subscription_service.planos_ativos(db)
    ]


@router.get("/subscription")
async def minha_assinatura(db: DbSession, user: DriverUser) -> dict:
    """Plano, franquia restante e proxima cobranca - so' de quem esta pedindo."""
    return await subscription_service.minha_assinatura(db, user)


@router.post("/subscription", status_code=201)
async def assinar(payload: dict, db: DbSession, user: DriverUser) -> dict:
    """Assina e cobra a primeira mensalidade da carteira.

    Saldo insuficiente vira 402, e nao 500: e' uma condicao esperada, e o app
    precisa distinguir "recarregue a carteira" de "algo quebrou".
    """
    codigo = (payload or {}).get("codigo")
    if not codigo:
        raise HTTPException(status_code=422, detail="informe o código do plano")
    try:
        await subscription_service.assinar(db, user, str(codigo))
    except PaymentError as erro:
        raise HTTPException(status_code=402, detail=str(erro)) from erro
    return await subscription_service.minha_assinatura(db, user)


@router.delete("/subscription", response_model=None, response_class=Response, status_code=204)
async def cancelar_assinatura(db: DbSession, user: DriverUser):
    """Cancela a renovacao. O mes ja pago continua valendo ate o fim."""
    await subscription_service.cancelar(db, user)
    return Response(status_code=204)
