"""Controle de Demanda: quanto de potencia cada ponto pode puxar, agora.

Regra de ouro: a soma dos tetos aplicados nunca pode exceder o que o site
consegue entregar. O orcamento e recalculado a cada ciclo porque PV, bateria e
carga do predio mudam ao longo do dia.

    orcamento_ev = limite_da_rede + pv + bateria - reserva_predial

A distribuicao usa water-filling por faixa de prioridade: dentro de uma faixa
todos recebem parcela igual, e quem precisa de menos devolve a sobra para os
demais. Um ponto que nao alcanca a potencia minima do hardware (1,4 kW mono /
4,2 kW trifasico) e suspenso em vez de receber uma migalha inutil.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.charge_point import ChargePoint
from app.models.enums import ChargePointStatus, ReservationStatus
from app.models.reservation import Reservation
from app.models.site import Site, SiteMeterReading

if TYPE_CHECKING:
    from app.services.priority_service import PrioridadeResolvida, SiteMeterReading

log = get_logger(__name__)

# Abaixo disso a diferenca nao vale uma escrita Modbus.
WRITE_DEADBAND_KW = 0.3

# Motivo legivel de um ponto ficar fora do rateio - vai direto para a tela.
MOTIVO_FORA = {
    ChargePointStatus.AVAILABLE: "ocioso — não reserva potência",
    ChargePointStatus.FAULTED: "em falha",
    ChargePointStatus.OFFLINE: "sem comunicação",
    ChargePointStatus.MAINTENANCE: "em manutenção",
    ChargePointStatus.RESERVED: "reservado",
    ChargePointStatus.FINISHING: "encerrando a sessão",
}


def _para_decimo(kw: float) -> float:
    """Trunca para o decimo de kW, a resolucao do registrador 10029.

    Truncar e nao arredondar: com N pontos dividindo o orcamento, arredondar
    para cima soma ate 0,05 kW por ponto acima do disponivel. Num site com
    dezenas de eletropostos isso passa do limite contratado - justamente o
    disjuntor que o controle de demanda existe para proteger.
    """
    return math.floor(kw * 10) / 10


# Alem disso a leitura do medidor nao vale mais: PV e bateria saem do orcamento
# e so a rede sustenta os eletropostos.
LEITURA_VALIDA_MIN = 15


@dataclass(slots=True)
class PowerBudget:
    grid_limit_kw: float
    pv_kw: float
    battery_kw: float
    reserved_kw: float
    building_load_kw: float
    ev_load_kw: float
    # Potencia comprometida com agendamentos em curso. Fica fora do rateio ate
    # o motorista chegar: reserva que nao segura capacidade nao e reserva.
    booked_kw: float = 0.0
    reading_at: datetime | None = None
    reading_stale: bool = True

    @property
    def available_kw(self) -> float:
        """Teto que os eletropostos podem consumir somados."""
        supply = self.grid_limit_kw + self.pv_kw + self.battery_kw
        # A reserva predial protege as cargas nao-EV; se o predio ja consome mais
        # que a reserva, e o consumo real que manda.
        non_ev = max(self.reserved_kw, self.building_load_kw)
        return max(0.0, round(supply - non_ev - self.booked_kw, 2))

    def as_dict(self) -> dict:
        return {
            "grid_limit_kw": self.grid_limit_kw,
            "pv_kw": self.pv_kw,
            "battery_kw": self.battery_kw,
            "reserved_kw": self.reserved_kw,
            "building_load_kw": self.building_load_kw,
            "ev_load_kw": self.ev_load_kw,
            "booked_kw": self.booked_kw,
            "available_kw": self.available_kw,
            "reading_at": self.reading_at.isoformat() if self.reading_at else None,
            "reading_stale": self.reading_stale,
        }


@dataclass(slots=True)
class Allocation:
    charge_point_id: str
    code: str
    priority: int
    requested_kw: float
    granted_kw: float
    suspended: bool = False
    reason: str = ""
    # Nome da regra de prioridade que definiu a faixa. Vazio = nenhuma regra
    # casou e valeu o inteiro do proprio ponto. E' o que permite ao painel
    # responder "por que este ponto foi cortado e aquele nao".
    regra: str = ""


@dataclass(slots=True)
class AllocationPlan:
    budget: PowerBudget
    allocations: list[Allocation] = field(default_factory=list)
    total_granted_kw: float = 0.0
    over_budget: bool = False

    def as_dict(self) -> dict:
        return {
            "budget": self.budget.as_dict(),
            "total_granted_kw": round(self.total_granted_kw, 2),
            "over_budget": self.over_budget,
            "allocations": [
                {
                    "charge_point_id": a.charge_point_id,
                    "code": a.code,
                    "priority": a.priority,
                    "requested_kw": round(a.requested_kw, 2),
                    "granted_kw": round(a.granted_kw, 2),
                    "suspended": a.suspended,
                    "reason": a.reason,
                    "regra": a.regra,
                }
                for a in self.allocations
            ],
        }


async def load_budget(db: AsyncSession, site: Site) -> PowerBudget:
    """Monta o orcamento com a leitura mais recente do smart meter do site."""
    reading = (
        await db.execute(
            select(SiteMeterReading)
            .where(SiteMeterReading.site_id == site.id)
            .order_by(SiteMeterReading.recorded_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    pv_kw = battery_kw = building_kw = ev_kw = 0.0
    fresca = reading is not None and reading.recorded_at > datetime.now(UTC) - timedelta(
        minutes=LEITURA_VALIDA_MIN
    )
    if fresca:
        pv_kw = float(reading.pv_kw) if site.allow_pv_kw else 0.0
        battery_kw = float(reading.battery_kw) if site.allow_battery_kw else 0.0
        # Bateria abaixo do SOC minimo nao entra no orcamento (espelha o reg 10030).
        if reading.battery_soc is not None and float(reading.battery_soc) <= float(
            site.battery_min_soc
        ):
            battery_kw = 0.0
        building_kw = float(reading.building_load_kw)
        ev_kw = float(reading.ev_load_kw)

    # Agendamentos com janela em curso seguram capacidade ate serem usados.
    agora = datetime.now(UTC)
    booked = (
        await db.execute(
            select(func.coalesce(func.sum(Reservation.reserved_kw), 0)).where(
                Reservation.site_id == site.id,
                Reservation.status == ReservationStatus.CONFIRMED,
                Reservation.starts_at <= agora,
                Reservation.ends_at > agora,
            )
        )
    ).scalar_one()

    return PowerBudget(
        grid_limit_kw=float(site.grid_limit_kw),
        booked_kw=float(booked or 0),
        pv_kw=max(0.0, pv_kw),
        battery_kw=max(0.0, battery_kw),
        reserved_kw=float(site.reserved_kw),
        building_load_kw=max(0.0, building_kw),
        ev_load_kw=max(0.0, ev_kw),
        reading_at=reading.recorded_at if reading is not None else None,
        reading_stale=not fresca,
    )


def build_plan(
    budget: PowerBudget,
    charge_points: list[ChargePoint],
    *,
    starting_ids: set[str] | None = None,
    prioridades: dict[str, PrioridadeResolvida] | None = None,
) -> AllocationPlan:
    """Water-filling por faixa de prioridade. Funcao pura - testavel sem banco.

    starting_ids inclui no rateio pontos que ainda estao AVAILABLE mas estao
    prestes a energizar. Sem isso ha um impasse de partida: o ponto so recebe
    potencia se ja estiver carregando, e so comeca a carregar se receber
    potencia. Pontos ociosos continuam fora - senao reservariam o orcamento
    inteiro sem entregar energia a ninguem.
    """
    plan = AllocationPlan(budget=budget)
    starting = starting_ids or set()
    resolvidas = prioridades or {}

    def faixa(cp: ChargePoint) -> int:
        """Prioridade efetiva: a da regra nomeada, ou o inteiro do proprio ponto."""
        r = resolvidas.get(str(cp.id))
        return r.prioridade if r is not None else int(cp.priority)

    def regra_de(cp: ChargePoint) -> str:
        r = resolvidas.get(str(cp.id))
        return (r.regra or "") if r is not None else ""

    # `starting` entra por fora do is_dispatchable porque o ponto ainda esta
    # AVAILABLE - mas nao por fora do corte manual: admitir um ponto cortado
    # dava potencia a quem o operador mandou parar, e como is_dispatchable
    # continua falso, os ciclos seguintes o excluiam do orcamento enquanto ele
    # carregava. O site passava do teto com o alocador dizendo que estava bem.
    candidates = [
        cp
        for cp in charge_points
        if cp.is_dispatchable
        or (cp.enabled and not cp.operator_throttled and str(cp.id) in starting)
    ]

    for cp in charge_points:
        if cp not in candidates:
            plan.allocations.append(
                Allocation(
                    charge_point_id=str(cp.id),
                    code=cp.code,
                    priority=faixa(cp),
                    regra=regra_de(cp),
                    requested_kw=0.0,
                    granted_kw=0.0,
                    suspended=cp.status in {ChargePointStatus.FAULTED, ChargePointStatus.OFFLINE},
                    reason=(
                        "cortado pelo operador"
                        if cp.operator_throttled
                        else MOTIVO_FORA.get(cp.status, f"fora do rateio ({cp.status})")
                    ),
                )
            )

    remaining = budget.available_kw
    # Prioridade decrescente: quem tem numero maior e servido primeiro.
    tiers = sorted({faixa(cp) for cp in candidates}, reverse=True)

    for priority in tiers:
        tier = [cp for cp in candidates if faixa(cp) == priority]
        granted = _water_fill(tier, remaining, starting)
        for cp in tier:
            kw = granted[str(cp.id)]
            suspended = kw <= 0
            plan.allocations.append(
                Allocation(
                    charge_point_id=str(cp.id),
                    code=cp.code,
                    priority=faixa(cp),
                    regra=regra_de(cp),
                    requested_kw=cp.effective_max_kw,
                    granted_kw=kw,
                    suspended=suspended,
                    reason="orçamento insuficiente para a potência mínima" if suspended else "",
                )
            )
            remaining -= kw
        remaining = max(0.0, remaining)

    plan.total_granted_kw = sum(a.granted_kw for a in plan.allocations)
    plan.over_budget = plan.total_granted_kw > budget.available_kw + 0.01
    return plan


def _water_fill(
    tier: list[ChargePoint], budget_kw: float, starting: set[str] | None = None
) -> dict[str, float]:
    """Divide o orcamento igualmente na faixa; sobra de quem satura vai para os demais.

    Se nao houver folga para todos alcancarem a potencia minima, alguem fica de
    fora - manter tres carros em 1 kW nao carrega nenhum deles. A ordem de corte
    protege quem ja esta carregando: sai primeiro quem esta chegando agora, que
    e quem pode esperar na fila. Sem essa regra, um recem-chegado derrubava um
    cliente no meio da recarga e nunca ia para a fila.
    """
    if not tier or budget_kw <= 0:
        return {str(cp.id): 0.0 for cp in tier}

    chegando = starting or set()
    active = list(tier)
    while active:
        min_total = sum(float(cp.min_kw) for cp in active)
        if min_total <= budget_kw:
            break
        # 1) quem esta chegando agora; 2) menor nominal; 3) codigo, para desempate.
        active.sort(key=lambda cp: (str(cp.id) not in chegando, cp.effective_max_kw, cp.code))
        active.pop(0)

    granted = {str(cp.id): 0.0 for cp in tier}
    if not active:
        return granted

    pending = {str(cp.id): cp.effective_max_kw for cp in active}
    remaining = budget_kw
    unsaturated = list(pending.keys())

    while unsaturated and remaining > 0.01:
        share = remaining / len(unsaturated)
        saturated_now = [cp_id for cp_id in unsaturated if pending[cp_id] <= share]
        if not saturated_now:
            for cp_id in unsaturated:
                granted[cp_id] += share
            remaining = 0.0
            break
        for cp_id in saturated_now:
            granted[cp_id] += pending[cp_id]
            remaining -= pending[cp_id]
            pending[cp_id] = 0.0
            unsaturated.remove(cp_id)

    # Respeita o piso do hardware e arredonda para a resolucao do reg 10029.
    for cp in active:
        cp_id = str(cp.id)
        teto = min(_para_decimo(granted[cp_id]), cp.effective_max_kw)
        granted[cp_id] = max(float(cp.min_kw), teto)
    return granted


async def get_site_with_points(db: AsyncSession, site_id) -> tuple[Site, list[ChargePoint]]:
    site = (await db.execute(select(Site).where(Site.id == site_id))).scalar_one()
    points = list(
        (
            await db.execute(
                select(ChargePoint)
                .where(ChargePoint.site_id == site_id)
                .options(selectinload(ChargePoint.connection))
                .order_by(ChargePoint.code)
            )
        )
        .scalars()
        .all()
    )
    return site, points


async def plan_for_site(
    db: AsyncSession, site_id, *, starting_ids: set[str] | None = None
) -> AllocationPlan:
    """Calcula o plano sem tocar no hardware - usado pelo preview do dashboard."""
    from app.services import priority_service

    site, points = await get_site_with_points(db, site_id)
    budget = await load_budget(db, site)
    prioridades = await priority_service.resolver_para_site(db, site, points)
    return build_plan(budget, points, starting_ids=starting_ids, prioridades=prioridades)


async def apply_plan(
    db: AsyncSession,
    plan: AllocationPlan,
    points: list[ChargePoint],
    *,
    triggered_by: str = "system",
    dry_run: bool = False,
) -> dict:
    """Escreve os tetos no hardware e persiste o que foi efetivamente aplicado."""
    from app.services.command_service import send_command

    by_id = {str(cp.id): cp for cp in points}
    applied, skipped, failed = 0, 0, 0

    for allocation in plan.allocations:
        cp = by_id.get(allocation.charge_point_id)
        if cp is None or not cp.is_dispatchable:
            continue

        if allocation.suspended:
            if not dry_run:
                result = await send_command(
                    db, cp, "set_dispatch_throttle", triggered_by=triggered_by, throttled=True
                )
                failed += 0 if result.ok else 1
                applied += 1 if result.ok else 0
                # So registra o corte se o hardware confirmou. Marcar SUSPENDED
                # depois de uma escrita que falhou punha o banco a mentir: o
                # ponto seguia puxando potencia plena enquanto o orcamento
                # contava com ele cortado.
                if result.ok:
                    cp.status = ChargePointStatus.SUSPENDED
            continue

        # Um ponto suspenso precisa ser liberado mesmo que o teto calculado seja
        # igual ao que ja esta gravado: o corte vive no reg 10000, nao no 10029.
        # Sem esta excecao o deadband pula a linha e o ponto fica na potencia
        # minima para sempre, mesmo com o site inteiro livre.
        retomando = cp.status == ChargePointStatus.SUSPENDED
        if not retomando and abs(float(cp.limit_kw) - allocation.granted_kw) < WRITE_DEADBAND_KW:
            skipped += 1
            continue

        if dry_run:
            applied += 1
            continue

        result = await send_command(
            db, cp, "set_power_limit", triggered_by=triggered_by, kw=allocation.granted_kw
        )
        if result.ok:
            cp.limit_kw = allocation.granted_kw
            if cp.status == ChargePointStatus.SUSPENDED:
                # Voltou a caber no orcamento: libera o corte do reg 10000.
                #
                # O estado so muda se a liberacao passou - simetrico ao corte
                # logo acima. Marcar CHARGING sem conferir deixava o reg 10000
                # cortado com o banco dizendo que o ponto carrega:
                # is_dispatchable virava verdadeiro e o alocador comprometia
                # potencia com um ponto que nao entrega nada.
                liberacao = await send_command(
                    db, cp, "set_dispatch_throttle", triggered_by=triggered_by, throttled=False
                )
                if liberacao.ok:
                    cp.status = ChargePointStatus.CHARGING
                else:
                    # O teto foi escrito, mas o reg 10000 continua cortado: o
                    # ponto nao voltou. Contar como aplicado faria o log dizer
                    # sucesso para um ponto que nao entrega nada - e o log e' o
                    # unico lugar onde isso apareceria.
                    failed += 1
                    continue
            applied += 1
        else:
            failed += 1

    if not dry_run:
        await db.commit()

    log.info(
        "power.plan_applied",
        available_kw=plan.budget.available_kw,
        granted_kw=round(plan.total_granted_kw, 2),
        applied=applied,
        skipped=skipped,
        failed=failed,
        dry_run=dry_run,
    )
    return {"applied": applied, "skipped": skipped, "failed": failed, "plan": plan.as_dict()}


async def rebalance_site(
    db: AsyncSession, site_id, *, triggered_by: str = "system", dry_run: bool = False
) -> dict:
    """Ciclo completo: le o orcamento, planeja e aplica. Chamado pelo worker."""
    from app.services import priority_service

    site, points = await get_site_with_points(db, site_id)
    budget = await load_budget(db, site)
    prioridades = await priority_service.resolver_para_site(db, site, points)
    plan = build_plan(budget, points, prioridades=prioridades)
    result = await apply_plan(db, plan, points, triggered_by=triggered_by, dry_run=dry_run)
    if get_settings().precificacao_dinamica and not dry_run:
        from app.services import bandeira

        result["bandeira"] = await bandeira.registrar(db, site, plan)
    return result
