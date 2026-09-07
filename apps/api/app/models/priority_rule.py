"""Regras de prioridade nomeadas.

`charge_points.priority` e um inteiro solto. Ele decide quem e servido primeiro
quando falta potencia - a decisao mais consequente do rateio - e nao carrega
nenhuma explicacao: o operador ve "100" e nao sabe se e muito, se e pouco, nem
por que aquele ponto ficou com esse numero. Quando alguem sai da empresa, o
motivo vai junto.

Uma regra da nome ao numero e diz a que ponto ele se aplica:

    "Frota da noite"  prioridade 200  pontos CP-01,CP-02  das 22h as 6h
    "Visitantes"      prioridade  50  todos os demais

A regra tambem resolve o que o inteiro sozinho nao resolvia: prioridade que
muda com a hora. A frota corporativa precisa sair carregada as 7h, mas durante
o dia o visitante e quem paga a tarifa cheia - com um inteiro fixo era preciso
escolher um dos dois turnos e viver com o outro errado.
"""

from __future__ import annotations

import uuid
from datetime import time

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class PriorityRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "priority_rules"
    __table_args__ = (
        Index("ix_priority_rules_site_ordem", "site_id", "ordem"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(80), nullable=False)
    prioridade: Mapped[int] = mapped_column(Integer, nullable=False)

    # Menor `ordem` decide primeiro. A primeira regra que casa vence e as demais
    # nem sao consultadas - sem isso duas regras conflitantes dariam resultado
    # dependente da ordem em que o banco devolveu as linhas, que nao e estavel.
    ordem: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 'ponto'    -> criterio_valor e uma lista de codigos separada por virgula
    # 'conector' -> criterio_valor e o tipo de conector (TYPE2, CCS2, ...)
    # 'sempre'   -> casa com qualquer ponto; serve de padrao do site
    criterio_tipo: Mapped[str] = mapped_column(String(16), default="sempre", nullable=False)
    criterio_valor: Mapped[str | None] = mapped_column(String(400))

    # Janela horaria opcional, na hora local do site. Nula dos dois lados = vale
    # o dia inteiro. Janela que cruza a meia-noite (22h -> 6h) e' o caso comum
    # da recarga noturna de frota, entao precisa funcionar.
    janela_inicio: Mapped[time | None] = mapped_column(Time)
    janela_fim: Mapped[time | None] = mapped_column(Time)
