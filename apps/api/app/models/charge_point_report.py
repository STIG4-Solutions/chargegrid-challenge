"""Problema reportado por quem estava no ponto.

`charge_point_faults` e' o que o equipamento consegue dizer de si mesmo: bits
de registrador, com rotulo e contagem de ciclos. Isso cobre o que tem sensor -
sobretemperatura, falha de trava, perda de comunicacao.

Nao cobre o resto. Cabo cortado, tela apagada, vaga tomada por um carro a
combustao, adesivo do QR arrancado: o ponto reporta "disponivel" com toda a
sinceridade, porque do ponto de vista dele esta tudo bem. Quem ve e' a pessoa
que chegou ali e nao conseguiu carregar.

Por isso a tabela e' separada em vez de virar mais um `ChargePointFault`. As
duas fontes tem formatos diferentes - uma tem ciclos e bit, a outra tem
categoria e texto de gente - e forcar um formato no outro perderia justamente
o que cada uma sabe. A manutencao preditiva le as duas.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin

# O que da' para reportar. Lista curta e fechada de proposito: campo livre
# sozinho vira depoimento, e depoimento nao agrega - tres pessoas descrevendo
# o mesmo cabo rompido com palavras diferentes viram tres problemas distintos
# num relatorio que deveria mostrar um.
CATEGORIAS = (
    "nao_inicia",
    "conector_travado",
    "cabo_danificado",
    "tela_apagada",
    "vaga_ocupada",
    "qr_ilegivel",
    "outro",
)


class ChargePointReport(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "charge_point_reports"
    # Constraints declaradas aqui, e nao so' na migration: o que existe apenas
    # la' some de um banco criado por `create_all`, e `alembic check` acusa
    # deriva permanente - ele compara MODELOS com migrations.
    #
    # Os nomes vao SEM o prefixo `ck_charge_point_reports_`: a
    # NAMING_CONVENTION o acrescenta.
    __table_args__ = (
        Index("ix_charge_point_reports_cp_time", "charge_point_id", "created_at"),
        # A manutencao consulta o que ainda esta aberto; e' a fatia pequena.
        Index(
            "ix_charge_point_reports_abertos",
            "charge_point_id",
            postgresql_where=text("resolved_at IS NULL"),
        ),
        CheckConstraint("categoria IN ('" + "', '".join(CATEGORIAS) + "')", name="categoria"),
        # Resolver exige dizer quando. Sem isso um registro com `resolucao`
        # preenchida e sem responsavel se declara resolvido por ninguem.
        CheckConstraint(
            "(resolved_at IS NULL) OR (resolved_by IS NOT NULL)",
            name="resolucao_completa",
        ),
    )

    charge_point_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("charge_points.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    # A sessao em que o problema apareceu, quando havia uma. Reportar sem
    # sessao e' o caso mais importante: o motorista que NAO conseguiu comecar.
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("charging_sessions.id", ondelete="SET NULL")
    )

    categoria: Mapped[str] = mapped_column(String(24), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)

    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    resolucao: Mapped[str | None] = mapped_column(Text)
