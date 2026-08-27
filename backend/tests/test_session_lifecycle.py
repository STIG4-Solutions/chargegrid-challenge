"""Maquina de estados da sessao de recarga.

Cada teste aqui corresponde a um defeito que ja aconteceu ou que custaria caro:
sessao que acumula energia sem ter comecado, ponto que fica bloqueado depois de
uma falha, fila que nao anda. O teste de fumaca cobre o caminho feliz de ponta a
ponta; estes cobrem as bordas, que e' onde o dinheiro e a disponibilidade
escorrem.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.errors import Conflict, InsufficientPower, InvalidTransition
from app.drivers.base import ChargePointReading
from app.models.enums import AuthMethod, ChargePointStatus, SessionState, StopReason
from app.models.session import ChargingSession
from app.services import session_service


async def _autorizar(db, ponto, motorista=None):
    return await session_service.authorize(
        db, ponto, user=motorista, auth_method=AuthMethod.OPERATOR
    )


def _leitura(*, potencia=11.0, energia=0.0, quando=None, verde=None):
    return ChargePointReading(
        recorded_at=quando or datetime.now(UTC),
        power_kw=potencia,
        session_energy_kwh=energia,
        green_kwh=verde,
    )


# ------------------------------------------------------------------ autorizacao


async def test_autorizar_cria_sessao_com_codigo_legivel(db, ponto, motorista):
    sessao = await _autorizar(db, ponto, motorista)
    assert sessao.state == SessionState.AUTHORIZING
    assert sessao.code.startswith("SES-")
    assert sessao.charge_point_id == ponto.id
    assert sessao.user_id == motorista.id


async def test_codigos_de_sessao_nao_colidem(db):
    """A sequence do Postgres existe porque contagem + random colidia quando
    duas sessoes comecavam no mesmo instante - e o codigo tem unique constraint."""
    codigos = {await session_service._next_code(db) for _ in range(20)}
    assert len(codigos) == 20
    assert all(c.startswith("SES-") for c in codigos)


async def test_um_ponto_nao_aceita_duas_sessoes_ao_mesmo_tempo(db, ponto, motorista):
    """Guarda que impede duas cobrancas simultaneas na mesma vaga."""
    await _autorizar(db, ponto, motorista)
    with pytest.raises(Conflict):
        await _autorizar(db, ponto, motorista)


async def test_autorizar_herda_a_tarifa_do_ponto(db, ponto, motorista, tarifa):
    sessao = await _autorizar(db, ponto, motorista)
    assert sessao.tariff_id == tarifa.id


# ----------------------------------------------------------------------- inicio


async def test_iniciar_energiza_e_marca_o_ponto(db, ponto, motorista):
    sessao = await _autorizar(db, ponto, motorista)
    await session_service.start(db, sessao, ponto)
    assert sessao.state == SessionState.CHARGING
    assert sessao.started_at is not None
    assert ponto.status == ChargePointStatus.CHARGING


async def test_sem_potencia_a_sessao_entra_na_fila(db, site, ponto, motorista):
    """Regressao: a sessao ficava presa em STARTING e bloqueava o eletroposto."""
    site.grid_limit_kw = 1
    site.reserved_kw = 0
    await db.flush()

    sessao = await _autorizar(db, ponto, motorista)
    await session_service.start(db, sessao, ponto)

    assert sessao.state == SessionState.QUEUED
    assert sessao.queued_at is not None
    assert sessao.started_at is None


async def test_sem_potencia_e_sem_fila_a_sessao_e_recusada(db, site, ponto, motorista):
    site.grid_limit_kw = 1
    site.reserved_kw = 0
    await db.flush()

    sessao = await _autorizar(db, ponto, motorista)
    with pytest.raises(InsufficientPower):
        await session_service.start(db, sessao, ponto, enqueue=False)


# ------------------------------------------------------------------- telemetria


async def test_sessao_na_fila_nao_acumula_energia(db, site, ponto, motorista):
    """Regressao: a tela mostrava 0,41 kWh e R$ 5,00 para quem nunca carregou.

    O poller copiava o contador do carregador para qualquer sessao ativa, e
    QUEUED conta como ativa porque ocupa o ponto.
    """
    site.grid_limit_kw = 1
    site.reserved_kw = 0
    await db.flush()

    sessao = await _autorizar(db, ponto, motorista)
    await session_service.start(db, sessao, ponto)
    assert sessao.state == SessionState.QUEUED

    await session_service.apply_reading(db, sessao, _leitura(potencia=7.0, energia=3.5))

    assert float(sessao.energy_kwh) == 0
    assert sessao.duration_s == 0
    assert float(sessao.estimated_cost) == 0


async def test_energia_so_sobe(db, ponto, motorista):
    """O contador do carregador zera ao reconectar; a sessao nao pode regredir."""
    sessao = await _autorizar(db, ponto, motorista)
    await session_service.start(db, sessao, ponto)

    await session_service.apply_reading(db, sessao, _leitura(energia=8.0))
    assert float(sessao.energy_kwh) == 8.0

    await session_service.apply_reading(db, sessao, _leitura(energia=0.0))
    assert float(sessao.energy_kwh) == 8.0


async def test_pico_de_potencia_guarda_o_maximo(db, ponto, motorista):
    sessao = await _autorizar(db, ponto, motorista)
    await session_service.start(db, sessao, ponto)

    await session_service.apply_reading(db, sessao, _leitura(potencia=11.0))
    await session_service.apply_reading(db, sessao, _leitura(potencia=18.5))
    await session_service.apply_reading(db, sessao, _leitura(potencia=6.0))

    assert float(sessao.peak_power_kw) == 18.5


async def test_ociosidade_comeca_quando_a_potencia_zera(db, ponto, motorista):
    sessao = await _autorizar(db, ponto, motorista)
    await session_service.start(db, sessao, ponto)
    inicio = datetime.now(UTC)

    await session_service.apply_reading(db, sessao, _leitura(potencia=0.0, quando=inicio))
    assert sessao.charging_stopped_at is not None

    await session_service.apply_reading(
        db, sessao, _leitura(potencia=0.0, quando=inicio + timedelta(minutes=25))
    )
    assert sessao.idle_minutes == 25


async def test_carro_voltando_a_puxar_zera_a_ociosidade(db, ponto, motorista):
    """Regressao: o painel exibia minutos ociosos que a fatura nao cobrava."""
    sessao = await _autorizar(db, ponto, motorista)
    await session_service.start(db, sessao, ponto)
    inicio = datetime.now(UTC)

    await session_service.apply_reading(db, sessao, _leitura(potencia=0.0, quando=inicio))
    await session_service.apply_reading(
        db, sessao, _leitura(potencia=0.0, quando=inicio + timedelta(minutes=12))
    )
    assert sessao.idle_minutes == 12

    await session_service.apply_reading(
        db, sessao, _leitura(potencia=9.0, quando=inicio + timedelta(minutes=13))
    )
    assert sessao.idle_minutes == 0
    assert sessao.charging_stopped_at is None


# ---------------------------------------------------------------------- limites


def _sessao_nua(**campos) -> ChargingSession:
    base = {"energy_kwh": 0, "duration_s": 0, "estimated_cost": 0, "preauth_amount": 0}
    return ChargingSession(**{**base, **campos})


def test_limite_de_energia():
    assert (
        session_service.reached_limit(_sessao_nua(limit_kwh=20, energy_kwh=20.1))
        == StopReason.ENERGY_LIMIT
    )


def test_limite_de_tempo():
    assert (
        session_service.reached_limit(_sessao_nua(limit_minutes=30, duration_s=1800))
        == StopReason.TIME_LIMIT
    )


def test_limite_de_valor():
    assert (
        session_service.reached_limit(_sessao_nua(limit_amount=25, estimated_cost=25))
        == StopReason.AMOUNT_LIMIT
    )


def test_preautorizacao_tambem_e_teto():
    """Sem isto, uma pre-autorizacao de R$ 30 nao impediria uma conta de R$ 200."""
    assert (
        session_service.reached_limit(_sessao_nua(preauth_amount=30, estimated_cost=31))
        == StopReason.AMOUNT_LIMIT
    )


def test_sem_limite_configurado_nao_para():
    assert session_service.reached_limit(_sessao_nua(energy_kwh=999, duration_s=99999)) is None


# ------------------------------------------------------------------ encerramento


async def test_encerrar_libera_o_ponto(db, ponto, motorista):
    sessao = await _autorizar(db, ponto, motorista)
    await session_service.start(db, sessao, ponto)
    await session_service.apply_reading(db, sessao, _leitura(energia=12.0))

    await session_service.stop(db, sessao, ponto, reason=StopReason.REMOTE)

    assert sessao.state in {SessionState.FINISHED, SessionState.BILLED}
    assert sessao.ended_at is not None
    assert sessao.stop_reason == StopReason.REMOTE
    assert ponto.status == ChargePointStatus.AVAILABLE


async def test_encerrar_duas_vezes_e_barrado(db, ponto, motorista):
    """Sem a guarda, a segunda chamada emitiria uma fatura duplicada."""
    sessao = await _autorizar(db, ponto, motorista)
    await session_service.start(db, sessao, ponto)
    await session_service.stop(db, sessao, ponto)

    with pytest.raises(InvalidTransition):
        await session_service.stop(db, sessao, ponto)


async def test_falha_nao_deixa_o_ponto_bloqueado(db, ponto, motorista):
    """Regressao: sessao presa em AUTHORIZING inutilizava o eletroposto."""
    sessao = await _autorizar(db, ponto, motorista)
    await session_service.fail(db, sessao, "ponto nao respondeu")
    await db.flush()

    assert sessao.state == SessionState.ERROR
    assert sessao.error_message

    outra = await _autorizar(db, ponto, motorista)
    assert outra.id != sessao.id
    ativa = await session_service.active_session_for(db, ponto.id)
    assert ativa is not None and ativa.id == outra.id


async def test_apenas_uma_sessao_ativa_por_ponto(db, ponto, motorista):
    sessao = await _autorizar(db, ponto, motorista)
    await session_service.start(db, sessao, ponto)
    await db.flush()

    ativas = (
        (
            await db.execute(
                select(ChargingSession).where(
                    ChargingSession.charge_point_id == ponto.id,
                    ChargingSession.state.in_(
                        [SessionState.CHARGING, SessionState.QUEUED, SessionState.STARTING]
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(ativas) == 1
    assert ativas[0].id == sessao.id
