"""Regras de prioridade nomeadas.

A prioridade decide quem fica sem carregar quando falta potencia. Um erro aqui
nao gera excecao nem log: alguem simplesmente nao carrega, e ninguem sabe por
que. Por isso os testes carregam nas armadilhas silenciosas - a janela que
cruza a meia-noite, o desempate entre regras, e o caminho que liga a regra ao
rateio de verdade.
"""

import uuid
from datetime import time

import pytest

from app.models.priority_rule import PriorityRule
from app.services import power_manager
from app.services import priority_service as ps


def _regra(**kw) -> PriorityRule:
    base = dict(
        id=uuid.uuid4(),
        site_id=uuid.uuid4(),
        nome="Regra",
        prioridade=100,
        ordem=100,
        ativo=True,
        criterio_tipo="sempre",
        criterio_valor=None,
        janela_inicio=None,
        janela_fim=None,
    )
    base.update(kw)
    return PriorityRule(**base)


# ------------------------------------------------------------------ janelas


def test_janela_normal():
    assert ps.dentro_da_janela(time(8), time(18), time(12))
    assert not ps.dentro_da_janela(time(8), time(18), time(20))


def test_sem_janela_vale_o_dia_inteiro():
    assert ps.dentro_da_janela(None, None, time(3))
    assert ps.dentro_da_janela(None, None, time(23, 59))


@pytest.mark.parametrize(
    "momento,esperado",
    [
        (time(23, 0), True),  # depois do inicio
        (time(2, 0), True),  # depois da meia-noite, antes do fim
        (time(5, 59), True),  # ultimo minuto
        (time(6, 0), True),  # limite fechado
        (time(7, 0), False),  # ja amanheceu
        (time(12, 0), False),  # meio-dia
        (time(21, 59), False),  # um minuto antes de comecar
    ],
)
def test_janela_que_cruza_a_meia_noite(momento, esperado):
    """22h -> 6h e' a recarga noturna de frota: o caso comum, nao a excecao.

    Com a comparacao ingenua `inicio <= t <= fim` nenhum horario satisfaz
    simultaneamente >= 22h e <= 6h, entao a regra nunca casaria - e falharia em
    silencio, deixando a frota disputando potencia com visitante a noite toda.
    """
    assert ps.dentro_da_janela(time(22), time(6), momento) is esperado


# ---------------------------------------------------------------- criterios


def test_criterio_por_ponto_aceita_lista_e_ignora_caixa(ponto):
    regra = _regra(criterio_tipo="ponto", criterio_valor="cp-teste, CP-99")
    assert ps._casa_criterio(regra, ponto)

    fora = _regra(criterio_tipo="ponto", criterio_valor="CP-99")
    assert not ps._casa_criterio(fora, ponto)


def test_criterio_por_conector(ponto):
    regra = _regra(criterio_tipo="conector", criterio_valor="TYPE2")
    assert ps._casa_criterio(regra, ponto)
    assert not ps._casa_criterio(_regra(criterio_tipo="conector", criterio_valor="CCS2"), ponto)


def test_criterio_sempre_casa_com_qualquer_ponto(ponto):
    assert ps._casa_criterio(_regra(), ponto)


def test_criterio_sem_valor_nao_casa(ponto):
    """Regra incompleta nao pode virar regra curinga.

    Casar por engano daria a prioridade dela a TODOS os pontos - a falha mais
    cara possivel numa regra que decide quem carrega.
    """
    assert not ps._casa_criterio(_regra(criterio_tipo="ponto", criterio_valor=None), ponto)
    assert not ps._casa_criterio(_regra(criterio_tipo="ponto", criterio_valor="  "), ponto)


# ----------------------------------------------------------------- resolucao


def test_primeira_regra_na_ordem_vence(ponto):
    """Duas regras casam; quem decide e' a de menor `ordem`."""
    generosa = _regra(nome="Todos", prioridade=10, ordem=200)
    especifica = _regra(
        nome="VIP", prioridade=900, ordem=10, criterio_tipo="ponto", criterio_valor=ponto.code
    )

    r = ps.resolver([generosa, especifica], [ponto], agora_local=time(12))
    assert r[str(ponto.id)].prioridade == 900
    assert r[str(ponto.id)].regra == "VIP"


def test_regra_inativa_e_ignorada(ponto):
    r = ps.resolver(
        [_regra(nome="Desligada", prioridade=999, ativo=False)], [ponto], agora_local=time(12)
    )
    assert r[str(ponto.id)].prioridade == int(ponto.priority)
    assert r[str(ponto.id)].regra is None


def test_sem_regra_vale_o_inteiro_do_ponto(ponto):
    r = ps.resolver([], [ponto], agora_local=time(12))
    assert r[str(ponto.id)].prioridade == int(ponto.priority)
    assert r[str(ponto.id)].regra is None


def test_regra_fora_da_janela_nao_vale(ponto):
    noturna = _regra(nome="Noturna", prioridade=900, janela_inicio=time(22), janela_fim=time(6))
    de_dia = ps.resolver([noturna], [ponto], agora_local=time(14))
    de_noite = ps.resolver([noturna], [ponto], agora_local=time(23))

    assert de_dia[str(ponto.id)].regra is None
    assert de_noite[str(ponto.id)].regra == "Noturna"


def test_desempate_e_estavel_quando_a_ordem_empata(ponto):
    """Duas regras com a mesma `ordem` nao podem alternar entre chamadas.

    Sem o desempate por id, o vencedor dependia da ordem em que o banco
    devolveu as linhas - estavel nos testes, instavel em producao.
    """
    a = _regra(nome="A", prioridade=1, ordem=50)
    b = _regra(nome="B", prioridade=2, ordem=50)
    primeiro = ps.resolver([a, b], [ponto], agora_local=time(12))[str(ponto.id)].regra
    segundo = ps.resolver([b, a], [ponto], agora_local=time(12))[str(ponto.id)].regra
    assert primeiro == segundo


# ------------------------------------------------- a regra muda o rateio


def test_regra_inverte_quem_e_servido_primeiro(ponto, segundo_ponto):
    """O teste que importa: a regra tem que mudar o resultado do rateio.

    Sem esta ligacao, tudo o que veio acima seria configuracao bonita sem
    efeito nenhum sobre quem carrega.
    """
    # available_kw e' derivado: 25 = 25 de rede, sem PV, sem bateria, sem reserva.
    orcamento = power_manager.PowerBudget(
        grid_limit_kw=25,
        pv_kw=0,
        battery_kw=0,
        reserved_kw=0,
        building_load_kw=0,
        ev_load_kw=0,
    )
    for cp in (ponto, segundo_ponto):
        cp.status = __import__(
            "app.models.enums", fromlist=["ChargePointStatus"]
        ).ChargePointStatus.CHARGING

    # Sem regras: o `ponto` tem priority maior e e' servido primeiro.
    sem = power_manager.build_plan(orcamento, [ponto, segundo_ponto])
    kw_sem = {a.code: a.granted_kw for a in sem.allocations}

    # Com a regra, o segundo ponto sobe para uma faixa acima do primeiro.
    promove = _regra(
        nome="Frota",
        prioridade=int(ponto.priority) + 500,
        criterio_tipo="ponto",
        criterio_valor=segundo_ponto.code,
    )
    resolvidas = ps.resolver([promove], [ponto, segundo_ponto], agora_local=time(12))
    com = power_manager.build_plan(orcamento, [ponto, segundo_ponto], prioridades=resolvidas)
    kw_com = {a.code: a.granted_kw for a in com.allocations}

    assert kw_com[segundo_ponto.code] > kw_sem[segundo_ponto.code]
    assert any(a.regra == "Frota" for a in com.allocations)


def test_plano_expoe_a_regra_que_decidiu(ponto):
    """O painel precisa poder responder "por que este ponto foi cortado"."""
    orcamento = power_manager.PowerBudget(
        grid_limit_kw=50,
        pv_kw=0,
        battery_kw=0,
        reserved_kw=0,
        building_load_kw=0,
        ev_load_kw=0,
    )
    resolvidas = ps.resolver(
        [_regra(nome="Visitantes", prioridade=7)], [ponto], agora_local=time(12)
    )
    plano = power_manager.build_plan(orcamento, [ponto], prioridades=resolvidas)
    alocacao = next(a for a in plano.allocations if a.code == ponto.code)
    assert alocacao.priority == 7
    assert alocacao.regra == "Visitantes"
    assert plano.as_dict()["allocations"][0]["regra"] == "Visitantes"


# ---------------------------------------------------------------- fuso


async def test_resolucao_usa_a_hora_local_do_site(db, site, ponto):
    """A janela e' escrita em hora local; resolve-la em UTC deslocaria 3 horas.

    Uma regra "das 22h as 6h" resolvida em UTC comecaria as 19h local - e a
    frota ganharia prioridade no meio do horario comercial.
    """
    from datetime import UTC, datetime

    site.timezone = "America/Sao_Paulo"
    db.add(
        PriorityRule(
            id=uuid.uuid4(),
            site_id=site.id,
            nome="Noturna",
            prioridade=900,
            ordem=10,
            ativo=True,
            criterio_tipo="sempre",
            janela_inicio=time(22),
            janela_fim=time(6),
        )
    )
    await db.flush()

    # 2026-01-01 01:00 UTC == 2026-01-01 22:00 em Sao Paulo (UTC-3): dentro.
    dentro = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)
    r = await ps.resolver_para_site(db, site, [ponto], agora=dentro)
    assert r[str(ponto.id)].regra == "Noturna"

    # 2026-01-01 18:00 UTC == 15:00 em Sao Paulo: fora.
    fora = datetime(2026, 1, 1, 18, 0, tzinfo=UTC)
    r = await ps.resolver_para_site(db, site, [ponto], agora=fora)
    assert r[str(ponto.id)].regra is None


async def test_fuso_invalido_nao_derruba_o_rateio(db, site, ponto):
    """Cadastro ruim nao pode parar a distribuicao: sem rateio, ninguem carrega."""
    site.timezone = "Nao/Existe"
    db.add(
        PriorityRule(
            id=uuid.uuid4(),
            site_id=site.id,
            nome="Padrao",
            prioridade=42,
            ordem=10,
            ativo=True,
            criterio_tipo="sempre",
        )
    )
    await db.flush()

    r = await ps.resolver_para_site(db, site, [ponto])
    assert r[str(ponto.id)].prioridade == 42


# ------------------------------------------------------------------- HTTP


async def test_crud_completo(api, site, ponto, como_operador):
    corpo = {
        "nome": "Frota da noite",
        "prioridade": 800,
        "ordem": 10,
        "criterio_tipo": "ponto",
        "criterio_valor": ponto.code,
        "janela_inicio": "22:00",
        "janela_fim": "06:00",
    }
    criada = await api.post("/api/v1/power/priority-rules", json=corpo, headers=como_operador)
    assert criada.status_code == 201, criada.text
    regra_id = criada.json()["id"]
    assert criada.json()["janela_inicio"] == "22:00"

    listadas = await api.get("/api/v1/power/priority-rules", headers=como_operador)
    assert listadas.status_code == 200
    assert any(r["id"] == regra_id for r in listadas.json())

    corpo["prioridade"] = 900
    alterada = await api.put(
        f"/api/v1/power/priority-rules/{regra_id}", json=corpo, headers=como_operador
    )
    assert alterada.status_code == 200
    assert alterada.json()["prioridade"] == 900

    apagada = await api.delete(f"/api/v1/power/priority-rules/{regra_id}", headers=como_operador)
    assert apagada.status_code == 204


async def test_janela_pela_metade_e_recusada(api, site, ponto, como_operador):
    r = await api.post(
        "/api/v1/power/priority-rules",
        json={"nome": "Meia janela", "prioridade": 100, "janela_inicio": "22:00"},
        headers=como_operador,
    )
    assert r.status_code == 422


async def test_criterio_sem_valor_e_recusado(api, site, ponto, como_operador):
    r = await api.post(
        "/api/v1/power/priority-rules",
        json={"nome": "Vazia", "prioridade": 100, "criterio_tipo": "ponto"},
        headers=como_operador,
    )
    assert r.status_code == 422


async def test_janela_de_duracao_zero_e_recusada(api, site, ponto, como_operador):
    r = await api.post(
        "/api/v1/power/priority-rules",
        json={
            "nome": "Instante",
            "prioridade": 100,
            "janela_inicio": "10:00",
            "janela_fim": "10:00",
        },
        headers=como_operador,
    )
    assert r.status_code == 422


async def test_preview_nao_colide_com_a_rota_de_id(api, site, ponto, como_operador):
    """/priority-rules/preview e' declarada depois de /priority-rules/{id}.

    Nao colidem hoje porque os metodos diferem, mas basta alguem adicionar um
    GET por id para "preview" virar um uuid invalido e devolver 422.
    """
    r = await api.get("/api/v1/power/priority-rules/preview", headers=como_operador)
    assert r.status_code == 200
    assert "pontos" in r.json()


async def test_preview_em_hora_escolhida(api, db, site, ponto, como_operador):
    db.add(
        PriorityRule(
            id=uuid.uuid4(),
            site_id=site.id,
            nome="Noturna",
            prioridade=900,
            ordem=10,
            ativo=True,
            criterio_tipo="sempre",
            janela_inicio=time(22),
            janela_fim=time(6),
        )
    )
    await db.flush()

    de_noite = await api.get(
        "/api/v1/power/priority-rules/preview?hora=23:30", headers=como_operador
    )
    assert de_noite.status_code == 200
    assert de_noite.json()["pontos"][0]["regra"] == "Noturna"

    de_dia = await api.get("/api/v1/power/priority-rules/preview?hora=14:00", headers=como_operador)
    assert de_dia.json()["pontos"][0]["regra"] is None


async def test_preview_com_hora_invalida(api, site, ponto, como_operador):
    r = await api.get("/api/v1/power/priority-rules/preview?hora=25h", headers=como_operador)
    assert r.status_code == 422


async def test_motorista_nao_mexe_nas_regras(api, site, ponto, como_motorista):
    assert (
        await api.get("/api/v1/power/priority-rules", headers=como_motorista)
    ).status_code == 403
    assert (
        await api.post(
            "/api/v1/power/priority-rules",
            json={"nome": "x", "prioridade": 1},
            headers=como_motorista,
        )
    ).status_code == 403


async def test_operador_vizinho_nao_altera_regra_alheia(
    api, db, site, ponto, como_operador_do_site, como_operador_vizinho
):
    """Regra de outro site responde 404, nao 403.

    403 confirmaria que o id existe - o vizinho nao precisa saber quais regras
    o site ao lado tem.
    """
    criada = await api.post(
        "/api/v1/power/priority-rules",
        json={"nome": "Minha", "prioridade": 100},
        headers=como_operador_do_site,
    )
    assert criada.status_code == 201
    regra_id = criada.json()["id"]

    invasao = await api.put(
        f"/api/v1/power/priority-rules/{regra_id}",
        json={"nome": "Sequestrada", "prioridade": 999},
        headers=como_operador_vizinho,
    )
    assert invasao.status_code == 404

    remocao = await api.delete(
        f"/api/v1/power/priority-rules/{regra_id}", headers=como_operador_vizinho
    )
    assert remocao.status_code == 404
