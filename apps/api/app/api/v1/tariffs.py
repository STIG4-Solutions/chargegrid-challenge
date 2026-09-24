"""Modulo Tarifacao e Pagamento: politicas, simulador, metodos, faturas e cobranca."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import (
    AdminUser,
    Auditor,
    CurrentUser,
    DbSession,
    OperatorUser,
    ScopedSiteId,
    get_scoped_site_id,
)
from app.models.billing import Invoice, SitePaymentMethod
from app.models.charge_point import ChargePoint
from app.models.enums import InvoiceStatus, UserRole
from app.models.session import ChargingSession
from app.models.site import Site
from app.models.tariff import Tariff, TariffWindow
from app.models.user import User
from app.schemas.common import Page
from app.schemas.ev import (
    AjusteDeCarteiraIn,
    ChargeRequestIn,
    InvoiceOut,
    PaymentMethodIn,
    PaymentMethodOut,
    PaymentOut,
    RatingOut,
    RevenueSummary,
    SimulationRequest,
    TariffCreate,
    TariffOut,
    TariffUpdate,
    TariffWindowIn,
)
from app.services import (
    audit_service,
    billing_service,
    payment_service,
    tariff_rules,
    wallet_service,
)
from app.services.tariff_engine import simulate

router = APIRouter(tags=["recarga ev · tarifação e pagamento"])


# ------------------------------------------------------------------ tarifas
@router.get("/tariffs", response_model=list[TariffOut])
async def list_tariffs(db: DbSession, site_id: ScopedSiteId, _: OperatorUser):
    return (
        (
            await db.execute(
                select(Tariff)
                .where(Tariff.site_id == site_id)
                .options(selectinload(Tariff.windows))
                .order_by(Tariff.name)
            )
        )
        .scalars()
        .all()
    )


@router.post("/tariffs", response_model=TariffOut, status_code=201)
async def create_tariff(
    payload: TariffCreate, db: DbSession, site_id: ScopedSiteId, _: OperatorUser
):
    data = payload.model_dump(exclude={"windows"})
    tariff_rules.validar(data["type"], data)
    tariff = Tariff(site_id=site_id, **data)
    for window in payload.windows:
        tariff.windows.append(TariffWindow(**window.model_dump()))
    db.add(tariff)
    await db.flush()

    # A PRIMEIRA tarifa da praca vira a PADRAO dela.
    #
    # `default_tariff_id` so' era definido dentro do `seed()`. Enquanto apenas o
    # seed criava praca, isso bastava - mas desde que o painel ganhou "Nova
    # praca", toda praca nascida pelo produto ficava sem tarifa padrao e sem jeito
    # de ganhar uma: nao ha rota que a defina.
    #
    # As consequencias eram tres, e nenhuma dava erro:
    #   - `session_service` precifica por cartao > ponto > PADRAO DO SITE. Sem
    #     nenhum dos tres, a sessao fica sem tarifa e sem fatura.
    #   - o app do motorista so' mostra preco quando ha padrao.
    #   - `forecast/banco._TARIFAS` junta por `default_tariff_id`, entao a
    #     previsao daquela praca saia sem faturamento.
    #
    # A regra e' a que nao surpreende ninguem: a primeira tarifa de uma praca e'
    # obviamente a dela. Nao sobrepoe uma escolha existente - se ja' ha padrao,
    # trocar exige acao explicita, e nao um efeito colateral de cadastrar tarifa.
    site = (await db.execute(select(Site).where(Site.id == site_id))).scalar_one()
    if site.default_tariff_id is None:
        site.default_tariff_id = tariff.id

    await db.commit()
    await db.refresh(tariff, attribute_names=["windows"])
    return tariff


@router.patch("/tariffs/{tariff_id}", response_model=TariffOut)
async def update_tariff(
    tariff_id: uuid.UUID,
    payload: TariffUpdate,
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
):
    tariff = await _get_tariff(db, site_id, tariff_id)
    mudancas = payload.model_dump(exclude_unset=True)

    # Valida o estado resultante, nao so os campos enviados: um PATCH parcial
    # pode tornar a tarifa inconsistente com o proprio tipo.
    resultante = {
        campo: mudancas.get(campo, float(getattr(tariff, campo)))
        for campo in ("price_per_kwh", "price_per_min", "session_fee")
    }
    tariff_rules.validar(mudancas.get("type", tariff.type), resultante)

    for field, value in mudancas.items():
        setattr(tariff, field, value)
    await db.commit()
    await db.refresh(tariff, attribute_names=["windows"])
    return tariff


@router.put("/tariffs/{tariff_id}/windows", response_model=TariffOut)
async def replace_windows(
    tariff_id: uuid.UUID,
    windows: list[TariffWindowIn],
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
):
    """Substitui as janelas de uma vez - o editor do dashboard salva o conjunto inteiro."""
    tariff = await _get_tariff(db, site_id, tariff_id)
    tariff.windows.clear()
    await db.flush()
    for window in windows:
        tariff.windows.append(TariffWindow(**window.model_dump()))
    await db.commit()
    await db.refresh(tariff, attribute_names=["windows"])
    return tariff


@router.delete("/tariffs/{tariff_id}", status_code=204, response_model=None)
async def delete_tariff(
    tariff_id: uuid.UUID, db: DbSession, site_id: ScopedSiteId, _: OperatorUser
) -> None:
    """Remove uma tarifa que nunca foi usada.

    Tarifa com sessão faturada não é apagada: o histórico de cobrança perderia a
    referência, e a fatura guarda o snapshot justamente para ser reproduzível. O
    caminho nesse caso é desativar, e a mensagem diz isso.
    """
    tariff = await _get_tariff(db, site_id, tariff_id)

    usos = (
        await db.execute(
            select(func.count(ChargingSession.id)).where(ChargingSession.tariff_id == tariff_id)
        )
    ).scalar_one()
    if usos:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{tariff.name} já foi aplicada em {usos} sessão(ões) e não pode ser excluída. "
                "Desative-a para parar de usá-la nas próximas recargas."
            ),
        )

    vinculada = (
        await db.execute(
            select(func.count(ChargePoint.id)).where(ChargePoint.tariff_id == tariff_id)
        )
    ).scalar_one()
    site_padrao = (
        await db.execute(select(func.count(Site.id)).where(Site.default_tariff_id == tariff_id))
    ).scalar_one()
    if vinculada or site_padrao:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{tariff.name} ainda está vinculada a "
                f"{vinculada} ponto(s) e {site_padrao} site(s). Troque a tarifa deles primeiro."
            ),
        )

    await db.delete(tariff)
    await db.commit()


@router.post("/tariffs/simulate", response_model=RatingOut)
async def simulate_cost(
    payload: SimulationRequest, db: DbSession, site_id: ScopedSiteId, _: OperatorUser
) -> dict:
    """Simulador de custo da tela de tarifacao."""
    tariff = await _get_tariff(db, site_id, payload.tariff_id)
    return simulate(
        tariff,
        energy_kwh=payload.energy_kwh,
        minutes=payload.minutes,
        idle_minutes=payload.idle_minutes,
        at=payload.at,
    ).as_dict()


async def _get_tariff(db, site_id, tariff_id) -> Tariff:
    tariff = (
        await db.execute(
            select(Tariff)
            .where(Tariff.id == tariff_id, Tariff.site_id == site_id)
            .options(selectinload(Tariff.windows))
        )
    ).scalar_one_or_none()
    if tariff is None:
        raise HTTPException(status_code=404, detail="tarifa não encontrada")
    return tariff


# --------------------------------------------------------- metodos de pagamento
@router.get("/payment-methods", response_model=list[PaymentMethodOut])
async def list_payment_methods(db: DbSession, site_id: ScopedSiteId, _: OperatorUser):
    return (
        (
            await db.execute(
                select(SitePaymentMethod)
                .where(SitePaymentMethod.site_id == site_id)
                .order_by(SitePaymentMethod.label)
            )
        )
        .scalars()
        .all()
    )


@router.put("/payment-methods", response_model=PaymentMethodOut)
async def upsert_payment_method(
    payload: PaymentMethodIn,
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    aud: Auditor,
):
    """Habilita ou atualiza um metodo. Um por tipo por site.

    AUDITADO, e e' o caso que exigiu mascara: `provider_config` carrega
    `client_secret` e `webhook_secret`. Gravar o "antes e depois" cru escreveria
    a credencial do PSP numa tabela feita para ser lida por gente - trocaria um
    defeito por outro pior.
    """
    method = (
        await db.execute(
            select(SitePaymentMethod).where(
                SitePaymentMethod.site_id == site_id, SitePaymentMethod.kind == payload.kind
            )
        )
    ).scalar_one_or_none()
    antes = (
        {}
        if method is None
        else {
            "enabled": method.enabled,
            "provider": method.provider,
            "fee_percent": float(method.fee_percent),
            "provider_config": method.provider_config,
        }
    )
    if method is None:
        method = SitePaymentMethod(site_id=site_id, kind=payload.kind)
        db.add(method)
    for field, value in payload.model_dump(exclude={"kind"}).items():
        setattr(method, field, value)

    await aud.registrar(
        db,
        "metodo_de_pagamento.alterado",
        "site_payment_method",
        entidade_id=site_id,
        antes=antes,
        depois={
            "kind": str(payload.kind),
            "enabled": method.enabled,
            "provider": method.provider,
            "fee_percent": float(method.fee_percent),
            "provider_config": method.provider_config,
        },
    )
    await db.commit()
    await db.refresh(method)
    return method


# ---------------------------------------------------------------------- faturas
def _com_motorista(fatura: Invoice) -> InvoiceOut:
    """A fatura com o e-mail de quem a deve.

    Montado aqui e nao por `computed_field` no schema: o campo depende de um
    relacionamento CARREGADO, e um schema que acessa relacionamento por conta
    propria dispara consulta durante a serializacao - fora da sessao, na pior
    das hipoteses.
    """
    saida = InvoiceOut.model_validate(fatura)
    saida.user_email = fatura.user.email if fatura.user is not None else None
    return saida


@router.get("/invoices", response_model=Page[InvoiceOut])
async def list_invoices(
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    status: InvoiceStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[InvoiceOut]:
    filters = [Invoice.site_id == site_id]
    if status is not None:
        filters.append(Invoice.status == status)

    total = (await db.execute(select(func.count(Invoice.id)).where(*filters))).scalar_one()
    rows = (
        (
            await db.execute(
                select(Invoice)
                .where(*filters)
                .options(
                    selectinload(Invoice.lines),
                    selectinload(Invoice.payments),
                    # Carregado junto de proposito: `lazy="raise"` no
                    # relacionamento transforma o N+1 acidental em erro em vez
                    # de em lentidao silenciosa - uma consulta por fatura numa
                    # pagina de 200 nao aparece em teste, so' em producao.
                    selectinload(Invoice.user),
                )
                .order_by(Invoice.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return Page(
        items=[_com_motorista(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


async def _fatura_permitida(db, invoice_id: uuid.UUID, user: User) -> Invoice:
    """Fatura que este usuario pode ver ou cobrar.

    Motorista so alcanca a propria; operador e admin, so as do proprio
    estabelecimento. Antes, `get_invoice` exigia apenas um token valido - com
    isso qualquer motorista lia a fatura de qualquer outro pelo identificador,
    com valor, linhas e pagamentos. E a cobranca so barrava motorista, entao um
    operador cobrava fatura de outro site e, no metodo carteira, debitava o
    saldo de uma pessoa que nao era cliente dele.

    404 e nao 403 nos dois casos: um 403 confirmaria que a fatura existe.
    """
    invoice = await billing_service.get_invoice(db, invoice_id)

    if user.role == UserRole.DRIVER:
        if invoice.user_id != user.id:
            raise HTTPException(status_code=404, detail="fatura não encontrada")
        return invoice

    site_id = await get_scoped_site_id(db, user)
    if invoice.site_id != site_id:
        raise HTTPException(status_code=404, detail="fatura não encontrada neste site")
    return invoice


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
async def get_invoice(invoice_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return await _fatura_permitida(db, invoice_id, user)


@router.post("/invoices/{invoice_id}/charge", response_model=PaymentOut, status_code=201)
async def charge_invoice(
    invoice_id: uuid.UUID, payload: ChargeRequestIn, db: DbSession, user: CurrentUser
):
    """Dispara a cobranca. Motorista paga a propria; operador, as do seu site."""
    invoice = await _fatura_permitida(db, invoice_id, user)

    payer = user
    if invoice.user_id and invoice.user_id != user.id:
        payer = (
            await db.execute(select(User).where(User.id == invoice.user_id))
        ).scalar_one_or_none() or user

    return await payment_service.charge_invoice(
        db, invoice, payload.method, idempotency_key=payload.idempotency_key, payer=payer
    )


@router.post("/invoices/{invoice_id}/refund", response_model=PaymentOut)
async def refund_invoice(invoice_id: uuid.UUID, db: DbSession, admin: AdminUser, aud: Auditor):
    """Estorna a fatura: devolve o que foi cobrado.

    ADMIN, e nao operador nem motorista. Devolver dinheiro e' decisao da rede -
    o motorista nao pode se auto-reembolsar, e o operador nao pode devolver do
    caixa da plataforma. Mesmo criterio da baixa da cobranca da plataforma.

    Pagamento por CARTEIRA volta como credito no razao, na hora. Por PSP, quem
    devolve e' o provedor - marcar `REFUNDED` sem chama-lo seria dizer que
    devolveu sem devolver.
    """
    invoice = (
        await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    ).scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="fatura não encontrada")
    antes = str(invoice.status)
    pagamento = await payment_service.estornar(db, invoice, autor=admin)
    await aud.registrar(
        db,
        "fatura.estornada",
        "invoice",
        entidade_id=invoice.id,
        antes={"status": antes},
        depois={"status": str(invoice.status), "valor": float(pagamento.amount)},
    )
    await db.commit()
    return pagamento


@router.get("/audit")
async def audit_trail(
    db: DbSession,
    _: AdminUser,
    limit: int = Query(default=100, ge=1, le=500),
    action: str | None = None,
    entity: str | None = None,
) -> list[dict]:
    """A trilha de auditoria. So' admin.

    Existe porque trilha que ninguem consegue ler e' meio caminho do defeito que
    ela veio consertar: o dado estaria no banco e a pergunta continuaria
    dependendo de alguem com acesso a producao.

    Admin porque a propria trilha e' informacao sensivel - ela diz quem mexeu em
    que e de qual IP, e isso nao e' assunto de operador de praca.
    """
    return await audit_service.listar(db, limite=limit, acao=action, entidade=entity)


@router.post("/wallets/{user_id}/adjust")
async def adjust_wallet(
    user_id: uuid.UUID,
    payload: AjusteDeCarteiraIn,
    db: DbSession,
    admin: AdminUser,
    aud: Auditor,
) -> dict:
    """Correcao manual de saldo, com motivo e responsavel.

    ADMIN, e nao operador. E' o unico lancamento do razao em que alguem escolhe
    o numero, sem fatura nem recarga por tras - e quem pode criar saldo do nada
    precisa ser o menor grupo possivel.

    Devolve o extrato atualizado, e nao so' o saldo: quem acabou de mexer no
    dinheiro de alguem tem de ver a linha que criou.
    """
    dono = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if dono is None:
        raise HTTPException(status_code=404, detail="motorista não encontrado")
    antes = float(dono.wallet_balance)
    extrato = await wallet_service.ajustar(
        db,
        dono,
        payload.valor,
        payload.motivo,
        autor=admin,
        idempotency_key=payload.idempotency_key,
    )
    await aud.registrar(
        db,
        "carteira.ajustada",
        "user",
        entidade_id=dono.id,
        antes={"saldo": antes},
        depois={"saldo": extrato["saldo"], "valor": float(payload.valor), "motivo": payload.motivo},
    )
    await db.commit()
    return extrato


@router.post("/payments/webhook", include_in_schema=True)
async def payment_webhook(request: Request, db: DbSession) -> dict:
    """Liquidacao assincrona do PSP. Assinatura HMAC obrigatoria.

    Um POST pode trazer MAIS DE UM pagamento: o Pix notifica em lote, com uma
    lista de recebimentos no mesmo corpo. Quem sabe desmontar isso e' o
    provedor - a rota nao supoe a forma do corpo, e por isso a resposta e'
    sempre `{"eventos": [...]}`, com um elemento no caso comum.
    """
    body = await request.body()
    signature = request.headers.get("x-signature") or request.headers.get("x-hub-signature-256")

    # A referencia do corpo (ainda nao confiavel) serve so para escolher QUAL
    # segredo tentar - o do PSP daquele estabelecimento. A assinatura continua
    # sendo verificada contra o corpo cru, entao um corpo forjado nao passa.
    provedor = await payment_service.provedor_do_evento(db, body)
    if not provedor.verify_webhook(body, signature):
        raise HTTPException(status_code=401, detail="assinatura de webhook inválida")

    eventos = provedor.traduzir_webhook(await request.json())
    if not eventos:
        raise HTTPException(status_code=422, detail="webhook sem pagamento reconhecível")
    # Um a um, e cada um no proprio commit: o lote do PSP pode citar um
    # pagamento que nao e' nosso, e derrubar os outros por causa dele faria o
    # PSP reenviar o lote inteiro para sempre.
    return {"eventos": [await payment_service.handle_webhook(db, e) for e in eventos]}


@router.get("/revenue/summary", response_model=RevenueSummary)
async def revenue_summary(
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    days: int = Query(default=30, ge=1, le=365),
) -> RevenueSummary:
    """Receita bruta x liquida do periodo - o que o lojista realmente leva."""
    since = datetime.now(UTC) - timedelta(days=days)
    base = [Invoice.site_id == site_id, Invoice.created_at >= since]

    gross, fees, net = (
        await db.execute(
            select(
                func.coalesce(func.sum(Invoice.total), 0),
                func.coalesce(func.sum(Invoice.processing_fee), 0),
                func.coalesce(func.sum(Invoice.net_amount), 0),
            ).where(*base, Invoice.status == InvoiceStatus.PAID)
        )
    ).one()

    async def count(status: InvoiceStatus) -> int:
        return (
            await db.execute(select(func.count(Invoice.id)).where(*base, Invoice.status == status))
        ).scalar_one()

    paid = await count(InvoiceStatus.PAID)
    energy = (
        await db.execute(
            select(func.coalesce(func.sum(ChargingSession.energy_kwh), 0)).where(
                ChargingSession.site_id == site_id, ChargingSession.created_at >= since
            )
        )
    ).scalar_one()

    return RevenueSummary(
        gross=float(gross),
        net=float(net),
        processing_fees=float(fees),
        paid_invoices=paid,
        open_invoices=await count(InvoiceStatus.OPEN),
        failed_invoices=await count(InvoiceStatus.FAILED),
        energy_kwh=float(energy),
        average_ticket=round(float(gross) / paid, 2) if paid else 0.0,
    )
