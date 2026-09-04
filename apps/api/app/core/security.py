"""Hash de senha e emissão/verificação de JWT."""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

ACCESS = "access"
REFRESH = "refresh"


def _prepare(plain: str) -> bytes:
    """Normaliza a senha para 44 bytes antes do bcrypt.

    O bcrypt opera sobre no maximo 72 bytes e ignora tudo depois do primeiro
    byte nulo. O pre-hash SHA-256 em base64 remove os dois limites sem descartar
    entropia - e a mesma construcao do esquema bcrypt_sha256.
    """
    return base64.b64encode(hashlib.sha256(plain.encode("utf-8")).digest())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prepare(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("ascii"))
    except ValueError:
        # Hash malformado no banco nao pode derrubar o login com excecao.
        return False


def _create_token(subject: str, token_type: str, expires: timedelta, claims: dict[str, Any]) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires,
        **claims,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, **claims: Any) -> str:
    return _create_token(
        subject, ACCESS, timedelta(minutes=settings.access_token_expire_minutes), claims
    )


def create_refresh_token(subject: str, **claims: Any) -> str:
    return _create_token(
        subject, REFRESH, timedelta(days=settings.refresh_token_expire_days), claims
    )


def decode_token(token: str, expected_type: str = ACCESS) -> dict[str, Any]:
    """Levanta jwt.PyJWTError se inválido/expirado ou se o tipo não bater."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"esperado token do tipo {expected_type}")
    return payload
