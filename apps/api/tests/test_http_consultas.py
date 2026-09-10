"""Custo de consulta do mapa de estacoes.

A primeira tela do app lista todas as estacoes. O preco de cada uma vinha de uma
consulta propria dentro do laco - um N+1 invisivel com um site so, e cinquenta e
uma consultas com cinquenta sites. Este teste conta as idas ao banco para que a
regressao apareca antes do usuario.
"""

import uuid

import pytest
from sqlalchemy import event

CAB = "/api/v1/app"


@pytest.fixture
def contar_consultas(engine):
    """Conta SELECTs por tabela durante o bloco."""
    contagem: dict[str, int] = {}

    def antes(conn, cursor, sql, params, contexto, muitos):
        texto = " ".join(sql.lower().split())
        for tabela in ("tariffs", "sites", "charge_points"):
            if f"from {tabela}" in texto:
                contagem[tabela] = contagem.get(tabela, 0) + 1

    event.listen(engine.sync_engine, "before_cursor_execute", antes)
    try:
        yield contagem
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", antes)


async def _mais_um_site_com_tarifa(db, nome: str):
    from app.models.charge_point import ChargePoint
    from app.models.enums import ChargePointStatus, ConnectorType, TariffType
    from app.models.site import Site
    from app.models.tariff import Tariff

    # Slug sorteado: o helper e chamado varias vezes no mesmo teste, e o
    # indice unico recusaria o segundo site.
    s = Site(
        id=uuid.uuid4(),
        slug=f"site-{uuid.uuid4().hex[:8]}",
        name=nome,
        grid_limit_kw=75,
        reserved_kw=10,
    )
    db.add(s)
    await db.flush()

    t = Tariff(
        id=uuid.uuid4(),
        site_id=s.id,
        name=f"Tarifa {nome}",
        type=TariffType.PER_KWH,
        price_per_kwh=2,
        active=True,
    )
    db.add(t)
    await db.flush()
    s.default_tariff_id = t.id

    db.add(
        ChargePoint(
            id=uuid.uuid4(),
            site_id=s.id,
            code=f"CP-{uuid.uuid4().hex[:4].upper()}",
            name=f"Ponto {nome}",
            connector=ConnectorType.TYPE2,
            rated_kw=22,
            min_kw=4.2,
            limit_kw=22,
            operator_max_kw=22,
            status=ChargePointStatus.AVAILABLE,
            enabled=True,
        )
    )
    await db.flush()
    return s


async def test_preco_das_estacoes_sai_em_uma_consulta_so(
    api, como_motorista, db, ponto, tarifa, contar_consultas
):
    """Tres estacoes, tres tarifas distintas - e uma unica consulta em tariffs."""
    await _mais_um_site_com_tarifa(db, "Segundo Site")
    await _mais_um_site_com_tarifa(db, "Terceiro Site")

    contar_consultas.clear()
    r = await api.get(f"{CAB}/stations", headers=como_motorista)
    assert r.status_code == 200

    assert len(r.json()) == 3, "as tres estacoes deveriam aparecer"
    assert contar_consultas.get("tariffs", 0) == 1, (
        f"o preco voltou a ser buscado por estacao: {contar_consultas}"
    )


async def test_precos_continuam_corretos_por_estacao(
    api, como_motorista, db, ponto, tarifa
):
    """Uma consulta so nao pode significar preco trocado entre estacoes."""
    await _mais_um_site_com_tarifa(db, "Outro Site")

    estacoes = (await api.get(f"{CAB}/stations", headers=como_motorista)).json()
    for e in estacoes:
        assert e["price_per_kwh"] == 2.0, e
