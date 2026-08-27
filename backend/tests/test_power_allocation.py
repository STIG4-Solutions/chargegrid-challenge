"""Testes do rateio de potencia - funcao pura, sem banco nem hardware."""

import uuid

from app.models.charge_point import ChargePoint
from app.models.enums import ChargePointStatus
from app.services.power_manager import PowerBudget, build_plan


def make_cp(
    code: str,
    rated: float,
    *,
    min_kw: float = 4.2,
    priority: int = 100,
    status: ChargePointStatus = ChargePointStatus.CHARGING,
) -> ChargePoint:
    cp = ChargePoint(
        id=uuid.uuid4(),
        code=code,
        name=code,
        rated_kw=rated,
        min_kw=min_kw,
        limit_kw=rated,
        priority=priority,
        status=status,
        enabled=True,
    )
    return cp


def budget(available: float) -> PowerBudget:
    return PowerBudget(
        grid_limit_kw=available,
        pv_kw=0,
        battery_kw=0,
        reserved_kw=0,
        building_load_kw=0,
        ev_load_kw=0,
    )


def test_folga_atende_todos_no_nominal():
    points = [make_cp("CP-01", 22), make_cp("CP-02", 22)]
    plan = build_plan(budget(100), points)
    assert all(a.granted_kw == 22 for a in plan.allocations)
    assert not plan.over_budget


def test_orcamento_apertado_divide_e_nao_estoura():
    points = [make_cp("CP-01", 22), make_cp("CP-02", 22), make_cp("CP-03", 22)]
    plan = build_plan(budget(30), points)
    assert plan.total_granted_kw <= 30.01
    assert not plan.over_budget


def test_sobra_de_quem_satura_vai_para_os_outros():
    # CP-01 so aceita 7 kW: os 23 kW restantes devem ir para os dois maiores.
    points = [make_cp("CP-01", 7, min_kw=1.4), make_cp("CP-02", 22), make_cp("CP-03", 22)]
    plan = build_plan(budget(30), points)
    granted = {a.code: a.granted_kw for a in plan.allocations}
    assert granted["CP-01"] == 7
    assert granted["CP-02"] > 10 and granted["CP-03"] > 10


def test_prioridade_alta_e_servida_primeiro():
    points = [make_cp("CP-VIP", 22, priority=500), make_cp("CP-COMUM", 22, priority=100)]
    plan = build_plan(budget(25), points)
    granted = {a.code: a.granted_kw for a in plan.allocations}
    assert granted["CP-VIP"] == 22
    assert granted["CP-COMUM"] < 22


def test_suspende_em_vez_de_dividir_abaixo_do_minimo():
    # 6 kW nao sustentam dois pontos com piso de 4,2 kW cada.
    points = [make_cp("CP-01", 22), make_cp("CP-02", 22)]
    plan = build_plan(budget(6), points)
    suspended = [a for a in plan.allocations if a.suspended]
    assert len(suspended) == 1
    served = [a for a in plan.allocations if not a.suspended]
    assert served[0].granted_kw >= 4.2


def test_ponto_em_falha_nao_recebe_potencia():
    points = [make_cp("CP-01", 22), make_cp("CP-02", 22, status=ChargePointStatus.FAULTED)]
    plan = build_plan(budget(50), points)
    granted = {a.code: a.granted_kw for a in plan.allocations}
    assert granted["CP-02"] == 0


def test_reserva_predial_reduz_o_orcamento():
    b = PowerBudget(
        grid_limit_kw=100,
        pv_kw=20,
        battery_kw=10,
        reserved_kw=30,
        building_load_kw=45,  # predio consome mais que a reserva: vale o real
        ev_load_kw=0,
    )
    assert b.available_kw == 85.0


def test_ponto_disponivel_entra_no_rateio_ao_iniciar():
    """Regressao do impasse de partida.

    Um ponto AVAILABLE nao e despachavel, entao sem o aviso de que esta prestes
    a iniciar ele recebe 0 kW - e a sessao nunca energiza, mesmo com o site
    inteiro livre.
    """
    cp = make_cp("CP-01", 22, status=ChargePointStatus.AVAILABLE)

    sem_aviso = build_plan(budget(100), [cp])
    assert sem_aviso.total_granted_kw == 0

    com_aviso = build_plan(budget(100), [cp], starting_ids={str(cp.id)})
    assert com_aviso.total_granted_kw == 22


def test_ponto_ocioso_nao_reserva_orcamento():
    """So quem esta iniciando entra; os demais ociosos continuam de fora."""
    iniciando = make_cp("CP-01", 22, status=ChargePointStatus.AVAILABLE)
    ocioso = make_cp("CP-02", 22, status=ChargePointStatus.AVAILABLE)

    plan = build_plan(budget(100), [iniciando, ocioso], starting_ids={str(iniciando.id)})
    concedido = {a.code: a.granted_kw for a in plan.allocations}
    assert concedido["CP-01"] == 22
    assert concedido["CP-02"] == 0


def test_teto_do_operador_limita_o_rateio():
    """O ajuste manual do painel e um teto, nao uma sugestao.

    Sem isso o rateio automatico devolvia o ponto ao nominal no ciclo seguinte.
    """
    cp = make_cp("CP-01", 22)
    cp.operator_max_kw = 15

    plan = build_plan(budget(100), [cp])
    assert plan.allocations[0].granted_kw == 15


def test_teto_do_operador_nao_ultrapassa_o_nominal():
    cp = make_cp("CP-01", 22)
    cp.operator_max_kw = 50  # acima do que o equipamento aguenta

    plan = build_plan(budget(100), [cp])
    assert plan.allocations[0].granted_kw == 22


def test_plano_nunca_excede_o_orcamento():
    """Regressao do arredondamento.

    round(x, 1) arredonda para cima, entao N pontos dividindo o orcamento
    somavam ate 0,05 kW a mais cada. Num site grande isso passa do limite
    contratado - o disjuntor que o controle de demanda existe para proteger.
    """
    for quantidade, disponivel in ((7, 100), (13, 100), (40, 300), (3, 10), (9, 55)):
        pontos = [make_cp(f"CP-{i:02d}", 22) for i in range(quantidade)]
        plan = build_plan(budget(disponivel), pontos)
        assert plan.total_granted_kw <= disponivel, (
            f"{quantidade} pontos / {disponivel} kW concedeu {plan.total_granted_kw}"
        )
        assert not plan.over_budget


def test_concessao_sempre_em_decimos_de_kw():
    """O registrador 10029 so aceita decimos: nao adianta conceder 14,2857 kW."""
    pontos = [make_cp(f"CP-{i:02d}", 22) for i in range(7)]
    for a in build_plan(budget(100), pontos).allocations:
        assert round(a.granted_kw * 10) == a.granted_kw * 10, a.granted_kw


def test_autorizacao_pode_ser_cancelada():
    """Regressao: sessao presa em AUTHORIZING inutilizava o eletroposto.

    AUTHORIZING conta como sessao ativa e bloqueia o ponto, mas nao permitia
    transicao para FINISHING — entao stop() devolvia 409 e nao havia saida pela
    API. Interromper o processo entre authorize() e start() bastava para chegar
    la.
    """
    from app.models.enums import ACTIVE_SESSION_STATES, SessionState
    from app.services.session_service import ALLOWED

    assert SessionState.AUTHORIZING in ACTIVE_SESSION_STATES
    assert SessionState.FINISHING in ALLOWED[SessionState.AUTHORIZING]

    # Todo estado que bloqueia o ponto precisa ter rota de saida.
    for estado in ACTIVE_SESSION_STATES:
        assert ALLOWED[estado], f"{estado} nao tem transicao de saida"
        assert SessionState.FINISHING in ALLOWED[estado] or SessionState.ERROR in ALLOWED[estado], (
            f"{estado} bloqueia o ponto sem forma de encerrar"
        )


def test_agendamento_segura_potencia_no_orcamento():
    """Regressao: Reservation.reserved_kw era gravado e nunca lido pelo rateio.

    Um agendamento nao garantia capacidade nenhuma no horario marcado — a
    promessa do campo nao era cumprida.
    """
    sem_reserva = PowerBudget(
        grid_limit_kw=75,
        pv_kw=38.4,
        battery_kw=12,
        reserved_kw=20,
        building_load_kw=0,
        ev_load_kw=0,
    )
    com_reserva = PowerBudget(
        grid_limit_kw=75,
        pv_kw=38.4,
        battery_kw=12,
        reserved_kw=20,
        building_load_kw=0,
        ev_load_kw=0,
        booked_kw=22,
    )
    assert com_reserva.available_kw == sem_reserva.available_kw - 22
    assert "booked_kw" in com_reserva.as_dict()


def test_orcamento_nunca_fica_negativo_com_agendamentos():
    """Mais reservado que disponivel nao pode virar orcamento negativo."""
    orcamento = PowerBudget(
        grid_limit_kw=10,
        pv_kw=0,
        battery_kw=0,
        reserved_kw=0,
        building_load_kw=0,
        ev_load_kw=0,
        booked_kw=50,
    )
    assert orcamento.available_kw == 0


def test_recem_chegado_nao_derruba_quem_ja_carrega():
    """Regressao: sem essa ordem de corte a fila nunca disparava.

    O rateio cortava por menor nominal, sem olhar quem ja estava carregando.
    Um carro chegando derrubava um cliente no meio da recarga e assumia a vaga,
    em vez de esperar - exatamente o oposto do que uma fila existe para fazer.
    """
    carregando = make_cp("CP-01", 22, status=ChargePointStatus.CHARGING)
    chegando = make_cp("CP-02", 22, status=ChargePointStatus.AVAILABLE)

    plan = build_plan(budget(6), [carregando, chegando], starting_ids={str(chegando.id)})
    concedido = {a.code: a.granted_kw for a in plan.allocations}
    assert concedido["CP-01"] > 0, "quem ja carregava foi derrubado"
    assert concedido["CP-02"] == 0, "o recem-chegado deveria ir para a fila"


def test_ponto_plugado_sem_carregar_nao_reserva_potencia():
    """PREPARING fora do rateio.

    Carro plugado que nao carrega nao consome nada. Incluir esse estado fazia um
    carro na fila reservar exatamente a potencia que estava esperando.
    """
    preparando = make_cp("CP-01", 22, status=ChargePointStatus.PREPARING)
    assert not preparando.is_dispatchable

    plan = build_plan(budget(50), [preparando])
    assert plan.allocations[0].granted_kw == 0


def test_fila_tem_saida_para_todos_os_estados_ativos():
    """Nenhum estado que bloqueia o ponto pode ser um beco sem saida."""
    from app.models.enums import ACTIVE_SESSION_STATES, SessionState
    from app.services.session_service import ALLOWED

    assert SessionState.QUEUED in ACTIVE_SESSION_STATES
    assert SessionState.STARTING in ALLOWED[SessionState.QUEUED]
    for estado in ACTIVE_SESSION_STATES:
        saidas = ALLOWED[estado]
        assert SessionState.FINISHING in saidas or SessionState.ERROR in saidas, (
            f"{estado} bloqueia o ponto sem forma de encerrar"
        )


def test_potencia_alocada_conta_so_quem_pode_puxar():
    """Regressao do alarme falso no painel.

    A soma dos limites incluia pontos ociosos, na fila e cortados pelo operador —
    tetos que ninguem estava usando. O painel mostrava "excede a disponibilidade"
    em vermelho com o site inteiro tranquilo.
    """
    carregando = make_cp("CP-01", 22, status=ChargePointStatus.CHARGING)
    carregando.limit_kw = 6
    na_fila = make_cp("CP-02", 22, status=ChargePointStatus.PREPARING)
    na_fila.limit_kw = 5.5
    ocioso = make_cp("CP-03", 11, status=ChargePointStatus.AVAILABLE)
    ocioso.limit_kw = 11
    cortado = make_cp("CP-04", 7, status=ChargePointStatus.SUSPENDED)
    cortado.limit_kw = 7
    cortado.operator_throttled = True

    pontos = [carregando, na_fila, ocioso, cortado]
    alocado = sum(float(cp.limit_kw) for cp in pontos if cp.is_dispatchable)

    assert alocado == 6, f"esperado só o ponto carregando, veio {alocado}"
    assert alocado <= 6, "não pode acusar excesso com o site tranquilo"
