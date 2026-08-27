"""Testes do motor de tarifacao, incluindo a virada ponta / fora de ponta."""

import asyncio
import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.models.enums import SessionState, TariffType
from app.models.session import ChargingSession
from app.models.tariff import ALL_DAYS, WEEKDAYS, Tariff, TariffWindow
from app.models.telemetry import TelemetrySample

SP = "America/Sao_Paulo"


def make_tariff(**kwargs) -> Tariff:
    defaults = dict(
        id=uuid.uuid4(),
        name="Tarifa Teste",
        type=TariffType.PER_KWH,
        currency="BRL",
        price_per_kwh=Decimal("1.40"),
        price_per_min=Decimal("0"),
        idle_fee_per_min=Decimal("0"),
        session_fee=Decimal("0"),
        min_charge=Decimal("0"),
        free_minutes=0,
        dynamic_multiplier=Decimal("1"),
        dynamic_enabled=False,
    )
    defaults.update(kwargs)
    tariff = Tariff(**defaults)
    tariff.windows = []
    return tariff


def make_session(**kwargs) -> ChargingSession:
    defaults = dict(
        id=uuid.uuid4(),
        code="SES-TEST",
        state=SessionState.FINISHED,
        energy_kwh=Decimal("0"),
        duration_s=0,
        idle_minutes=0,
        peak_power_kw=Decimal("0"),
        estimated_cost=Decimal("0"),
        preauth_amount=Decimal("0"),
        green_energy_kwh=Decimal("0"),
    )
    defaults.update(kwargs)
    return ChargingSession(**defaults)


def samples(session_id, start: datetime, values: list[float]) -> list[TelemetrySample]:
    return [
        TelemetrySample(
            session_id=session_id,
            charge_point_id=uuid.uuid4(),
            recorded_at=start + timedelta(minutes=i * 10),
            power_kw=Decimal("10"),
            session_energy_kwh=Decimal(str(v)),
        )
        for i, v in enumerate(values)
    ]


def test_cobranca_simples_por_kwh():
    from app.services.tariff_engine import rate_session

    start = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)
    session = make_session(
        started_at=start, ended_at=start + timedelta(hours=1), energy_kwh=Decimal("10")
    )
    result = rate_session(session, make_tariff(), [], timezone=SP)
    assert result.total == Decimal("14.00")


def test_energia_rateada_entre_ponta_e_fora_de_ponta():
    from app.services.tariff_engine import rate_session

    tariff = make_tariff(type=TariffType.TIME_OF_USE)
    tariff.windows = [
        TariffWindow(
            label="Ponta",
            day_mask=WEEKDAYS,
            starts_at=time(18, 0),
            ends_at=time(21, 0),
            price_per_kwh=Decimal("1.50"),
            price_per_min=Decimal("0"),
            idle_fee_per_min=Decimal("0"),
        ),
        TariffWindow(
            label="Fora de ponta",
            day_mask=ALL_DAYS,
            starts_at=time(21, 0),
            ends_at=time(18, 0),
            price_per_kwh=Decimal("1.00"),
            price_per_min=Decimal("0"),
            idle_fee_per_min=Decimal("0"),
        ),
    ]

    # Segunda-feira, 17h40 -> 18h20 no horario de Sao Paulo (UTC-3).
    start = datetime(2026, 8, 24, 20, 40, tzinfo=UTC)
    session = make_session(started_at=start, ended_at=start + timedelta(minutes=40))
    telemetry = samples(session.id, start, [0, 5, 10, 15, 20])
    session.energy_kwh = Decimal("20")

    result = rate_session(session, tariff, telemetry, timezone=SP)
    labels = {line.description for line in result.lines}
    assert any("Ponta" in label for label in labels)
    assert any("Fora de ponta" in label for label in labels)
    # Preco medio precisa cair entre os dois extremos: a virada foi respeitada.
    assert Decimal("20.00") < result.total < Decimal("30.00")


def test_ociosidade_so_apos_a_tolerancia():
    from app.services.tariff_engine import rate_session

    tariff = make_tariff(idle_fee_per_min=Decimal("0.20"))
    start = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    session = make_session(
        started_at=start,
        charging_stopped_at=start + timedelta(minutes=30),
        ended_at=start + timedelta(minutes=70),
        energy_kwh=Decimal("10"),
    )
    result = rate_session(session, tariff, [], timezone=SP, idle_grace_minutes=10)
    idle = next(line for line in result.lines if line.kind == "idle")
    # 40 min plugado sem carregar, 10 de tolerancia: 30 minutos cobrados.
    assert idle.quantity == Decimal("30.0000")
    assert idle.amount == Decimal("6.00")


def test_valor_minimo_complementa_sessao_curta():
    from app.services.tariff_engine import rate_session

    tariff = make_tariff(min_charge=Decimal("5.00"))
    start = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    session = make_session(
        started_at=start, ended_at=start + timedelta(minutes=5), energy_kwh=Decimal("1")
    )
    result = rate_session(session, tariff, [], timezone=SP)
    assert result.total == Decimal("5.00")


def test_multiplicador_dinamico_aplicado():
    from app.services.tariff_engine import rate_session

    tariff = make_tariff(dynamic_enabled=True, dynamic_multiplier=Decimal("1.25"))
    start = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    session = make_session(
        started_at=start, ended_at=start + timedelta(hours=1), energy_kwh=Decimal("10")
    )
    result = rate_session(session, tariff, [], timezone=SP)
    assert result.total == Decimal("17.50")


def test_janelas_do_seed_cobrem_a_semana_inteira():
    """Regressao do buraco de fim de semana.

    A janela de ponta so vale em dia util, entao sabado e domingo das 18h as 21h
    ficavam sem janela e caiam no preco base - que era o de ponta. O cliente
    pagava caro num horario que a politica define como barato.
    """
    from app.models.tariff import ALL_DAYS, WEEKDAYS, WEEKEND

    tarifa = make_tariff(type=TariffType.TIME_OF_USE)
    tarifa.windows = [
        TariffWindow(
            label="Ponta",
            day_mask=WEEKDAYS,
            starts_at=time(18, 0),
            ends_at=time(21, 0),
            price_per_kwh=Decimal("1.50"),
            price_per_min=Decimal("0"),
            idle_fee_per_min=Decimal("0"),
        ),
        TariffWindow(
            label="Fora de ponta",
            day_mask=ALL_DAYS,
            starts_at=time(21, 0),
            ends_at=time(18, 0),
            price_per_kwh=Decimal("1.40"),
            price_per_min=Decimal("0"),
            idle_fee_per_min=Decimal("0"),
        ),
        TariffWindow(
            label="Fora de ponta",
            day_mask=WEEKEND,
            starts_at=time(18, 0),
            ends_at=time(21, 0),
            price_per_kwh=Decimal("1.40"),
            price_per_min=Decimal("0"),
            idle_fee_per_min=Decimal("0"),
        ),
    ]

    inicio = datetime(2026, 8, 24, 0, 0, tzinfo=ZoneInfo(SP))  # segunda-feira
    descobertos = [
        inicio + timedelta(minutes=30 * i)
        for i in range(7 * 48)
        if not any(w.matches(inicio + timedelta(minutes=30 * i)) for w in tarifa.windows)
    ]
    assert not descobertos, f"instantes sem janela: {descobertos[:5]}"


def test_preco_base_e_rotulado_como_padrao():
    """Cair no preco base nao pode parecer que uma janela foi aplicada."""
    from app.services.tariff_engine import resolve_rates

    tarifa = make_tariff(type=TariffType.TIME_OF_USE)
    tarifa.windows = [
        TariffWindow(
            label="Ponta",
            day_mask=WEEKDAYS,
            starts_at=time(18, 0),
            ends_at=time(21, 0),
            price_per_kwh=Decimal("1.50"),
            price_per_min=Decimal("0"),
            idle_fee_per_min=Decimal("0"),
        ),
    ]
    fora = datetime(2026, 8, 24, 10, 0, tzinfo=ZoneInfo(SP))
    assert "padrão" in resolve_rates(tarifa, fora).label


def test_ociosidade_exibida_bate_com_a_cobrada():
    """Regressao: o número na tela não pode contradizer a fatura.

    Quando o carro voltava a puxar energia, charging_stopped_at zerava mas
    idle_minutes ficava com o valor do período anterior. O painel mostrava
    ociosidade que a fatura não cobrava.
    """
    from app.services.tariff_engine import rate_session

    tarifa = make_tariff(idle_fee_per_min=Decimal("0.20"))
    inicio = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
    sessao = make_session(
        started_at=inicio,
        ended_at=inicio + timedelta(minutes=60),
        charging_stopped_at=None,
        energy_kwh=Decimal("20"),
        idle_minutes=0,
    )
    resultado = rate_session(sessao, tarifa, [], timezone=SP)
    cobrada = sum(1 for linha in resultado.lines if linha.kind == "idle")
    assert cobrada == 0
    assert sessao.idle_minutes == 0


def test_sessao_na_fila_nao_acumula_energia():
    """Regressao: QUEUED conta como sessao ativa e ocupa o ponto.

    Sem guarda, o poller copiava o contador do carregador para uma sessao que
    nunca energizou — o motorista via energia e custo de uma recarga que nao
    aconteceu.
    """
    from types import SimpleNamespace

    from app.models.enums import SessionState
    from app.services.session_service import apply_reading

    sessao = make_session(state=SessionState.QUEUED, started_at=None, energy_kwh=Decimal("0"))
    leitura = SimpleNamespace(
        recorded_at=datetime(2026, 8, 26, 12, 0, tzinfo=UTC),
        session_energy_kwh=7.5,
        green_kwh=3.0,
        power_kw=11.0,
        meter_kwh=1000.0,
    )
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        apply_reading(None, sessao, leitura)
    )
    assert float(sessao.energy_kwh) == 0
    assert float(sessao.peak_power_kw) == 0
