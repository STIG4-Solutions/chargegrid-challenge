"""Desfaz o prefixo dobrado em 21 CHECKs.

`Base.metadata` tem a convencao `ck_%(table_name)s_%(constraint_name)s`. Quem
declara `name="ck_campaigns_beneficio"` no modelo nao esta escolhendo o nome
final - esta escolhendo o SUFIXO, e a convencao prefixa por cima. O resultado e'
`ck_campaigns_ck_campaigns_beneficio`.

POR QUE ISSO IMPORTA, e nao e' so' feio:

1. O nome aparece na mensagem de erro do Postgres, que e' o que alguem le as
   duas da manha quando uma insercao e' recusada. `ck_rewards_ck_rewards_tipo`
   custa um segundo a mais de leitura em cada uma dessas vezes.

2. O limite de identificador do Postgres e' 63 caracteres, e ele TRUNCA em
   silencio: a migration seguinte nao encontra mais a constraint que ela mesma
   criou. Ja aconteceu neste repositorio - foi o que a 0018 precisou consertar.
   Dobrar o prefixo gasta o dobro do nome da tabela em orcamento de caracteres,
   o que aproxima do teto exatamente as tabelas de nome longo.

   O folego que sobra continua apertado por outro motivo, e esse esta fora do
   alcance desta migration: a convencao de FK
   (`fk_<tabela>_<coluna>_<tabela_referida>`) ja produz 60 caracteres em
   `fk_platform_invoices_site_subscription_id_site_subscriptions`. Nao ha nada
   dobrado ali - e' o nome legitimo, e ele esta a tres caracteres do corte.

3. `op.drop_constraint` TAMBEM aplica a convencao ao que recebe. Com metade do
   schema dobrado e metade nao, nao ha regra unica para escrever um downgrade:
   ora se passa o nome curto, ora o longo, e a escolha errada so' aparece quando
   alguem roda o downgrade. A 0021 teve de recorrer a SQL cru por causa disso.

As 22 constraints que ja' seguiam a convencao ficam como estao. Depois desta
migration a regra passa a ser uma so': **no modelo, nome CURTO**.

Revision ID: 0022_nomes_de_constraint
Revises: 0021_razao_da_carteira
Create Date: 2026-09-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0022_nomes_de_constraint"
down_revision: str | None = "0021_razao_da_carteira"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (tabela, sufixo). O nome errado e' `ck_<tabela>_ck_<tabela>_<sufixo>`; o certo
# e' `ck_<tabela>_<sufixo>`. Listadas e nao descobertas do catalogo de proposito:
# uma migration que calcula o proprio alvo em tempo de execucao nao pode ser
# revisada lendo o diff, que e' justamente o que se quer de uma migration.
DOBRADAS: tuple[tuple[str, str], ...] = (
    ("campaigns", "beneficio"),
    ("campaigns", "beneficio_valor"),
    ("campaigns", "consumido_nao_negativo"),
    ("campaigns", "escopo_coerente"),
    ("campaigns", "patrocinador"),
    ("campaigns", "periodo_valido"),
    ("driver_plans", "desconto"),
    ("driver_plans", "entrega_algo"),
    ("driver_plans", "kwh"),
    ("driver_plans", "preco"),
    ("driver_subscriptions", "estado"),
    ("driver_subscriptions", "periodo"),
    ("missions", "alvo"),
    ("missions", "janela"),
    ("missions", "metrica"),
    ("rewards", "credito_completo"),
    ("rewards", "estado"),
    ("rewards", "tipo"),
    ("rewards", "valor_nao_negativo"),
    ("site_forecasts", "banda_completa"),
    ("site_forecasts", "kwh_nao_negativo"),
)


def _renomear(de: str, para: str, tabela: str) -> None:
    # SQL cru porque `op.drop_constraint`/`create_check_constraint` aplicam a
    # convencao de nomes ao argumento - e o ponto desta migration e' justamente
    # escrever o nome final, sem ninguem prefixar por cima.
    #
    # RENAME e nao drop+create: recriar um CHECK faz o Postgres revalidar a
    # tabela inteira, e `charging_sessions` tem dezenas de milhares de linhas
    # depois do seed historico. Renomear e' so' catalogo.
    op.execute(f"ALTER TABLE {tabela} RENAME CONSTRAINT {de} TO {para}")


def upgrade() -> None:
    for tabela, sufixo in DOBRADAS:
        _renomear(f"ck_{tabela}_ck_{tabela}_{sufixo}", f"ck_{tabela}_{sufixo}", tabela)


def downgrade() -> None:
    for tabela, sufixo in DOBRADAS:
        _renomear(f"ck_{tabela}_{sufixo}", f"ck_{tabela}_ck_{tabela}_{sufixo}", tabela)
