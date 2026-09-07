"""Conta corporativa.

O app hoje atende uma pessoa que paga a propria recarga. Uma frota e' outro
cliente: quem dirige nao e' quem paga, quem paga precisa saber quanto cada
area gastou, e ninguem quer somar recibo a mao no fim do mes.

Tres pecas resolvem isso, e todas ja tinham metade pronta:

  a frota agrupa os motoristas. `users.fleet_id` diz de quem e' a conta.

  o centro de custo mora no VEICULO, nao na pessoa. E' assim que frota
  funciona: o carro pertence a um departamento e roda com motoristas
  diferentes. Amarrar na pessoa erraria toda vez que alguem pega o carro de
  outra area - que e' o caso comum, nao a excecao.

  o relatorio mensal ja tinha os dados. Sessao aponta veiculo, veiculo aponta
  centro de custo, fatura aponta sessao. Faltava a consulta que junta.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class Fleet(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fleets"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    document: Mapped[str | None] = mapped_column(String(32), doc="CNPJ da empresa")
    # Para onde vai o relatorio e a cobranca consolidada.
    billing_email: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def as_dict(self) -> dict:
        return {
            "id": str(self.id),
            "nome": self.name,
            "documento": self.document,
            "email_de_cobranca": self.billing_email,
            "ativa": self.active,
        }


__all__ = ["Fleet"]
