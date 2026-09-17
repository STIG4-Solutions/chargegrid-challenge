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
from app.services import (
    events,
    power_manager,
    reservation_service,
    session_service,
    telemetry_service,
)
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

        # Aqui, e nao antes: `expirar_reservas_vencidas` acabou de mudar o
        # estado de algumas reservas, e e' esse estado que decide o que sai do
        # equipamento. Sincronizar antes retiraria no ciclo seguinte.
        #
        # E neste laco, e nao no de push: empurrar reserva e' conversa Modbus
        # com o ponto, o mesmo assunto do poller, que ja' tem a conexao aberta.
        await reservation_service.sincronizar(db)

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
    """Concede recompensas pendentes e drena as duas filas de notificacao.

    Sao dois outbox porque sao duas tabelas: `session_events.notified_at` para o
    que acontece na sessao, e `rewards.notified_at` para recompensa concedida. O
    segundo nao cabia no primeiro - `session_events.session_id` e' obrigatorio, e
    missao do tipo "cadastre dois veiculos" nao nasce de sessao nenhuma.

    Um `_loop` so' para os tres: e' a mesma operacao externa (falar com a Expo) no
    mesmo intervalo, e conceder antes de notificar faz a recompensa criada agora
    sair avisada neste ciclo em vez de esperar o proximo.
    """
    from app.services import (
        campaign_service,
        notification_service,
        platform_service,
        subscription_service,
    )

    async with SessionLocal() as db:
        # Mensalidade vencida entra no mesmo ciclo: sao poucas por dia, e um
        # laco proprio para elas seria um worker que dorme 99% do tempo.
        await subscription_service.cobrar_mensalidades(db)
        # Contrato do estabelecimento: avanca o ciclo e emite a cobranca do
        # mes. Ambos idempotentes - `renova_em` so' avanca uma vez, e a
        # UNIQUE (contrato, competencia) barra a segunda emissao.
        await platform_service.renovar_vencidos(db)
        await platform_service.emitir_competencia(db)
        # Depois de emitir, e nao antes: a cobranca do mes nasce com dez dias de
        # prazo, entao nunca vence no mesmo ciclo em que e' criada. A ordem so'
        # importa para quem for ler - o resultado e' o mesmo.
        await platform_service.marcar_vencidas(db)
        # Fecha quem chegou ao fim do aviso previo. Depois de emitir, pelo
        # mesmo motivo da linha acima: a competencia do mes de encerramento
        # ainda e' devida, e `emitir_competencia` ja para em `encerra_em`.
        await platform_service.encerrar_vencidos(db)
        concedidas = await campaign_service.conceder_pendentes(db)
        sessoes = await notification_service.enviar_pendentes(db)
        recompensas = await notification_service.enviar_recompensas_pendentes(db)
        return {"concedidas": concedidas, **sessoes, **recompensas}


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
    tarefas.append(asyncio.create_task(_loop("push", _enviar_push, settings.push_interval_s)))
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
