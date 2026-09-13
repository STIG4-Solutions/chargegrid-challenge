"""Contas de operacao: quem opera a rede, criado por quem administra a rede.

Ate' aqui, operador e admin so' nasciam do seed ou de um INSERT no banco. A
docstring de `/auth/register` chegou a apontar para uma rota `/users` que NUNCA
EXISTIU - conferido no contrato, 82 rotas, nenhuma delas.

QUEM PODE: admin, e so'. `ADMIN` ja' e' global por construcao neste projeto -
`get_scoped_site_id` o deixa escolher qualquer praca porque "administra a rede
inteira". Nao ha admin de site, entao nao ha conceito novo aqui: quem cria
operador e' a GoodWe, e nao o estabelecimento.

QUEM NAO APARECE: motorista. Esta tela e' sobre quem OPERA - motorista se
cadastra sozinho pelo app, e sao milhares. Misturar os dois transformaria a
lista de contas da operacao numa lista de clientes, e a acao de desligar - que
aqui significa "tirar o acesso de um funcionario" - passaria a significar
tambem "bloquear um cliente", que e' outra decisao, com outras consequencias e
outra tela. Bloquear motorista abusivo continua sem caminho, e isso e' limite
declarado, nao esquecimento.

NAO HA APAGAR. As FKs de auditoria e faturamento sao SET NULL: apagar a conta
apaga o vinculo do rastro dela. Desativar tira o acesso e preserva quem fez o
que.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core.deps import AdminUser, Auditor, DbSession
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.site import Site
from app.models.user import User
from app.schemas.auth import ContaAtivaIn, ContaNovaIn, ContaOut

router = APIRouter(prefix="/users", tags=["contas"])

# A tela e' sobre quem opera a rede. Motorista tem porta propria.
DA_OPERACAO = (UserRole.ADMIN, UserRole.OPERATOR)


def _saida(user: User, site_nome: str | None) -> ContaOut:
    return ContaOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        site_id=user.site_id,
        site_nome=site_nome,
        last_login_at=user.last_login_at,
    )


async def _da_operacao(db, user_id: uuid.UUID) -> User:
    """Busca a conta, recusando motorista pelo mesmo 404.

    404 e nao 403 para o motorista: dizer "existe, mas nao e' deste tipo" ja'
    confirmaria que o identificador existe.
    """
    conta = (
        await db.execute(select(User).where(User.id == user_id, User.role.in_(DA_OPERACAO)))
    ).scalar_one_or_none()
    if conta is None:
        raise HTTPException(status_code=404, detail="conta não encontrada")
    return conta


@router.get("", response_model=list[ContaOut])
async def listar_contas(
    db: DbSession,
    _: AdminUser,
    inativas: bool = Query(default=True, description="incluir contas desligadas"),
) -> list[ContaOut]:
    """As contas de operacao, com a praca de cada uma.

    Traz as inativas por padrao: a lista existe para administrar acesso, e uma
    conta desligada e' justamente a que alguem pode precisar religar. Esconde-la
    faria a tela parecer que ela nao existe, e a tentativa de recriar bateria
    no e-mail unico.
    """
    consulta = (
        select(User, Site.name)
        .join(Site, Site.id == User.site_id, isouter=True)
        .where(User.role.in_(DA_OPERACAO))
        .order_by(User.role, User.full_name)
    )
    if not inativas:
        consulta = consulta.where(User.is_active.is_(True))

    return [_saida(u, nome) for u, nome in (await db.execute(consulta)).all()]


@router.post("", response_model=ContaOut, status_code=201)
async def criar_conta(payload: ContaNovaIn, db: DbSession, _: AdminUser, aud: Auditor):
    """Cria operador ou admin.

    OPERADOR EXIGE `site_id`, e a guarda e' de seguranca, nao de formulario.
    `get_scoped_site_id` devolve o PRIMEIRO site cadastrado quando o usuario nao
    tem um - entao um operador criado sem praca nao ficaria sem acesso: ficaria
    com acesso a praca de outra pessoa, sem nada indicando isso na tela dele.
    """
    if payload.role == UserRole.OPERATOR and payload.site_id is None:
        raise HTTPException(
            status_code=422,
            detail="operador precisa de um site: sem ele, o escopo cai no primeiro da rede",
        )

    ja_existe = (
        await db.execute(select(User.id).where(User.email == payload.email))
    ).scalar_one_or_none()
    if ja_existe is not None:
        raise HTTPException(status_code=409, detail="e-mail já cadastrado")

    nome_do_site = None
    if payload.site_id is not None:
        nome_do_site = (
            await db.execute(select(Site.name).where(Site.id == payload.site_id))
        ).scalar_one_or_none()
        if nome_do_site is None:
            raise HTTPException(status_code=404, detail="site não encontrado")

    conta = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=UserRole(payload.role),
        site_id=payload.site_id,
        is_active=True,
    )
    db.add(conta)
    await db.flush()

    # A senha NAO entra no rastro, e nem depende da mascara para isso: o que nao
    # e' passado nao pode vazar. `SIGILOSAS` fica como segunda linha.
    await aud.registrar(
        db,
        "conta.criada",
        "user",
        entidade_id=conta.id,
        depois={"email": conta.email, "papel": str(conta.role), "site_id": str(payload.site_id)},
    )
    await db.commit()
    await db.refresh(conta)
    return _saida(conta, nome_do_site)


@router.patch("/{user_id}", response_model=ContaOut)
async def mudar_acesso(
    user_id: uuid.UUID, payload: ContaAtivaIn, db: DbSession, admin: AdminUser, aud: Auditor
):
    """Liga ou desliga o acesso.

    UMA guarda: ninguem desliga a propria conta. Um clique distraido tiraria o
    proprio acesso, e religar exigiria outro admin - ou o banco.

    E NAO ha guarda de "ultimo admin ativo", embora ela pareca obrigatoria aqui.
    Foi escrita e removida: e' INALCANCAVEL. Quem chama esta rota e' um admin
    ATIVO - `get_current_user` recusa conta desligada com 401 -, entao desligar
    OUTRO admin sempre deixa pelo menos o proprio solicitante de pe', e desligar
    a si mesmo esbarra na guarda acima antes de chegar la'. A regra que ela
    tentava impor ja' e' consequencia desta, e um `if` que nunca roda parece
    protecao sem proteger nada.
    """
    conta = await _da_operacao(db, user_id)

    if conta.id == admin.id and not payload.is_active:
        raise HTTPException(status_code=409, detail="você não pode desligar a própria conta")

    antes = conta.is_active
    conta.is_active = payload.is_active

    # Sem rastro quando nada mudou: religar quem ja' estava ligado nao e' um
    # fato, e a trilha existe para guardar fato.
    if antes != conta.is_active:
        await aud.registrar(
            db,
            "conta.ativada" if payload.is_active else "conta.desativada",
            "user",
            entidade_id=conta.id,
            antes={"is_active": antes},
            depois={"is_active": conta.is_active, "email": conta.email},
        )
    await db.commit()
    await db.refresh(conta)

    nome = (
        await db.execute(select(Site.name).where(Site.id == conta.site_id))
    ).scalar_one_or_none()
    return _saida(conta, nome)
