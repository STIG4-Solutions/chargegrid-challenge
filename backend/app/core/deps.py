"""Dependencias de autenticacao e autorizacao."""

from __future__ import annotations

import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.site import Site
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/token")

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(db: DbSession, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise credentials_error from exc

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    """Guarda de papel: o dashboard comercial nao pode ser operado por motorista."""

    async def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"acesso restrito a: {', '.join(str(r) for r in roles)}",
            )
        return user

    return dependency


require_operator = require_roles(UserRole.ADMIN, UserRole.OPERATOR)
require_admin = require_roles(UserRole.ADMIN)

OperatorUser = Annotated[User, Depends(require_operator)]
AdminUser = Annotated[User, Depends(require_admin)]


async def get_scoped_site_id(db: DbSession, user: OperatorUser) -> uuid.UUID:
    """Site do operador logado.

    Multi-tenant por construcao: o operador so enxerga o proprio estabelecimento.
    Admin sem site vinculado cai no primeiro site (cenario de instalacao unica).
    """
    if user.site_id is not None:
        return user.site_id
    site_id = (
        await db.execute(select(Site.id).order_by(Site.created_at).limit(1))
    ).scalar_one_or_none()
    if site_id is None:
        raise HTTPException(status_code=404, detail="nenhum site cadastrado")
    return site_id


ScopedSiteId = Annotated[uuid.UUID, Depends(get_scoped_site_id)]
