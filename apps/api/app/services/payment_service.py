"""Orquestracao de pagamento: pre-autorizacao, cobranca, webhook e carteira."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import Conflict, NotFound, PaymentError
from app.core.logging import get_logger
from app.models.billing import Invoice, Payment, SitePaymentMethod, WalletEntry
from app.models.enums import InvoiceStatus, PaymentMethodKind, PaymentStatus
from app.models.user import User
from app.services import billing_service
from app.services.payment_providers import ChargeRequest, get_provider
from app.services.tariff_engine import money

log = get_logger(__name__)


async def _method_config(db: AsyncSession, site_id, kind: PaymentMethodKind) -> SitePaymentMethod:
    method = (
        await db.execute(
            select(SitePaymentMethod).where(
                SitePaymentMethod.site_id == site_id, SitePaymentMethod.kind == kind
            )
        )
    ).scalar_one_or_none()
    if method is None or not method.enabled:
        raise PaymentError(f"método de pagamento não habilitado neste site: {kind}")
    return method


async def charge_invoice(
    db: AsyncSession,
    invoice: Invoice,
    kind: PaymentMethodKind,
    *,
    idempotency_key: str | None = None,
    payer: User | None = None,
) -> Payment:
    """Cria a cobranca. A chave de idempotencia protege contra retry do app."""
    # A idempotencia vem antes de qualquer guarda, e nao depois.
    #
    # O caso que ela existe para atender e' exatamente este: a primeira chamada
    # deu certo, a fatura virou PAID, e a resposta se perdeu no caminho. Com a
    # checagem de "ja paga" na frente, o retry do app tomava 409 e a tela
    # mostrava erro num pagamento que tinha funcionado. Devolver o pagamento
    # original e' a unica resposta correta para a mesma chave.
    if idempotency_key:
        existing = (
            await db.execute(select(Payment).where(Payment.idempotency_key == idempotency_key))
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    if invoice.status == InvoiceStatus.PAID:
        raise Conflict("fatura já paga")
    if float(invoice.total) <= 0:
        raise PaymentError("fatura sem valor a cobrar")

    # Fatura SEM site e' da rede - hoje, a mensalidade de assinatura. Nao ha
    # estabelecimento a quem perguntar se o meio esta habilitado, e a carteira e'
    # instrumento da propria plataforma: nao passa por adquirente e nao tem taxa
    # de site. Qualquer outro meio exige um site, porque a taxa do adquirente
    # sai do que o estabelecimento recebe - e sem estabelecimento nao ha de onde.
    if invoice.site_id is None:
        if kind != PaymentMethodKind.WALLET:
            raise PaymentError(
                "fatura da rede só pode ser paga pela carteira: "
                f"{kind} depende de um estabelecimento"
            )
        return await _charge_wallet(db, invoice, payer, idempotency_key)

    method = await _method_config(db, invoice.site_id, kind)

    # Carteira pre-paga liquida internamente, sem passar por adquirente.
    if kind == PaymentMethodKind.WALLET:
        return await _charge_wallet(db, invoice, payer, idempotency_key)

    provider = get_provider(method.provider, method.provider_config)
    response = await provider.create_charge(
        ChargeRequest(
            amount=Decimal(str(invoice.total)),
            currency=invoice.currency,
            method=kind,
            reference=invoice.code,
            description=f"Recarga EV - fatura {invoice.code}",
            payer_document=payer.document if payer else None,
            payer_email=payer.email if payer else None,
            metadata={"invoice_id": str(invoice.id), "session_id": str(invoice.session_id)},
        )
    )

    now = datetime.now(UTC)
    payment = Payment(
        invoice_id=invoice.id,
        method=kind,
        status=response.status,
        amount=invoice.total,
        provider=method.provider,
        provider_ref=response.provider_ref,
        idempotency_key=idempotency_key,
        qr_code=response.qr_code,
        failure_reason=response.failure_reason,
        authorized_at=now if response.status != PaymentStatus.PENDING else None,
        captured_at=now if response.status == PaymentStatus.CAPTURED else None,
        raw_response=response.raw,
    )
    db.add(payment)

    invoice.status = InvoiceStatus.OPEN
    if response.status == PaymentStatus.CAPTURED:
        await _settle(db, invoice, payment)
    elif response.status == PaymentStatus.FAILED:
        invoice.status = InvoiceStatus.FAILED

    await db.commit()
    await db.refresh(payment)
    log.info("payment.created", invoice=invoice.code, method=str(kind), status=str(payment.status))
    return payment


async def _charge_wallet(
    db: AsyncSession, invoice: Invoice, payer: User | None, idempotency_key: str | None
) -> Payment:
    if payer is None:
        raise PaymentError("carteira exige usuário identificado")

    # Trava a linha antes de ler o saldo. Sem isso, duas cobrancas simultaneas
    # leem o mesmo valor, cada uma se ve com saldo suficiente, e o motorista
    # gasta duas vezes o que tem.
    saldo = (
        await db.execute(select(User.wallet_balance).where(User.id == payer.id).with_for_update())
    ).scalar_one()

    total = Decimal(str(invoice.total))
    if Decimal(str(saldo)) < total:
        raise PaymentError(
            f"saldo insuficiente na carteira: {saldo} disponível, {total} necessário"
        )

    novo_saldo = money(Decimal(str(saldo)) - total)
    payer.wallet_balance = novo_saldo

    # A linha do debito. Ate aqui o saldo caia sem deixar rastro, e a carteira
    # so' tinha meio razao: o motorista via o numero diminuir e nao havia o que
    # conferir. Sem esta linha `SUM(wallet_entries.amount)` deixa de bater com
    # `users.wallet_balance`, que e' a invariante que o teste fixa.
    #
    # Vai no MESMO commit do `Payment`, e nao podia ser diferente: ou o dinheiro
    # saiu e a linha existe, ou nenhum dos dois aconteceu.
    #
    # A chave de idempotencia e' deterministica pela fatura - `wallet:<codigo>`.
    # O retry que ja' foi cobrado esbarra no UNIQUE em vez de debitar de novo.
    db.add(
        WalletEntry(
            user_id=payer.id,
            amount=-total,
            balance_after=novo_saldo,
            idempotency_key=f"wallet:{invoice.code}",
            provider="wallet",
            provider_ref=f"wallet_{invoice.code}",
            origem="pagamento",
            invoice_id=invoice.id,
        )
    )

    payment = Payment(
        invoice_id=invoice.id,
        method=PaymentMethodKind.WALLET,
        status=PaymentStatus.CAPTURED,
        amount=invoice.total,
        provider="wallet",
        provider_ref=f"wallet_{invoice.code}",
        idempotency_key=idempotency_key,
        authorized_at=datetime.now(UTC),
        captured_at=datetime.now(UTC),
    )
    db.add(payment)
    await _settle(db, invoice, payment)
    await db.commit()
    await db.refresh(payment)
    return payment


async def _settle(db: AsyncSession, invoice: Invoice, payment: Payment) -> None:
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = payment.captured_at or datetime.now(UTC)
    await billing_service.apply_processing_fee(db, invoice, payment.method)


async def handle_webhook(db: AsyncSession, event: dict) -> dict:
    """Liquidacao assincrona (Pix confirmado, cartao capturado).

    Idempotente: um evento repetido pelo PSP nao pode pagar a fatura duas vezes.
    """
    provider_ref = event.get("provider_ref") or event.get("txid")
    status = event.get("status")
    if not provider_ref:
        raise PaymentError("webhook sem referência do provedor")

    payment = (
        await db.execute(
            select(Payment)
            .where(Payment.provider_ref == provider_ref)
            .options(selectinload(Payment.invoice))
        )
    ).scalar_one_or_none()
    if payment is None:
        raise NotFound("pagamento não encontrado para a referência informada")

    if payment.status in {PaymentStatus.CAPTURED, PaymentStatus.REFUNDED}:
        return {"status": str(payment.status), "idempotent": True}

    now = datetime.now(UTC)
    if status in {"paid", "captured", "settled", "CONCLUIDA"}:
        payment.status = PaymentStatus.CAPTURED
        payment.captured_at = now
        payment.raw_response = event
        await _settle(db, payment.invoice, payment)
    elif status in {"failed", "expired", "REMOVIDA_PELO_PSP"}:
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = event.get("reason", status)
        payment.invoice.status = InvoiceStatus.FAILED
    elif status == "refunded":
        payment.status = PaymentStatus.REFUNDED
        payment.invoice.status = InvoiceStatus.REFUNDED

    await db.commit()
    return {"status": str(payment.status), "invoice": payment.invoice.code}


async def estornar(db: AsyncSession, invoice: Invoice, *, autor: User) -> Payment:
    """Devolve o que foi cobrado por uma fatura.

    Nao havia caminho nenhum para isto. `handle_webhook` sabia marcar
    `REFUNDED` quando o PSP avisava, mas pagamento por CARTEIRA nunca gera
    webhook - ele e' capturado na hora -, entao uma recarga cobrada errado do
    saldo do motorista era irreversivel pela API. So' mexendo no banco.

    Dois caminhos, e a diferenca e' de onde o dinheiro volta:

      - CARTEIRA: o credito nasce aqui, como lancamento `estorno` no razao. Nao
        ha terceiro envolvido - o dinheiro nunca saiu da plataforma.
      - PSP: quem devolve e' o provedor, e o razao nao tem o que registrar,
        porque o dinheiro nunca esteve na carteira. Marcar `REFUNDED` sem
        chamar o provedor seria dizer que devolveu sem devolver.

    A chave de idempotencia e' deterministica pela fatura. Duas chamadas nao
    creditam duas vezes: a segunda esbarra no UNIQUE, e o estado ja e'
    `REFUNDED` de qualquer forma.
    """
    # CAPTURED **ou** REFUNDED na mesma consulta, e a ordem das checagens
    # abaixo importa: filtrar so' por CAPTURED faria a segunda chamada nao achar
    # nada e estourar "nao ha pagamento capturado" - uma mensagem errada para um
    # estorno que ja aconteceu, e que transformaria repetir a operacao em erro
    # em vez de no-op.
    pagamento = (
        await db.execute(
            select(Payment)
            .where(
                Payment.invoice_id == invoice.id,
                Payment.status.in_((PaymentStatus.CAPTURED, PaymentStatus.REFUNDED)),
            )
            .order_by(Payment.captured_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if pagamento is None:
        raise PaymentError("não há pagamento capturado nesta fatura para estornar")
    if pagamento.status == PaymentStatus.REFUNDED:
        return pagamento

    total = Decimal(str(pagamento.amount))

    if pagamento.method == PaymentMethodKind.WALLET:
        pagador = (
            await db.execute(
                select(User).where(User.id == invoice.user_id).with_for_update()
            )
        ).scalar_one_or_none()
        if pagador is None:
            raise PaymentError("fatura sem pagador: não há carteira para devolver")

        saldo = money(Decimal(str(pagador.wallet_balance)) + total)
        db.add(
            WalletEntry(
                user_id=pagador.id,
                amount=total,
                balance_after=saldo,
                idempotency_key=f"estorno:{invoice.code}",
                provider="wallet",
                provider_ref=f"estorno_{invoice.code}",
                origem="estorno",
                invoice_id=invoice.id,
                # Sem `motivo`: a fatura E' a justificativa, e repetir "estorno
                # da INV-1042" numa coluna que ja tem `invoice_id` seria ruido.
                criado_por=autor.id,
            )
        )
        try:
            await db.flush()
        except IntegrityError:
            # Ja estornado por outra chamada. O saldo dela vale; nao se soma de
            # novo. Mesmo desenho de `topup_wallet`.
            await db.rollback()
            return pagamento
        pagador.wallet_balance = saldo
    else:
        provedor = await provedor_do_pagamento(db, pagamento, invoice)
        resposta = await provedor.refund(pagamento.provider_ref or "", total)
        if resposta.status != PaymentStatus.REFUNDED:
            raise PaymentError(
                f"provedor não confirmou a devolução: {resposta.failure_reason or resposta.status}"
            )

    pagamento.status = PaymentStatus.REFUNDED
    invoice.status = InvoiceStatus.REFUNDED
    await db.commit()
    log.info(
        "fatura.estornada",
        fatura=invoice.code,
        metodo=str(pagamento.method),
        valor=float(total),
        por=str(autor.id),
    )
    await db.refresh(pagamento)
    return pagamento


async def provedor_do_pagamento(db: AsyncSession, pagamento: Payment, invoice: Invoice):
    """O provedor configurado para o meio com que ESTA fatura foi paga.

    Nao e' `get_provider()` global: com dois sites em PSPs diferentes, devolver
    pelo provedor errado falha - ou, pior, devolve da conta do vizinho.
    """
    metodo = (
        await db.execute(
            select(SitePaymentMethod).where(
                SitePaymentMethod.site_id == invoice.site_id,
                SitePaymentMethod.kind == pagamento.method,
            )
        )
    ).scalar_one_or_none()
    if metodo is None:
        return get_provider()
    return get_provider(metodo.provider, metodo.provider_config)


async def topup_wallet(
    db: AsyncSession, user: User, amount: Decimal, idempotency_key: str | None = None
) -> User:
    if amount <= 0:
        raise PaymentError("valor de recarga inválido")

    # Chave repetida devolve o saldo de entao, sem creditar de novo. O SELECT
    # aqui atende o caso comum - o retry depois de uma resposta perdida na rede.
    # Quem barra a corrida de dois toques simultaneos e' o UNIQUE do banco, no
    # INSERT abaixo.
    if idempotency_key:
        anterior = (
            await db.execute(
                select(WalletEntry).where(WalletEntry.idempotency_key == idempotency_key)
            )
        ).scalar_one_or_none()
        if anterior is not None:
            return user

    saldo = (
        await db.execute(select(User.wallet_balance).where(User.id == user.id).with_for_update())
    ).scalar_one()
    novo_saldo = money(Decimal(str(saldo)) + amount)

    db.add(
        WalletEntry(
            user_id=user.id,
            amount=amount,
            balance_after=novo_saldo,
            idempotency_key=idempotency_key,
            origem="topup",
        )
    )
    user.wallet_balance = novo_saldo
    try:
        await db.commit()
    except IntegrityError:
        # O outro toque chegou primeiro e ja creditou. Desfaz este e devolve o
        # que ficou valendo, em vez de creditar duas vezes.
        await db.rollback()
        await db.refresh(user)
        return user

    await db.refresh(user)
    return user


async def provedor_do_evento(db: AsyncSession, body: bytes):
    """Descobre com qual segredo verificar a assinatura deste webhook.

    A referencia vem do corpo, que ainda nao e confiavel - mas ela so escolhe
    QUAL chave tentar. A assinatura continua sendo conferida contra o corpo cru,
    entao um corpo forjado nao passa por apontar para outro estabelecimento.
    Cai no provedor global quando a referencia nao casa com nada.
    """
    try:
        evento = json.loads(body)
        referencia = evento.get("provider_ref") or evento.get("txid")
        if not referencia:
            # O Pix nao poe referencia no topo: o corpo dele e'
            # `{"pix": [{"txid": ..., "endToEndId": ...}, ...]}`. Sem olhar
            # dentro da lista, a busca falha, cai-se no provedor global - que e'
            # o `mock` - e o corpo nunca chega a ser traduzido: a fatura fica
            # aberta com o dinheiro ja recebido.
            recebidos = evento.get("pix")
            if isinstance(recebidos, list) and recebidos:
                referencia = (recebidos[0] or {}).get("txid")
    except (ValueError, AttributeError):
        referencia = None

    if not referencia:
        return get_provider()

    pagamento = (
        await db.execute(
            select(Payment)
            .where(Payment.provider_ref == referencia)
            .options(selectinload(Payment.invoice))
        )
    ).scalar_one_or_none()
    if pagamento is None or pagamento.invoice is None:
        return get_provider()

    metodo = (
        await db.execute(
            select(SitePaymentMethod).where(
                SitePaymentMethod.site_id == pagamento.invoice.site_id,
                SitePaymentMethod.kind == pagamento.method,
            )
        )
    ).scalar_one_or_none()
    if metodo is None:
        return get_provider()
    return get_provider(metodo.provider, metodo.provider_config)
