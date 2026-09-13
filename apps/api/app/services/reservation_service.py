"""Leva a reserva ate' o equipamento - e a retira quando ela deixa de valer.

`reservations.pushed_to_hardware` existe desde a 0001, com o comentario "Escrita
nos registradores 10020-10022 do ponto?" logo acima, e era FALSO em todas as
linhas do banco. Nao por engano de escrita: a coluna nunca teve produtor.

O resto do caminho estava pronto e igualmente parado. `modbus_map` declara
RESERVATION_STATUS/START/DURATION (10020-10022), `ModbusDriver.push_reservation`
escreve os tres, o simulador responde, e `COMMANDS` mapeia o nome - **e nada
nunca chamou**. A reserva existia so' no banco: o app confirmava, o
`session_service` respeitava, e o carregador nao ficava sabendo. Quem chegasse
com cartao na frente do titular era atendido pelo equipamento.

POR QUE UM RECONCILIADOR, e nao um empurrao na rota que cria a reserva:

  - o registrador guarda HORA:MINUTO, nao data (`encode_hhmm`, reg 10021). O
    equipamento tem relogio, nao calendario. Empurrar hoje uma reserva de
    terca-feira faria o ponto bloquear a vaga HOJE naquela hora. Por isso so'
    entra o que esta' dentro de `JANELA_DE_PUSH`;
  - cancelar precisa RETIRAR. Uma reserva empurrada e depois cancelada deixaria
    o equipamento recusando todo mundo ate' a janela passar;
  - carregador reinicia e perde o registrador. Um empurrao unico no momento da
    criacao nao tem como saber disso; uma varredura que compara o desejado com
    `pushed_to_hardware` reconverge sozinha no ciclo seguinte.

A reserva NAO depende disto para valer: `session_service` continua sendo a
autoridade, e por isso falha de comunicacao aqui nunca derruba a reserva. A
coluna passa a responder uma pergunta honesta - "o equipamento tambem sabe?" - e
`false` deixa de significar "ninguem nunca escreveu" para significar "vale so' no
software".
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.charge_point import ChargePoint
from app.models.enums import ReservationStatus
from app.models.reservation import Reservation
from app.models.site import Site
from app.services.command_service import send_command

log = structlog.get_logger(__name__)

# So' entra no equipamento a reserva que comeca dentro desta janela.
#
# O limite nao e' de desempenho: o reg 10021 e' hora:minuto sem data, entao uma
# reserva mais distante que isto seria escrita como se fosse hoje. Menos de 24h
# mantem a leitura do registrador nao ambigua.
JANELA_DE_PUSH = timedelta(hours=24)

# Reg 10022 e' U16 em minutos.
DURACAO_MAXIMA_MIN = 0xFFFF

# Estados em que a reserva ainda vale.
VIVAS = (ReservationStatus.PENDING, ReservationStatus.CONFIRMED)

FUSO_PADRAO = "America/Sao_Paulo"


def duracao_em_minutos(comeca: datetime, termina: datetime) -> int:
    """Minutos da janela, no minimo 1 e no maximo o que cabe no registrador.

    Zero desligaria a reserva no mesmo comando que a liga (o equipamento leria
    "reservado por 0 minuto"), e por isso o piso e' 1 e nao 0.
    """
    minutos = int((termina - comeca).total_seconds() // 60)
    return max(1, min(minutos, DURACAO_MAXIMA_MIN))


def hora_local(quando: datetime, fuso: str | None) -> tuple[int, int]:
    """Hora e minuto no fuso do site.

    O banco guarda tudo em UTC e o equipamento esta' na calcada: escrever a hora
    UTC no reg 10021 reservaria a vaga tres horas fora do lugar.
    """
    local = quando.astimezone(ZoneInfo(fuso or FUSO_PADRAO))
    return local.hour, local.minute


def deve_estar_no_equipamento(reserva: Reservation, agora: datetime) -> bool:
    """A reserva deveria estar escrita no ponto neste instante?

    Esta e' a funcao inteira da sincronizacao: o que ela devolve e' comparado com
    `pushed_to_hardware`, e a diferenca vira um comando.
    """
    if reserva.status not in VIVAS:
        return False
    if reserva.ends_at <= agora:
        return False
    return reserva.starts_at <= agora + JANELA_DE_PUSH


async def sincronizar(db: AsyncSession, *, agora: datetime | None = None) -> dict:
    """Aproxima o equipamento do banco: empurra o que entrou, retira o que saiu.

    Idempotente por construcao - o que ja esta' no estado certo nao gera comando,
    entao passar de novo no ciclo seguinte nao conversa com o equipamento a toa.
    """
    agora = agora or datetime.now(UTC)
    empurradas = retiradas = falhas = 0

    candidatas = (
        (
            await db.execute(
                select(Reservation)
                # `connection` junto: `registry.get` le a conexao do ponto para
                # escolher o driver, e relacao lazy em contexto async estoura
                # MissingGreenlet. E' o mesmo cuidado que `poll_once` ja' toma.
                .options(
                    selectinload(Reservation.charge_point).selectinload(ChargePoint.connection)
                )
                .where(
                    or_(
                        # Ja' esta' no equipamento: talvez precise SAIR. Inclui
                        # cancelada e consumida, que e' o caso que devolve a vaga.
                        Reservation.pushed_to_hardware.is_(True),
                        # Ou esta' viva e dentro da janela: talvez precise ENTRAR.
                        # A janela repetida aqui e' RECORTE DE CARGA, e nao a
                        # guarda: quem decide e' `deve_estar_no_equipamento`,
                        # abaixo. Serve para nao trazer do banco toda reserva
                        # futura da rede a cada varredura.
                        and_(
                            Reservation.status.in_(VIVAS),
                            Reservation.ends_at > agora,
                            Reservation.starts_at <= agora + JANELA_DE_PUSH,
                        ),
                    )
                )
            )
        )
        .scalars()
        .all()
    )

    fusos: dict = {}
    for reserva in candidatas:
        desejado = deve_estar_no_equipamento(reserva, agora)
        if desejado == reserva.pushed_to_hardware:
            continue

        ponto = reserva.charge_point
        if ponto is None or not ponto.enabled:
            # Ponto desabilitado nao recebe comando - e continua marcado como
            # nao-empurrado, que e' a verdade.
            continue

        if desejado:
            if ponto.site_id not in fusos:
                site = await db.get(Site, ponto.site_id)
                fusos[ponto.site_id] = site.timezone if site else FUSO_PADRAO
            hora, minuto = hora_local(reserva.starts_at, fusos[ponto.site_id])
            resultado = await send_command(
                db,
                ponto,
                "push_reservation",
                triggered_by=f"reserva:{reserva.code}",
                hour=hora,
                minute=minuto,
                duration_min=duracao_em_minutos(reserva.starts_at, reserva.ends_at),
            )
        else:
            resultado = await send_command(
                db, ponto, "clear_reservation", triggered_by=f"reserva:{reserva.code}"
            )

        if not resultado.ok:
            # A reserva continua valendo no software. O flag nao avanca, e a
            # proxima varredura tenta de novo - que e' o unico tratamento
            # honesto para equipamento fora do ar.
            falhas += 1
            continue

        reserva.pushed_to_hardware = desejado
        if desejado:
            empurradas += 1
        else:
            retiradas += 1

    if empurradas or retiradas or falhas:
        await db.commit()
        log.info(
            "reservas.sincronizadas",
            empurradas=empurradas,
            retiradas=retiradas,
            falhas=falhas,
        )

    return {"empurradas": empurradas, "retiradas": retiradas, "falhas": falhas}


__all__ = [
    "JANELA_DE_PUSH",
    "deve_estar_no_equipamento",
    "duracao_em_minutos",
    "hora_local",
    "sincronizar",
]
