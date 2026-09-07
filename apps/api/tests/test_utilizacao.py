"""Ocupacao e retorno por ponto.

O que estes testes protegem nao e a aritmetica - e a honestidade do
denominador. Ocupacao e uma razao, e uma razao errada nao parece errada: ela
so' aponta o investimento para o lado errado, em silencio.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import SessionState
from app.services import utilization_service as us


def _janela(inicio_h: int, fim_h: int, base: datetime) -> tuple[datetime, datetime]:
    return (base + timedelta(hours=inicio_h), base + timedelta(hours=fim_h))


# ---------------------------------------------------------------- mesclagem


def test_falhas_sobrepostas_nao_contam_o_mesmo_tempo_duas_vezes():
    """Dois defeitos simultaneos sao um periodo parado, nao dois.

    Somar duracoes de episodios sobrepostos inflava as horas indisponiveis. Com
    folga suficiente isso zerava as horas disponiveis e o ponto passava a ser
    classificado como "indisponivel" tendo funcionado o mes inteiro.
    """
    base = datetime(2026, 1, 1, tzinfo=UTC)
    # trava aberta das 2h as 8h; medidor mudo das 5h as 10h. Parado: 2h-10h = 8h.
    unidas = us._mescla([_janela(2, 8, base), _janela(5, 10, base)])
    assert len(unidas) == 1
    assert (unidas[0][1] - unidas[0][0]).total_seconds() / 3600 == 8


def test_falhas_separadas_permanecem_separadas():
    base = datetime(2026, 1, 1, tzinfo=UTC)
    unidas = us._mescla([_janela(0, 2, base), _janela(6, 9, base)])
    assert len(unidas) == 2
    total = sum((f - i).total_seconds() / 3600 for i, f in unidas)
    assert total == 5


def test_mescla_ordena_antes_de_unir():
    """A entrada vem do banco sem ordem garantida."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    unidas = us._mescla([_janela(5, 10, base), _janela(2, 8, base)])
    assert len(unidas) == 1


# ------------------------------------------------------------- denominador


def test_ponto_quebrado_nao_e_classificado_como_ocioso():
    """Falha terminal sai do denominador.

    Sem isso, o ponto que passou 20 dos 30 dias quebrado aparecia com ocupacao
    baixissima e o rotulo "ocioso" - o conselho seria remove-lo, quando o certo
    e' conserta-lo. E o pior tipo de erro: leva a decisao para o lado oposto.
    """
    p = us.PontoUtilizado(
        charge_point_id=str(uuid.uuid4()),
        code="CP-01",
        name="Quebrado",
        rated_kw=22,
        horas_da_janela=30 * 24,
        horas_indisponiveis=20 * 24,
        horas_ocupadas=0.6 * (10 * 24),  # 60% das horas em que deu para atender
        receita_brl=1000.0,
    )
    assert p.horas_disponiveis == 10 * 24
    assert p.classificacao == "saudavel"
    assert 59 < p.ocupacao * 100 < 61


def test_horas_disponiveis_nunca_fica_negativa():
    """Falha aberta que comecou antes da janela pode exceder o periodo."""
    p = us.PontoUtilizado(
        charge_point_id=str(uuid.uuid4()),
        code="CP-02",
        name="Morto",
        rated_kw=22,
        horas_da_janela=24,
        horas_indisponiveis=999,
    )
    assert p.horas_disponiveis == 0
    assert p.ocupacao == 0
    assert p.receita_por_hora_disponivel == 0
    assert p.classificacao == "indisponivel"


def test_ocupacao_nao_passa_de_cem_por_cento():
    """A sessao pode continuar aberta durante a falha do proprio ponto."""
    p = us.PontoUtilizado(
        charge_point_id=str(uuid.uuid4()),
        code="CP-03",
        name="Travado",
        rated_kw=22,
        horas_da_janela=24,
        horas_indisponiveis=12,
        horas_ocupadas=24,
    )
    assert p.ocupacao == 1.0


# ------------------------------------------------------------- ociosidade


def test_ponto_cheio_mas_sem_consumir_e_bloqueado_e_nao_congestionado():
    """A distincao que justifica a taxa de ociosidade.

    Dois pontos com 80% de ocupacao pedem acoes opostas: um esta recusando
    cliente (falta ponto), o outro esta servindo de vaga de estacionamento
    (falta cobrar ociosidade). Sem separar, o operador compra hardware para
    resolver um problema de politica de preco.
    """
    comum = dict(
        charge_point_id=str(uuid.uuid4()), rated_kw=22, horas_da_janela=100, horas_ocupadas=80
    )
    congestionado = us.PontoUtilizado(code="CP-A", name="Disputado", horas_ociosas=4, **comum)
    bloqueado = us.PontoUtilizado(code="CP-B", name="Estacionamento", horas_ociosas=40, **comum)

    assert congestionado.classificacao == "congestionado"
    assert bloqueado.classificacao == "bloqueado"


def test_ociosidade_sem_ocupacao_nao_divide_por_zero():
    p = us.PontoUtilizado(
        charge_point_id=str(uuid.uuid4()), code="CP-Z", name="Novo", rated_kw=22,
        horas_da_janela=24,
    )
    assert p.ociosidade == 0.0
    assert p.classificacao == "ocioso"


# ------------------------------------------------------------------ banco


@pytest.fixture
async def _sessoes(db, site, ponto, segundo_ponto, motorista, agora):
    """Duas sessoes no CP-TESTE e uma, mais pobre, no segundo ponto."""
    from app.models.session import ChargingSession

    def nova(cp, horas_atras, duracao_h, kwh, brl, ocioso_min=0):
        inicio = agora - timedelta(hours=horas_atras)
        return ChargingSession(
            id=uuid.uuid4(),
            code=f"S-{uuid.uuid4().hex[:8]}",
            site_id=site.id,
            charge_point_id=cp.id,
            user_id=motorista.id,
            state=SessionState.BILLED,
            started_at=inicio,
            ended_at=inicio + timedelta(hours=duracao_h),
            duration_s=int(duracao_h * 3600),
            energy_kwh=kwh,
            estimated_cost=brl,
            idle_minutes=ocioso_min,
        )

    db.add_all(
        [
            nova(ponto, 48, 2, 30, 60),
            nova(ponto, 24, 3, 45, 90, ocioso_min=60),
            nova(segundo_ponto, 12, 1, 10, 20),
        ]
    )
    await db.flush()


async def test_relatorio_separa_os_pontos_e_ranqueia_por_receita_por_hora(
    db, site, _sessoes, agora
):
    r = await us.ocupacao_por_ponto(db, site.id, dias=30, agora=agora)

    assert r["sessoes_total"] == 3
    assert r["receita_total_brl"] == 170.0
    assert r["energia_total_kwh"] == 85.0

    por_codigo = {p["code"]: p for p in r["pontos"]}
    assert por_codigo["CP-TESTE"]["sessoes"] == 2
    assert por_codigo["CP-TESTE"]["receita_brl"] == 150.0
    assert por_codigo["CP-TESTE"]["horas_ocupadas"] == 5.0
    assert por_codigo["CP-TESTE"]["horas_ociosas"] == 1.0

    # A lista sai ordenada: o primeiro e o que mais rende por hora disponivel.
    assert r["pontos"][0]["receita_por_hora_brl"] >= r["pontos"][-1]["receita_por_hora_brl"]
    assert r["melhor"] == "CP-TESTE"


async def test_sessao_em_fila_nao_ocupa_o_conector(db, site, ponto, motorista, agora):
    """QUEUED e' carro esperando vaga, nao carro plugado.

    Contar a fila como ocupacao inflaria justamente o ponto mais concorrido -
    e a fila existe porque o ponto ja esta cheio, entao o erro se somava a si
    mesmo.
    """
    from app.models.session import ChargingSession

    db.add(
        ChargingSession(
            id=uuid.uuid4(),
            code="S-FILA",
            site_id=site.id,
            charge_point_id=ponto.id,
            user_id=motorista.id,
            state=SessionState.QUEUED,
            started_at=agora - timedelta(hours=5),
            duration_s=5 * 3600,
            energy_kwh=0,
            estimated_cost=0,
        )
    )
    await db.flush()

    r = await us.ocupacao_por_ponto(db, site.id, dias=30, agora=agora)
    alvo = next(p for p in r["pontos"] if p["code"] == ponto.code)
    assert alvo["sessoes"] == 0
    assert alvo["horas_ocupadas"] == 0.0


async def test_sessao_aberta_conta_ate_agora(db, site, ponto, motorista, agora):
    """Sem isto, o ponto que esta carregando neste instante parece o mais vazio."""
    from app.models.session import ChargingSession

    db.add(
        ChargingSession(
            id=uuid.uuid4(),
            code="S-ABERTA",
            site_id=site.id,
            charge_point_id=ponto.id,
            user_id=motorista.id,
            state=SessionState.CHARGING,
            started_at=agora - timedelta(hours=3),
            ended_at=None,
            duration_s=0,
            energy_kwh=20,
            estimated_cost=40,
        )
    )
    await db.flush()

    r = await us.ocupacao_por_ponto(db, site.id, dias=30, agora=agora)
    alvo = next(p for p in r["pontos"] if p["code"] == ponto.code)
    assert alvo["horas_ocupadas"] == pytest.approx(3.0, abs=0.1)


async def test_falha_terminal_reduz_as_horas_disponiveis(db, site, ponto, agora):
    from app.models.charge_point import ChargePointFault

    # Site antigo: a janela de 30 dias cabe inteira na idade dele.
    site.created_at = agora - timedelta(days=90)
    await db.flush()

    db.add(
        ChargePointFault(
            id=uuid.uuid4(),
            charge_point_id=ponto.id,
            label="trava do conector",
            terminal=True,
            first_seen_at=agora - timedelta(days=2),
            last_seen_at=agora - timedelta(days=1),
            resolved_at=agora - timedelta(days=1),
            ciclos=100,
        )
    )
    await db.flush()

    r = await us.ocupacao_por_ponto(db, site.id, dias=30, agora=agora)
    alvo = next(p for p in r["pontos"] if p["code"] == ponto.code)
    assert alvo["horas_indisponiveis"] == pytest.approx(24.0, abs=0.1)
    assert alvo["horas_disponiveis"] == pytest.approx(30 * 24 - 24, abs=0.1)


async def test_site_sem_pontos_devolve_relatorio_vazio(db, segundo_site, agora):
    r = await us.ocupacao_por_ponto(db, segundo_site.id, dias=30, agora=agora)
    assert r["pontos"] == []
    assert r["receita_total_brl"] == 0.0
    assert r["melhor"] is None


# -------------------------------------------------------------------- HTTP


async def test_rota_responde_e_respeita_o_papel(api, site, ponto, como_operador, como_motorista):
    """A rota e' do operador. Motorista nao ve o faturamento do site."""
    ok = await api.get("/api/v1/power/utilization/by-point", headers=como_operador)
    assert ok.status_code == 200
    assert "pontos" in ok.json()

    negado = await api.get("/api/v1/power/utilization/by-point", headers=como_motorista)
    assert negado.status_code == 403


async def test_rota_nao_vaza_o_site_do_vizinho(api, site, _sessoes, como_operador_vizinho):
    """Multi-tenant: o operador do outro site nao ve estes pontos.

    O escopo vem do token, nao da query - passar site_id alheio nao muda nada.
    """
    r = await api.get(
        f"/api/v1/power/utilization/by-point?site_id={site.id}", headers=como_operador_vizinho
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["sessoes_total"] == 0
    assert all(p["code"] != "CP-TESTE" for p in corpo["pontos"])


async def test_janela_nao_passa_da_idade_do_site(db, site, ponto, motorista, agora):
    """Um site instalado ontem nao tem 30 dias de ociosidade a explicar.

    Sem este limite o denominador era sempre `dias * 24`. Um site com duas
    horas de operacao aparecia com todos os pontos "ociosos" - a conta cobrava
    deles 29 dias em que nao existiam, e o painel recomendava desativar pontos
    recem-instalados.
    """
    site.created_at = agora - timedelta(days=2)
    await db.flush()

    r = await us.ocupacao_por_ponto(db, site.id, dias=30, agora=agora)
    assert r["dias"] == 30
    assert r["dias_efetivos"] == pytest.approx(2.0, abs=0.01)
    assert r["janela_completa"] is False

    alvo = next(p for p in r["pontos"] if p["code"] == ponto.code)
    assert alvo["horas_disponiveis"] == pytest.approx(48.0, abs=0.1)


async def test_sessao_anterior_ao_cadastro_estende_a_janela(db, site, ponto, motorista, agora):
    """Site migrado tem historico anterior a propria linha.

    Se o limite olhasse so o created_at, um site importado ontem descartaria
    meses de sessoes reais e a ocupacao dispararia sobre um denominador minusculo.
    """
    from app.models.session import ChargingSession

    site.created_at = agora - timedelta(hours=1)
    db.add(
        ChargingSession(
            id=uuid.uuid4(),
            code="S-MIGRADA",
            site_id=site.id,
            charge_point_id=ponto.id,
            user_id=motorista.id,
            state=SessionState.BILLED,
            started_at=agora - timedelta(days=10),
            ended_at=agora - timedelta(days=10) + timedelta(hours=1),
            duration_s=3600,
            energy_kwh=10,
            estimated_cost=25,
        )
    )
    await db.flush()

    r = await us.ocupacao_por_ponto(db, site.id, dias=30, agora=agora)
    assert r["dias_efetivos"] == pytest.approx(10.0, abs=0.05)


async def test_janela_completa_quando_o_site_e_mais_velho_que_o_periodo(
    db, site, ponto, agora
):
    site.created_at = agora - timedelta(days=365)
    await db.flush()

    r = await us.ocupacao_por_ponto(db, site.id, dias=30, agora=agora)
    assert r["janela_completa"] is True
    assert r["dias_efetivos"] == pytest.approx(30.0, abs=0.01)
