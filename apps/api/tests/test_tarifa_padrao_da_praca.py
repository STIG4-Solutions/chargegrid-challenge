"""A primeira tarifa de uma praca vira a PADRAO dela.

`default_tariff_id` so' era definido dentro do `seed()`. Enquanto apenas o seed
criava praca isso bastava - mas desde que o painel ganhou "Nova praca", toda praca
nascida pelo produto ficava sem tarifa padrao e sem jeito de ganhar uma: nao ha
rota que a defina.

Nenhuma das tres consequencias dava erro, e foi por isso que passou:

  - `session_service` precifica por cartao > ponto > PADRAO DO SITE. Sem nenhum
    dos tres a sessao fica sem tarifa e sem fatura.
  - o app do motorista so' mostra preco quando ha padrao.
  - `forecast/banco._TARIFAS` junta por `default_tariff_id`, entao a previsao
    daquela praca saia sem faturamento.

Encontrado no staging: duas pracas criadas pelo produto, ambas com zero tarifas.
"""

import uuid

from sqlalchemy import select

from app.models.site import Site

ROTA = "/api/v1/tariffs"

CORPO = {
    "name": "Tarifa por Energia",
    "type": "per_kwh",
    "price_per_kwh": 2.60,
    "min_charge": 5.0,
}


async def _padrao_do_site(db, site_id) -> uuid.UUID | None:
    site = (await db.execute(select(Site).where(Site.id == site_id))).scalar_one()
    return site.default_tariff_id


async def test_a_primeira_tarifa_da_praca_vira_a_padrao(db, api, site, como_operador_do_site):
    """A praca nasce sem padrao, e a primeira tarifa a resolve."""
    assert await _padrao_do_site(db, site.id) is None

    r = await api.post(ROTA, json=CORPO, headers=como_operador_do_site)
    assert r.status_code == 201
    criada = uuid.UUID(r.json()["id"])

    assert await _padrao_do_site(db, site.id) == criada


async def test_a_segunda_tarifa_nao_rouba_o_padrao(db, api, site, como_operador_do_site):
    """Trocar a tarifa padrao exige acao explicita.

    Se cadastrar a segunda tarifa mudasse o padrao, o preco de toda sessao nova
    mudaria como efeito colateral de um cadastro - sem ninguem pedir.
    """
    primeira = uuid.UUID(
        (await api.post(ROTA, json=CORPO, headers=como_operador_do_site)).json()["id"]
    )
    outra = {
        **CORPO,
        "name": "Tarifa por Tempo",
        "type": "per_time",
        "price_per_kwh": 0,
        "price_per_min": 0.9,
    }
    segunda = await api.post(ROTA, json=outra, headers=como_operador_do_site)
    assert segunda.status_code == 201
    assert segunda.json()["id"] != str(primeira)

    assert await _padrao_do_site(db, site.id) == primeira


async def test_a_tarifa_de_uma_praca_nao_vira_padrao_da_vizinha(
    db, api, site, segundo_site, como_operador_do_site
):
    """Escopo: o padrao definido e' o da praca de quem cadastrou."""
    r = await api.post(ROTA, json=CORPO, headers=como_operador_do_site)
    assert r.status_code == 201

    assert await _padrao_do_site(db, site.id) is not None
    assert await _padrao_do_site(db, segundo_site.id) is None


async def test_uma_praca_que_ja_tem_padrao_o_conserva(db, api, site, tarifa, como_operador_do_site):
    """A fixture `tarifa` NAO define o padrao, entao este teste o define a mao.

    O que se prende aqui e' a guarda `if site.default_tariff_id is None`: sem ela,
    qualquer cadastro posterior sobrescreveria a escolha de quem opera.
    """
    site.default_tariff_id = tarifa.id
    await db.flush()

    r = await api.post(ROTA, json=CORPO, headers=como_operador_do_site)
    assert r.status_code == 201
    assert r.json()["id"] != str(tarifa.id)

    assert await _padrao_do_site(db, site.id) == tarifa.id


async def test_motorista_nao_cadastra_tarifa(api, como_motorista):
    """A regra nova nao afrouxa o papel: quem nao opera nao cadastra.

    A fixture entra por parametro, e nao por `request.getfixturevalue`: as
    fixtures daqui sao assincronas, e pedi-las por nome devolve a corrotina em vez
    do valor - o erro que sai e' "coroutine was never awaited", que nao aponta
    para ca'.
    """
    r = await api.post(ROTA, json=CORPO, headers=como_motorista)
    assert r.status_code == 403
