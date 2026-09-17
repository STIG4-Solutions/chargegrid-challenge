"""Multi-site: o admin escolhe a praca, o operador nunca sai da dele.

Esta feature afrouxa deliberadamente o escopo que protege o isolamento
multi-tenant - passa a existir um caminho em que `site_id` da query decide qual
site responde. A maior parte destes testes existe para provar que esse caminho
esta fechado para o operador, inclusive quando ele manda um id valido de outro
site.
"""

import uuid

from app.models.enums import SessionState
from app.services import portfolio_service as pf

# --------------------------------------------------------------- o escopo


async def test_operador_nao_escapa_com_site_id_de_outro_site(
    api, site, segundo_site, ponto, como_operador_do_site
):
    """O parametro e' ignorado, nao rejeitado.

    Rejeitar com 403 confirmaria que aquele id existe. Ignorar nao vaza nada -
    e o operador recebe os proprios dados, como se nao tivesse pedido.
    """
    r = await api.get(
        f"/api/v1/power/utilization/by-point?site_id={segundo_site.id}",
        headers=como_operador_do_site,
    )
    assert r.status_code == 200
    # Veio o site do operador: o ponto dele esta na lista.
    assert any(p["code"] == ponto.code for p in r.json()["pontos"])


async def test_admin_escolhe_o_site(api, db, site, segundo_site, ponto, como_admin):
    """Admin com site_id explicito recebe aquele site."""
    from app.models.charge_point import ChargePoint
    from app.models.enums import ChargePointStatus, ConnectorType, PhaseType

    vizinho = ChargePoint(
        id=uuid.uuid4(),
        site_id=segundo_site.id,
        code="CP-VIZINHO",
        name="Do outro site",
        connector=ConnectorType.TYPE2,
        phase_type=PhaseType.THREE,
        rated_kw=22,
        min_kw=4.2,
        limit_kw=22,
        operator_max_kw=22,
        status=ChargePointStatus.AVAILABLE,
        priority=100,
        enabled=True,
    )
    db.add(vizinho)
    await db.flush()

    r = await api.get(
        f"/api/v1/power/utilization/by-point?site_id={segundo_site.id}", headers=como_admin
    )
    assert r.status_code == 200
    codigos = {p["code"] for p in r.json()["pontos"]}
    assert "CP-VIZINHO" in codigos
    assert ponto.code not in codigos


async def test_admin_com_site_inexistente_recebe_404(api, site, ponto, como_admin):
    """Sem a conferencia, um uuid digitado errado devolvia 200 com tudo vazio.

    E' o pior tipo de resposta: um site sem movimento e um site que nao existe
    se parecem exatamente na tela.
    """
    r = await api.get(
        f"/api/v1/power/utilization/by-point?site_id={uuid.uuid4()}", headers=como_admin
    )
    assert r.status_code == 404


async def test_admin_sem_escolha_cai_no_padrao(api, site, ponto, como_admin):
    r = await api.get("/api/v1/power/utilization/by-point", headers=como_admin)
    assert r.status_code == 200
    assert any(p["code"] == ponto.code for p in r.json()["pontos"])


async def test_site_id_malformado_e_422(api, site, ponto, como_admin):
    r = await api.get("/api/v1/power/utilization/by-point?site_id=nao-e-uuid", headers=como_admin)
    assert r.status_code == 422


# --------------------------------------------------------- seletor de sites


async def test_operador_so_ve_o_proprio_site_no_seletor(
    api, site, segundo_site, como_operador_do_site
):
    """A lista tambem e superficie de informacao.

    Nao adianta o escopo barrar a consulta se o seletor entrega os nomes e as
    cidades da rede inteira.
    """
    r = await api.get("/api/v1/power/sites", headers=como_operador_do_site)
    assert r.status_code == 200
    assert [s["site_id"] for s in r.json()] == [str(site.id)]


async def test_admin_ve_todos_os_sites_no_seletor(api, site, segundo_site, como_admin):
    r = await api.get("/api/v1/power/sites", headers=como_admin)
    assert r.status_code == 200
    ids = {s["site_id"] for s in r.json()}
    assert {str(site.id), str(segundo_site.id)} <= ids


async def test_motorista_nao_lista_sites(api, site, como_motorista):
    """Rota de usuario autenticado, mas motorista nao tem site vinculado."""
    r = await api.get("/api/v1/power/sites", headers=como_motorista)
    assert r.status_code == 200
    assert r.json() == []


# ------------------------------------------------------------------ rede


async def test_portfolio_e_so_do_admin(api, site, ponto, como_admin, como_operador_do_site):
    """A visao da rede nao e' do operador - ele nao administra as outras pracas."""
    assert (await api.get("/api/v1/power/sites/portfolio", headers=como_admin)).status_code == 200
    negado = await api.get("/api/v1/power/sites/portfolio", headers=como_operador_do_site)
    assert negado.status_code == 403


async def test_portfolio_nao_colide_com_a_rota_de_lista(api, site, como_admin):
    """/sites/portfolio e literal; /sites devolve lista. Nao podem se confundir."""
    lista = await api.get("/api/v1/power/sites", headers=como_admin)
    rede = await api.get("/api/v1/power/sites/portfolio", headers=como_admin)
    assert isinstance(lista.json(), list)
    assert isinstance(rede.json(), dict)
    assert "totais" in rede.json()


async def test_rede_agrega_os_dois_sites(db, site, segundo_site, ponto, motorista, agora):
    from datetime import timedelta

    from app.models.session import ChargingSession

    db.add(
        ChargingSession(
            id=uuid.uuid4(),
            code="S-REDE",
            site_id=site.id,
            charge_point_id=ponto.id,
            user_id=motorista.id,
            state=SessionState.BILLED,
            started_at=agora - timedelta(hours=2),
            ended_at=agora - timedelta(hours=1),
            duration_s=3600,
            energy_kwh=40,
            estimated_cost=100,
        )
    )
    await db.flush()

    r = await pf.visao_da_rede(db, dias=30, agora=agora)
    assert r["totais"]["sites"] >= 2
    assert r["totais"]["receita_brl"] >= 100.0

    por_nome = {s["nome"]: s for s in r["sites"]}
    assert por_nome[site.name]["receita_brl"] == 100.0
    assert por_nome[site.name]["sessoes"] == 1
    assert por_nome[segundo_site.name]["receita_brl"] == 0.0


async def test_ranking_e_por_receita_por_ponto(db, site, segundo_site, ponto, motorista, agora):
    """Comparar totais premiaria a praca maior por ser maior.

    Um site de dez pontos fatura mais que um de dois quase por definicao. O que
    diz se ele vai bem e a receita por ponto - senao a tela sempre recomendaria
    investir onde ja se investiu.
    """
    from datetime import timedelta

    from app.models.charge_point import ChargePoint
    from app.models.enums import ChargePointStatus, ConnectorType, PhaseType
    from app.models.session import ChargingSession

    def novo_cp(site_id, code):
        return ChargePoint(
            id=uuid.uuid4(),
            site_id=site_id,
            code=code,
            name=code,
            connector=ConnectorType.TYPE2,
            phase_type=PhaseType.THREE,
            rated_kw=22,
            min_kw=4.2,
            limit_kw=22,
            operator_max_kw=22,
            status=ChargePointStatus.AVAILABLE,
            priority=100,
            enabled=True,
        )

    # O primeiro site fica GRANDE: 4 pontos no total, faturando R$ 100 -> 25/ponto.
    db.add_all([novo_cp(site.id, f"CP-G{i}") for i in range(3)])

    # O segundo ganha UM ponto faturando R$ 80: menos no total, 80/ponto.
    unico = ChargePoint(
        id=uuid.uuid4(),
        site_id=segundo_site.id,
        code="CP-U",
        name="Unico",
        connector=ConnectorType.TYPE2,
        phase_type=PhaseType.THREE,
        rated_kw=22,
        min_kw=4.2,
        limit_kw=22,
        operator_max_kw=22,
        status=ChargePointStatus.AVAILABLE,
        priority=100,
        enabled=True,
    )
    db.add(unico)
    await db.flush()

    def sessao(site_id, cp_id, brl, code):
        return ChargingSession(
            id=uuid.uuid4(),
            code=code,
            site_id=site_id,
            charge_point_id=cp_id,
            user_id=motorista.id,
            state=SessionState.BILLED,
            started_at=agora - timedelta(hours=2),
            ended_at=agora - timedelta(hours=1),
            duration_s=3600,
            energy_kwh=10,
            estimated_cost=brl,
        )

    db.add_all(
        [
            sessao(site.id, ponto.id, 100, "S-A"),  # site com mais pontos
            sessao(segundo_site.id, unico.id, 80, "S-B"),  # menos total, mais por ponto
        ]
    )
    await db.flush()

    r = await pf.visao_da_rede(db, dias=30, agora=agora)
    por_nome = {s["nome"]: s for s in r["sites"]}
    assert por_nome[segundo_site.name]["receita_brl"] < por_nome[site.name]["receita_brl"]
    assert (
        por_nome[segundo_site.name]["receita_por_ponto_brl"]
        > por_nome[site.name]["receita_por_ponto_brl"]
    )
    # E o ranking segue a receita por ponto, nao o total.
    assert r["sites"][0]["nome"] == segundo_site.name


async def test_disponibilidade_da_rede_e_ponderada_por_pontos(db, site, segundo_site, agora):
    """Media das medias deixaria uma praca de dois pontos pesar como uma de vinte."""
    from app.models.charge_point import ChargePoint
    from app.models.enums import ChargePointStatus, ConnectorType, PhaseType

    def cp(site_id, code, status):
        return ChargePoint(
            id=uuid.uuid4(),
            site_id=site_id,
            code=code,
            name=code,
            connector=ConnectorType.TYPE2,
            phase_type=PhaseType.THREE,
            rated_kw=22,
            min_kw=4.2,
            limit_kw=22,
            operator_max_kw=22,
            status=status,
            priority=100,
            enabled=True,
        )

    # Site grande: 4 pontos, todos bons. Site pequeno: 1 ponto, quebrado.
    db.add_all([cp(site.id, f"G-{i}", ChargePointStatus.AVAILABLE) for i in range(4)])
    db.add_all([cp(segundo_site.id, "P-1", ChargePointStatus.FAULTED)])
    await db.flush()

    r = await pf.visao_da_rede(db, dias=30, agora=agora)
    # 5 pontos, 1 em falha -> 80%. A media das medias daria (100 + 0) / 2 = 50%.
    assert r["totais"]["disponibilidade_pct"] == 80.0


async def test_rede_vazia_nao_estoura(db, agora):
    """Sem nenhum site cadastrado a tela ainda precisa abrir."""
    from sqlalchemy import delete

    from app.models.site import Site

    await db.execute(delete(Site))
    await db.flush()

    r = await pf.visao_da_rede(db, dias=30, agora=agora)
    assert r["sites"] == []
    assert r["totais"]["sites"] == 0
    assert r["totais"]["disponibilidade_pct"] == 0.0
