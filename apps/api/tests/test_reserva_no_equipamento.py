"""A reserva chega ao carregador - e volta quando deixa de valer.

`reservations.pushed_to_hardware` era FALSO em todas as linhas do banco. O
caminho inteiro existia parado: os registradores 10020-10022 no `modbus_map`, o
`push_reservation` no driver e no simulador, a entrada em `COMMANDS` - e nenhum
chamador. O app confirmava a reserva, o `session_service` a respeitava, e o
equipamento na calcada nao ficava sabendo: quem chegasse com cartao na frente do
titular era atendido.

O que estes testes fixam vai alem de "escreve o registrador". Sao as tres coisas
que separam um reconciliador util de um empurrao ingenuo:

  - a JANELA. O reg 10021 e' hora:minuto sem data. Empurrar hoje uma reserva de
    terca bloquearia a vaga HOJE naquela hora - o defeito seria pior que o
    silencio que ele veio consertar;
  - a RETIRADA. Cancelar sem retirar deixaria o ponto recusando todo mundo ate'
    a janela passar;
  - o FUSO. O banco guarda UTC e o equipamento esta' na calcada: escrever a hora
    UTC reservaria a vaga tres horas fora do lugar.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.drivers.simulator import SimulatedChargePointDriver
from app.models.audit import CommandLog
from app.models.enums import ReservationStatus
from app.models.reservation import Reservation
from app.services import reservation_service as rs

AGORA = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)


def _reserva(ponto, motorista, *, comeca, dura=timedelta(hours=1), status=None, empurrada=False):
    return Reservation(
        code=f"RES-{uuid.uuid4().hex[:8].upper()}",
        site_id=ponto.site_id,
        charge_point_id=ponto.id,
        user_id=motorista.id,
        status=status or ReservationStatus.CONFIRMED,
        starts_at=comeca,
        ends_at=comeca + dura,
        reserved_kw=22,
        pushed_to_hardware=empurrada,
    )


async def _comandos(db, ponto, nome=None) -> list[CommandLog]:
    consulta = select(CommandLog).where(CommandLog.charge_point_id == ponto.id)
    if nome:
        consulta = consulta.where(CommandLog.command == nome)
    return list((await db.execute(consulta)).scalars().all())


# ------------------------------------------------------------------ funcoes puras


@pytest.mark.parametrize(
    "minutos,esperado",
    [(90, 90), (0, 1), (-5, 1), (60 * 24 * 60, rs.DURACAO_MAXIMA_MIN)],
)
def test_duracao_cabe_no_registrador(minutos, esperado):
    """Reg 10022 e' U16 em minutos, e zero desligaria a reserva no mesmo comando
    que a liga - o equipamento leria "reservado por 0 minuto"."""
    assert rs.duracao_em_minutos(AGORA, AGORA + timedelta(minutes=minutos)) == esperado


def test_hora_e_a_do_site_e_nao_a_do_banco():
    """12:00 UTC e' 09:00 em Sao Paulo. Escrever 12 no reg 10021 reservaria a
    vaga tres horas fora do lugar."""
    assert rs.hora_local(AGORA, "America/Sao_Paulo") == (9, 0)
    assert rs.hora_local(AGORA, None) == (9, 0), "sem fuso cadastrado, o padrao da casa"
    assert rs.hora_local(AGORA, "UTC") == (12, 0)


# --------------------------------------------------------------- o predicado
#
# `deve_estar_no_equipamento` e' a autoridade sobre a janela, e por isso e'
# testada sozinha. A consulta de `sincronizar` repete o mesmo recorte, mas ali
# ele e' SO' carga: serve para nao trazer do banco toda reserva futura da rede.
# Testar a janela pelo caminho longo deixaria as duas se cobrindo - reverter
# qualquer uma passaria despercebido, que foi exatamente o que a mutacao mostrou.


def _so_datas(comeca, dura=timedelta(hours=1), status=None, empurrada=False):
    return Reservation(
        status=status or ReservationStatus.CONFIRMED,
        starts_at=comeca,
        ends_at=comeca + dura,
        pushed_to_hardware=empurrada,
    )


def test_predicado_aceita_o_que_esta_na_janela():
    assert rs.deve_estar_no_equipamento(_so_datas(AGORA + timedelta(hours=2)), AGORA) is True
    assert rs.deve_estar_no_equipamento(_so_datas(AGORA - timedelta(minutes=10)), AGORA) is True


def test_predicado_recusa_o_que_esta_longe_demais():
    """A guarda contra o registrador sem calendario.

    O reg 10021 e' hora:minuto. Uma reserva de terca que passasse por aqui hoje
    seria escrita como se fosse hoje, e o ponto recusaria cartao no horario
    errado, no dia errado.
    """
    distante = _so_datas(AGORA + rs.JANELA_DE_PUSH + timedelta(minutes=1))
    assert rs.deve_estar_no_equipamento(distante, AGORA) is False

    na_borda = _so_datas(AGORA + rs.JANELA_DE_PUSH)
    assert rs.deve_estar_no_equipamento(na_borda, AGORA) is True


@pytest.mark.parametrize(
    "estado",
    [ReservationStatus.CANCELLED, ReservationStatus.CONSUMED, ReservationStatus.EXPIRED],
)
def test_predicado_recusa_quem_nao_vale_mais(estado):
    morta = _so_datas(AGORA + timedelta(hours=2), status=estado)
    assert rs.deve_estar_no_equipamento(morta, AGORA) is False


def test_predicado_recusa_janela_que_ja_terminou():
    passada = _so_datas(AGORA - timedelta(hours=5))
    assert rs.deve_estar_no_equipamento(passada, AGORA) is False


# ------------------------------------------------------------------ empurrar


async def test_reserva_proxima_vai_para_o_equipamento(db, ponto, motorista):
    r = _reserva(ponto, motorista, comeca=AGORA + timedelta(hours=2))
    db.add(r)
    await db.flush()

    assert (await rs.sincronizar(db, agora=AGORA))["empurradas"] == 1

    await db.refresh(r)
    assert r.pushed_to_hardware is True
    (comando,) = await _comandos(db, ponto, "push_reservation")
    assert comando.success is True
    assert comando.payload["hour"] == 11, "14:00 UTC e' 11:00 em Sao Paulo"
    assert comando.payload["duration_min"] == 60
    assert comando.triggered_by == f"reserva:{r.code}"


async def test_reserva_distante_nao_vai(db, ponto, motorista):
    """O caso que obriga a janela a existir.

    O reg 10021 guarda hora:minuto e o equipamento tem relogio, nao calendario.
    Uma reserva de terca empurrada hoje bloquearia a vaga HOJE naquele horario -
    o motorista que chegasse encontraria o ponto recusando cartao sem motivo.
    """
    r = _reserva(ponto, motorista, comeca=AGORA + timedelta(days=3))
    db.add(r)
    await db.flush()

    assert (await rs.sincronizar(db, agora=AGORA))["empurradas"] == 0

    await db.refresh(r)
    assert r.pushed_to_hardware is False
    assert await _comandos(db, ponto) == []


async def test_reserva_cancelada_nunca_e_empurrada(db, ponto, motorista):
    db.add(
        _reserva(
            ponto,
            motorista,
            comeca=AGORA + timedelta(hours=2),
            status=ReservationStatus.CANCELLED,
        )
    )
    await db.flush()

    assert (await rs.sincronizar(db, agora=AGORA))["empurradas"] == 0
    assert await _comandos(db, ponto) == []


async def test_ponto_desabilitado_nao_recebe_comando(db, ponto, motorista):
    ponto.enabled = False
    r = _reserva(ponto, motorista, comeca=AGORA + timedelta(hours=2))
    db.add(r)
    await db.flush()

    await rs.sincronizar(db, agora=AGORA)

    await db.refresh(r)
    assert r.pushed_to_hardware is False, "marcar sem enviar seria mentira no banco"
    assert await _comandos(db, ponto) == []


# ------------------------------------------------------------------ retirar


async def test_cancelar_devolve_a_vaga(db, ponto, motorista):
    """A outra metade do defeito.

    Sem a retirada, cancelar no app deixaria o equipamento recusando cartao
    alheio ate' a janela passar - a reserva sumiria da tela do titular e
    continuaria de pe' na calcada.
    """
    r = _reserva(ponto, motorista, comeca=AGORA + timedelta(hours=2), empurrada=True)
    db.add(r)
    await db.flush()
    r.status = ReservationStatus.CANCELLED

    assert (await rs.sincronizar(db, agora=AGORA))["retiradas"] == 1

    await db.refresh(r)
    assert r.pushed_to_hardware is False
    assert len(await _comandos(db, ponto, "clear_reservation")) == 1


async def test_janela_que_passou_e_retirada(db, ponto, motorista):
    """Reserva nao usada tambem prende a vaga: o `expirar_reservas_vencidas`
    devolve a potencia ao rateio, e isto devolve o conector."""
    r = _reserva(ponto, motorista, comeca=AGORA - timedelta(hours=3), empurrada=True)
    db.add(r)
    await db.flush()

    assert (await rs.sincronizar(db, agora=AGORA))["retiradas"] == 1

    await db.refresh(r)
    assert r.pushed_to_hardware is False


async def test_reserva_consumida_e_retirada(db, ponto, motorista):
    r = _reserva(ponto, motorista, comeca=AGORA + timedelta(hours=2), empurrada=True)
    db.add(r)
    await db.flush()
    r.status = ReservationStatus.CONSUMED

    assert (await rs.sincronizar(db, agora=AGORA))["retiradas"] == 1
    await db.refresh(r)
    assert r.pushed_to_hardware is False


# ------------------------------------------------------------------ reconciliacao


async def test_passar_de_novo_nao_fala_com_o_equipamento(db, ponto, motorista):
    """O worker chama a cada varredura, em segundos.

    Sem a comparacao com o estado atual, cada ciclo reescreveria os tres
    registradores de toda reserva viva da rede - trafego Modbus constante para
    nao mudar nada.
    """
    db.add(_reserva(ponto, motorista, comeca=AGORA + timedelta(hours=2)))
    await db.flush()
    await rs.sincronizar(db, agora=AGORA)
    antes = len(await _comandos(db, ponto))

    resultado = await rs.sincronizar(db, agora=AGORA)

    assert resultado == {"empurradas": 0, "retiradas": 0, "falhas": 0}
    assert len(await _comandos(db, ponto)) == antes


async def test_equipamento_fora_do_ar_nao_marca_e_tenta_de_novo(db, ponto, motorista, monkeypatch):
    """Falar com o equipamento pode falhar, e a reserva continua valendo.

    `session_service` e' a autoridade sobre a reserva; o registrador e' reforco.
    Marcar `pushed_to_hardware` sem ter conseguido escrever trocaria uma reserva
    que vale so' no software por uma linha dizendo que o equipamento sabe.
    """

    async def tomb(self, *a, **k):
        raise TimeoutError("ponto nao responde")

    monkeypatch.setattr(SimulatedChargePointDriver, "push_reservation", tomb)
    r = _reserva(ponto, motorista, comeca=AGORA + timedelta(hours=2))
    db.add(r)
    await db.flush()

    assert (await rs.sincronizar(db, agora=AGORA))["falhas"] == 1

    await db.refresh(r)
    assert r.pushed_to_hardware is False
    (registro,) = await _comandos(db, ponto, "push_reservation")
    assert registro.success is False, "a tentativa fracassada tambem e' prova"

    monkeypatch.undo()
    assert (await rs.sincronizar(db, agora=AGORA))["empurradas"] == 1


async def test_uma_reserva_nao_mexe_no_ponto_da_outra(db, ponto, segundo_ponto, motorista):
    db.add(_reserva(ponto, motorista, comeca=AGORA + timedelta(hours=2)))
    await db.flush()

    await rs.sincronizar(db, agora=AGORA)

    assert await _comandos(db, segundo_ponto) == []
