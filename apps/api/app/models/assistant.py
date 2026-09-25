"""Conversas do assistente do operador.

Persistidas, e nao so' na memoria do navegador, por tres motivos: retomar a
conversa depois de recarregar a pagina, auditar o que o modelo respondeu com
base em qual consulta, e medir custo (tokens) e latencia por usuario.

Tabela de mensagem guarda tambem as chamadas de ferramenta (`papel='tool'`):
e' o rastro de onde saiu cada numero. Elas NAO voltam ao modelo como
historico - so' o texto de usuario e assistente volta; se precisar do dado de
novo, o modelo consulta de novo, com o estado atual.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin, utcnow

PAPEIS = ("user", "assistant", "tool")


class AssistantConversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "assistant_conversations"
    __table_args__ = (
        # A lista do widget: as conversas deste usuario, mais recentes primeiro.
        Index("ix_assistant_conversations_user_updated", "user_id", "updated_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    titulo: Mapped[str | None] = mapped_column(String(120))


class AssistantMessage(UUIDMixin, Base):
    __tablename__ = "assistant_messages"
    # Nomes SEM o prefixo `ck_assistant_messages_`: a NAMING_CONVENTION o
    # acrescenta. A FK vai por `conversa_id`, e nao `conversation_id`: com o nome
    # longo a convencao de FK passava de 60 caracteres, e o Postgres trunca em 63
    # sem avisar.
    __table_args__ = (
        Index("ix_assistant_messages_conversa_created", "conversa_id", "created_at"),
        CheckConstraint("papel IN ('" + "', '".join(PAPEIS) + "')", name="papel"),
        # Linha de ferramenta sem o nome da ferramenta nao e' rastro de nada.
        CheckConstraint("papel <> 'tool' OR ferramenta IS NOT NULL", name="ferramenta_nomeada"),
    )

    conversa_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    papel: Mapped[str] = mapped_column(String(16), nullable=False)
    conteudo: Mapped[str | None] = mapped_column(Text)

    # Chamada de ferramenta: nome, argumentos que o modelo pediu e o resultado
    # (ja truncado) que voltou para ele.
    ferramenta: Mapped[str | None] = mapped_column(String(64))
    argumentos: Mapped[dict | None] = mapped_column(JSONB)
    resultado: Mapped[str | None] = mapped_column(Text)

    # Custo e desfecho. `fim` e' o finish_reason do modelo ou um desfecho nosso
    # ("interrompida", "erro"); `bloqueio` diz qual guarda barrou a resposta.
    tokens_entrada: Mapped[int | None] = mapped_column(Integer)
    tokens_saida: Mapped[int | None] = mapped_column(Integer)
    # Parte da entrada que o Azure serviu do cache de prompt, cobrada com
    # desconto. Sem ela o custo estimado a partir de `tokens_entrada` sai maior
    # do que a fatura.
    tokens_em_cache: Mapped[int | None] = mapped_column(Integer)
    latencia_ms: Mapped[int | None] = mapped_column(Integer)
    fim: Mapped[str | None] = mapped_column(String(32))
    bloqueio: Mapped[str | None] = mapped_column(String(64))

    # Default no Python TAMBEM: o orquestrador le `created_at` logo depois de
    # inserir, e so' com o do servidor o atributo exigiria um refresh - que numa
    # sessao assincrona estoura como lazy load em vez de simplesmente consultar.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, nullable=False
    )
