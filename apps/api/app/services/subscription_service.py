"""Assinatura de plano de recarga pelo motorista.

O plano entrega tres coisas, e todas passam pelo `Beneficio` que o motor de
tarifacao ja recebe desde a Fase 1: percentual de desconto, kWh inclusos por mes
e isencao da taxa de conexao. `rate_session` continua puro e nao sabe que
assinatura existe - quem consulta o banco e monta o objeto e' este servico.

FRANQUIA E' ABSOLUTA, NAO INCREMENTAL. Quanto da franquia ja foi usado sai de uma
consulta sobre as sessoes do periodo, e nao de um contador que se soma. Mesmo
motivo de `mission_progress`: reprocessar uma sessao nao pode consumir a franquia
duas vezes, e um contador que so' cresce nao sobrevive a nenhum estorno.

A sessao que esta sendo faturada NAO entra nessa conta, e isso nao e' sorte de
ordenacao: `billing_service` resolve o beneficio ANTES de transicionar a sessao
para BILLED, e a consulta filtra por BILLED. Se alguem inverter a ordem, a
franquia passa a se descontar a si mesma.

MENSALIDADE. Vira uma `Invoice` sem `site_id` e sem `session_id`, cobrada pela
carteira. Sem site porque a assinatura e' da rede: atribui-la a uma praca
inflaria o faturamento de um estabelecimento com dinheiro que ele nao recebeu.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound, PaymentError
from app.core.logging import get_logger
from app.models.billing import Invoice, InvoiceLine, Payment
from app.models.enums import InvoiceStatus, PaymentMethodKind, SessionState
from app.models.session import ChargingSession
from app.models.subscription import DriverPlan, DriverSubscription
from app.models.user import User
from app.services import payment_service
from app.services.tariff_engine import Beneficio, money

log = get_logger(__name__)

# Quantas mensalidades o worker cobra por ciclo.
LOTE = 50


def _fim_do_periodo(inicio: date) -> date:
    """Um mes cheio a partir do inicio.

    `timedelta(days=30)` daria periodos que desalinham do calendario e a segunda
    cobranca cairia no dia 31, a terceira no 30 e assim por diante. Somar um mes
    mantem o mesmo dia, que e' o que o motorista espera ver na fatura.
    """
    if inicio.month == 12:
        return inicio.replace(year=inicio.year + 1, month=1)
    try:
        return inicio.replace(month=inicio.month + 1)
    except ValueError:
        # Dia 31 em mes que nao tem 31: cai no ultimo dia do mes seguinte.
        seguinte = inicio.replace(day=1, month=inicio.month + 1)
        proximo = (seguinte + timedelta(days=32)).replace(day=1)
        return proximo - timedelta(days=1)


async def ativa_de(db: AsyncSession, user: User) -> DriverSubscription | None:
    """A assinatura ATIVA. E' a que o indice unico parcial protege.

    Serve para barrar segunda assinatura e para o cancelamento. NAO serve para
    decidir desconto - para isso ha `vigente_de`, e a diferenca entre as duas
    esta documentada la'.
    """
    return (
        await db.execute(
            select(DriverSubscription).where(
                DriverSubscription.user_id == user.id,
                DriverSubscription.estado == "ativa",
            )
        )
    ).scalar_one_or_none()


async def vigente_de(db: AsyncSession, user: User) -> DriverSubscription | None:
    """A assinatura que ainda VALE, que nao e' a mesma coisa que estar ativa.

    Cancelar interrompe a renovacao, nao o mes ja pago. Cortar o beneficio no
    instante do cancelamento seria cobrar um mes inteiro e entregar cinco dias -
    e o motorista que cancelasse no dia 2 pagaria pelos 28 restantes sem receber
    nada. Toda assinatura de mercado funciona assim, e o motivo e' esse.

    Por isso ha duas funcoes. `ativa_de` responde "pode assinar de novo?"; esta
    responde "esta recarga tem desconto?". Usar uma no lugar da outra produz ou
    cobranca dupla, ou beneficio retirado de quem pagou por ele.
    """
    hoje = datetime.now(UTC).date()
    return (
        await db.execute(
            select(DriverSubscription)
            .where(
                DriverSubscription.user_id == user.id,
                DriverSubscription.current_period_end > hoje,
                DriverSubscription.estado.in_(("ativa", "cancelada")),
            )
            .order_by(DriverSubscription.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _franquia_usada(db: AsyncSession, assinatura: DriverSubscription) -> Decimal:
    """kWh ja consumidos no periodo corrente.

    Conta a energia TOTAL das sessoes ja faturadas, e nao so' a parcela
    subsidiada: a franquia se gasta na ordem em que as recargas acontecem.
    """
    total = (
        await db.execute(
            select(func.coalesce(func.sum(ChargingSession.energy_kwh), 0)).where(
                ChargingSession.user_id == assinatura.user_id,
                ChargingSession.state == SessionState.BILLED,
                func.date(ChargingSession.started_at) >= assinatura.current_period_start,
                func.date(ChargingSession.started_at) < assinatura.current_period_end,
            )
        )
    ).scalar_one()
    return Decimal(str(total))


async def beneficio_do_plano(db: AsyncSession, user: User) -> Beneficio | None:
    """O que a assinatura deste motorista vale nesta recarga.

    Le a assinatura VIGENTE - inclui a cancelada cujo mes pago ainda nao
    terminou. Devolve `None` para quem nao assina, e o motor, recebendo `None`,
    produz exatamente o resultado de sempre.
    """
    assinatura = await vigente_de(db, user)
    if assinatura is None:
        return None

    plano = assinatura.plan
    inclusos = Decimal(str(plano.kwh_inclusos))
    if inclusos > 0:
        usada = await _franquia_usada(db, assinatura)
        inclusos = max(Decimal("0"), inclusos - usada)

    return Beneficio(
        rotulo=plano.nome,
        desconto_pct=Decimal(str(plano.desconto_pct)),
        kwh_inclusos=inclusos,
        isenta_session_fee=bool(plano.isenta_taxa_de_conexao),
    )


# ----------------------------------------------------------------- assinar


async def planos_ativos(db: AsyncSession) -> list[DriverPlan]:
    return list(
        (
            await db.execute(
                select(DriverPlan)
                .where(DriverPlan.ativo.is_(True))
                .order_by(DriverPlan.preco_mensal_brl)
            )
        )
        .scalars()
        .all()
    )


async def assinar(db: AsyncSession, user: User, codigo: str) -> DriverSubscription:
    """Cria a assinatura e cobra a primeira mensalidade.

    Cobra ANTES de deixar a assinatura valendo? Nao: a assinatura e' criada, a
    cobranca acontece, e uma falha de saldo desfaz tudo. Criar primeiro e' o que
    permite usar o `id` dela como chave de idempotencia do pagamento.
    """
    plano = (
        await db.execute(
            select(DriverPlan).where(DriverPlan.codigo == codigo, DriverPlan.ativo.is_(True))
        )
    ).scalar_one_or_none()
    if plano is None:
        raise NotFound("plano não encontrado")

    if await ativa_de(db, user) is not None:
        raise Conflict("já existe uma assinatura ativa para este motorista")

    hoje = datetime.now(UTC).date()
    assinatura = DriverSubscription(
        id=uuid.uuid4(),
        user_id=user.id,
        plan_id=plano.id,
        estado="ativa",
        started_at=datetime.now(UTC),
        current_period_start=hoje,
        current_period_end=_fim_do_periodo(hoje),
    )
    db.add(assinatura)
    try:
        await db.flush()
    except IntegrityError as erro:
        # O indice unico parcial e' a garantia real: dois toques simultaneos
        # atravessam o SELECT acima juntos, e so' o banco desempata.
        await db.rollback()
        raise Conflict("já existe uma assinatura ativa para este motorista") from erro

    try:
        await _cobrar(db, assinatura, plano, assinatura.current_period_start, user)
    except PaymentError:
        # Sem pagamento nao ha assinatura. Deixa-la ativa daria desconto de
        # graca a quem nao pagou.
        await db.delete(assinatura)
        await db.commit()
        raise

    log.info("assinatura.criada", motorista=str(user.id), plano=plano.codigo)
    return assinatura


async def cancelar(db: AsyncSession, user: User) -> DriverSubscription:
    """Cancela, sem estorno e sem apagar.

    O periodo ja pago continua valendo ate o fim - `current_period_end` nao
    muda. Cortar o beneficio no ato seria cobrar por um mes e entregar parte
    dele.
    """
    assinatura = await ativa_de(db, user)
    if assinatura is None:
        raise NotFound("nenhuma assinatura ativa")

    assinatura.estado = "cancelada"
    assinatura.canceled_at = datetime.now(UTC)
    await db.commit()
    log.info("assinatura.cancelada", motorista=str(user.id))
    return assinatura


# ------------------------------------------------------------- mensalidade


async def _cobrar(
    db: AsyncSession,
    assinatura: DriverSubscription,
    plano: DriverPlan,
    competencia: date,
    pagador: User,
) -> Invoice | None:
    """Emite e cobra a mensalidade de UM periodo.

    A chave de idempotencia e' deterministica - `sub:<id>:<competencia>` - e o
    UNIQUE que ja existe em `payments.idempotency_key` e' quem impede a segunda
    cobranca do mesmo mes. E' o defeito classico de cobranca recorrente, e o
    unico que realmente machuca.
    """
    chave = f"sub:{assinatura.id}:{competencia.isoformat()}"

    ja_cobrado = (
        await db.execute(select(Payment.id).where(Payment.idempotency_key == chave))
    ).scalar_one_or_none()
    if ja_cobrado is not None:
        return None

    preco = money(Decimal(str(plano.preco_mensal_brl)))
    fatura = Invoice(
        id=uuid.uuid4(),
        code=await _codigo_de_fatura(db),
        # Sem site e sem sessao: a assinatura e' da rede, e nao nasce de uma
        # recarga. As consultas de receita por praca filtram `= :site_id` e ja
        # excluem esta linha.
        site_id=None,
        session_id=None,
        user_id=pagador.id,
        status=InvoiceStatus.OPEN,
        subtotal=preco,
        discount=Decimal("0"),
        total=preco,
        net_amount=preco,
        issued_on=competencia,
        tariff_snapshot={"plano": plano.codigo, "nome": plano.nome},
    )
    db.add(fatura)
    await db.flush()

    db.add(
        InvoiceLine(
            invoice_id=fatura.id,
            position=0,
            kind="assinatura",
            description=f"{plano.nome} — mensalidade",
            quantity=1,
            unit="mês",
            unit_price=preco,
            amount=preco,
        )
    )
    await db.flush()

    await payment_service.charge_invoice(
        db, fatura, PaymentMethodKind.WALLET, idempotency_key=chave, payer=pagador
    )
    return fatura


async def _codigo_de_fatura(db: AsyncSession) -> str:
    from app.services.billing_service import _next_code

    return await _next_code(db)


async def cobrar_mensalidades(db: AsyncSession, limite: int = LOTE) -> int:
    """Cobra quem chegou ao fim do periodo. Chamada pelo worker.

    Assinatura sem saldo vira `inadimplente` em vez de sumir: o motorista pode
    recarregar a carteira e voltar, e apagar o registro perderia desde quando
    ele assina.
    """
    hoje = datetime.now(UTC).date()
    vencidas = (
        (
            await db.execute(
                select(DriverSubscription)
                .where(
                    DriverSubscription.estado == "ativa",
                    DriverSubscription.current_period_end <= hoje,
                )
                .limit(limite)
            )
        )
        .scalars()
        .all()
    )

    cobradas = 0
    for assinatura in vencidas:
        pagador = (
            await db.execute(select(User).where(User.id == assinatura.user_id))
        ).scalar_one_or_none()
        if pagador is None:
            continue

        competencia = assinatura.current_period_end
        try:
            await _cobrar(db, assinatura, assinatura.plan, competencia, pagador)
        except PaymentError as erro:
            assinatura.estado = "inadimplente"
            await db.commit()
            log.info("assinatura.inadimplente", motorista=str(pagador.id), motivo=str(erro))
            continue

        assinatura.current_period_start = competencia
        assinatura.current_period_end = _fim_do_periodo(competencia)
        assinatura.kwh_consumidos_no_periodo = Decimal("0")
        await db.commit()
        cobradas += 1

    return cobradas


# ---------------------------------------------------------------- leitura


async def minha_assinatura(db: AsyncSession, user: User) -> dict:
    """O que o app mostra: plano, franquia restante e proxima cobranca."""
    assinatura = (
        await db.execute(
            select(DriverSubscription)
            .where(DriverSubscription.user_id == user.id)
            .order_by(DriverSubscription.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if assinatura is None:
        return {"assinante": False}

    plano = assinatura.plan
    hoje = datetime.now(UTC).date()
    # "Vale ainda" e' diferente de "esta ativa": cancelada dentro do mes pago
    # continua dando desconto, e a tela precisa dizer isso em vez de sugerir
    # que o beneficio ja acabou.
    vale_ainda = assinatura.estado in ("ativa", "cancelada") and (
        assinatura.current_period_end > hoje
    )
    inclusos = Decimal(str(plano.kwh_inclusos))
    restante = None
    if inclusos > 0 and vale_ainda:
        restante = float(max(Decimal("0"), inclusos - await _franquia_usada(db, assinatura)))

    return {
        "assinante": vale_ainda,
        "renova": assinatura.estado == "ativa",
        "estado": assinatura.estado,
        "plano": {
            "codigo": plano.codigo,
            "nome": plano.nome,
            "preco_mensal_brl": float(plano.preco_mensal_brl),
            "desconto_pct": float(plano.desconto_pct),
            "kwh_inclusos": float(plano.kwh_inclusos),
            "isenta_taxa_de_conexao": plano.isenta_taxa_de_conexao,
        },
        "kwh_restantes": restante,
        "periodo_ate": assinatura.current_period_end.isoformat(),
        "cancelada_em": assinatura.canceled_at.isoformat() if assinatura.canceled_at else None,
    }
