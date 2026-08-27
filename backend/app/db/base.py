"""Base declarativa + mixins comuns."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData, Sequence, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Convenção de nomes para o Alembic gerar migrations estáveis.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Codigos legiveis (SES-20483, INV-1042, RES-5007) vem de sequencias do banco:
# geracao por contagem colide sob concorrencia e os tres campos sao unique.
SESSION_CODE_SEQ = Sequence("session_code_seq", start=20001, metadata=Base.metadata)
INVOICE_CODE_SEQ = Sequence("invoice_code_seq", start=1001, metadata=Base.metadata)
RESERVATION_CODE_SEQ = Sequence("reservation_code_seq", start=5001, metadata=Base.metadata)


def utcnow() -> datetime:
    return datetime.now(UTC)


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=utcnow, nullable=False
    )
