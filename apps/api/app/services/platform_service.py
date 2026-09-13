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
            select(PlatformPlan).where(PlatformPlan.codigo == codigo, PlatformPlan.ativo.is_(True))
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
    multa = multa_por_rescisao(contrato.plan.preco_mensal_brl, restantes, contrato.multa_percentual)

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
            select(func.count()).select_from(ChargePoint).where(ChargePoint.site_id == site_id)
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
        transacao = money(faturado * Decimal(str(plano.fee_percent_transacao)) / Decimal("100"))

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


async def encerrar_vencidos(db: AsyncSession) -> int:
    """Fecha o contrato que chegou ao fim do aviso previo.

    `rescindir` punha o contrato em `em_aviso_previo` e gravava `encerra_em` - e
    nada nunca o levava a `encerrada`. O estado existia no CHECK e no badge do
    painel desde a 0019, inalcancavel: so' aparecia em teste que montava a linha
    a mao.

    O efeito nao era cosmetico. `vigente_do_site` filtra `estado <> 'encerrada'`,
    e `contratar` recusa quem ja tem contrato vigente - entao o estabelecimento
    que rescindia ficava SEM SAIDA: nao era mais faturado (`emitir_competencia`
    respeita `encerra_em`), continuava marcado como "Em aviso previo" para
    sempre, e nunca mais conseguia assinar outro plano.

    DIVIDA NAO SEGURA O ENCERRAMENTO. O periodo de servico acabou na data
    combinada, e prender o contrato aberto para cobrar seria usar o cadastro
    como instrumento de cobranca. As cobrancas continuam existindo - a FK e'
    RESTRICT justamente para o historico nao sumir com o contrato - e
    `contrato_do_site` continua mostrando o que ficou em aberto.

    O que NAO existe, e vale dizer em vez de deixar implicito: nenhuma regra
    impede um devedor de assinar de novo. Isso e' politica comercial, e
    inventa-la aqui seria decidir sozinho uma coisa que nao e' tecnica.
    """
    hoje = date.today()
    vencidos = (
        (
            await db.execute(
                select(SiteSubscription).where(
                    SiteSubscription.estado == "em_aviso_previo",
                    SiteSubscription.encerra_em.isnot(None),
                    SiteSubscription.encerra_em <= hoje,
                )
            )
        )
        .scalars()
        .all()
    )
    for contrato in vencidos:
        contrato.estado = "encerrada"
        log.info(
            "contrato.encerrado", site=str(contrato.site_id), em=contrato.encerra_em.isoformat()
        )
    if vencidos:
        await db.commit()
    return len(vencidos)


async def ultimo_do_site(db: AsyncSession, site_id: uuid.UUID) -> SiteSubscription | None:
    """O contrato vigente ou, na falta dele, o ultimo que existiu.

    Serve a tela, e nao as regras. `vigente_do_site` continua sendo quem decide
    se cabe contratar - misturar os dois faria um contrato encerrado bloquear o
    proximo, que e' exatamente o defeito que `encerrar_vencidos` desfaz.

    Existe porque encerrar nao pode virar um jeito de sumir com divida: sem
    isto, o contrato encerrado com cobranca em aberto devolveria
    `{"contratado": false}` e o que ficou devendo sairia da tela junto.
    """
    vigente = await vigente_do_site(db, site_id)
    if vigente is not None:
        return vigente
    return (
        (
            await db.execute(
                select(SiteSubscription)
                .where(SiteSubscription.site_id == site_id)
                .order_by(SiteSubscription.starts_on.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )


async def marcar_vencidas(db: AsyncSession) -> dict:
    """Faz o prazo ter efeito: cobranca vence, contrato fica inadimplente.

    Ate aqui `vence_em` era escrita e nunca lida, e `inadimplente` existia no
    CHECK e no badge do painel sem que nada jamais o atribuisse. Uma divida de
    tres meses era indistinguivel de uma cobranca emitida ontem.

    UM LIMIAR SO'. A cobranca vence no dia seguinte a `vence_em`, e o contrato
    fica inadimplente por ter QUALQUER cobranca vencida - nao ha segunda
    carencia. Os dez dias de `DIAS_PARA_VENCER` ja sao a carencia; empilhar
    outra em cima daria ao lojista trinta dias para descobrir que devia dez.

    `em_aviso_previo` NAO vira `inadimplente`, e nao e' descuido: quem ja pediu
    rescisao esta de saida, o desfecho nao muda, e sobrescrever o estado
    apagaria a informacao que importa - a data em que o contrato acaba. A divida
    continua registrada na propria cobranca.

    O QUE NAO ACONTECE: ninguem fica sem recarregar. Quem deixou de pagar foi o
    estabelecimento; cortar o servico puniria o motorista, que nao tem nada com
    isso. A consequencia e' parar de renovar - `renovar_vencidos` so' olha
    contratos `ativa` - e aparecer em vermelho para quem pode resolver.
    """
    hoje = date.today()

    vencidas = (
        (
            await db.execute(
                select(PlatformInvoice).where(
                    PlatformInvoice.estado == "aberta",
                    PlatformInvoice.vence_em < hoje,
                )
            )
        )
        .scalars()
        .all()
    )
    for cobranca in vencidas:
        cobranca.estado = "vencida"

    # NAO ha flush explicito aqui, e a ausencia e' deliberada: `SessionLocal` usa
    # o autoflush padrao do SQLAlchemy, entao o SELECT abaixo ja descarrega as
    # mudancas pendentes antes de consultar. Um flush a mais seria decorativo -
    # foi o que o teste de mutacao mostrou ao remove-lo sem quebrar nada.
    #
    # O que NAO seria decorativo: desligar `autoflush` em `SessionLocal`. Ai as
    # cobrancas recem-vencidas ficariam so' na sessao, a consulta abaixo nao as
    # enxergaria, e o contrato so' cairia em inadimplencia no ciclo seguinte -
    # com a tela mostrando cobranca vencida num contrato "ativa" nesse meio
    # tempo. `test_inadimplencia_acontece_na_mesma_passada` e' quem acusa.
    inadimplentes = (
        (
            await db.execute(
                select(SiteSubscription)
                .where(
                    SiteSubscription.estado == "ativa",
                    SiteSubscription.id.in_(
                        select(PlatformInvoice.site_subscription_id).where(
                            PlatformInvoice.estado == "vencida"
                        )
                    ),
                )
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )
    for contrato in inadimplentes:
        contrato.estado = "inadimplente"
        log.info("contrato.inadimplente", site=str(contrato.site_id))

    if vencidas or inadimplentes:
        await db.commit()
    return {"cobrancas_vencidas": len(vencidas), "contratos_inadimplentes": len(inadimplentes)}


async def _reavaliar_inadimplencia(db: AsyncSession, contrato_id: uuid.UUID) -> None:
    """Contrato sem cobranca vencida volta a ser `ativa`.

    So' sai de `inadimplente`, e so' para `ativa`. Um contrato `encerrada` ou
    `em_aviso_previo` nao pode ser ressuscitado por uma baixa de cobranca - o
    pagamento quita a divida, nao desfaz a rescisao.
    """
    contrato = (
        await db.execute(
            select(SiteSubscription)
            .where(SiteSubscription.id == contrato_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if contrato is None or contrato.estado != "inadimplente":
        return

    ainda_deve = (
        await db.execute(
            select(PlatformInvoice.id).where(
                PlatformInvoice.site_subscription_id == contrato_id,
                PlatformInvoice.estado == "vencida",
            )
        )
    ).first()
    if ainda_deve is None:
        contrato.estado = "ativa"
        log.info("contrato.regularizado", site=str(contrato.site_id))


async def marcar_como_paga(db: AsyncSession, cobranca_id: uuid.UUID) -> PlatformInvoice:
    """Baixa manual.

    Existe porque a liquidacao bancaria B2B nao existe, e essa e' uma DECISAO,
    nao uma lacuna: cobrar o estabelecimento por Pix exigiria credencial de PSP
    da PLATAFORMA - a chave da GoodWe, nao a do lojista, que e' o que
    `SitePaymentMethod` guarda. Nao ha essa conta, e `liquidacao_automatica:
    false` na resposta continua dizendo a verdade.

    O que foi construido em vez dela e' o CICLO: a cobranca vence, o contrato
    fica inadimplente e para de renovar, e esta baixa desfaz os dois. E' o que
    nao depende de banco nenhum.
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
    # Quitar a ultima divida tira o contrato da inadimplencia. Sem isto o
    # lojista pagaria e continuaria em vermelho ate alguem mexer no banco - e
    # `renovar_vencidos`, que so' olha `ativa`, nunca mais avancaria o ciclo.
    await db.flush()
    await _reavaliar_inadimplencia(db, cobranca.site_subscription_id)
    await db.commit()
    return cobranca


# ------------------------------------------------------------------- leitura


async def contrato_do_site(db: AsyncSession, site_id: uuid.UUID) -> dict:
    # `ultimo_do_site`, e nao `vigente_do_site`: um contrato encerrado com
    # cobranca em aberto continua tendo o que mostrar. Ler so' o vigente faria
    # encerrar virar um jeito de sumir com divida da tela.
    contrato = await ultimo_do_site(db, site_id)
    if contrato is None:
        return {"contratado": False}

    hoje = date.today()
    restantes = meses_restantes(hoje, contrato.minimo_ate)
    plano = contrato.plan

    # Escopo de SITE, e nao do contrato exibido.
    #
    # `ultimo_do_site` devolve o VIGENTE quando ha' um, entao filtrar por
    # `contrato.id` fazia a divida do contrato anterior sumir da tela no instante
    # em que o site assinava de novo. E' o mesmo defeito que `ultimo_do_site`
    # existe para impedir, entrando por outra porta: em vez de encerrar e sumir
    # com a divida, bastava RECONTRATAR e sumir com ela.
    #
    # Quem deve continua devendo a rede, e nao ao contrato que assinou na epoca.
    do_site = (
        select(PlatformInvoice)
        .join(SiteSubscription, SiteSubscription.id == PlatformInvoice.site_subscription_id)
        .where(SiteSubscription.site_id == site_id)
    )

    cobrancas = (
        (
            await db.execute(
                do_site.order_by(
                    PlatformInvoice.competencia.desc(),
                    # Desempate: a UNIQUE e' (contrato, competencia), entao dois
                    # contratos do mesmo site PODEM ter a mesma competencia -
                    # recontratar no meio do mes basta. Sem isto a ordem entre as
                    # duas linhas ficaria por conta do banco.
                    SiteSubscription.starts_on.desc(),
                ).limit(12)
            )
        )
        .scalars()
        .all()
    )

    # Consulta PROPRIA, e nao um filtro sobre `cobrancas`: aquela lista vem
    # limitada as 12 competencias mais recentes, e a divida nao pode depender
    # disso. Um contrato parado ha' mais de um ano teria a cobranca mais antiga
    # fora da janela, e o total em atraso sairia menor do que e' - justamente no
    # caso em que ele e' maior.
    atraso = (
        await db.execute(
            select(
                func.count(PlatformInvoice.id),
                func.coalesce(func.sum(PlatformInvoice.total_brl), 0),
                func.min(PlatformInvoice.vence_em),
            )
            .join(SiteSubscription, SiteSubscription.id == PlatformInvoice.site_subscription_id)
            .where(
                SiteSubscription.site_id == site_id,
                PlatformInvoice.estado == "vencida",
            )
        )
    ).one()
    atrasadas, total_atrasado, desde = atraso

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
        # A divida em atraso, somada e contada. Vem pronta porque a pergunta e'
        # sempre a mesma - "quanto esta vencido?" - e deixar a tela reduzir a
        # lista faria cada consumidor da API repetir a mesma soma, com a chance
        # de um deles esquecer de filtrar por estado.
        "em_atraso": {
            "cobrancas": int(atrasadas),
            "total_brl": float(total_atrasado),
            "desde": desde.isoformat() if desde else None,
        },
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
                # A lista pode misturar contratos desde que ela passou a ter
                # escopo de site. Sem este campo, duas competencias iguais de
                # contratos diferentes ficariam indistinguiveis na tela, e uma
                # cobranca herdada pareceria do contrato que esta' correndo.
                "contrato_anterior": c.site_subscription_id != contrato.id,
            }
            for c in cobrancas
        ],
    }
