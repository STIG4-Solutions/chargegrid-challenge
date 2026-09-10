"""Contrato do estabelecimento com a plataforma.

ESCOPO HONESTO. Este servico EMITE cobrancas; ele nao as liquida. Nao ha
integracao bancaria, boleto, retentativa de inadimplencia nem dunning, e nao
existe relogio de competencia: o `poller` roda em segundos e nunca foi desenhado
para granularidade mensal. `SitePaymentMethod` tambem nao serve - ele diz por
qual meio o site RECEBE, nao por qual ele PAGA.

Entao a cobranca nasce `aberta` e alguem a marca como paga a mao. Isso esta
declarado na tela e aqui, porque o contrario - uma cobranca que parece liquidada
sem liquidacao nenhuma - e' pior que a limitacao.

A RECEITA QUE IMPORTA nao e' a mensalidade. E' `fee_percent_transacao` sobre o
faturamento do site, que ja e' calculavel a partir de `invoices.total` agrupado
por `site_id` - a mesma consulta que `portfolio_service` faz. A mensalidade e' a
parte chata; o take rate e' o que cresce com o cliente.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound
from app.core.logging import get_logger
from app.models.billing import Invoice
from app.models.charge_point import ChargePoint
from app.models.enums import InvoiceStatus
from app.models.platform import PlatformInvoice, PlatformPlan, SiteSubscription
from app.services.tariff_engine import money

log = get_logger(__name__)

# Prazo de pagamento da cobranca emitida.
DIAS_PARA_VENCER = 10


def primeiro_do_mes(dia: date) -> date:
    return dia.replace(day=1)


def mes_seguinte(dia: date) -> date:
    """Primeiro dia do mes seguinte. Serve para COMPETENCIA, nao para prazo."""
    return (primeiro_do_mes(dia) + timedelta(days=32)).replace(day=1)


def somar_meses(dia: date, meses: int) -> date:
    """Mesma data, N meses adiante - preservando o DIA.

    `mes_seguinte` nao serve aqui: ela devolve sempre o dia 1, entao somar doze
    vezes daria o primeiro dia de um mes em vez da mesma data um ano depois. O
    contrato assinado dia 20 tem prazo minimo ate o dia 20, e nao ate o dia 1 -
    e a diferenca custava um mes inteiro de multa a menos.

    Dia 31 em mes que nao tem 31 cai no ultimo dia do mes, que e' a convencao de
    qualquer contrato.
    """
    total = dia.month - 1 + meses
    ano = dia.year + total // 12
    mes = total % 12 + 1
    # Ultimo dia do mes de destino, sem depender do calendario.
    ultimo = (date(ano, mes, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return date(ano, mes, min(dia.day, ultimo.day))


def meses_restantes(hoje: date, minimo_ate: date) -> int:
    """Meses inteiros que faltam para o fim do prazo minimo.

    NUNCA NEGATIVO, e quem garante isso e' a saida antecipada logo abaixo -
    nao um `max(0, ...)` no fim. Havia um, e o teste de mutacao mostrou que
    remove-lo nao quebrava nada: com a saida antecipada no lugar, `meses` nunca
    chega a ser negativo, e o piso era codigo morto dando impressao de guarda.

    O que aconteceria sem a saida antecipada: contrato com prazo vencido daria
    meses negativos, a multa viraria CREDITO, e a rede pagaria o estabelecimento
    para sair. E' isso que a primeira linha impede.
    """
    if minimo_ate <= hoje:
        return 0
    meses = (minimo_ate.year - hoje.year) * 12 + (minimo_ate.month - hoje.month)
    if minimo_ate.day < hoje.day:
        meses -= 1
    # Sem piso: `minimo_ate > hoje` garante `meses >= 0` mesmo apos o ajuste do
    # dia, porque o ajuste so' pode tirar um mes de uma diferenca de pelo menos um.
    return meses


def multa_por_rescisao(mensal: Decimal, restantes: int, percentual: Decimal) -> Decimal:
    """O que se cobra de quem sai antes do prazo.

    Percentual sobre as mensalidades que faltavam. Cobrar 100% seria cobrar o
    contrato inteiro sem prestar o servico; cobrar zero tornaria o prazo minimo
    uma frase sem efeito.
    """
    if restantes <= 0 or percentual <= 0:
        return Decimal("0.00")
    return money(Decimal(str(mensal)) * restantes * Decimal(str(percentual)) / Decimal("100"))


# ------------------------------------------------------------------ contrato


async def vigente_do_site(db: AsyncSession, site_id: uuid.UUID) -> SiteSubscription | None:
    return (
        await db.execute(
            select(SiteSubscription).where(
                SiteSubscription.site_id == site_id,
                SiteSubscription.estado != "encerrada",
            )
        )
    ).scalar_one_or_none()


async def planos_ativos(db: AsyncSession) -> list[PlatformPlan]:
    return list(
        (
            await db.execute(
                select(PlatformPlan)
                .where(PlatformPlan.ativo.is_(True))
                .order_by(PlatformPlan.preco_mensal_brl)
            )
        )
        .scalars()
        .all()
    )


async def contratar(
    db: AsyncSession, site_id: uuid.UUID, codigo: str, multa_percentual: Decimal | None = None
) -> SiteSubscription:
    plano = (
        await db.execute(
            select(PlatformPlan).where(
                PlatformPlan.codigo == codigo, PlatformPlan.ativo.is_(True)
            )
        )
    ).scalar_one_or_none()
    if plano is None:
        raise NotFound("plano não encontrado")

    if await vigente_do_site(db, site_id) is not None:
        raise Conflict("este estabelecimento já tem um contrato vigente")

    hoje = date.today()
    minimo = somar_meses(hoje, plano.meses_minimos)

    contrato = SiteSubscription(
        id=uuid.uuid4(),
        site_id=site_id,
        plan_id=plano.id,
        estado="ativa",
        starts_on=hoje,
        minimo_ate=minimo,
        renova_em=mes_seguinte(hoje),
        renovacao_automatica=True,
        multa_percentual=multa_percentual if multa_percentual is not None else Decimal("30"),
    )
    db.add(contrato)
    try:
        await db.commit()
    except IntegrityError as erro:
        # O indice unico parcial e' a garantia real contra dois contratos vivos.
        await db.rollback()
        raise Conflict("este estabelecimento já tem um contrato vigente") from erro

    log.info("contrato.criado", site=str(site_id), plano=plano.codigo)
    return contrato


async def rescindir(db: AsyncSession, site_id: uuid.UUID) -> dict:
    """Pede a rescisao. O contrato corre ate o fim do ciclo pago.

    Nao encerra no ato: o mes corrente ja foi cobrado, e cortar o acesso
    entregaria menos do que se cobrou. Dentro do prazo minimo, emite a multa
    junto - e' a unica coisa que da efeito pratico ao prazo.
    """
    contrato = await vigente_do_site(db, site_id)
    if contrato is None:
        raise NotFound("nenhum contrato vigente")
    if contrato.estado == "em_aviso_previo":
        raise Conflict("a rescisão já foi solicitada")

    hoje = date.today()
    restantes = meses_restantes(hoje, contrato.minimo_ate)
    multa = multa_por_rescisao(
        contrato.plan.preco_mensal_brl, restantes, contrato.multa_percentual
    )

    contrato.estado = "em_aviso_previo"
    contrato.encerra_em = contrato.renova_em
    contrato.renovacao_automatica = False

    cobranca = None
    if multa > 0:
        cobranca = await _emitir(
            db, contrato, primeiro_do_mes(hoje), multa=multa, apenas_multa=True
        )

    await db.commit()
    log.info(
        "contrato.rescindido",
        site=str(site_id),
        meses_restantes=restantes,
        multa=float(multa),
    )
    return {
        "encerra_em": contrato.encerra_em.isoformat(),
        "meses_restantes": restantes,
        "multa_brl": float(multa),
        "cobranca_da_multa": str(cobranca.id) if cobranca else None,
    }


async def renovar_vencidos(db: AsyncSession) -> int:
    """Avanca o ciclo de quem chegou em `renova_em`.

    `minimo_ate` NAO avanca. Renovar prendendo por mais um prazo minimo quem
    apenas deixou o contrato correr e' abusivo - e o prazo minimo existe para
    cobrir o custo de aquisicao, que so' acontece uma vez.
    """
    hoje = date.today()
    vencidos = (
        (
            await db.execute(
                select(SiteSubscription).where(
                    SiteSubscription.estado == "ativa",
                    SiteSubscription.renova_em <= hoje,
                    SiteSubscription.renovacao_automatica.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    for contrato in vencidos:
        contrato.renova_em = mes_seguinte(contrato.renova_em)
    if vencidos:
        await db.commit()
    return len(vencidos)


# ------------------------------------------------------------------ cobranca


async def _base_de_calculo(
    db: AsyncSession, site_id: uuid.UUID, competencia: date
) -> tuple[int, Decimal]:
    """Pontos ativos e faturamento do site na competencia.

    O faturamento exclui `VOID` pelo mesmo motivo de `fleet_service`: fatura
    anulada nao e' receita, e cobrar taxa sobre ela cobraria por dinheiro que
    nunca existiu.
    """
    fim = mes_seguinte(competencia)
    pontos = (
        await db.execute(
            select(func.count())
            .select_from(ChargePoint)
            .where(ChargePoint.site_id == site_id)
        )
    ).scalar_one()

    faturado = (
        await db.execute(
            select(func.coalesce(func.sum(Invoice.total), 0)).where(
                Invoice.site_id == site_id,
                Invoice.issued_on >= competencia,
                Invoice.issued_on < fim,
                Invoice.status != InvoiceStatus.VOID,
            )
        )
    ).scalar_one()
    return int(pontos), Decimal(str(faturado))


async def _emitir(
    db: AsyncSession,
    contrato: SiteSubscription,
    competencia: date,
    *,
    multa: Decimal = Decimal("0"),
    apenas_multa: bool = False,
) -> PlatformInvoice | None:
    """Monta a cobranca de uma competencia. `None` se ela ja existe."""
    ja_existe = (
        await db.execute(
            select(PlatformInvoice.id).where(
                PlatformInvoice.site_subscription_id == contrato.id,
                PlatformInvoice.competencia == competencia,
            )
        )
    ).scalar_one_or_none()
    if ja_existe is not None:
        return None

    plano = contrato.plan
    if apenas_multa:
        pontos, faturado = 0, Decimal("0")
        assinatura = pontos_brl = transacao = Decimal("0.00")
    else:
        pontos, faturado = await _base_de_calculo(db, contrato.site_id, competencia)
        assinatura = money(Decimal(str(plano.preco_mensal_brl)))
        excedentes = max(0, pontos - plano.pontos_inclusos)
        pontos_brl = money(Decimal(str(plano.preco_por_ponto_brl)) * excedentes)
        transacao = money(
            faturado * Decimal(str(plano.fee_percent_transacao)) / Decimal("100")
        )

    hoje = date.today()
    cobranca = PlatformInvoice(
        id=uuid.uuid4(),
        site_subscription_id=contrato.id,
        competencia=competencia,
        emitida_em=hoje,
        vence_em=hoje + timedelta(days=DIAS_PARA_VENCER),
        assinatura_brl=assinatura,
        pontos_brl=pontos_brl,
        transacao_brl=transacao,
        multa_brl=money(multa),
        total_brl=money(assinatura + pontos_brl + transacao + multa),
        pontos_cobrados=pontos,
        faturamento_base_brl=money(faturado),
        estado="aberta",
    )
    db.add(cobranca)
    await db.flush()
    return cobranca


async def emitir_competencia(db: AsyncSession, competencia: date | None = None) -> int:
    """Emite a cobranca do mes para todos os contratos vivos.

    Idempotente pela UNIQUE (contrato, competencia): rodar duas vezes no mesmo
    mes nao emite duas cobrancas. E' o defeito classico de cobranca recorrente.
    """
    competencia = primeiro_do_mes(competencia or date.today())
    contratos = (
        (
            await db.execute(
                select(SiteSubscription).where(
                    SiteSubscription.estado.in_(("ativa", "em_aviso_previo"))
                )
            )
        )
        .scalars()
        .all()
    )

    emitidas = 0
    for contrato in contratos:
        # Contrato em aviso previo ainda e' cobrado ate a data de encerramento:
        # o servico continua sendo prestado ate la'.
        if contrato.encerra_em is not None and competencia >= contrato.encerra_em:
            continue
        if await _emitir(db, contrato, competencia) is not None:
            emitidas += 1

    if emitidas:
        await db.commit()
    return emitidas


async def marcar_como_paga(db: AsyncSession, cobranca_id: uuid.UUID) -> PlatformInvoice:
    """Baixa manual.

    Existe porque a liquidacao B2B nao existe - ver o docstring do modulo. Nao e'
    um atalho: e' o reconhecimento de que nao ha integracao bancaria, e um botao
    honesto e' melhor que um fluxo que finge liquidar.
    """
    cobranca = (
        await db.execute(select(PlatformInvoice).where(PlatformInvoice.id == cobranca_id))
    ).scalar_one_or_none()
    if cobranca is None:
        raise NotFound("cobrança não encontrada")
    if cobranca.estado == "paga":
        return cobranca

    cobranca.estado = "paga"
    cobranca.paga_em = date.today()
    await db.commit()
    return cobranca


# ------------------------------------------------------------------- leitura


async def contrato_do_site(db: AsyncSession, site_id: uuid.UUID) -> dict:
    contrato = await vigente_do_site(db, site_id)
    if contrato is None:
        return {"contratado": False}

    hoje = date.today()
    restantes = meses_restantes(hoje, contrato.minimo_ate)
    plano = contrato.plan

    cobrancas = (
        (
            await db.execute(
                select(PlatformInvoice)
                .where(PlatformInvoice.site_subscription_id == contrato.id)
                .order_by(PlatformInvoice.competencia.desc())
                .limit(12)
            )
        )
        .scalars()
        .all()
    )

    return {
        "contratado": True,
        "estado": contrato.estado,
        "plano": {
            "codigo": plano.codigo,
            "nome": plano.nome,
            "preco_mensal_brl": float(plano.preco_mensal_brl),
            "preco_por_ponto_brl": float(plano.preco_por_ponto_brl),
            "pontos_inclusos": plano.pontos_inclusos,
            "fee_percent_transacao": float(plano.fee_percent_transacao),
            "meses_minimos": plano.meses_minimos,
        },
        "starts_on": contrato.starts_on.isoformat(),
        "minimo_ate": contrato.minimo_ate.isoformat(),
        "renova_em": contrato.renova_em.isoformat(),
        "encerra_em": contrato.encerra_em.isoformat() if contrato.encerra_em else None,
        "dentro_do_prazo_minimo": restantes > 0,
        "meses_restantes": restantes,
        "multa_percentual": float(contrato.multa_percentual),
        "multa_se_rescindir_hoje": float(
            multa_por_rescisao(plano.preco_mensal_brl, restantes, contrato.multa_percentual)
        ),
        # Declarado na resposta, e nao so' na tela: quem consumir esta API por
        # outro caminho precisa saber que "aberta" nunca vira "paga" sozinha.
        "liquidacao_automatica": False,
        "cobrancas": [
            {
                "id": str(c.id),
                "competencia": c.competencia.isoformat(),
                "vence_em": c.vence_em.isoformat(),
                "assinatura_brl": float(c.assinatura_brl),
                "pontos_brl": float(c.pontos_brl),
                "transacao_brl": float(c.transacao_brl),
                "multa_brl": float(c.multa_brl),
                "total_brl": float(c.total_brl),
                "pontos_cobrados": c.pontos_cobrados,
                "faturamento_base_brl": float(c.faturamento_base_brl),
                "estado": c.estado,
            }
            for c in cobrancas
        ],
    }
