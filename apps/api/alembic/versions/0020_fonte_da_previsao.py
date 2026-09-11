"""A previsao passa a declarar de ONDE veio o numero.

O modelo de previsao e' melhor que a media movel no DIARIO - 29,4% de erro
contra 34,3% - e pior no agregado MENSAL, que e' justamente o que a tela mostra.
Medido sobre 36 estacao-meses fora da amostra, em tres horizontes de backtest, e
em todas as tres estacoes: a regua ganha no mensal.

Combinar os dois nao resolve. A correlacao entre os erros mensais e' 0,944 - eles
erram junto, porque no agregado ambos sao essencialmente "nivel x dias". Testado:
qualquer peso dado ao modelo piora o WAPE mensal monotonicamente.

Entao o job passa a gravar o numero que MEDE melhor, e `fonte` diz qual e'. Nao
e' desistir do modelo: quando ele passar a ganhar - com operacao real, com mais
estacoes - o proprio backtest inverte a escolha, sem ninguem mexer em codigo.

Antes havia so' `modelo_aplicavel`, que respondia "o modelo conhece este local?".
Isso nao basta: um local conhecido cujo modelo perde da regua e' um terceiro
caso, e sem `fonte` a tela apresentaria como previsao um numero que veio de
outro lugar.

Revision ID: 0020_fonte_da_previsao
Revises: 0019_assinatura_da_plataforma
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_fonte_da_previsao"
down_revision: str | None = "0019_assinatura_da_plataforma"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `media_movel` como padrao: e' o valor conservador. Linha antiga sem a
    # coluna vira media movel, e a tela deixa de chamar de previsao um numero
    # cuja origem nao da' para afirmar.
    op.add_column(
        "site_forecasts",
        sa.Column("fonte", sa.String(16), nullable=False, server_default="media_movel"),
    )
    op.create_check_constraint(
        "fonte_conhecida", "site_forecasts", "fonte IN ('modelo', 'media_movel')"
    )

    # Backfill pela BANDA, que e' o unico rastro de origem que as linhas antigas
    # tem: so' previsao de modelo recebia p10/p90 - o fallback nunca teve. Sem
    # isto, o CHECK abaixo recusa a propria criacao num banco que ja rodou o job,
    # porque as linhas existentes ficariam com banda e `fonte = media_movel`.
    op.execute(
        "UPDATE site_forecasts SET fonte = 'modelo' WHERE kwh_p10 IS NOT NULL"
    )

    # A banda passa a depender da FONTE, e nao de `modelo_aplicavel`. Desenhar
    # incerteza em volta de uma media movel daria ares de previsao a uma conta de
    # padaria - e agora ha um caso em que o modelo se aplica mas nao e' usado.
    op.drop_constraint(
        "ck_site_forecasts_fallback_sem_banda", "site_forecasts", type_="check"
    )
    op.create_check_constraint(
        "banda_so_do_modelo", "site_forecasts", "fonte = 'modelo' OR kwh_p10 IS NULL"
    )


def downgrade() -> None:
    # Nomes CURTOS: a convencao prefixa `ck_<tabela>_`. Passar o nome completo
    # aqui pediria `ck_site_forecasts_ck_site_forecasts_...`, que nao existe.
    op.drop_constraint("banda_so_do_modelo", "site_forecasts", type_="check")
    op.create_check_constraint(
        "ck_site_forecasts_fallback_sem_banda",
        "site_forecasts",
        "modelo_aplicavel OR kwh_p10 IS NULL",
    )  # nome completo aqui: e' o que a 0016 criou, ja' dobrado pela convencao
    op.drop_constraint("fonte_conhecida", "site_forecasts", type_="check")
    op.drop_column("site_forecasts", "fonte")
