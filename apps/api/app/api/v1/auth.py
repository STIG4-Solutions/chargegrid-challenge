"""Autenticacao: login do dashboard e do app mobile compartilham o mesmo emissor."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.security import (
    REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegistroPublicoIn,
    TokenPair,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["autenticação"])


def _tokens(user: User) -> TokenPair:
    claims = {"role": str(user.role), "site_id": str(user.site_id) if user.site_id else None}
    return TokenPair(
        access_token=create_access_token(str(user.id), **claims),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=settings.access_token_expire_minutes * 60,
    )


async def _authenticate(db, email: str, password: str) -> User:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    # Verifica o hash mesmo sem usuario, para nao vazar quais emails existem.
    reference = user.hashed_password if user else hash_password("timing-safe-placeholder")
    valid = verify_password(password, reference)
    if user is None or not valid or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="e-mail ou senha inválidos"
        )
    user.last_login_at = datetime.now(UTC)
    return user


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: DbSession) -> TokenPair:
    user = await _authenticate(db, payload.email, payload.password)
    await db.commit()
    return _tokens(user)


@router.post("/token", response_model=TokenPair, include_in_schema=False)
async def login_form(
    db: DbSession, form: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> TokenPair:
    """Fluxo password do OAuth2 - alimenta o botao Authorize do Swagger."""
    user = await _authenticate(db, form.username, form.password)
    await db.commit()
    return _tokens(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token, expected_type=REFRESH)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="refresh token inválido") from exc
    user = (await db.execute(select(User).where(User.id == claims["sub"]))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="usuário inativo")
    return _tokens(user)


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: RegistroPublicoIn, db: DbSession) -> User:
    """Cadastro publico do app do motorista - sempre cria motorista.

    `role` e' fixado aqui e o schema nem aceita o campo: sao as duas metades da
    mesma guarda. Ver `RegistroPublicoIn` para o porque de nao bastar uma.

    Contas de operador e admin nascem do seed. Uma rota de administracao de
    contas nao existe ainda - ate' ela existir, esta docstring nao aponta para
    lugar nenhum de proposito, porque apontar para uma rota inexistente foi
    exatamente o que esta linha fazia antes.
    """
    exists = (
        await db.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="e-mail já cadastrado")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role="driver",
        phone=payload.phone,
        document=payload.document,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user
