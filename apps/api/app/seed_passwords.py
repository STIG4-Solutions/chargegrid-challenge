"""Sincroniza as senhas das contas de demonstração já criadas pelo seed."""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models.user import User
from app.seed import DRIVERS

log = get_logger(__name__)


def passwords_by_email(
    admin_password: str | None,
    operator_password: str | None,
    driver_password: str | None,
) -> dict[str, str]:
    """Monta o conjunto fechado de contas gerenciadas pelo seed."""
    if not admin_password or not operator_password or not driver_password:
        raise RuntimeError("as três variáveis SEED_*_PASSWORD são obrigatórias")

    passwords = {
        "admin@chargegrid.com.br": admin_password,
        "operador@chargegrid.com.br": operator_password,
    }
    passwords.update({email: driver_password for email, *_ in DRIVERS})
    return passwords


async def sync_passwords(db: AsyncSession, passwords: dict[str, str]) -> int:
    """Atualiza somente as contas conhecidas, ou falha sem gravar nada."""
    users = list((await db.execute(select(User).where(User.email.in_(passwords)))).scalars().all())
    found = {user.email for user in users}
    missing = sorted(set(passwords) - found)
    if missing:
        raise RuntimeError(f"contas da seed ausentes: {', '.join(missing)}")

    for user in users:
        user.hashed_password = hash_password(passwords[user.email])
    await db.commit()
    return len(users)


async def main() -> None:
    configure_logging()
    cfg = get_settings()
    passwords = passwords_by_email(
        cfg.seed_admin_password,
        cfg.seed_operator_password,
        cfg.seed_driver_password,
    )
    async with SessionLocal() as db:
        updated = await sync_passwords(db, passwords)
    await engine.dispose()
    log.info("seed.passwords_synced", accounts=updated)


if __name__ == "__main__":
    asyncio.run(main())
