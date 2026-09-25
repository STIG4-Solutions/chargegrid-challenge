"""O preco travado no inicio da recarga, de ponta a ponta contra o banco.

A cor do site muda pelo caminho real - reserva predial alterada e um ciclo de
`rebalance_site` -, e nao escrevendo nas colunas da bandeira: o teste e' sobre o
que o motorista paga, nao sobre onde o numero mora.

Site do conftest: rede de 75 kW, reserva de 20 kW. Tarifa: R$ 2,00/kWh.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.config import settings
from app.drivers.base import ChargePointReading
from app.models.enums import AuthMethod, SessionState
from app.services import power_manager, session_service


@pytest.fixture
def ligada(monkeypatch):
    monkeypatch.setattr(settings, "precificacao_dinamica", True)


async def _pintar(db, site, reserva_kw: float) -> None:
    """Muda a folga do site e roda um ciclo: 45 kW amarela, 65 kW vermelha."""
    site.reserved_kw = reserva_kw
    await db.flush()
    await power_manager.rebalance_site(db, site.id, triggered_by="teste")


async def _carregar_e_faturar(db, sessao, ponto, kwh: float = 20.0):
    await session_service.apply_reading(
        db,
        sessao,
        ChargePointReading(recorded_at=datetime.now(UTC), power_kw=11.0, session_energy_kwh=kwh),
    )
    await session_service.stop(db, sessao, ponto)
    from app.services import billing_service

    return await billing_service.bill_session(db, sessao)


async def _iniciar(db, ponto, motorista):
    sessao = await session_service.authorize(
        db, ponto, user=motorista, auth_method=AuthMethod.OPERATOR
    )
    return await session_service.start(db, sessao, ponto)


async def test_o_preco_fica_o_do_inicio_mesmo_se_a_bandeira_muda(
    db, site, ponto, motorista, ligada
):
    await _pintar(db, site, 45)  # amarela
    sessao = await _iniciar(db, ponto, motorista)
    assert sessao.state == SessionState.CHARGING
    assert Decimal(str(sessao.multiplicador_travado)) == Decimal("1.15")
    assert sessao.cor_travada == "amarela"

    await _pintar(db, site, 65)  # o site fica vermelho no meio da recarga
    fatura = await _carregar_e_faturar(db, sessao, ponto)

    # 20 kWh x R$ 2,00 = R$ 40,00; x1,15 = R$ 46,00 - e nao os R$ 52,00 da vermelha.
    assert fatura.total == Decimal("46.00")


async def test_quem_espera_na_fila_paga_o_multiplicador_do_pedido(
    db, site, ponto, motorista, ligada
):
    # Reserva de 72 kW: sobram 3 de 75 (4%), abaixo do piso de 4,2 kW do ponto.
    # A sessao entra na fila com o site vermelho.
    await _pintar(db, site, 72)
    sessao = await _iniciar(db, ponto, motorista)
    assert sessao.state == SessionState.QUEUED
    assert Decimal(str(sessao.multiplicador_travado)) == Decimal("1.30")

    # A potencia volta, o site fica verde e a fila anda.
    await _pintar(db, site, 20)
    await session_service.promote_queue(db, site.id)
    await db.refresh(sessao)

    assert sessao.state == SessionState.CHARGING
    assert Decimal(str(sessao.multiplicador_travado)) == Decimal("1.30")
    assert sessao.cor_travada == "vermelha"


async def test_bandeira_velha_nao_trava_preco(db, site, ponto, motorista, ligada):
    await _pintar(db, site, 65)  # vermelha...
    site.bandeira_calculada_em = datetime.now(UTC) - timedelta(
        seconds=settings.bandeira_validade_s + 30
    )  # ...mas o rebalanceador parou ha' tempo
    await db.flush()

    sessao = await _iniciar(db, ponto, motorista)
    assert Decimal(str(sessao.multiplicador_travado)) == Decimal("1.00")
    assert sessao.cor_travada is None

    fatura = await _carregar_e_faturar(db, sessao, ponto)
    assert fatura.total == Decimal("40.00")


async def test_site_sem_bandeira_calculada_trava_neutro(db, site, ponto, motorista, ligada):
    sessao = await _iniciar(db, ponto, motorista)
    assert Decimal(str(sessao.multiplicador_travado)) == Decimal("1.00")
    assert sessao.cor_travada is None


async def test_com_a_flag_desligada_nada_e_travado_e_a_fatura_e_a_de_hoje(
    db, site, ponto, motorista
):
    # Mesmo com uma bandeira vermelha fresca gravada no site (de quando a flag
    # estava ligada), desligar a flag devolve o comportamento anterior.
    site.bandeira_cor = "vermelha"
    site.bandeira_multiplicador = Decimal("1.30")
    site.bandeira_calculada_em = datetime.now(UTC)
    await db.flush()

    sessao = await _iniciar(db, ponto, motorista)
    assert sessao.multiplicador_travado is None
    assert sessao.cor_travada is None

    fatura = await _carregar_e_faturar(db, sessao, ponto)
    assert fatura.total == Decimal("40.00")
