"""O catalogo de planos da plataforma passa a chegar pelas migrations.

O DEFEITO, que chegou a producao e foi relatado da tela: a aba Plano & Contrato
dizia "Este ponto ainda nao tem contrato com a plataforma. Escolha um plano
abaixo." e logo em seguida "Nenhum plano publicado". Nao havia o que escolher, e
o estabelecimento nao tinha como contratar nada.

A causa nao estava na tela. Os planos so' nasciam dentro de `seed()`, que
desiste inteiro na primeira linha quando enxerga um site - "ja existem dados". O
banco do staging foi povoado ANTES de o catalogo existir, entao a tabela ficou
vazia para sempre: rodar o seed de novo nao ajudava, e nao ha rota que crie
plano. Restava um passo manual que alguem precisava lembrar de dar em cada
ambiente, e foi exatamente o que nao aconteceu.

Por que MIGRATION e nao um passo de deploy: catalogo de plano e' dado de
REFERENCIA da rede, da mesma natureza do schema - nao e' dado de demonstracao
preso a um site. Como migration ele chega a todo ambiente pelo caminho que ja'
existe (`alembic upgrade head`, que o workflow de staging ja' roda a cada push),
uma vez so', sem passo manual e sem ninguem precisar lembrar.

OS VALORES SAO LITERAIS AQUI, e nao importados de `app.seed`. Migration importa
codigo de aplicacao envelhece mal: ela descreve o banco de UM momento, e o
modulo que ela importaria continua mudando. Se um plano novo entrar no catalogo,
ele vem numa migration nova - e `test_catalogo_de_planos.py` compara os dois
conjuntos justamente para que esquecer disso quebre o teste em vez de produzir
outro staging com tela vazia.

INSERE SO' O QUE FALTA. `ON CONFLICT DO NOTHING` sobre `uq_platform_plans_codigo`:
em banco que ja' tem o catalogo (o de desenvolvimento, criado pelo seed antigo) a
migration nao faz nada, e - o que mais importa - NAO reescreve preco de plano
publicado. Preco de plano vivo e' clausula de contrato em vigor; mexer nele por
migration mudaria por baixo o que o estabelecimento assinou.

Revision ID: 0027_catalogo_de_planos
Revises: 0026_carimbo_por_linha
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0027_catalogo_de_planos"
down_revision: str | None = "0026_carimbo_por_linha"
branch_labels: str | None = None
depends_on: str | None = None


# codigo, nome, descricao, mensal, por ponto, inclusos, taxa %, meses minimos
PLANOS = [
    (
        "essencial",
        "Essencial",
        "Para quem esta comecando: mensalidade baixa, taxa maior por transacao.",
        "149.00",
        "35.00",
        2,
        "3.5",
        12,
    ),
    (
        "rede",
        "Rede",
        "Para operacao com varios pontos: mensalidade maior, taxa menor.",
        "499.00",
        "20.00",
        8,
        "1.5",
        12,
    ),
]

_INSERIR = sa.text(
    """
    INSERT INTO platform_plans (
        id, codigo, nome, descricao,
        preco_mensal_brl, preco_por_ponto_brl, pontos_inclusos,
        fee_percent_transacao, meses_minimos, ativo,
        created_at, updated_at
    )
    VALUES (
        gen_random_uuid(), :codigo, :nome, :descricao,
        :mensal, :por_ponto, :inclusos,
        :taxa, :meses, true,
        now(), now()
    )
    ON CONFLICT ON CONSTRAINT uq_platform_plans_codigo DO NOTHING
    """
)


def upgrade() -> None:
    conexao = op.get_bind()
    for codigo, nome, descricao, mensal, por_ponto, inclusos, taxa, meses in PLANOS:
        conexao.execute(
            _INSERIR,
            {
                "codigo": codigo,
                "nome": nome,
                "descricao": descricao,
                "mensal": mensal,
                "por_ponto": por_ponto,
                "inclusos": inclusos,
                "taxa": taxa,
                "meses": meses,
            },
        )


def downgrade() -> None:
    """Nao remove nada, e e' deliberado.

    Um plano publicado pode ter contrato apontando para ele
    (`site_subscriptions.plan_id`). Apagar quebraria a FK no melhor caso e, no
    pior, deixaria contrato orfao - desfazendo uma relacao comercial para
    reverter uma migration de dado de referencia.

    Apagar so' os planos sem contrato tambem nao serve: o estado resultante
    depende de quem contratou o que, entao o downgrade produziria bancos
    diferentes a partir do mesmo ponto. Catalogo que sobra e' inofensivo; o
    `ON CONFLICT` acima garante que subir de novo nao duplica.
    """
