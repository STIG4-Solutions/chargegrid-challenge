"""Abrir uma praca na rede.

Ate esta rota existir, `Site` so' nascia dentro do `seed()` — e a falta nao
aparecia em log nenhum, aparecia na tela: seletor de praca e Visao de Rede so'
se mostram com mais de um site, entao um ambiente real ficava preso ao que o
seed criou e a promessa multi-praca nao tinha caminho.

O que estes testes fixam nao e' "cria a linha". E' o que faz uma praca nascer
quebrada de um jeito que ninguem percebe na hora:

- reserva maior que o limite deixa o orcamento negativo: a praca aparece no
  seletor, aceita sessao e rateia zero para todos;
- fuso digitado errado passa por qualquer `max_length` e so' falha muito
  depois, na primeira conta de janela horaria — como numero errado, nao
  como erro;
- slug repetido quebraria no indice unico, e `IntegrityError` nao e' resposta
  para uma pessoa que escolheu o identificador;
- e operador nao decide que a rede tem outra praca.
"""

from sqlalchemy import select

from app.models.enums import UserRole
from app.models.site import Site

NOVA = {
    "nome": "Shopping Ibirapuera",
    "slug": "shopping-ibirapuera",
    "cidade": "São Paulo",
    "estado": "sp",
    "timezone": "America/Sao_Paulo",
    "limite_da_rede_kw": 150,
    "reserva_kw": 30,
}


async def test_admin_abre_uma_praca(api, db, como_admin):
    resposta = await api.post("/api/v1/power/sites", json=NOVA, headers=como_admin)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["nome"] == "Shopping Ibirapuera"
    # Devolve no formato do SELETOR, e nao o registro cru: quem acabou de
    # cadastrar escolhe a praca sem uma segunda chamada.
    assert set(corpo) == {"site_id", "nome", "cidade", "estado", "timezone"}

    site = (await db.execute(select(Site).where(Site.slug == "shopping-ibirapuera"))).scalar_one()
    assert float(site.grid_limit_kw) == 150
    assert float(site.reserved_kw) == 30
    assert site.state == "SP", "a UF é normalizada para maiúscula"


async def test_a_praca_nova_aparece_no_seletor(api, db, site, como_admin):
    """É o ponto inteiro da rota: com duas praças, o seletor passa a existir."""
    antes = await api.get("/api/v1/power/sites", headers=como_admin)
    assert len(antes.json()) == 1

    await api.post("/api/v1/power/sites", json=NOVA, headers=como_admin)

    depois = await api.get("/api/v1/power/sites", headers=como_admin)
    assert len(depois.json()) == 2
    assert "Shopping Ibirapuera" in [s["nome"] for s in depois.json()]


async def test_reserva_maior_que_o_limite_e_recusada(api, como_admin):
    """Orçamento negativo é uma praça que não carrega ninguém, e não avisa."""
    resposta = await api.post(
        "/api/v1/power/sites",
        json={**NOVA, "limite_da_rede_kw": 50, "reserva_kw": 80},
        headers=como_admin,
    )

    assert resposta.status_code == 409
    assert "reserva" in resposta.json()["detail"].lower()


async def test_fuso_desconhecido_e_recusado(api, como_admin):
    """`America/Sao_Pualo` tem o tamanho certo e o conteúdo errado.

    Sem esta guarda ele entraria, e o erro apareceria semanas depois como
    janela tarifária cobrando no horário errado.
    """
    resposta = await api.post(
        "/api/v1/power/sites",
        json={**NOVA, "timezone": "America/Sao_Pualo"},
        headers=como_admin,
    )

    assert resposta.status_code == 409
    assert "fuso" in resposta.json()["detail"].lower()


async def test_slug_repetido_responde_409_e_nao_erro_de_banco(api, como_admin):
    await api.post("/api/v1/power/sites", json=NOVA, headers=como_admin)

    resposta = await api.post(
        "/api/v1/power/sites", json={**NOVA, "nome": "Outro nome"}, headers=como_admin
    )

    assert resposta.status_code == 409
    assert "shopping-ibirapuera" in resposta.json()["detail"]


async def test_slug_com_maiuscula_ou_espaco_e_recusado(api, como_admin):
    """O slug vai para o artefato do modelo de previsão e para a URL.

    Duas grafias do mesmo local fazem o modelo cair em fallback silencioso.
    """
    for ruim in ("Shopping Ibirapuera", "shopping_ibirapuera", "shopping--x", "-x"):
        resposta = await api.post(
            "/api/v1/power/sites", json={**NOVA, "slug": ruim}, headers=como_admin
        )
        assert resposta.status_code == 422, f"aceitou slug inválido: {ruim!r}"


async def test_limite_da_rede_zero_e_recusado(api, como_admin):
    """Praça sem potência fica de pé, aparece no seletor e não carrega ninguém."""
    resposta = await api.post(
        "/api/v1/power/sites", json={**NOVA, "limite_da_rede_kw": 0}, headers=como_admin
    )

    assert resposta.status_code == 422


async def test_operador_nao_abre_praca(api, db, como_operador):
    """Quem opera uma praça não decide que a rede tem outra."""
    resposta = await api.post("/api/v1/power/sites", json=NOVA, headers=como_operador)

    assert resposta.status_code == 403
    assert (
        await db.execute(select(Site).where(Site.slug == "shopping-ibirapuera"))
    ).scalar_one_or_none() is None


async def test_o_cadastro_fica_na_trilha_de_auditoria(api, db, como_admin, administrador):
    from app.models.audit import AuditLog

    await api.post("/api/v1/power/sites", json=NOVA, headers=como_admin)

    linha = (
        await db.execute(select(AuditLog).where(AuditLog.action == "site.criado"))
    ).scalar_one()
    assert linha.actor_id == administrador.id
    assert linha.actor_email == administrador.email
    assert linha.after["slug"] == "shopping-ibirapuera"


async def test_a_praca_nasce_vazia(api, db, como_admin):
    """Sem ponto, tarifa ou método de pagamento — e isso é deliberado.

    Criar um ponto padrão inventaria hardware que ninguém instalou; uma tarifa
    padrão cobraria um preço que ninguém definiu.
    """
    from app.models.charge_point import ChargePoint

    corpo = (await api.post("/api/v1/power/sites", json=NOVA, headers=como_admin)).json()

    pontos = (
        (await db.execute(select(ChargePoint).where(ChargePoint.site_id == corpo["site_id"])))
        .scalars()
        .all()
    )
    assert pontos == []


async def test_operador_da_praca_nova_enxerga_so_ela(api, db, como_admin):
    """O escopo vale para a praça recém-criada como para qualquer outra."""
    from app.core.security import create_access_token
    from app.models.user import User

    corpo = (await api.post("/api/v1/power/sites", json=NOVA, headers=como_admin)).json()

    operador = User(
        email="operador.ibirapuera@chargegrid.com.br",
        full_name="Operador Ibirapuera",
        hashed_password="x",
        role=UserRole.OPERATOR,
        site_id=corpo["site_id"],
    )
    db.add(operador)
    await db.flush()

    visiveis = await api.get(
        "/api/v1/power/sites",
        headers={"Authorization": f"Bearer {create_access_token(str(operador.id))}"},
    )
    assert [s["nome"] for s in visiveis.json()] == ["Shopping Ibirapuera"]
