"""Campanhas, missoes e a concessao das recompensas.

DOIS CAMINHOS, e o tipo de beneficio da campanha decide qual:

- `desconto_*` e' INSTANTANEO. Nao passa por missao: no momento de faturar, o
  motor recebe um `Beneficio` e a reducao aparece na propria fatura. Quem paga e'
  o estabelecimento, cedendo a margem daquela sessao, e o motorista ve o
  beneficio quando decide onde carregar - que e' quando o comportamento muda.

- `cashback_*` e' CONQUISTADO. Depende de missao cumprida, vira credito na
  carteira e so' se realiza na proxima recarga. Quem paga e' a rede, porque
  credito em carteira e' resgatavel em qualquer site: um estabelecimento que o
  bancasse estaria financiando uma recarga do concorrente ao lado.

AGREGACAO SINCRONA, PAGAMENTO ASSINCRONO. O progresso e' recalculado dentro do
mesmo commit que fecha a fatura - e' agregacao deterministica da sessao que
acabou de encerrar, sem I/O externo, entao ou os dois existem ou nenhum. A
concessao da recompensa nao: mexe em dinheiro e em push, e vai para worker.

O progresso e' recalculado por consulta, e nao incrementado. Sai mais caro - uma
agregacao por janela distinta - e paga por si em duas coisas: `dias_distintos`
nao e' somavel, e reprocessar uma sessao nao pode dobrar a contagem de ninguem.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Numeric, and_, cast, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.billing import Invoice, WalletEntry
from app.models.campaign import Campaign, Mission, MissionProgress, Reward
from app.models.enums import InvoiceStatus, SessionState
from app.models.session import ChargingSession
from app.models.site import Site
from app.models.user import User
from app.services.tariff_engine import Beneficio, money

log = get_logger(__name__)

# As janelas de tarifa sao locais, e "fora de ponta" tambem precisa ser. Medir em
# UTC deslocaria a ponta em tres horas e a missao premiaria o horario errado.
FUSO = ZoneInfo("America/Sao_Paulo")

# Ponta: dia util, das 18h as 21h. Mesma regra das janelas gravadas na tarifa do
# seed; se as duas divergirem, a missao contradiz a propria fatura.
PONTA_INICIO = 18
PONTA_FIM = 21

# Quantas recompensas o worker concede por ciclo. Mesmo tamanho do lote de push,
# e pelo mesmo motivo: limitar o tempo que uma transacao segura linhas.
LOTE = 50


# ---------------------------------------------------------------- elegibilidade


async def _vigentes(
    db: AsyncSession, sessao: ChargingSession, momento: datetime
) -> list[Campaign]:
    """Campanhas ativas, dentro do periodo e cujo escopo cobre esta sessao.

    O escopo e' decidido AQUI, numa clausula so'. Havia uma segunda checagem em
    Python depois desta consulta, repetindo a mesma regra; teste de mutacao
    mostrou que remove-la nao quebrava nada - o filtro SQL ja fazia todo o
    trabalho. Guarda duplicada e' guarda que ninguem testa, e a que sobra da a
    impressao de proteger algo que ja estava protegido em outro lugar.
    """
    consulta = (
        select(Campaign)
        .where(
            Campaign.ativa.is_(True),
            Campaign.starts_at <= momento,
            Campaign.ends_at >= momento,
            # Campanha de site vale so' no site dela; a de rede (site_id nulo)
            # vale em qualquer lugar. Quem paga nao banca recarga do vizinho.
            or_(Campaign.site_id.is_(None), Campaign.site_id == sessao.site_id),
            # Frota fica de fora, e nao por esforco: nenhuma fatura aponta para
            # `fleet_id` - `Invoice.user_id` e' pessoa fisica. Campanha
            # corporativa faria a empresa pagar e o funcionario embolsar. A
            # coluna existe para nao exigir migration depois; o caminho, nao.
            Campaign.patrocinador != "frota",
        )
        .options(selectinload(Campaign.missions))
    )
    return list((await db.execute(consulta)).scalars().all())


def _janela(
    missao: Mission, campanha: Campaign, momento: datetime
) -> tuple[date, datetime, datetime]:
    """Periodo em que esta missao conta, ja recortado pela vigencia da campanha.

    Sem o recorte, uma missao mensal numa campanha que comecou dia 20 contaria as
    recargas do dia 1 - o motorista cumpriria antes de a campanha existir.
    """
    local = momento.astimezone(FUSO)
    if missao.janela == "mensal":
        primeiro = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        seguinte = (primeiro + timedelta(days=32)).replace(day=1)
    elif missao.janela == "semanal":
        primeiro = (local - timedelta(days=local.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        seguinte = primeiro + timedelta(days=7)
    else:
        primeiro, seguinte = campanha.starts_at.astimezone(FUSO), campanha.ends_at.astimezone(FUSO)

    inicio = max(primeiro, campanha.starts_at.astimezone(FUSO))
    fim = min(seguinte, campanha.ends_at.astimezone(FUSO))
    # A chave do progresso e' o inicio NOMINAL da janela, nao o recortado: duas
    # campanhas com inicios diferentes no mesmo mes precisam colidir na mesma
    # linha de progresso de cada uma, nao criar uma linha por dia de largada.
    return primeiro.date(), inicio, fim


# ------------------------------------------------------------------ agregacao


async def _agregar(
    db: AsyncSession,
    user_id: uuid.UUID,
    inicio: datetime,
    fim: datetime,
    site_id: uuid.UUID | None,
) -> dict[str, Decimal]:
    """As seis metricas de uma vez, numa consulta so'.

    Uma consulta por janela distinta, e nao uma por missao: campanhas costumam
    ter varias missoes sobre o mesmo periodo.
    """
    local = func.timezone(Site.timezone, ChargingSession.started_at)
    na_ponta = and_(
        func.extract("isodow", local) <= 5,
        func.extract("hour", local) >= PONTA_INICIO,
        func.extract("hour", local) < PONTA_FIM,
    )

    consulta = (
        select(
            func.count().label("sessoes"),
            func.coalesce(func.sum(ChargingSession.energy_kwh), 0).label("energia_kwh"),
            func.coalesce(func.sum(ChargingSession.green_energy_kwh), 0).label(
                "energia_verde_kwh"
            ),
            func.coalesce(func.sum(Invoice.total), 0).label("valor_brl"),
            func.count(func.distinct(func.date(local))).label("dias_distintos"),
            func.count().filter(~na_ponta).label("sessoes_fora_de_ponta"),
        )
        .select_from(ChargingSession)
        .join(Site, Site.id == ChargingSession.site_id)
        .outerjoin(
            Invoice,
            and_(Invoice.session_id == ChargingSession.id, Invoice.status != InvoiceStatus.VOID),
        )
        .where(
            ChargingSession.user_id == user_id,
            ChargingSession.started_at >= inicio,
            ChargingSession.started_at < fim,
            ChargingSession.state == SessionState.BILLED,
        )
    )
    if site_id is not None:
        consulta = consulta.where(ChargingSession.site_id == site_id)

    linha = (await db.execute(consulta)).one()
    return {
        "sessoes": Decimal(linha.sessoes),
        "energia_kwh": Decimal(str(linha.energia_kwh)),
        "energia_verde_kwh": Decimal(str(linha.energia_verde_kwh)),
        "valor_brl": Decimal(str(linha.valor_brl)),
        "dias_distintos": Decimal(linha.dias_distintos),
        "sessoes_fora_de_ponta": Decimal(linha.sessoes_fora_de_ponta),
    }


async def atualizar_progresso(
    db: AsyncSession, sessao: ChargingSession, momento: datetime | None = None
) -> int:
    """Recalcula o progresso deste motorista nas missoes vigentes.

    Chamada de dentro de `bill_session`, no MESMO commit. Devolve quantas missoes
    foram concluidas agora. Nao concede recompensa: isso e' do worker.
    """
    if sessao.user_id is None:
        # Sessao avulsa (RFID sem conta). Nao ha a quem creditar nada.
        return 0

    momento = momento or datetime.now(UTC)
    campanhas = await _vigentes(db, sessao, momento)
    if not campanhas:
        return 0

    # Agrupa por (janela, escopo): missoes que medem o mesmo periodo sobre o
    # mesmo conjunto de sites compartilham uma unica agregacao.
    grupos: dict[tuple, list[tuple[Campaign, Mission]]] = {}
    for campanha in campanhas:
        if not campanha.beneficio_tipo.startswith("cashback"):
            # Campanha de desconto age na hora de faturar, nao por missao.
            continue
        for missao in campanha.missions:
            periodo, inicio, fim = _janela(missao, campanha, momento)
            chave = (periodo, inicio, fim, campanha.site_id)
            grupos.setdefault(chave, []).append((campanha, missao))

    # Estado anterior de todas as missoes envolvidas, numa consulta so'. Sem ele
    # nao da' para dizer se a missao fechou AGORA: o `ON CONFLICT ... RETURNING`
    # devolve a linha nova, e "esta concluida" seria verdade em todo faturamento
    # seguinte tambem - o contador acusaria conclusao a cada recarga.
    ids = [missao.id for pares in grupos.values() for _campanha, missao in pares]
    anteriores = {
        (linha.mission_id, linha.periodo): linha.concluida_em
        for linha in (
            await db.execute(
                select(MissionProgress).where(
                    MissionProgress.user_id == sessao.user_id,
                    MissionProgress.mission_id.in_(ids),
                )
            )
        ).scalars()
    }

    concluidas = 0
    for (periodo, inicio, fim, site_id), pares in grupos.items():
        agregados = await _agregar(db, sessao.user_id, inicio, fim, site_id)
        for _campanha, missao in pares:
            valor = agregados[missao.metrica]
            ja_estava = anteriores.get((missao.id, periodo)) is not None
            await _gravar_progresso(db, missao, sessao, periodo, valor, momento)
            if not ja_estava and valor >= Decimal(str(missao.alvo)):
                concluidas += 1
    return concluidas


async def _gravar_progresso(
    db: AsyncSession,
    missao: Mission,
    sessao: ChargingSession,
    periodo: date,
    valor: Decimal,
    momento: datetime,
) -> None:
    """Grava o valor absoluto e marca a conclusao, numa instrucao so'.

    Dois faturamentos simultaneos do mesmo motorista chegam aqui juntos; o
    `ON CONFLICT` da chave unica faz o segundo atualizar em vez de estourar.

    `concluida_em` NUNCA e' reescrito depois de gravado, e o `coalesce` e' quem
    garante. Conclusao e' fato consumado: se o operador subir o alvo de 5 para 6
    depois que alguem cumpriu, o valor recalculado cai abaixo do novo alvo - e
    zerar a marca ali retiraria do motorista uma conquista que o app ja comemorou.
    """
    alvo = Decimal(str(missao.alvo))
    tabela = MissionProgress.__table__
    fechou_agora = momento if valor >= alvo else None

    comando = (
        pg_insert(tabela)
        .values(
            id=uuid.uuid4(),
            mission_id=missao.id,
            user_id=sessao.user_id,
            periodo=periodo,
            valor=valor,
            concluida_em=fechou_agora,
            ultima_sessao_id=sessao.id,
        )
        .on_conflict_do_update(
            constraint="uq_mission_progress_missao_motorista_periodo",
            set_={
                "valor": cast(valor, Numeric(12, 3)),
                "ultima_sessao_id": sessao.id,
                "concluida_em": func.coalesce(tabela.c.concluida_em, fechou_agora),
                "updated_at": func.now(),
            },
        )
    )
    await db.execute(comando)


# --------------------------------------------------------- desconto na fatura


async def resolver_beneficio(
    db: AsyncSession, sessao: ChargingSession, momento: datetime | None = None
) -> Beneficio | None:
    """Monta o `Beneficio` que o motor de tarifacao recebe.

    Vive aqui, e nao dentro de `rate_session`, porque depende do banco. Manter o
    motor puro e' o que permite testa-lo sem subir Postgres.

    Havendo mais de uma campanha de desconto elegivel, vence a de maior valor -
    o motorista nao escolhe, entao a escolha e' a favor dele.
    """
    if sessao.user_id is None:
        return None

    momento = momento or datetime.now(UTC)
    candidatas = [
        c
        for c in await _vigentes(db, sessao, momento)
        if c.beneficio_tipo.startswith("desconto") and c.orcamento_disponivel > 0
    ]
    if not candidatas:
        return None

    melhor = max(candidatas, key=lambda c: Decimal(str(c.beneficio_valor)))
    if melhor.beneficio_tipo == "desconto_pct":
        return Beneficio(rotulo=melhor.nome, desconto_pct=Decimal(str(melhor.beneficio_valor)))
    # `desconto_fixo` ainda nao tem lugar no motor: ele conhece percentual, kWh
    # inclusos e isencao de taxa. Entregar valor fixo exigiria uma quarta forma
    # de abatimento, e a campanha de valor fixo nao foi pedida ainda - melhor
    # nao ter o caminho do que ter um que silenciosamente nao faz nada.
    return None


# ------------------------------------------------------------- concessao


def _valor_da_recompensa(campanha: Campaign, gasto_na_janela: Decimal) -> Decimal:
    if campanha.beneficio_tipo == "cashback_fixo":
        bruto = Decimal(str(campanha.beneficio_valor))
    else:
        bruto = gasto_na_janela * Decimal(str(campanha.beneficio_valor)) / Decimal("100")

    teto = campanha.teto_por_recompensa
    if teto is not None:
        bruto = min(bruto, Decimal(str(teto)))
    return money(bruto)


async def _pendentes(db: AsyncSession, limite: int) -> list[MissionProgress]:
    """Missoes concluidas que ainda nao geraram recompensa viva."""
    viva = (
        select(Reward.id)
        .where(
            Reward.mission_progress_id == MissionProgress.id,
            Reward.estado != "cancelada",
        )
        .exists()
    )
    consulta = (
        select(MissionProgress)
        .where(MissionProgress.concluida_em.isnot(None), ~viva)
        .order_by(MissionProgress.concluida_em)
        .limit(limite)
        .options(selectinload(MissionProgress.mission).selectinload(Mission.campaign))
    )
    return list((await db.execute(consulta)).scalars().all())


async def conceder_pendentes(db: AsyncSession, limite: int = LOTE) -> int:
    """Transforma missao concluida em dinheiro na carteira.

    Fora do commit do faturamento de proposito: aqui ha escrita de saldo, e uma
    falha nao pode desfazer a fatura que a originou.
    """
    progressos = await _pendentes(db, limite)
    concedidas = 0

    for progresso in progressos:
        campanha = progresso.mission.campaign
        if not campanha.beneficio_tipo.startswith("cashback"):
            continue

        periodo, inicio, fim = _janela(progresso.mission, campanha, progresso.concluida_em)
        agregados = await _agregar(db, progresso.user_id, inicio, fim, campanha.site_id)
        valor = _valor_da_recompensa(campanha, agregados["valor_brl"])

        # O orcamento e' teto duro: gastar alem dele e' comprometer dinheiro que
        # o patrocinador nao autorizou.
        if valor <= 0 or campanha.orcamento_disponivel < valor:
            log.info(
                "recompensa.sem_orcamento",
                campanha=str(campanha.id),
                pedido=float(valor),
                disponivel=float(campanha.orcamento_disponivel),
            )
            continue

        recompensa = Reward(
            id=uuid.uuid4(),
            user_id=progresso.user_id,
            campaign_id=campanha.id,
            mission_progress_id=progresso.id,
            tipo=campanha.beneficio_tipo,
            valor_brl=valor,
            estado="pendente",
        )
        db.add(recompensa)
        try:
            await db.flush()
        except IntegrityError:
            # Outra instancia do worker chegou primeiro. O indice unico parcial
            # e' quem garante - nao o SELECT la' em cima, que dois processos
            # atravessam juntos antes de qualquer INSERT.
            await db.rollback()
            continue

        await _creditar(db, recompensa, campanha)
        concedidas += 1

    if concedidas:
        await db.commit()
    return concedidas


async def _creditar(db: AsyncSession, recompensa: Reward, campanha: Campaign) -> None:
    """Credita a carteira, no mesmo desenho de `payment_service.topup_wallet`.

    A chave de idempotencia e' DETERMINISTICA - `reward:<id>` -, e nao sorteada:
    o UNIQUE que ja existe em `wallet_entries.idempotency_key` vira a protecao
    contra credito duplo sem precisar de tabela de trava nova.
    """
    dono = (
        await db.execute(
            select(User).where(User.id == recompensa.user_id).with_for_update()
        )
    ).scalar_one()

    saldo = Decimal(str(dono.wallet_balance)) + Decimal(str(recompensa.valor_brl))
    credito = WalletEntry(
        id=uuid.uuid4(),
        user_id=dono.id,
        amount=recompensa.valor_brl,
        balance_after=money(saldo),
        idempotency_key=f"reward:{recompensa.id}",
        provider="campanha",
        provider_ref=str(campanha.id),
        origem="cashback",
        origem_ref=recompensa.id,
    )
    db.add(credito)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return

    dono.wallet_balance = money(saldo)
    recompensa.wallet_entry_id = credito.id
    recompensa.estado = "creditada"
    campanha.consumido_brl = money(
        Decimal(str(campanha.consumido_brl)) + Decimal(str(recompensa.valor_brl))
    )
    log.info(
        "recompensa.creditada",
        recompensa=str(recompensa.id),
        motorista=str(dono.id),
        valor=float(recompensa.valor_brl),
    )


# ------------------------------------------------------------------- leituras


async def listar_do_site(db: AsyncSession, site_id: uuid.UUID) -> list[Campaign]:
    """Campanhas que o operador deste site pode ver.

    As dele mais as de rede. As de rede entram como leitura: ele nao as criou e
    nao as paga, mas elas agem sobre as recargas do site dele, e uma tela que as
    escondesse faria o desconto aparecer na fatura sem explicacao.
    """
    consulta = (
        select(Campaign)
        .where(or_(Campaign.site_id == site_id, Campaign.site_id.is_(None)))
        .order_by(Campaign.starts_at.desc())
        .options(selectinload(Campaign.missions))
    )
    return list((await db.execute(consulta)).scalars().all())


async def desempenho(db: AsyncSession, campanha: Campaign) -> dict:
    """Se o dinheiro comprou comportamento ou so' saiu do caixa.

    `consumido_brl` sozinho nao responde: R$ 500 gastos com duas pessoas e' outra
    coisa que R$ 500 com oitenta.
    """
    ids = [m.id for m in campanha.missions]
    alcancados = concluidas = 0
    if ids:
        linha = (
            await db.execute(
                select(
                    func.count(func.distinct(MissionProgress.user_id)),
                    func.count().filter(MissionProgress.concluida_em.isnot(None)),
                ).where(MissionProgress.mission_id.in_(ids))
            )
        ).one()
        alcancados, concluidas = linha[0], linha[1]

    creditadas = (
        await db.execute(
            select(func.count())
            .select_from(Reward)
            .where(Reward.campaign_id == campanha.id, Reward.estado == "creditada")
        )
    ).scalar_one()

    orcamento = Decimal(str(campanha.orcamento_brl))
    consumido = Decimal(str(campanha.consumido_brl))
    return {
        "campanha_id": campanha.id,
        "nome": campanha.nome,
        "motoristas_alcancados": alcancados,
        "missoes_concluidas": concluidas,
        "recompensas_creditadas": creditadas,
        "consumido_brl": float(consumido),
        "orcamento_brl": float(orcamento),
        "orcamento_disponivel": float(orcamento - consumido),
        "percentual_consumido": float(consumido / orcamento * 100) if orcamento > 0 else 0.0,
    }


def _rotulo_da_recompensa(campanha: Campaign) -> str:
    valor = Decimal(str(campanha.beneficio_valor))
    if campanha.beneficio_tipo.endswith("_pct"):
        return f"{valor.normalize()}% de volta"
    return f"R$ {valor:.2f}".replace(".", ",")


async def missoes_do_motorista(
    db: AsyncSession, user: User, momento: datetime | None = None
) -> list[dict]:
    """O que este motorista tem em aberto, com onde ele esta em cada uma.

    Devolve tambem as que ele ainda nao comecou - com progresso zero. Uma tela
    que so' mostrasse missao ja iniciada estaria vazia para quem acabou de
    instalar o app, que e' exatamente quem mais precisa ver o que ha para ganhar.
    """
    momento = momento or datetime.now(UTC)
    campanhas = (
        (
            await db.execute(
                select(Campaign)
                .where(
                    Campaign.ativa.is_(True),
                    Campaign.starts_at <= momento,
                    Campaign.ends_at >= momento,
                    Campaign.patrocinador != "frota",
                )
                .options(selectinload(Campaign.missions))
            )
        )
        .scalars()
        .all()
    )
    if not campanhas:
        return []

    ids = [m.id for c in campanhas for m in c.missions]
    progressos = {
        (p.mission_id, p.periodo): p
        for p in (
            await db.execute(
                select(MissionProgress)
                .where(
                    MissionProgress.user_id == user.id,
                    MissionProgress.mission_id.in_(ids),
                )
                .execution_options(populate_existing=True)
            )
        ).scalars()
    }

    saida: list[dict] = []
    for campanha in campanhas:
        if not campanha.beneficio_tipo.startswith("cashback"):
            continue
        for missao in sorted(campanha.missions, key=lambda m: (m.ordem, m.codigo)):
            periodo, _inicio, _fim = _janela(missao, campanha, momento)
            progresso = progressos.get((missao.id, periodo))
            saida.append(
                {
                    "id": missao.id,
                    "codigo": missao.codigo,
                    "titulo": missao.titulo,
                    "descricao": missao.descricao,
                    "metrica": missao.metrica,
                    "alvo": float(missao.alvo),
                    "janela": missao.janela,
                    "progresso": float(progresso.valor) if progresso else 0.0,
                    "concluida": bool(progresso and progresso.concluida_em),
                    "concluida_em": progresso.concluida_em if progresso else None,
                    "periodo": periodo,
                    "campanha": campanha.nome,
                    "recompensa": _rotulo_da_recompensa(campanha),
                }
            )
    return saida


async def recompensas_do_motorista(db: AsyncSession, user: User, limite: int = 50) -> list[dict]:
    consulta = (
        select(Reward)
        .where(Reward.user_id == user.id)
        .order_by(Reward.created_at.desc())
        .limit(limite)
        .options(selectinload(Reward.campaign))
    )
    return [
        {
            "id": r.id,
            "campanha": r.campaign.nome if r.campaign else "—",
            "valor_brl": float(r.valor_brl),
            "estado": r.estado,
            "tipo": r.tipo,
            "created_at": r.created_at,
        }
        for r in (await db.execute(consulta)).scalars()
    ]
