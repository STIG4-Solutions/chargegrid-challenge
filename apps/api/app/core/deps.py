"""Dependencias de autenticacao e autorizacao."""

from __future__ import annotations

import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Query, status
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

# Contrapartida do require_operator: as rotas /app/* sao do motorista.
#
# Sem esta guarda um token de operador entrava nelas e recebia 200. Nao havia
# vazamento - todas filtram por user.id, entao o operador via a propria lista
# vazia -, mas a ESCRITA passava: dava para cadastrar veiculo, agendar, iniciar
# sessao e creditar a propria carteira com uma conta que nao e de motorista.
#
# Admin fica de fora de proposito. Nao e privilegio que falta: as rotas se
# apoiam em user.id para achar veiculos, faturas e agendamentos, e um admin nao
# tem nenhum. Deixa-lo entrar so criaria estado de motorista pendurado numa
# conta administrativa.
require_driver = require_roles(UserRole.DRIVER)

async def require_fleet_manager(user: DriverUser) -> User:
    """Gestor de frota: um recorte de LEITURA sobre o papel de motorista.

    Nao vira `operator` de proposito. Operador administra estabelecimento, e o
    gestor nao administra nenhum - dar-lhe esse papel abriria o painel de sites
    onde a frota nem carrega. Ele ve o consolidado da propria frota e mais nada.
    """
    if not user.fleet_manager or user.fleet_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="conta sem permissão de gestor de frota",
        )
    return user


OperatorUser = Annotated[User, Depends(require_operator)]
AdminUser = Annotated[User, Depends(require_admin)]
DriverUser = Annotated[User, Depends(require_driver)]
FleetManager = Annotated[User, Depends(require_fleet_manager)]


async def get_scoped_site_id(
    db: DbSession,
    user: OperatorUser,
    site_id: Annotated[
        uuid.UUID | None, Query(description="admin: escolhe o site da rede")
    ] = None,
) -> uuid.UUID:
    """Site em que a requisicao opera.

    Multi-tenant por construcao. A assimetria entre os dois papeis e deliberada:

      OPERADOR - sempre o proprio estabelecimento. O parametro `site_id` da
      query e ignorado por completo, nao rejeitado: rejeitar com 403 avisaria
      que o id existe. Como o valor nunca chega a ser lido, nao ha caminho em
      que um operador alcance dado de outro site alterando a URL.

      ADMIN - pode escolher, porque e' quem administra a rede inteira e precisa
      comparar praca com praca. Sem escolha explicita, cai no proprio site e,
      nao tendo um, no primeiro cadastrado (instalacao unica).

    O site escolhido pelo admin e' conferido contra o banco antes de voltar: sem
    isso, um uuid digitado errado nao daria erro nenhum - as consultas apenas
    filtrariam por um id inexistente e a tela mostraria um site vazio, que se
    parece exatamente com uma praca sem movimento.
    """
    if user.site_id is not None and user.role != UserRole.ADMIN:
        return user.site_id

    if user.role == UserRole.ADMIN and site_id is not None:
        existe = (
            await db.execute(select(Site.id).where(Site.id == site_id))
        ).scalar_one_or_none()
        if existe is None:
            raise HTTPException(status_code=404, detail="site não encontrado")
        return existe

    if user.site_id is not None:
        return user.site_id

    primeiro = (
        await db.execute(select(Site.id).order_by(Site.created_at).limit(1))
    ).scalar_one_or_none()
    if primeiro is None:
        raise HTTPException(status_code=404, detail="nenhum site cadastrado")
    return primeiro


ScopedSiteId = Annotated[uuid.UUID, Depends(get_scoped_site_id)]
