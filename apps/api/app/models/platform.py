"""O estabelecimento assinando a plataforma da GoodWe.

Dinheiro na direcao OPOSTA ao resto do sistema. Em `invoices` o motorista paga o
estabelecimento; aqui o estabelecimento paga a rede. Confundir os dois destrui os
relatorios: `utilization_service` e `portfolio_service` somam `invoices` por
`site_id`, e a mensalidade da plataforma entraria como receita de recarga do
proprio lojista que a pagou.

Por isso `platform_invoices` e' tabela separada, e nao mais um `kind` de linha em
`invoices`. Nao e' preferencia de organizacao - e' que as duas respondem a
perguntas contrarias.

TRES FONTES DE RECEITA, e a ordem de importancia nao e' a da lista:
  1. `fee_percent_transacao` sobre o faturamento do site. E' o que faz este
     modelo valer: cresce com o cliente e ja e' calculavel a partir de
     `invoices.total` agrupado por site.
  2. `preco_por_ponto_brl` acima da franquia de pontos.
  3. `preco_mensal_brl`, a parte chata.

CONTRATO COM PRAZO MINIMO. `minimo_ate` NAO avanca na renovacao automatica.
Renovar prendendo por mais doze meses quem so' deixou o contrato correr e'
abusivo, e indefensavel em qualquer discussao sobre o modelo.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

ESTADOS_DO_CONTRATO = ("ativa", "em_aviso_previo", "encerrada", "inadimplente")
ESTADOS_DA_COBRANCA = ("aberta", "vencida", "paga", "cancelada")

# Os nomes de constraint aqui vao SEM o prefixo `ck_<tabela>_`: a
# NAMING_CONVENTION o acrescenta sozinha. Escrever o nome completo o duplica, e
# na 0017 isso passou dos 63 caracteres do identificador do Postgres, que truncou
# com hash e fez `alembic check` acusar deriva. Ver a 0018.


class PlatformPlan(UUIDMixin, TimestampMixin, Base):
    """O que a GoodWe vende ao estabelecimento."""

    __tablename__ = "platform_plans"
    __table_args__ = (
        UniqueConstraint("codigo", name="uq_platform_plans_codigo"),
        CheckConstraint("preco_mensal_brl >= 0", name="preco_nao_negativo"),
        CheckConstraint("preco_por_ponto_brl >= 0", name="preco_por_ponto_nao_negativo"),
        CheckConstraint("pontos_inclusos >= 0", name="pontos_nao_negativo"),
        CheckConstraint(
            "fee_percent_transacao >= 0 AND fee_percent_transacao <= 100",
            name="fee_entre_zero_e_cem",
        ),
        CheckConstraint("meses_minimos >= 0", name="meses_minimos_nao_negativo"),
    )

    codigo: Mapped[str] = mapped_column(String(24), nullable=False)
    nome: Mapped[str] = mapped_column(String(80), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)

    preco_mensal_brl: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Cobrado por ponto ACIMA da franquia. Um plano que inclui 4 pontos e cobra
    # por cada ponto extra cresce com o cliente sem renegociacao.
    preco_por_ponto_brl: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    pontos_inclusos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # A parte que realmente importa: percentual sobre o que o site faturou.
    fee_percent_transacao: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=0, nullable=False)

    meses_minimos: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SiteSubscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "site_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('ativa', 'em_aviso_previo', 'encerrada', 'inadimplente')",
            name="estado_conhecido",
        ),
        CheckConstraint("minimo_ate >= starts_on", name="minimo_depois_do_inicio"),
        # Encerrar exige dizer QUANDO. Sem a data, "esta competencia ainda e'
        # cobravel?" fica sem resposta no mes seguinte.
        CheckConstraint(
            "estado <> 'encerrada' OR encerra_em IS NOT NULL", name="encerramento_completo"
        ),
        CheckConstraint("multa_percentual >= 0 AND multa_percentual <= 100", name="multa_ate_cem"),
        # Um contrato vivo por site. Encerrados nao contam: o estabelecimento
        # pode voltar depois, e barrar isso o obrigaria a apagar o historico.
        Index(
            "uq_site_subscription_vigente",
            "site_id",
            unique=True,
            postgresql_where=text("estado <> 'encerrada'"),
        ),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    # RESTRICT: nao se apaga plano contratado. O preco dele explica cobrancas
    # ja emitidas.
    plan_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("platform_plans.id", ondelete="RESTRICT"), nullable=False
    )

    estado: Mapped[str] = mapped_column(String(16), default="ativa", nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    # Ate quando o estabelecimento esta preso ao contrato. NAO avanca na
    # renovacao automatica - ver o docstring do modulo.
    minimo_ate: Mapped[date] = mapped_column(Date, nullable=False)
    renova_em: Mapped[date] = mapped_column(Date, nullable=False)
    encerra_em: Mapped[date | None] = mapped_column(Date)
    renovacao_automatica: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    multa_percentual: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)

    plan = relationship("PlatformPlan", lazy="joined")

    @property
    def dentro_do_prazo_minimo(self) -> bool:
        return date.today() < self.minimo_ate


class PlatformInvoice(UUIDMixin, TimestampMixin, Base):
    """Cobranca da GoodWe ao estabelecimento.

    Tabela separada de `invoices` por necessidade, nao por gosto: os relatorios
    de receita somam `invoices` por site, e esta linha e' dinheiro saindo do
    site, nao entrando.
    """

    __tablename__ = "platform_invoices"
    __table_args__ = (
        # A protecao contra faturar o mesmo mes duas vezes. E' o defeito classico
        # de cobranca recorrente, e o unico que realmente machuca o cliente.
        UniqueConstraint(
            "site_subscription_id", "competencia", name="uq_platform_invoices_competencia"
        ),
        CheckConstraint(
            "estado IN ('aberta', 'vencida', 'paga', 'cancelada')", name="estado_conhecido"
        ),
        CheckConstraint("total_brl >= 0", name="total_nao_negativo"),
        # Declarar-se paga exige dizer quando. Sem a data nao ha como conciliar.
        CheckConstraint("estado <> 'paga' OR paga_em IS NOT NULL", name="pagamento_completo"),
        Index("ix_platform_invoices_competencia", "competencia"),
    )

    site_subscription_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        # RESTRICT: historico de cobranca nao some junto com o contrato.
        ForeignKey("site_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    competencia: Mapped[date] = mapped_column(Date, nullable=False)
    emitida_em: Mapped[date] = mapped_column(Date, nullable=False)
    # Lido por `marcar_vencidas`. Passou daqui, a cobranca vira `vencida` e o
    # contrato vira `inadimplente` - ate a 0023 esta coluna era escrita e nunca
    # consultada, e uma divida de tres meses era indistinguivel de uma de ontem.
    vence_em: Mapped[date] = mapped_column(Date, nullable=False)
    paga_em: Mapped[date | None] = mapped_column(Date)

    # As tres parcelas ficam separadas de proposito: "R$ 480" nao explica nada, e
    # o lojista precisa poder conferir cada uma contra o proprio extrato.
    assinatura_brl: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    pontos_brl: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    transacao_brl: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    multa_brl: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_brl: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    # A base de calculo, guardada junto: sem ela, conferir a taxa exigiria
    # reprocessar o mes inteiro de faturas do site.
    pontos_cobrados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    faturamento_base_brl: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    estado: Mapped[str] = mapped_column(String(12), default="aberta", nullable=False)

    assinatura = relationship("SiteSubscription", lazy="joined")
