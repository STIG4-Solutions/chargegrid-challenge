"""Aparelhos que recebem notificacao push.

Um motorista pode ter mais de um: troca de celular, tablet, o aparelho velho
que ficou na gaveta. Por isso a chave e' o token, nao o usuario - e o token
pertence ao aparelho, nao a pessoa.

Isso importa numa situacao concreta: dois motoristas usando o mesmo aparelho
emprestado. Se o token ficasse preso ao primeiro que entrou, o segundo
receberia as notificacoes do primeiro - recarga concluida de uma sessao que
nao e dele, com o codigo e o valor. Registrar de novo no login apenas
reaponta o token para quem esta usando agora.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class PushDevice(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "push_devices"
    __table_args__ = (
        # O envio busca por usuario a cada evento notificavel.
        Index("ix_push_devices_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Token do servico de push (Expo). Unico: o mesmo aparelho registrando duas
    # vezes tem de sobrescrever o dono, nao criar uma segunda linha que faria a
    # notificacao sair duplicada no mesmo celular.
    token: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    platform: Mapped[str] = mapped_column(String(16), default="android", nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
