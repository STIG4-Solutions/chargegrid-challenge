"""Faturamento: transforma uma sessao encerrada em fatura auditavel."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import Conflict, NotFound
from app.core.logging import get_logger
from app.db.base import INVOICE_CODE_SEQ
from app.models.billing import Invoice, InvoiceLine, SitePaymentMethod
from app.models.enums import InvoiceStatus, PaymentMethodKind, SessionState
from app.models.session import ChargingSession
from app.models.site import Site
from app.models.tariff import Tariff
from app.models.telemetry import TelemetrySample
from app.services import session_service
from app.services.tariff_engine import money, rate_session

log = get_logger(__name__)


async def _next_code(db: AsyncSession) -> str:
    number = (await db.execute(select(INVOICE_CODE_SEQ.next_value()))).scalar_one()
    return f"INV-{number}"


async def _amostras_cobraveis(db: AsyncSession, session: ChargingSession) -> list[TelemetrySample]:
    """Telemetria que pode virar dinheiro.

    `ingest` carimba a sessao em toda amostra, inclusive enquanto ela esta
    AUTHORIZING ou QUEUED, e `apply_reading` recusa essas de proposito - nao se
    cobra por recarga que nao comecou. A consulta pegava tudo, e os dois
    caminhos discordavam sobre o mesmo dado.

    Sem `started_at` a sessao nunca energizou: nao ha o que cobrar. Devolver a
    lista completa nesse caso seria justamente o contrario do que esta funcao
    existe para fazer - e `bill_session` aceita sessao em ERROR, que chega aqui
    exatamente assim.

    A previa usa o mesmo caminho de proposito: se ela filtrasse diferente, o
    valor mostrado durante a recarga nao fecharia com a fatura emitida no fim.
    """
    if session.started_at is None:
        return []

    consulta = (
        select(TelemetrySample)
        .where(
            TelemetrySample.session_id == session.id,
            TelemetrySample.recorded_at >= session.started_at,
        )
        .order_by(TelemetrySample.recorded_at)
    )
    return list((await db.execute(consulta)).scalars().all())


async def bill_session(db: AsyncSession, session: ChargingSession) -> Invoice:
    """Fatura uma sessao FINISHED. Idempotente: chamar duas vezes devolve a mesma fatura."""
    existing = (
        await db.execute(
            select(Invoice)
            .where(Invoice.session_id == session.id)
            .options(selectinload(Invoice.lines))
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    if session.state not in {SessionState.FINISHED, SessionState.ERROR}:
        raise Conflict(f"sessão ainda não encerrada ({session.state})")

    site = (await db.execute(select(Site).where(Site.id == session.site_id))).scalar_one()
    tariff = None
    if session.tariff_id:
        tariff = (
            await db.execute(
                select(Tariff)
                .where(Tariff.id == session.tariff_id)
                .options(selectinload(Tariff.windows))
            )
        ).scalar_one_or_none()

    samples = await _amostras_cobraveis(db, session)

    now = datetime.now(UTC)
    invoice = Invoice(
        code=await _next_code(db),
        site_id=session.site_id,
        session_id=session.id,
        user_id=session.user_id,
        status=InvoiceStatus.DRAFT,
        issued_on=now.date(),
    )

    if tariff is None:
        # Sem tarifa vinculada nao ha o que cobrar; a fatura zerada mantem o
        # rastro da energia entregue para conciliacao posterior.
        invoice.status = InvoiceStatus.VOID
        invoice.tariff_snapshot = {"error": "sessão sem tarifa vinculada"}
        db.add(invoice)
        session_service.record_event(
            db, session, "billing_skipped", message="Sessão sem tarifa vinculada"
        )
        await db.commit()
        return invoice

    # Import tardio: os servicos de beneficio leem o motor de tarifacao, e
    # importar os dois no topo fecharia o ciclo.
    from app.services import benefit_service, campaign_service

    rating = rate_session(
        session,
        tariff,
        samples,
        timezone=site.timezone,
        idle_grace_minutes=settings.idle_grace_minutes,
        now=now,
        # Assinatura E campanha podem valer ao mesmo tempo. `benefit_service`
        # decide o encontro: o melhor de cada componente, nunca a soma - somar
        # produziria desconto sem teto que ninguem orcou.
        beneficio=await benefit_service.resolver(db, session, now),
    )

    invoice.currency = tariff.currency
    invoice.subtotal = rating.subtotal
    # A coluna existe desde a 0001 e nunca teve produtor: `total` recebia
    # `rating.total` direto e a conta so' fechava porque o desconto era sempre
    # zero. Agora `subtotal - discount == total` vale por construcao, que e' o
    # que `InvoiceOut` documenta e o que a tela e o recibo somam.
    invoice.discount = rating.desconto
    invoice.total = rating.total
    invoice.net_amount = rating.total
    invoice.tariff_snapshot = rating.tariff_snapshot
    invoice.status = InvoiceStatus.OPEN if rating.total > 0 else InvoiceStatus.VOID
    for position, line in enumerate(rating.lines):
        invoice.lines.append(
            InvoiceLine(
                position=position,
                kind=line.kind,
                description=line.description,
                quantity=line.quantity,
                unit=line.unit,
                unit_price=line.unit_price,
                amount=line.amount,
            )
        )
    db.add(invoice)

    session.estimated_cost = float(rating.total)
    if session.state == SessionState.FINISHED:
        session_service.transition(
            db, session, SessionState.BILLED, message=f"Fatura {invoice.code} emitida"
        )

    # Progresso das missoes no MESMO commit. E' agregacao deterministica da
    # sessao que acabou de encerrar, sem I/O externo: ou os dois existem ou
    # nenhum, e nunca ha sessao faturada com progresso perdido. O que fica de
    # fora deste commit e' a concessao da recompensa - essa mexe em saldo e em
    # push, e uma falha la' nao pode desfazer a fatura.
    #
    # `session.state` ja e' BILLED aqui, que e' o que a agregacao conta.
    await campaign_service.atualizar_progresso(db, session, now)

    await db.commit()
    # Recarrega pelo mesmo caminho que a fatura ja existente usa la em cima.
    # O db.refresh() sozinho expira a colecao `lines` que acabou de ser montada,
    # e quem tocasse invoice.lines em seguida levaria um MissingGreenlet - o
    # carregamento preguicoso nao roda em contexto assincrono. Assim as duas
    # saidas da funcao devolvem a mesma coisa.
    invoice = await get_invoice(db, invoice.id)
    log.info("invoice.created", code=invoice.code, total=float(invoice.total))
    return invoice


async def preview_session(db: AsyncSession, session: ChargingSession) -> dict:
    """Previa do valor de uma sessao em andamento - usada pelo app e pelo dashboard."""
    if not session.tariff_id:
        return {"total": 0.0, "lines": [], "tariff_snapshot": {}}
    site = (await db.execute(select(Site).where(Site.id == session.site_id))).scalar_one()
    tariff = (
        await db.execute(
            select(Tariff)
            .where(Tariff.id == session.tariff_id)
            .options(selectinload(Tariff.windows))
        )
    ).scalar_one()
    samples = await _amostras_cobraveis(db, session)
    return rate_session(
        session,
        tariff,
        samples,
        timezone=site.timezone,
        idle_grace_minutes=settings.idle_grace_minutes,
    ).as_dict()


async def apply_processing_fee(db: AsyncSession, invoice: Invoice, kind: PaymentMethodKind) -> None:
    """Desconta a taxa do adquirente: receita liquida e o que o lojista recebe."""
    method = (
        await db.execute(
            select(SitePaymentMethod).where(
                SitePaymentMethod.site_id == invoice.site_id, SitePaymentMethod.kind == kind
            )
        )
    ).scalar_one_or_none()
    if method is None:
        return
    fee = money(
        Decimal(str(invoice.total)) * Decimal(str(method.fee_percent)) / Decimal("100")
        + Decimal(str(method.fee_fixed))
    )
    invoice.processing_fee = fee
    invoice.net_amount = money(Decimal(str(invoice.total)) - fee)


async def get_invoice(db: AsyncSession, invoice_id) -> Invoice:
    invoice = (
        await db.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(selectinload(Invoice.lines), selectinload(Invoice.payments))
        )
    ).scalar_one_or_none()
    if invoice is None:
        raise NotFound("fatura não encontrada")
    return invoice
