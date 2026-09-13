"""Cadastro publico do app do motorista.

A rota existia desde sempre, testada por NINGUEM - o que e' coerente com o resto
da historia dela: nao havia tela que a chamasse, entao nao havia nada que
quebrasse ao mexer nela. Ela passa a ter tela agora, e por isso passa a ter
teste.

O que estes testes fixam nao e' "cria usuario". Sao as duas metades da mesma
guarda:

  - o SCHEMA nao aceita `role` nem `site_id`;
  - a ROTA fixa `role="driver"` no corpo da funcao.

Uma so' bastaria hoje. As duas juntas e' que sobrevivem ao refactor: o idioma
`Model(**payload.model_dump())` aparece em `mobile.py` e `power.py`, e no dia em
que alguem aplicar aqui, com o schema aceitando `role`, qualquer pessoa na
internet cria um admin.

A MUTACAO MOSTRA ISSO, e o resultado precisa ficar escrito para nao parecer
teste fraco: devolver `role` e `site_id` ao schema, sozinho, NAO quebra nada -
a rota continua fixando `driver`. E' defesa em profundidade de graca, a mesma
situacao ja registrada em `patrocinador='frota'`, onde reverter so' o CHECK
tambem nao trazia o valor de volta.

Quebrar exige derrubar as DUAS: schema aceitando o campo E a rota construindo
por `model_dump()`. Feito isso, `test_papel_enviado_no_corpo_e_ignorado` e
`test_site_enviado_no_corpo_e_ignorado` caem juntos - que e' exatamente o
cenario que o refactor futuro produziria.
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.enums import UserRole
from app.models.user import User

NOVO = {
    "email": "maria.souza@email.com",
    "full_name": "Maria Souza",
    "password": "senha-bem-comprida",
    "phone": "+5511999990000",
    "document": "12345678901",
}


async def _do_banco(db, email: str) -> User | None:
    return (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()


# ------------------------------------------------------------------ o caminho


async def test_cadastro_cria_motorista(api, db):
    r = await api.post("/api/v1/auth/register", json=NOVO)

    assert r.status_code == 201, r.text
    assert r.json()["email"] == NOVO["email"]
    assert r.json()["role"] == "driver"

    criado = await _do_banco(db, NOVO["email"])
    assert criado is not None
    assert criado.phone == NOVO["phone"]
    assert criado.document == NOVO["document"]


async def test_telefone_e_documento_sao_opcionais(api):
    r = await api.post(
        "/api/v1/auth/register",
        json={"email": "sem.contato@email.com", "full_name": "Sem Contato", "password": "12345678"},
    )
    assert r.status_code == 201, r.text


async def test_quem_se_cadastra_consegue_entrar(api):
    """O ciclo que o app depende: a rota devolve o USUARIO, nao um token.

    Sem o login logo em seguida, quem acabou de se cadastrar ficaria numa tela
    de sucesso sem sessao - cadastrado e de fora ao mesmo tempo.
    """
    await api.post("/api/v1/auth/register", json=NOVO)

    entrada = await api.post(
        "/api/v1/auth/login",
        json={"email": NOVO["email"], "password": NOVO["password"]},
    )

    assert entrada.status_code == 200, entrada.text
    assert entrada.json()["access_token"]


# -------------------------------------------------------------- a guarda


async def test_papel_enviado_no_corpo_e_ignorado(api, db):
    """A razao de `RegistroPublicoIn` existir.

    Rota publica, sem token: quem posta escolhe o corpo. Se `role` chegasse ao
    modelo, criar um admin da rede seria uma linha de curl.
    """
    r = await api.post("/api/v1/auth/register", json={**NOVO, "role": "admin"})

    assert r.status_code == 201, r.text
    assert r.json()["role"] == "driver"
    criado = await _do_banco(db, NOVO["email"])
    assert criado.role == UserRole.DRIVER


async def test_site_enviado_no_corpo_e_ignorado(api, db, site):
    """`site_id` e' o que amarra um operador a uma praca.

    Vindo do cadastro publico, seria um desconhecido nascendo com escopo de um
    estabelecimento que nao e' dele.
    """
    r = await api.post("/api/v1/auth/register", json={**NOVO, "site_id": str(site.id)})

    assert r.status_code == 201, r.text
    criado = await _do_banco(db, NOVO["email"])
    assert criado.site_id is None


async def test_motorista_criado_nao_alcanca_rota_de_operador(api):
    """Fecha a guarda pelo efeito, e nao pelo campo.

    Os dois testes acima olham o que foi gravado; este olha o que a conta
    CONSEGUE. Se um dia o papel passar a ser decidido por outro caminho, e' ele
    que continua acusando.
    """
    await api.post("/api/v1/auth/register", json=NOVO)
    entrada = await api.post(
        "/api/v1/auth/login",
        json={"email": NOVO["email"], "password": NOVO["password"]},
    )
    token = entrada.json()["access_token"]

    r = await api.get("/api/v1/audit", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 403


# ------------------------------------------------------------------ recusas


async def test_email_repetido_da_409(api):
    await api.post("/api/v1/auth/register", json=NOVO)

    r = await api.post("/api/v1/auth/register", json=NOVO)

    assert r.status_code == 409
    assert "cadastrado" in r.json()["detail"]


async def test_senha_curta_e_recusada(api):
    """`min_length=8` no schema. O app espelha o piso, mas o servidor manda."""
    r = await api.post("/api/v1/auth/register", json={**NOVO, "password": "1234567"})
    assert r.status_code == 422


async def test_nome_de_uma_letra_e_recusado(api):
    r = await api.post("/api/v1/auth/register", json={**NOVO, "full_name": "M"})
    assert r.status_code == 422


async def test_email_invalido_e_recusado(api):
    r = await api.post("/api/v1/auth/register", json={**NOVO, "email": "nao-e-email"})
    assert r.status_code == 422
