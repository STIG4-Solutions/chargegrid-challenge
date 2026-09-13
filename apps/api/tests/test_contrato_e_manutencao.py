"""Simulador de contrato e manutencao preditiva.

O simulador responde "quanto contratar"; a manutencao responde "qual ponto vai
quebrar". As duas contas so' existem porque o sistema guarda historico - de
medicao num caso, de falha no outro.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.drivers.base import ChargePointReading
from app.models.charge_point import ChargePointFault
from app.models.site import SiteMeterReading
from app.services import demand_service as ds
from app.services import maintenance_service as ms
from app.services import telemetry_service


async def _leituras(db, site, *, horas: int, grid: float):
    inicio = datetime.now(UTC) - timedelta(hours=horas)
    for n in range(horas * 60):
        db.add(
            SiteMeterReading(
                id=uuid.uuid4(),
                site_id=site.id,
                recorded_at=inicio + timedelta(minutes=n),
                grid_import_kw=grid,
                pv_kw=0,
                battery_kw=0,
                building_load_kw=grid,
                ev_load_kw=0,
            )
        )
    await db.flush()


# ------------------------------------------------- simulador de contrato


async def test_sem_medicao_nao_ha_o_que_simular(db, site):
    r = await ds.simular_contrato(db, site, dias=30)
    assert r.opcoes == []
    assert r.as_dict()["melhor_kw"] is None


async def test_recomenda_contrato_proximo_do_pico(db, site):
    """Contratar muito acima do pico e' pagar folga o ano todo."""
    site.demand_tariff_brl_per_kw = 30.0
    site.contracted_demand_kw = 200.0
    await db.flush()
    await _leituras(db, site, horas=6, grid=40.0)

    r = await ds.simular_contrato(db, site, dias=1, passo_kw=5.0)
    assert r.melhor is not None
    # Com consumo estavel em 40 kW, o otimo fica logo abaixo por conta da
    # tolerancia de 5%: 40 kW de contrato ja cobre 42 kW medidos.
    assert 35 <= r.melhor.demanda_kw <= 45, r.melhor.demanda_kw
    assert r.as_dict()["economia_mensal_brl"] > 0


async def test_contrato_apertado_perde_para_a_ultrapassagem(db, site):
    """Abaixo do pico, a penalidade ao dobro come a economia do fixo."""
    site.demand_tariff_brl_per_kw = 30.0
    await db.flush()
    await _leituras(db, site, horas=6, grid=40.0)

    r = await ds.simular_contrato(db, site, dias=1, passo_kw=5.0)
    apertado = next(o for o in r.opcoes if o.demanda_kw == 10.0)
    otimo = r.melhor
    assert apertado.custo_total_brl > otimo.custo_total_brl
    assert apertado.janelas_excedidas > 0


async def test_a_curva_tem_um_minimo(db, site):
    """Se nao tiver, a recomendacao seria arbitraria."""
    site.demand_tariff_brl_per_kw = 30.0
    await db.flush()
    await _leituras(db, site, horas=6, grid=40.0)

    r = await ds.simular_contrato(db, site, dias=1, passo_kw=5.0)
    custos = [o.custo_total_brl for o in r.opcoes]
    i = custos.index(min(custos))
    assert 0 < i < len(custos) - 1, "o mínimo caiu na borda: a varredura é curta demais"


async def test_sem_tarifa_a_simulacao_nao_promete_reais(db, site):
    await _leituras(db, site, horas=6, grid=40.0)
    r = await ds.simular_contrato(db, site, dias=1)
    assert r.as_dict()["tarifa_configurada"] is False


# ------------------------------------------------- manutencao preditiva


def _leitura(*, faults=(), flags=()):
    return ChargePointReading(
        recorded_at=datetime.now(UTC),
        hw_status="charging",
        car_connection="charging",
        power_kw=7.0,
        session_energy_kwh=1.0,
        faults=list(faults),
        operational_flags=list(flags),
    )


async def test_alarme_abre_episodio_e_persiste(db, ponto):
    await telemetry_service.ingest(db, ponto, _leitura(flags=["Alarme de aterramento"]))
    episodios = (
        (
            await db.execute(
                select(ChargePointFault).where(ChargePointFault.charge_point_id == ponto.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(episodios) == 1
    assert episodios[0].resolved_at is None
    assert episodios[0].terminal is False


async def test_o_mesmo_alarme_nao_vira_um_episodio_por_ciclo(db, ponto):
    """O poller le a cada 5s; sem isso um minuto de alarme viraria doze episodios."""
    for _ in range(5):
        await telemetry_service.ingest(db, ponto, _leitura(flags=["Alarme de aterramento"]))

    episodios = (
        (
            await db.execute(
                select(ChargePointFault).where(ChargePointFault.charge_point_id == ponto.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(episodios) == 1
    assert episodios[0].ciclos == 5


async def test_alarme_que_some_fecha_o_episodio(db, ponto):
    await telemetry_service.ingest(db, ponto, _leitura(flags=["Alarme de aterramento"]))
    await telemetry_service.ingest(db, ponto, _leitura())

    episodio = (
        (
            await db.execute(
                select(ChargePointFault).where(ChargePointFault.charge_point_id == ponto.id)
            )
        )
        .scalars()
        .one()
    )
    assert episodio.resolved_at is not None


async def test_recorrencia_vira_episodios_separados(db, ponto, site):
    """E' a recorrencia, e nao a duracao, que caracteriza manutencao."""
    for _ in range(3):
        for _ in range(2):  # dois ciclos: acima do corte de ruido
            await telemetry_service.ingest(db, ponto, _leitura(flags=["Alarme de aterramento"]))
        await telemetry_service.ingest(db, ponto, _leitura())

    r = await ms.pontos_em_atencao(db, site.id, dias=30)
    assert not r["sem_ocorrencias"]
    assert r["pontos"][0]["episodios"] == 3


async def test_episodio_de_um_ciclo_e_ruido(db, ponto, site):
    """Um bit que pisca uma leitura e' ruido do barramento, nao sintoma."""
    await telemetry_service.ingest(db, ponto, _leitura(flags=["Alarme de aterramento"]))
    await telemetry_service.ingest(db, ponto, _leitura())

    r = await ms.pontos_em_atencao(db, site.id, dias=30)
    assert r["sem_ocorrencias"], "um único ciclo não deveria virar ocorrência"


async def test_falha_terminal_tem_prioridade_alta(db, ponto, site):
    """Terminal ja encerrou uma recarga; alarme ainda nao parou nada.

    Carrega o ponto com a conexao, como o poller faz: a falha terminal encerra
    a sessao, e encerrar manda comando ao equipamento - que precisa saber por
    onde falar com ele.
    """
    from sqlalchemy.orm import selectinload

    from app.models.charge_point import ChargePoint

    com_conexao = (
        await db.execute(
            select(ChargePoint)
            .where(ChargePoint.id == ponto.id)
            .options(selectinload(ChargePoint.connection))
        )
    ).scalar_one()

    for _ in range(2):
        await telemetry_service.ingest(db, com_conexao, _leitura(faults=["Falha de aterramento"]))

    r = await ms.pontos_em_atencao(db, site.id, dias=30)
    assert r["pontos"][0]["prioridade"] == "alta"


async def test_sem_falha_a_lista_fica_vazia(db, ponto, site):
    await telemetry_service.ingest(db, ponto, _leitura())
    r = await ms.pontos_em_atencao(db, site.id, dias=30)
    assert r["sem_ocorrencias"]


def test_simulacao_marca_amostra_insuficiente_como_nao_confiavel():
    """Poucas janelas nao autorizam recomendar demanda menor.

    A tarifa de demanda e cobrada pelo maior pico do mes. Com meia duzia de
    janelas medidas, nada garante que esse pico ja apareceu - e a recomendacao
    de "contrate menos" custaria ultrapassagem ao dobro, todo mes. O numero
    continua sendo devolvido; o que a guarda faz e nao chama-lo de conselho.
    """
    magra = ds.SimulacaoDeContrato(
        atual_kw=75.0,
        tarifa_brl_por_kw=28.5,
        pico_medido_kw=32.0,
        janelas_analisadas=2,
        dias=30,
        opcoes=[ds.OpcaoDeContrato(30.0, 855.0, 0.0, 0)],
    )
    assert magra.as_dict()["confiavel"] is False

    farta = ds.SimulacaoDeContrato(
        atual_kw=75.0,
        tarifa_brl_por_kw=28.5,
        pico_medido_kw=32.0,
        janelas_analisadas=ds.JANELAS_MINIMAS_CONFIANCA,
        dias=30,
        opcoes=[ds.OpcaoDeContrato(30.0, 855.0, 0.0, 0)],
    )
    assert farta.as_dict()["confiavel"] is True
