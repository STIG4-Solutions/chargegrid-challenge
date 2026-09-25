"""Junta as duas linhas de migracao que nasceram da 0028.

NAO CRIA NEM ALTERA NADA. E' uma revisao de juncao: existe so' para que a arvore
volte a ter uma ponta, e `upgrade` e `downgrade` sao vazios de proposito.

POR QUE HAVIA DUAS PONTAS. Dois trabalhos partiram da `0028_previsao_por_janela` ao
mesmo tempo e nenhum dos dois soube do outro, porque foram para bases diferentes:

    0028_previsao_por_janela
      |-- 0029_bandeira_do_site --- 0030_pico_simulado_do_site     (PR #29, staging)
      +-- 0029_assistente --------- 0030_tokens_em_cache           (PR #28, main)

O git NAO acusa isso. Os arquivos tem nomes diferentes, entao
`git merge-tree origin/staging origin/main` sai com zero conflito e o merge parece
limpo. O que quebra e' depois:

    $ alembic upgrade head
    FAILED: Multiple head revisions are present for given argument 'head'

E a queda nao e' local. O `conftest.py` da suite monta o schema com
`alembic upgrade head`, entao a suite inteira da API vai com ela: medido no merge de
teste, 928 erros e nenhum teste passando. O mesmo comando roda em
`migrate-staging.yml` e em `migrate-production.yml`.

POR QUE JUNCAO, E NAO REENCADEAMENTO. A alternativa seria apontar
`0029_assistente.down_revision` para `0030_pico_simulado_do_site` e deixar uma linha
so'. Nao serve: a PR #28 foi para `main`, `migrate-production.yml` dispara em push
para `main` e a execucao PASSOU em 2026-09-25. Produção ja' esta' estampada em
`0030_tokens_em_cache`. Reencadear faria o alembic tentar reexecutar, naquele banco,
migracoes que ele ja' aplicou.

A juncao nao tem esse problema porque nao reescreve historia nenhuma: os dois
caminhos continuam validos, e quem esta' em qualquer um dos dois chega aqui com um
passo que nao faz nada.

O 0031 FORA DA SEQUENCIA. Existem hoje dois arquivos `0029_*` e dois `0030_*` - o
prefixo deixou de indicar ordem no momento em que as duas linhas nasceram. `0031`
e' o proximo numero livre, e a ordem de verdade esta' em `down_revision`, que e'
onde o alembic a le.

Revision ID: 0031_junta_assistente_e_bandeira
Revises: 0030_pico_simulado_do_site, 0030_tokens_em_cache
"""

from __future__ import annotations

revision: str = "0031_junta_assistente_e_bandeira"
# Tupla, e nao string: e' isto que faz desta revisao uma juncao. As duas pontas
# passam a ter um descendente comum, e `heads` volta a devolver uma.
down_revision: tuple[str, str] = (
    "0030_pico_simulado_do_site",
    "0030_tokens_em_cache",
)
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Vazio de proposito - ver o cabecalho. Juntar a arvore nao mexe no banco."""


def downgrade() -> None:
    """Vazio de proposito, e descer daqui exige NOMEAR o alvo.

    `alembic downgrade -1` NAO funciona num ponto de juncao - sai `Ambiguous walk`,
    porque ha' duas revisoes anteriores e o alembic nao escolhe entre elas. Medido.

    O que funciona e' nomear qualquer uma das duas pontas:

        alembic downgrade 0030_tokens_em_cache

    Isso desfaz SO' a juncao, e `alembic current` volta a listar as duas pontas.
    Depois `alembic upgrade head` junta de novo. Nada disso toca o schema: nao ha' o
    que desfazer porque nada foi feito.
    """
