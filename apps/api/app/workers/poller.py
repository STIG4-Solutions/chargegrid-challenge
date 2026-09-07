"""Workers de fundo: varredura dos pontos e rebalanceamento do site.

O SEMS+ da GoodWe so responde a consulta (pull) e nao empurra dados. Estes dois
lacos sao o que transforma consulta periodica em operacao em tempo real.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.drivers.registry import registry
from app.models.charge_point import ChargePoint
from app.models.site import Site
from app.services import events, power_manager, session_service, telemetry_service
from app.workers import virtual_meter

log = get_logger(__name__)


async def poll_once() -> dict:
    """Uma varredura de todos os pontos habilitados, agrupada por site."""
    scanned = failed = 0
    async with SessionLocal() as db:
        points = list(
            (
                await db.execute(
                    select(ChargePoint)
                    .where(ChargePoint.enabled.is_(True))
                    .options(selectinload(ChargePoint.connection))
                    .order_by(ChargePoint.site_id, ChargePoint.code)
                )
            )
            .scalars()
            .all()
        )

        # Le todos os pontos em paralelo: 40 eletropostos nao podem virar 40x o
        # timeout de um. Cada driver serializa suas proprias transacoes.
        async def read(cp: ChargePoint):
            driver = await registry.get(cp)
            return cp, await driver.read()

        results = await asyncio.gather(*(read(cp) for cp in points), return_exceptions=True)

        touched_sites: set = set()
        for item in results:
            if isinstance(item, BaseException):
                failed += 1
                log.warning("poller.read_error", error=str(item))
                continue
            cp, reading = item
            try:
                await telemetry_service.ingest(db, cp, reading)
                scanned += 1
                touched_sites.add(cp.site_id)
            except Exception as exc:  # noqa: BLE001 - um ponto ruim nao derruba o ciclo
                failed += 1
                log.warning("poller.ingest_error", cp=cp.code, error=str(exc))

        await telemetry_service.mark_stale_offline(db)
        # Agendamento vencido sem uso precisa devolver a potencia ao rateio.
        await session_service.expirar_reservas_vencidas(db)
        # Fila nao pode prender o ponto para sempre.
        await session_service.expire_queue(db)
        await db.commit()

        for site_id in touched_sites:
            await _publish_snapshot(db, site_id)

    return {"scanned": scanned, "failed": failed}


async def _publish_snapshot(db, site_id) -> None:
    """Empurra o estado atual do site para os dashboards conectados."""
    points = list(
        (
            await db.execute(
                select(ChargePoint).where(ChargePoint.site_id == site_id).order_by(ChargePoint.code)
            )
        )
        .scalars()
        .all()
    )
    budget = await power_manager.load_budget(
        db, (await db.execute(select(Site).where(Site.id == site_id))).scalar_one()
    )
    await events.bus.publish(
        events.site_topic(site_id),
        "telemetry",
        {
            "recorded_at": datetime.now(UTC).isoformat(),
            "budget": budget.as_dict(),
            "charge_points": [
                {
                    "id": str(cp.id),
                    "code": cp.code,
                    "status": str(cp.status),
                    "current_kw": float(cp.current_kw),
                    "limit_kw": float(cp.limit_kw),
                    "faults": cp.active_faults,
                }
                for cp in points
            ],
        },
    )


async def rebalance_once() -> dict:
    """Recalcula e aplica o orcamento de potencia de cada site."""
    applied = 0
    async with SessionLocal() as db:
        site_ids = list((await db.execute(select(Site.id))).scalars().all())
        for site_id in site_ids:
            try:
                result = await power_manager.rebalance_site(db, site_id, triggered_by="system")
                applied += result["applied"]
                # Redistribuir pode ter aberto folga: quem esta na fila entra agora.
                promovidas = await session_service.promote_queue(db, site_id)
                if promovidas:
                    log.info("queue.promoted", site_id=str(site_id), sessions=promovidas)
                await events.bus.publish(events.site_topic(site_id), "power_plan", result["plan"])
            except Exception as exc:  # noqa: BLE001
                log.warning("rebalance.error", site_id=str(site_id), error=str(exc))
    return {"applied": applied}


async def _enviar_push() -> dict:
    """Drena a fila de notificacoes pendentes."""
    from app.services import notification_service

    async with SessionLocal() as db:
        return await notification_service.enviar_pendentes(db)


async def _loop(name: str, coro, interval: int) -> None:
    log.info("worker.started", worker=name, interval_s=interval)
    while True:
        try:
            await coro()
        except asyncio.CancelledError:
            log.info("worker.stopped", worker=name)
            raise
        except Exception as exc:  # noqa: BLE001 - o laco nunca pode morrer
            log.error("worker.error", worker=name, error=str(exc))
        await asyncio.sleep(interval)


def start_workers() -> list[asyncio.Task]:
    if not settings.enable_workers:
        log.info("worker.disabled")
        return []
    tarefas = [
        asyncio.create_task(_loop("poller", poll_once, settings.poll_interval_s)),
        asyncio.create_task(
            _loop("rebalancer", rebalance_once, settings.power_rebalance_interval_s)
        ),
    ]
    # A fila de push e' drenada por worker, e nao no momento em que o evento e'
    # gravado: um servico externo lento ou fora do ar travaria a transicao de
    # estado da sessao - o carro deixaria de ser liberado porque a Expo caiu.
    tarefas.append(
        asyncio.create_task(_loop("push", _enviar_push, settings.push_interval_s))
    )
    # Sem medidor fisico, um worker sintetiza a curva do dia na mesma tabela.
    # Com METER_SOURCE=push, so' entram leituras enviadas por POST.
    if virtual_meter.habilitado():
        tarefas.append(
            asyncio.create_task(
                _loop("medidor_virtual", virtual_meter.gerar_leitura, settings.meter_interval_s)
            )
        )
    return tarefas


async def stop_workers(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
    await registry.close_all()
