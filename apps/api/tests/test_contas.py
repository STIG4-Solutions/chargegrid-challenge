"""Contas de operacao, criadas por admin da rede.

Ate' aqui operador e admin so' nasciam do seed ou de SQL - e a docstring de
`/auth/register` apontava para uma rota `/users` que nunca existiu.

O que estes testes fixam, alem de "cria conta":

  - so' ADMIN entra. Operador administrando contas criaria a propria conta de
    admin, e a hierarquia deixaria de existir;
  - OPERADOR EXIGE SITE. Sem `site_id`, `get_scoped_site_id` cai no PRIMEIRO
    site da rede - entao um operador sem praca nao fica sem acesso, fica com o
    acesso da praca errada. E' a guarda menos obvia e a mais importante;
  - NINGUEM SE TRANCA DO LADO DE FORA: nao da' para desligar a propria conta. A
    saida seria um UPDATE no banco, que e' exatamente o estado que esta rota
    veio desfazer.

Uma guarda de "ultimo admin ativo" chegou a ser escrita e foi REMOVIDA por ser
inalcancavel - `test_desligar_outro_admin_pode` guarda o raciocinio, para que
ela nao volte por parecer obrigatoria.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.enums import UserRole
from app.models.user import User

NOVA = {
    "email": "operador.novo@chargegrid.com.br",
    "full_name": "Operador Novo",
    "password": "senha-bem-comprida",
    "role": "operator",
}


async def _conta(db, email: str) -> User | None:
    return (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def _acoes(db) -> list[str]:
    linhas = (await db.execute(select(AuditLog.action))).scalars().all()
    return list(linhas)


# ------------------------------------------------------------------ quem pode


async def test_admin_cria_operador(api, como_admin, db, site):
    r = await api.post("/api/v1/users", headers=como_admin, json={**NOVA, "site_id": str(site.id)})

    assert r.status_code == 201, r.text
    assert r.json()["role"] == "operator"
    assert r.json()["site_nome"] == site.name
    assert r.json()["is_active"] is True

    criada = await _conta(db, NOVA["email"])
    assert criada.site_id == site.id
    assert criada.hashed_password != NOVA["password"], "senha gravada em claro"


async def test_operador_nao_cria_conta(api, como_operador_do_site, site):
    """A hierarquia so' existe se o degrau de baixo nao puder criar o de cima."""
    r = await api.post(
        "/api/v1/users", headers=como_operador_do_site, json={**NOVA, "site_id": str(site.id)}
    )
    assert r.status_code == 403


async def test_motorista_nao_cria_conta(api, como_motorista, site):
    r = await api.post(
        "/api/v1/users", headers=como_motorista, json={**NOVA, "site_id": str(site.id)}
    )
    assert r.status_code == 403


async def test_operador_nao_le_a_lista(api, como_operador_do_site):
    """A lista diz quem tem acesso a que na rede inteira."""
    assert (await api.get("/api/v1/users", headers=como_operador_do_site)).status_code == 403


# ---------------------------------------------------- operador exige site


async def test_operador_sem_site_e_recusado(api, como_admin, db):
    """A guarda que nao parece guarda.

    `get_scoped_site_id` devolve o primeiro site cadastrado para quem nao tem
    `site_id`. Um operador criado sem praca abriria o painel vendo a praca de
    outra pessoa, sem nada na tela indicando isso.
    """
    r = await api.post("/api/v1/users", headers=como_admin, json=NOVA)

    assert r.status_code == 422
    assert await _conta(db, NOVA["email"]) is None, "recusou e criou assim mesmo"


async def test_admin_pode_nao_ter_site(api, como_admin):
    """Admin e' global: `site_id` nele e' so' a praca que abre por padrao."""
    r = await api.post(
        "/api/v1/users",
        headers=como_admin,
        json={**NOVA, "email": "admin.novo@chargegrid.com.br", "role": "admin"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["site_id"] is None


async def test_site_inexistente_da_404(api, como_admin):
    r = await api.post(
        "/api/v1/users", headers=como_admin, json={**NOVA, "site_id": str(uuid.uuid4())}
    )
    assert r.status_code == 404


async def test_papel_motorista_e_recusado_pelo_schema(api, como_admin, site):
    """Motorista se cadastra sozinho. Criado daqui, nasceria com uma senha
    escolhida por outra pessoa."""
    r = await api.post(
        "/api/v1/users",
        headers=como_admin,
        json={**NOVA, "role": "driver", "site_id": str(site.id)},
    )
    assert r.status_code == 422


async def test_email_repetido_da_409(api, como_admin, site, motorista):
    r = await api.post(
        "/api/v1/users",
        headers=como_admin,
        json={**NOVA, "email": motorista.email, "site_id": str(site.id)},
    )
    assert r.status_code == 409


# ------------------------------------------------------------------ a lista


async def test_a_lista_traz_operacao_e_nao_motorista(api, como_admin, motorista):
    r = await api.get("/api/v1/users", headers=como_admin)

    assert r.status_code == 200, r.text
    papeis = {c["role"] for c in r.json()}
    assert papeis <= {"admin", "operator"}
    assert motorista.email not in [c["email"] for c in r.json()]


async def test_a_lista_traz_desligados_por_padrao(api, como_admin, db, operador):
    operador.is_active = False
    await db.flush()

    todos = await api.get("/api/v1/users", headers=como_admin)
    so_ativos = await api.get("/api/v1/users", headers=como_admin, params={"inativas": "false"})

    assert operador.email in [c["email"] for c in todos.json()]
    assert operador.email not in [c["email"] for c in so_ativos.json()]


async def test_a_lista_nao_vaza_senha(api, como_admin):
    r = await api.get("/api/v1/users", headers=como_admin)
    assert "hashed_password" not in str(r.json())
    assert "wallet_balance" not in str(r.json()), "saldo e' dado de motorista"


# ------------------------------------------------------------------ acesso


async def test_admin_desliga_operador(api, como_admin, db, operador):
    r = await api.patch(
        f"/api/v1/users/{operador.id}", headers=como_admin, json={"is_active": False}
    )

    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False
    await db.refresh(operador)
    assert operador.is_active is False


async def test_desligado_nao_entra_mais(api, como_admin, site):
    """O efeito, e nao so' a coluna.

    Cria pela ROTA, e nao pela fixture `operador`: aquela grava
    `hashed_password="x"`, entao o login falharia por senha errada e o teste
    passaria sem provar nada sobre o desligamento. Aqui a senha e' conhecida e o
    login funciona ANTES - e' isso que faz o 401 depois significar alguma coisa.
    """
    criada = await api.post(
        "/api/v1/users", headers=como_admin, json={**NOVA, "site_id": str(site.id)}
    )
    credenciais = {"email": NOVA["email"], "password": NOVA["password"]}
    assert (await api.post("/api/v1/auth/login", json=credenciais)).status_code == 200

    await api.patch(
        f"/api/v1/users/{criada.json()['id']}", headers=como_admin, json={"is_active": False}
    )

    assert (await api.post("/api/v1/auth/login", json=credenciais)).status_code == 401


async def test_ninguem_desliga_a_propria_conta(api, como_admin, db, administrador):
    r = await api.patch(
        f"/api/v1/users/{administrador.id}", headers=como_admin, json={"is_active": False}
    )

    assert r.status_code == 409
    await db.refresh(administrador)
    assert administrador.is_active is True


async def test_desligar_outro_admin_pode(db, api, como_admin):
    """Nao ha guarda de "ultimo admin ativo", e este teste registra por que.

    Ela foi escrita e removida: era INALCANCAVEL. Quem chama a rota e' um admin
    ativo - conta desligada leva 401 no `get_current_user` -, entao desligar
    outro admin sempre deixa o solicitante de pe'; e desligar a si mesmo esbarra
    na outra guarda antes. A regra ja' e' consequencia daquela.

    O que sobra e' isto: desligar outro admin FUNCIONA, e nao ha `if` fingindo
    impedir.
    """
    outro = User(
        email="admin.extra@chargegrid.com.br",
        full_name="Admin Extra",
        hashed_password="x",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(outro)
    await db.flush()

    r = await api.patch(f"/api/v1/users/{outro.id}", headers=como_admin, json={"is_active": False})

    assert r.status_code == 200, r.text
    await db.refresh(outro)
    assert outro.is_active is False


async def test_religar_quem_ja_esta_ligado_nao_deixa_rastro(api, como_admin, db, operador):
    """A trilha guarda FATO. "Continuou ligado" nao e' um."""
    antes = len([a for a in await _acoes(db) if a.startswith("conta.")])

    r = await api.patch(
        f"/api/v1/users/{operador.id}", headers=como_admin, json={"is_active": True}
    )

    assert r.status_code == 200
    assert len([a for a in await _acoes(db) if a.startswith("conta.")]) == antes


async def test_conta_de_motorista_nao_e_alcancavel(api, como_admin, motorista):
    """404 e nao 403: a porta do motorista e' outra, e dizer "existe mas nao e'
    deste tipo" ja' confirma o identificador."""
    r = await api.patch(
        f"/api/v1/users/{motorista.id}", headers=como_admin, json={"is_active": False}
    )
    assert r.status_code == 404


# ------------------------------------------------------------------ rastro


async def test_criar_conta_deixa_rastro_sem_a_senha(api, como_admin, db, site, administrador):
    await api.post("/api/v1/users", headers=como_admin, json={**NOVA, "site_id": str(site.id)})

    linha = (
        (await db.execute(select(AuditLog).where(AuditLog.action == "conta.criada")))
        .scalars()
        .first()
    )

    assert linha is not None
    assert linha.actor_email == administrador.email
    assert linha.after["papel"] == "operator"
    assert NOVA["password"] not in str(linha.before) + str(linha.after)


async def test_desligar_deixa_rastro(api, como_admin, db, operador):
    await api.patch(f"/api/v1/users/{operador.id}", headers=como_admin, json={"is_active": False})

    linha = (
        (await db.execute(select(AuditLog).where(AuditLog.action == "conta.desativada")))
        .scalars()
        .first()
    )

    assert linha is not None
    assert linha.entity_id == str(operador.id)
    assert linha.before["is_active"] is True
    assert linha.after["is_active"] is False
