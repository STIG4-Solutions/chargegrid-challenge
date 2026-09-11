"""Previsao de energia e faturamento do proximo mes, por site.

A API so' LE esta tabela. Quem escreve e' um job separado (`apps/forecast`), e a
separacao nao e' estetica:

1. O processo do FastAPI tambem roda os workers. Um `import lightgbm` que falhe,
   ou um artefato corrompido, derrubaria junto o rebalanceamento de potencia -
   que e' o que impede o disjuntor de abrir. Previsao de faturamento nao pode
   compartilhar processo com controle de carga.
2. O modelo preve MES, com origem no ultimo dia do mes anterior. E' um calculo
   por mes, nao por requisicao; servir em processo seria pagar custo continuo
   por algo que roda doze vezes ao ano.
3. `lgb.predict` e' CPU-bound e a API e' async de ponta a ponta - exigiria
   `run_in_executor` e toda a complexidade que vem junto.

O que o job escreve aqui e' o resultado, versionado e auditavel. Tabela vazia
significa "nao ha previsao", e a tela diz isso em vez de inventar um numero.

AS DUAS COLUNAS DE COBERTURA existem por um motivo especifico. O modelo entrega
uma faixa p10-p90 que deveria conter o valor real em ~80% das vezes; o backtest
do retreino com os dados deste banco mediu 62,3%. A faixa e' mais estreita do que
anuncia, e o README do modelo afirma o contrario. Guardar os dois numeros lado a lado faz a
divergencia virar dado na linha, e nao nota de rodape que ninguem le.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class SiteForecast(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "site_forecasts"
    __table_args__ = (
        # A previsao vigente de um mes e' uma so'. Reexecutar o job atualiza a
        # linha em vez de empilhar versoes que ninguem sabe qual vale.
        UniqueConstraint("site_id", "competencia", name="uq_site_forecasts_site_competencia"),
        # Banda sem os dois extremos nao e' banda. Ou ha p10 e p90, ou nao ha
        # nenhum dos dois - meio intervalo desenhado na tela mente sobre a
        # incerteza que o modelo declarou.
        CheckConstraint(
            "(kwh_p10 IS NULL AND kwh_p90 IS NULL)"
            " OR (kwh_p10 IS NOT NULL AND kwh_p90 IS NOT NULL)",
            name="banda_completa",
        ),
        # A banda depende da FONTE, nao de `modelo_aplicavel`: ha um caso em
        # que o modelo se aplica e mesmo assim nao e' usado, porque perde da
        # regua. Desenhar incerteza em volta de uma media movel daria ares de
        # previsao a uma conta de padaria.
        CheckConstraint("fonte = 'modelo' OR kwh_p10 IS NULL", name="banda_so_do_modelo"),
        CheckConstraint("fonte IN ('modelo', 'media_movel')", name="fonte_conhecida"),
        CheckConstraint("kwh_previsto >= 0", name="kwh_nao_negativo"),
        Index("ix_site_forecasts_competencia", "competencia"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    # Primeiro dia do mes previsto.
    competencia: Mapped[date] = mapped_column(Date, nullable=False)
    gerado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    kwh_previsto: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    kwh_p10: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    kwh_p90: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))

    faturamento_previsto_brl: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    fat_p10_brl: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    fat_p90_brl: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    # A regua contra a qual o modelo precisa ganhar. Exibida junto do previsto:
    # sem ela, nao da' para dizer se o modelo agregou algo a uma media movel.
    media_diaria_28d: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))

    # `modelo_aplicavel` responde "o modelo CONHECE este local?"; `fonte`
    # responde "de onde veio o numero que esta em `kwh_previsto`?". Sao tres
    # casos, e sem as duas colunas o terceiro fica invisivel:
    #
    #   aplicavel=False, fonte=media_movel  -> historico curto demais
    #   aplicavel=True,  fonte=media_movel  -> o modelo perde da regua aqui
    #   aplicavel=True,  fonte=modelo       -> previsao de verdade
    modelo_aplicavel: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fonte: Mapped[str] = mapped_column(
        String(16), default="media_movel", server_default="media_movel", nullable=False
    )
    modelo_versao: Mapped[str | None] = mapped_column(String(40))
    dias_de_historico: Mapped[int | None] = mapped_column(Integer)

    cobertura_declarada_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    cobertura_medida_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # O erro do modelo, e o erro da REGUA que ele precisa bater: media movel
    # de 28 dias, tres linhas de codigo. Guardar so' o primeiro deixaria
    # "12% de erro" parecendo aceitavel sem dizer que a regua faz 9% - e a
    # decisao de contratar demanda seria tomada com o numero pior.
    wape_modelo_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    wape_baseline_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
