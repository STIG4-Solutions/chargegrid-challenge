"""Previsao de demanda e custo evitado.

A conta que estes testes protegem e' a que vira dinheiro: no Grupo A a demanda
(kW) e' contratada e faturada pela MAIOR media de 15 minutos do mes. Errar aqui
nao produz numero estranho na tela - produz decisao errada sobre um contrato.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.models.site import SiteMeterReading
from app.services import demand_service as ds


async def _leituras(db, site, *, horas: int, predio: float, solar: float = 0.0, ev: float = 0.0):
    """Historico sintetico, uma leitura por minuto."""
    inicio = datetime.now(UTC) - timedelta(hours=horas)
    for n in range(horas * 60):
        db.add(
            SiteMeterReading(
                id=uuid.uuid4(),
                site_id=site.id,
                recorded_at=inicio + timedelta(minutes=n),
                grid_import_kw=max(0.0, predio + ev - solar),
                pv_kw=solar,
                battery_kw=0.0,
                building_load_kw=predio,
                ev_load_kw=ev,
            )
        )
    await db.flush()


# ------------------------------------------------------------------- previsao


async def test_sem_historico_a_previsao_nao_inventa(db, site):
    p = await ds.prever_demanda(db, site, horizonte_horas=2)
    assert p.dias_de_historico == 0
    assert all(f.demanda_prevista_kw == 0 for f in p.fatias)
    assert not p.as_dict()["risco"]


async def test_fatias_sao_de_quinze_minutos(db, site):
    """E' a janela que a distribuidora integra; outra daria numero que nao fatura."""
    p = await ds.prever_demanda(db, site, horizonte_horas=3)
    assert len(p.fatias) == 12
    for a, b in zip(p.fatias, p.fatias[1:], strict=False):
        assert (b.inicio - a.inicio) == timedelta(minutes=15)


async def test_previsao_usa_o_perfil_do_predio(db, site):
    await _leituras(db, site, horas=48, predio=40.0)
    p = await ds.prever_demanda(db, site, horizonte_horas=2)
    assert all(abs(f.predio_kw - 40.0) < 0.01 for f in p.fatias)


async def test_solar_abate_a_demanda(db, site):
    site.allow_pv_kw = True
    await db.flush()
    await _leituras(db, site, horas=48, predio=40.0, solar=15.0)
    p = await ds.prever_demanda(db, site, horizonte_horas=2)
    assert all(abs(f.demanda_prevista_kw - 25.0) < 0.01 for f in p.fatias)


async def test_acusa_risco_quando_passa_do_teto(db, site):
    """O caso que justifica a feature: o perfil sozinho ja estoura."""
    site.grid_limit_kw = 30.0
    site.contracted_demand_kw = 30.0
    await db.flush()
    await _leituras(db, site, horas=48, predio=50.0)

    p = await ds.prever_demanda(db, site, horizonte_horas=2)
    assert p.as_dict()["risco"] is True
    assert p.primeira_excedente is not None


async def test_tolerancia_de_cinco_por_cento_e_respeitada(db, site):
    """Entre o contratado e o teto nao ha ultrapassagem - e' da norma."""
    site.grid_limit_kw = 100.0
    site.contracted_demand_kw = 100.0
    await db.flush()
    await _leituras(db, site, horas=48, predio=103.0)

    p = await ds.prever_demanda(db, site, horizonte_horas=2)
    assert p.teto_com_tolerancia_kw == 105.0
    assert not p.as_dict()["risco"], "103 kW está dentro da tolerância de 5%"


async def test_injecao_na_rede_nao_vira_demanda_negativa(db, site):
    site.allow_pv_kw = True
    await db.flush()
    await _leituras(db, site, horas=48, predio=10.0, solar=50.0)
    p = await ds.prever_demanda(db, site, horizonte_horas=2)
    assert all(f.demanda_prevista_kw >= 0 for f in p.fatias)


async def test_site_sem_solar_ignora_a_geracao(db, site):
    """O medidor registra geracao, mas o site nao a conta no orcamento."""
    site.allow_pv_kw = False
    await db.flush()
    await _leituras(db, site, horas=48, predio=40.0, solar=15.0)

    p = await ds.prever_demanda(db, site, horizonte_horas=2)
    assert all(f.solar_kw == 0.0 for f in p.fatias)
    assert all(abs(f.demanda_prevista_kw - 40.0) < 0.01 for f in p.fatias)


# -------------------------------------------------------------- custo evitado


async def _sessao_encerrada(db, ponto, motorista, *, inicio, fim):
    from app.models.enums import AuthMethod, SessionState
    from app.models.session import ChargingSession

    s = ChargingSession(
        id=uuid.uuid4(),
        code=f"D-{uuid.uuid4().hex[:6]}",
        site_id=ponto.site_id,
        charge_point_id=ponto.id,
        user_id=motorista.id,
        state=SessionState.BILLED,
        auth_method=AuthMethod.APP,
        started_at=inicio,
        ended_at=fim,
    )
    db.add(s)
    await db.flush()
    return s


async def test_sem_tarifa_o_resultado_sai_em_kw_e_nao_em_reais(db, site):
    """Numero em reais sem tarifa do contrato seria invencao."""
    await _leituras(db, site, horas=4, predio=40.0)
    r = await ds.custo_evitado(db, site, dias=1)
    assert r.as_dict()["tarifa_configurada"] is False
    assert r.evitado_brl == 0.0


async def test_sem_sessoes_os_dois_cenarios_coincidem(db, site):
    """Sem carro carregando, o rateio nao tinha o que segurar."""
    site.demand_tariff_brl_per_kw = 30.0
    await db.flush()
    await _leituras(db, site, horas=4, predio=40.0)

    r = await ds.custo_evitado(db, site, dias=1)
    assert abs(r.pico_real_kw - r.pico_sem_rateio_kw) < 0.01
    assert r.evitado_brl == 0.0


async def test_contrafactual_usa_a_potencia_nominal_do_ponto(db, site, ponto, motorista):
    """Sem teto, o ponto puxaria o nominal - e' o eletroposto sem controle."""
    site.demand_tariff_brl_per_kw = 30.0
    await db.flush()

    agora = datetime.now(UTC)
    await _sessao_encerrada(db, ponto, motorista, inicio=agora - timedelta(hours=3), fim=agora)
    # O medidor registrou pouco: o rateio segurou o ponto em 5 kW.
    await _leituras(db, site, horas=4, predio=20.0, ev=5.0)

    r = await ds.custo_evitado(db, site, dias=1)
    # O ponto do fixture e' 22 kW nominais.
    assert r.pico_sem_rateio_kw > r.pico_real_kw
    assert abs(r.pico_sem_rateio_kw - (20.0 + float(ponto.rated_kw))) < 0.5


async def test_ultrapassagem_e_cobrada_ao_dobro(db, site, ponto, motorista):
    """REN 1.000: o excedente sai ao dobro da tarifa de demanda."""
    site.grid_limit_kw = 20.0
    site.contracted_demand_kw = 20.0
    site.demand_tariff_brl_per_kw = 10.0
    await db.flush()

    agora = datetime.now(UTC)
    await _sessao_encerrada(db, ponto, motorista, inicio=agora - timedelta(hours=3), fim=agora)
    await _leituras(db, site, horas=4, predio=20.0, ev=0.0)

    r = await ds.custo_evitado(db, site, dias=1)
    esperado = r.ultrapassagem_sem_rateio_kw * 10.0 * 2.0
    assert abs(r.custo_sem_rateio_brl - esperado) < 0.01
    assert r.evitado_brl > 0, "o rateio evitou ultrapassagem e isso tem valor"


async def test_ponto_ocioso_nao_entra_no_contrafactual(db, site, ponto, segundo_ponto, motorista):
    """Supor o parque inteiro ligado inflaria o numero e o tornaria indefensavel."""
    site.demand_tariff_brl_per_kw = 30.0
    await db.flush()

    agora = datetime.now(UTC)
    await _sessao_encerrada(db, ponto, motorista, inicio=agora - timedelta(hours=3), fim=agora)
    await _leituras(db, site, horas=4, predio=20.0)

    r = await ds.custo_evitado(db, site, dias=1)
    dois_pontos = 20.0 + float(ponto.rated_kw) + float(segundo_ponto.rated_kw)
    assert r.pico_sem_rateio_kw < dois_pontos, "contou um ponto que estava ocioso"


async def test_sessao_fora_do_periodo_nao_conta(db, site, ponto, motorista):
    site.demand_tariff_brl_per_kw = 30.0
    await db.flush()

    antiga = datetime.now(UTC) - timedelta(days=40)
    await _sessao_encerrada(db, ponto, motorista, inicio=antiga, fim=antiga + timedelta(hours=1))
    await _leituras(db, site, horas=4, predio=20.0)

    r = await ds.custo_evitado(db, site, dias=1)
    assert abs(r.pico_sem_rateio_kw - 20.0) < 0.5
