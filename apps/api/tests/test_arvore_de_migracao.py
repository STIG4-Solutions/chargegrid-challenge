"""A arvore de migracao tem UMA ponta.

O DEFEITO QUE ISTO PRENDE, e ele ja' aconteceu. Duas PRs partiram da
`0028_previsao_por_janela` ao mesmo tempo, para bases diferentes - a #28 para `main`
e a #29 para `staging`. Cada uma acrescentou a sua linha:

    0028_previsao_por_janela
      |-- 0029_bandeira_do_site --- 0030_pico_simulado_do_site
      +-- 0029_assistente --------- 0030_tokens_em_cache

O git NAO acusa. Os arquivos tem nomes diferentes, entao
`git merge-tree origin/staging origin/main` sai com ZERO conflito e o merge parece
limpo. Quebra depois:

    $ alembic upgrade head
    FAILED: Multiple head revisions are present for given argument 'head'

E nao quebra so' o comando. `conftest.py` monta o schema da suite com
`alembic upgrade head`: no merge de teste foram 928 erros e NENHUM teste passando.
O mesmo comando roda em `migrate-staging.yml` e em `migrate-production.yml`.

Por que um teste, e nao confianca. A revisao de juncao conserta o estado de hoje;
nada impede a terceira linha de nascer amanha, do mesmo jeito e pelo mesmo motivo -
duas pessoas partindo da mesma ponta sem se ver. Este teste custa milissegundos, nao
toca o banco, e falha no CI da PR em vez de no deploy.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def arvore() -> ScriptDirectory:
    """As revisoes lidas do disco. Nao precisa de banco: e' so' o diretorio."""
    return ScriptDirectory.from_config(Config(str(RAIZ / "alembic.ini")))


def test_ha_exatamente_uma_ponta(arvore):
    """O assert que separa "arvore sa" de "deploy que vai falhar".

    Duas pontas fazem `alembic upgrade head` recusar por ambiguidade. A correcao,
    quando isto falhar, NAO e' reescrever `down_revision` de uma migracao que ja'
    rodou em algum ambiente - e' acrescentar uma revisao de juncao:

        alembic merge -m "junta <a> e <b>" heads
    """
    pontas = arvore.get_heads()
    assert len(pontas) == 1, (
        f"{len(pontas)} pontas na arvore de migracao: {sorted(pontas)}. "
        "`alembic upgrade head` vai falhar com 'Multiple head revisions', e a suite "
        "inteira cai junto porque o conftest monta o schema com ele."
    )


def test_toda_revisao_e_alcancavel_da_base(arvore):
    """Nenhuma migracao fica orfa.

    Uma revisao cujo `down_revision` aponta para um id que nao existe - erro de
    digitacao, ou arquivo removido sem ajustar quem vinha depois - nao aparece no
    caminho da base ate a ponta, e nunca roda. O banco fica sem aquela tabela e o
    unico sintoma e' um `UndefinedColumn` em producao.
    """
    todas = {r.revision for r in arvore.walk_revisions()}
    alcancaveis = {r.revision for r in arvore.iterate_revisions("heads", "base")}
    orfas = todas - alcancaveis
    assert not orfas, f"revisoes que nunca rodam: {sorted(orfas)}"


def test_a_juncao_declara_as_duas_pontas_que_junta(arvore):
    """`down_revision` em TUPLA e' o que faz uma revisao ser juncao.

    Com string, ela seria um passo normal atras de uma das duas linhas - e a outra
    continuaria sendo uma ponta solta. O teste acima ja' cairia, mas com uma mensagem
    que nao diz que o defeito esta' aqui.
    """
    juncao = arvore.get_revision("0031_junta_assistente_e_bandeira")
    assert set(juncao.down_revision) == {
        "0030_pico_simulado_do_site",
        "0030_tokens_em_cache",
    }, juncao.down_revision
    assert juncao.is_merge_point


def test_a_juncao_nao_mexe_no_banco(arvore):
    """Ela existe para juntar a arvore, e so'.

    DDL numa revisao de juncao e' armadilha: ela roda depois das duas linhas, entao
    quem le o diff de uma delas nao ve a alteracao. Se houver schema a mudar, ele vai
    numa migracao propria, depois desta.
    """
    fonte = Path(arvore.get_revision("0031_junta_assistente_e_bandeira").path).read_text(
        encoding="utf-8"
    )
    corpo = fonte.split("def upgrade()", 1)[1]
    for proibido in ("op.create_", "op.add_", "op.drop_", "op.alter_", "op.execute"):
        assert proibido not in corpo, f"a juncao chama {proibido} - isso e' migracao, nao juncao"


def test_as_duas_linhas_continuam_no_caminho(arvore):
    """A juncao nao pode ter deixado uma das linhas de fora.

    E' o erro que um reencadeamento apressado produz: apontar a juncao para uma ponta
    so' resolve o `heads` e perde a outra linha, que para de rodar. Aqui as quatro
    revisoes das duas linhas tem de estar no caminho da base ate a ponta.
    """
    caminho = {r.revision for r in arvore.iterate_revisions("heads", "base")}
    for revisao in (
        "0029_assistente",
        "0030_tokens_em_cache",
        "0029_bandeira_do_site",
        "0030_pico_simulado_do_site",
    ):
        assert revisao in caminho, f"{revisao} saiu do caminho e nao roda mais"
