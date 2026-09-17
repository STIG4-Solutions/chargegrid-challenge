"""Traduz evento de sessao em notificacao, e entrega.

O app fazia polling. Isso funciona enquanto ele esta aberto na tela certa - e
o momento em que a notificacao importa e' exatamente o outro: o motorista foi
almocar, a recarga terminou, e o conector fica parado gerando taxa de
ociosidade para ele e fila para os demais.

Os eventos ja existiam. O que este modulo faz e' escolher QUAIS deles valem
uma vibracao no bolso de alguem. Notificar tudo treina o motorista a ignorar,
e a partir dai a notificacao que importa tambem passa despercebida - entao a
lista e' curta de proposito:

  recarga concluida     ele precisa ir buscar o carro
  promovido na fila     a vaga e' dele agora, e nao espera para sempre
  encerrada por falha   parou sem ele pedir, e ele nao sabe

Fica de fora tudo que ele ja esta vendo: "autorizado" acontece com o app na
mao, e as transicoes intermediarias sao ruido.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.enums import SessionState, StopReason
from app.models.push_device import PushDevice
from app.models.session import ChargingSession, SessionEvent
from app.services.push_senders import Mensagem, PushError, get_sender

log = get_logger(__name__)

# Quantos eventos por ciclo. Um lote grande atrasa o proximo ciclo inteiro se
# o servico externo estiver lento; um pequeno demora a esvaziar um acumulo.
LOTE = 50

# Eventos que valem uma notificacao. Os demais sao gravados e nunca enviados -
# e continuam com notified_at nulo, o que e' correto: nao foram notificados.
NOTIFICAVEIS = {"state_change", "queue_promoted", "error"}

# Idade maxima de um evento para virar notificacao.
#
# Push aqui e' sempre sobre o agora: "venha buscar o carro", "a vaga e sua".
# Se o worker ficou fora do ar - ou o servico de push esteve inacessivel - por
# mais que isso, entregar atrasado e' pior que nao entregar: o motorista ja
# foi embora, e a mensagem so' confunde. Os eventos velhos sao marcados como
# avaliados e registrados no log, nao reenviados para sempre.
IDADE_MAXIMA_MIN = 30


def _mensagem(evento: SessionEvent, sessao: ChargingSession) -> tuple[str, str] | None:
    """Titulo e corpo, ou None quando este evento especifico nao vale push."""
    codigo = sessao.code

    if evento.event_type == "queue_promoted":
        return (
            "Sua vez chegou",
            f"O ponto liberou e a recarga {codigo} comecou. {evento.message or ''}".strip(),
        )

    if evento.event_type == "error":
        return ("Recarga interrompida", f"A recarga {codigo} parou: {evento.message or 'falha'}")

    if evento.event_type == "state_change":
        # So' FINISHED. Duas razoes, e a segunda foi encontrada no aparelho:
        #
        # As transicoes do meio acontecem com o motorista olhando o app, e
        # notificar cada uma treina a ignorar todas.
        #
        # E BILLED nunca pode ser o PRIMEIRO estado terminal: a maquina de
        # estados so' permite `finished -> billed`, entao toda sessao faturada
        # ja passou por FINISHED e ja recebeu o aviso. Aceitar os dois mandava
        # duas notificacoes com texto identico - energia e custo ja estao
        # fechados nas duas -, o que e' pior que nao avisar: o motorista
        # aprende que o app repete.
        if evento.to_state != str(SessionState.FINISHED):
            return None
        if sessao.stop_reason == StopReason.FAULT:
            return (
                "Recarga interrompida",
                f"A recarga {codigo} parou por falha no equipamento. "
                "Você não paga o que não recebeu.",
            )
        energia = float(sessao.energy_kwh or 0)
        custo = float(sessao.estimated_cost or 0)
        motivo = {
            StopReason.ENERGY_LIMIT: "atingiu o limite de energia",
            StopReason.TIME_LIMIT: "atingiu o limite de tempo",
            StopReason.AMOUNT_LIMIT: "atingiu o limite de valor",
        }.get(sessao.stop_reason, "terminou")
        return (
            "Recarga concluída",
            f"{energia:.1f} kWh · R$ {custo:.2f}. A recarga {motivo}. "
            "Libere o ponto para evitar taxa de ociosidade.",
        )

    return None


async def pendentes(db: AsyncSession, limite: int = LOTE) -> list[SessionEvent]:
    """Eventos notificaveis ainda nao enviados, do mais antigo para o mais novo.

    A ordem importa: notificar "concluida" antes de "promovido na fila" conta a
    historia ao contrario para quem estava esperando vaga.
    """
    return list(
        (
            await db.execute(
                select(SessionEvent)
                .where(
                    SessionEvent.notified_at.is_(None),
                    SessionEvent.event_type.in_(NOTIFICAVEIS),
                )
                .options(selectinload(SessionEvent.session))
                .order_by(SessionEvent.occurred_at)
                .limit(limite)
            )
        )
        .scalars()
        .all()
    )


async def enviar_pendentes(db: AsyncSession, limite: int = LOTE) -> dict:
    """Drena a fila uma vez. Chamada pelo worker."""
    eventos = await pendentes(db, limite)
    if not eventos:
        return {"eventos": 0, "mensagens": 0}

    # Um usuario pode ter varios aparelhos; busca todos de uma vez em vez de
    # uma consulta por evento.
    donos = {e.session.user_id for e in eventos if e.session and e.session.user_id}
    por_usuario: dict[str, list[PushDevice]] = {}
    if donos:
        for d in (
            (await db.execute(select(PushDevice).where(PushDevice.user_id.in_(donos))))
            .scalars()
            .all()
        ):
            por_usuario.setdefault(str(d.user_id), []).append(d)

    mensagens: list[Mensagem] = []
    marcados: list[SessionEvent] = []
    for evento in eventos:
        sessao = evento.session
        if sessao is None:
            # Evento orfao nao tem a quem notificar; marcar evita reprocessar
            # para sempre um item que nunca vai sair da fila.
            marcados.append(evento)
            continue

        atraso = (datetime.now(UTC) - evento.occurred_at).total_seconds() / 60
        if atraso > IDADE_MAXIMA_MIN:
            log.info(
                "push.descartado_por_idade",
                evento=evento.event_type,
                minutos=round(atraso),
                sessao=sessao.code,
            )
            marcados.append(evento)
            continue

        texto = _mensagem(evento, sessao)
        if texto is None:
            # Nao notificavel na pratica (uma transicao do meio, por exemplo).
            # Marcar e' o certo: ja foi avaliado e a decisao foi nao enviar.
            marcados.append(evento)
            continue

        titulo, corpo = texto
        aparelhos = por_usuario.get(str(sessao.user_id), [])
        for aparelho in aparelhos:
            mensagens.append(
                Mensagem(
                    token=aparelho.token,
                    titulo=titulo,
                    corpo=corpo,
                    dados={"session_id": str(sessao.id), "code": sessao.code},
                )
            )
        # Sem aparelho registrado tambem marca: a sessao e' de uma conta que
        # nunca abriu o app, e guardar o evento pendente para sempre so' faria
        # a fila crescer.
        marcados.append(evento)

    enviadas = 0
    if mensagens:
        try:
            enviadas = get_sender().send(mensagens)
        except PushError as erro:
            # Nada e' marcado: os eventos voltam no proximo ciclo. Marcar aqui
            # transformaria "nao entreguei" em "entreguei" e a notificacao
            # sumiria para sempre.
            log.warning("push.falhou", erro=str(erro), mensagens=len(mensagens))
            return {"eventos": 0, "mensagens": 0, "erro": str(erro)}

    agora = datetime.now(UTC)
    for evento in marcados:
        evento.notified_at = agora
    await db.commit()

    log.info("push.enviado", eventos=len(marcados), mensagens=enviadas)
    return {"eventos": len(marcados), "mensagens": enviadas}


def _mensagem_recompensa(recompensa) -> tuple[str, str]:
    """Titulo e corpo do aviso de recompensa. Aqui sempre ha o que dizer."""
    valor = f"R$ {float(recompensa.valor_brl):.2f}".replace(".", ",")
    nome = recompensa.campaign.nome if recompensa.campaign else "Campanha"
    return ("Recompensa liberada", f"{valor} na sua carteira — {nome}")


async def enviar_recompensas_pendentes(db: AsyncSession, limite: int = LOTE) -> dict:
    """Drena o segundo outbox: recompensas creditadas e ainda nao avisadas.

    Outbox proprio, e nao `session_events`. Afrouxar `session_events.session_id`
    para nulavel seria o caminho curto e destruiria uma guarda: `enviar_pendentes`
    trata `session is None` como evento ORFAO a descartar, e transformar isso num
    caso normal faria um defeito hoje detectado virar rotina. Aqui a propria
    existencia da linha ja e' o fato a notificar - nao ha duas versoes da verdade,
    que era a justificativa original para o outbox morar em `session_events`.

    IDADE_MAXIMA_MIN NAO SE APLICA AQUI, e precisa continuar assim. Aquela
    constante existe porque "venha buscar o carro" perde valor depois de 30
    minutos: o motorista ja foi embora e a mensagem so' confunde. "Voce ganhou
    R$ 12" nao perde valor nunca. Quem aplicar a mesma constante por simetria faz
    o motorista deixar de ser avisado do proprio dinheiro, e o silencio vai
    parecer intencional.
    """
    from app.models.campaign import Reward

    consulta = (
        select(Reward)
        .where(Reward.notified_at.is_(None), Reward.estado == "creditada")
        .order_by(Reward.created_at)
        .limit(limite)
    )
    recompensas = list((await db.execute(consulta)).scalars().all())
    if not recompensas:
        return {"recompensas": 0, "mensagens": 0}

    donos = {r.user_id for r in recompensas}
    por_usuario: dict[str, list[PushDevice]] = {}
    for aparelho in (
        (await db.execute(select(PushDevice).where(PushDevice.user_id.in_(donos)))).scalars().all()
    ):
        por_usuario.setdefault(str(aparelho.user_id), []).append(aparelho)

    mensagens: list[Mensagem] = []
    for recompensa in recompensas:
        titulo, corpo = _mensagem_recompensa(recompensa)
        for aparelho in por_usuario.get(str(recompensa.user_id), []):
            mensagens.append(
                Mensagem(
                    token=aparelho.token,
                    titulo=titulo,
                    corpo=corpo,
                    dados={"reward_id": str(recompensa.id), "tipo": "recompensa"},
                )
            )

    enviadas = 0
    if mensagens:
        try:
            enviadas = get_sender().send(mensagens)
        except PushError as erro:
            # Mesmo tratamento do outro dreno: nada marcado, tudo volta no
            # proximo ciclo.
            log.warning("push.recompensa_falhou", erro=str(erro), mensagens=len(mensagens))
            return {"recompensas": 0, "mensagens": 0, "erro": str(erro)}

    agora = datetime.now(UTC)
    for recompensa in recompensas:
        # Marca inclusive quem nao tem aparelho: a conta nunca abriu o app, e
        # guardar a linha pendente para sempre so' faria a fila crescer.
        recompensa.notified_at = agora
    await db.commit()

    log.info("push.recompensa_enviada", recompensas=len(recompensas), mensagens=enviadas)
    return {"recompensas": len(recompensas), "mensagens": enviadas}
