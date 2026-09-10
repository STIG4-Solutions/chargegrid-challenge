"""Acerto de duas coisas que sairam erradas nas migrations anteriores.

Ambas foram encontradas por `alembic check`, e nenhuma das duas daria erro em
execucao - o tipo que se descobre tarde.

1. COLUNAS DE COMPARACAO DA PREVISAO. `wape_modelo_pct` e `wape_baseline_pct`
   foram acrescentadas a 0016 DEPOIS de ela ja ter sido aplicada. Bancos criados
   antes daquela edicao ficaram sem as colunas; bancos criados depois as tinham.
   Editar migration ja aplicada e' exatamente isso: o schema passa a depender de
   QUANDO cada banco rodou. A 0016 voltou ao que era, e as colunas entram aqui.

2. NOME DE CONSTRAINT TRUNCADO. `NAMING_CONVENTION` monta
   `ck_%(table_name)s_%(constraint_name)s`, entao escrever o nome ja com o
   prefixo o duplica. Em `driver_subscriptions` isso passou dos 63 caracteres do
   identificador do Postgres, que truncou e acrescentou um hash - e o nome no
   banco deixou de bater com o do metadata.

   As demais constraints do projeto tem o mesmo prefixo duplicado e continuam
   assim: sao mais curtas, funcionam, e renomea-las custaria uma migration por
   nada. O que nao pode repetir e' passar do limite.

Revision ID: 0018_acertos_de_schema
Revises: 0017_assinatura_do_motorista
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_acertos_de_schema"
down_revision: str | None = "0017_assinatura_do_motorista"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# O nome que o Postgres gerou ao truncar. Fixo aqui porque e' o que existe nos
# bancos que rodaram a 0017 - procura-lo pelo nome curto nao acharia nada.
TRUNCADO = "ck_driver_subscriptions_ck_driver_subscriptions_cancela_504c"
CORRETO = "ck_driver_subscriptions_cancelamento_completo"


def upgrade() -> None:
    # `IF NOT EXISTS` porque ha bancos dos dois lados da edicao da 0016: os
    # criados depois dela ja tem as colunas, e um ADD COLUMN cru falharia neles.
    op.execute(
        "ALTER TABLE site_forecasts ADD COLUMN IF NOT EXISTS wape_modelo_pct NUMERIC(6, 2)"
    )
    op.execute(
        "ALTER TABLE site_forecasts ADD COLUMN IF NOT EXISTS wape_baseline_pct NUMERIC(6, 2)"
    )

    # Renomear em vez de recriar: a constraint ja valida as linhas existentes, e
    # DROP seguido de ADD reavaliaria a tabela inteira sem necessidade.
    op.execute(
        f'ALTER TABLE driver_subscriptions RENAME CONSTRAINT "{TRUNCADO}" TO "{CORRETO}"'
    )


def downgrade() -> None:
    op.execute(
        f'ALTER TABLE driver_subscriptions RENAME CONSTRAINT "{CORRETO}" TO "{TRUNCADO}"'
    )
    op.drop_column("site_forecasts", "wape_baseline_pct")
    op.drop_column("site_forecasts", "wape_modelo_pct")
