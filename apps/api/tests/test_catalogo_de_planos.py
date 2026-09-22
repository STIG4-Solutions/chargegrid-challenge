"""O catalogo de planos da rede: como ele chega, e por que por ai.

O defeito chegou a producao e a tela denunciou: "Este ponto ainda nao tem
contrato com a plataforma. Escolha um plano abaixo." seguido de "Nenhum plano
publicado."

A causa nao estava na tela. `seed()` desiste inteiro na primeira linha quando
enxerga um site - "ja existem dados" - e os planos nasciam cento e vinte linhas
la dentro. Banco povoado antes de o catalogo existir ficava sem plano PARA
SEMPRE: rodar o seed de novo nao ajudava, e nao ha rota que crie plano. O
estabelecimento nao tinha como contratar nada. Sobrava um passo manual por
ambiente, que e' precisamente o que ninguem lembra de dar.

Hoje o catalogo chega pela MIGRATION `0027_catalogo_de_planos`, pelo caminho que
todo ambiente ja percorre. `garantir_planos_da_plataforma` continua existindo e
continua testada: ela cobre o banco que ja' passou por aquela migration e perdeu
o catalogo depois - restauracao de dump antigo, limpeza manual - e e' ela que o
`seed()` chama antes de desistir.

O primeiro teste e' o que importa para o defeito relatado: sem seed nenhum, o
banco recem-migrado JA' TEM o que oferecer na tela.
"""

from decimal import Decimal

from sqlalchemy import select

from app.models.platform import PlatformPlan
from app.seed import PLANOS_DA_PLATAFORMA, garantir_planos_da_plataforma


async def _codigos(db) -> set[str]:
    return set((await db.execute(select(PlatformPlan.codigo))).scalars().all())


async def _esvaziar(db) -> None:
    """Desfaz a migration NESTA transacao, para simular o banco de antes.

    O `db` roda dentro de uma transacao que sofre rollback ao fim do teste,
    entao apagar aqui nao afeta os proximos.
    """
    for plano in (await db.execute(select(PlatformPlan))).scalars().all():
        await db.delete(plano)
    await db.flush()


async def test_o_catalogo_chega_pelas_migrations(db):
    """Sem seed nenhum, o banco migrado ja' tem o que a tela oferece.

    E' o teste do defeito relatado: staging tinha schema em dia e catalogo
    vazio, porque publicar dependia de um passo que ninguem deu.
    """
    assert await _codigos(db) == {linha[0] for linha in PLANOS_DA_PLATAFORMA}


async def test_a_migration_e_o_seed_nao_divergem(db):
    """Plano novo no seed sem migration daria outro staging de tela vazia.

    Compara os CODIGOS e nao o arquivo: o que precisa coincidir e' o que chega
    ao banco, e o banco deste teste foi construido pelas migrations.
    """
    do_banco = await _codigos(db)
    do_seed = {linha[0] for linha in PLANOS_DA_PLATAFORMA}
    assert do_banco == do_seed, (
        "catalogo do seed e do banco divergem - se um plano entrou em "
        "PLANOS_DA_PLATAFORMA, ele precisa de uma migration nova"
    )


async def test_republica_um_catalogo_perdido(db):
    """Dump antigo restaurado, ou limpeza manual: a funcao repoe."""
    await _esvaziar(db)

    entraram = await garantir_planos_da_plataforma(db)

    assert entraram == len(PLANOS_DA_PLATAFORMA)
    assert await _codigos(db) == {linha[0] for linha in PLANOS_DA_PLATAFORMA}


async def test_publica_mesmo_com_o_banco_ja_povoado(db, site):
    """O caso do staging, e a razao de existir desta funcao.

    A fixture `site` poe um site no banco - exatamente a condicao que faz
    `seed()` desistir. O catalogo tem de chegar assim mesmo.
    """
    await _esvaziar(db)
    assert await _codigos(db) == set()

    entraram = await garantir_planos_da_plataforma(db)

    assert entraram == len(PLANOS_DA_PLATAFORMA)
    assert "essencial" in await _codigos(db)


async def test_rodar_de_novo_nao_duplica(db):
    await garantir_planos_da_plataforma(db)

    entraram = await garantir_planos_da_plataforma(db)

    assert entraram == 0
    assert len(await _codigos(db)) == len(PLANOS_DA_PLATAFORMA)


async def test_publica_so_o_que_falta(db):
    """Catalogo meio publicado e' o estado real de quem ganhou um plano novo."""
    sobrevivente, *resto = sorted(await _codigos(db))
    for codigo in resto:
        plano = (
            await db.execute(select(PlatformPlan).where(PlatformPlan.codigo == codigo))
        ).scalar_one()
        await db.delete(plano)
    await db.flush()

    entraram = await garantir_planos_da_plataforma(db)

    assert entraram == len(PLANOS_DA_PLATAFORMA) - 1
    assert await _codigos(db) == {linha[0] for linha in PLANOS_DA_PLATAFORMA}


async def test_nao_reescreve_preco_de_plano_ja_publicado(db):
    """Contrato em vigor aponta para o plano. Mexer no preco aqui mudaria por
    baixo o que o estabelecimento assinou."""
    plano = (
        await db.execute(select(PlatformPlan).where(PlatformPlan.codigo == "essencial"))
    ).scalar_one()
    plano.preco_mensal_brl = Decimal("1.00")
    await db.flush()

    await garantir_planos_da_plataforma(db)

    await db.refresh(plano)
    assert plano.preco_mensal_brl == Decimal("1.00")
