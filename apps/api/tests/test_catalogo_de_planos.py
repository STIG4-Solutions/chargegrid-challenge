"""O catalogo de planos da rede, e o motivo de ele nao viver dentro do `seed()`.

O defeito chegou a producao e a tela denunciou: "Este ponto ainda nao tem
contrato com a plataforma. Escolha um plano abaixo." seguido de "Nenhum plano
publicado."

A causa nao estava na tela. `seed()` desiste inteiro na primeira linha quando
enxerga um site - "ja existem dados" - e os planos nasciam cento e vinte linhas
la dentro. Banco povoado antes de o catalogo existir ficava sem plano PARA
SEMPRE: rodar o seed de novo nao ajudava, e nao ha rota que crie plano. O
estabelecimento nao tinha como contratar nada.

O que estes testes fixam e' que publicar o catalogo independe de o banco estar
vazio, e que re-afirmar nao mexe em preco de plano ja publicado - preco de
plano vivo e' clausula de contrato em vigor.
"""

from decimal import Decimal

from sqlalchemy import select

from app.models.platform import PlatformPlan
from app.seed import PLANOS_DA_PLATAFORMA, garantir_planos_da_plataforma


async def _codigos(db) -> set[str]:
    return set((await db.execute(select(PlatformPlan.codigo))).scalars().all())


async def test_publica_o_catalogo_num_banco_vazio(db):
    entraram = await garantir_planos_da_plataforma(db)

    assert entraram == len(PLANOS_DA_PLATAFORMA)
    assert await _codigos(db) == {linha[0] for linha in PLANOS_DA_PLATAFORMA}


async def test_publica_mesmo_com_o_banco_ja_povoado(db, site):
    """O caso do staging, e a razao de existir desta funcao.

    A fixture `site` poe um site no banco - exatamente a condicao que faz
    `seed()` desistir. O catalogo tem de chegar assim mesmo.
    """
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
    await garantir_planos_da_plataforma(db)
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
    await garantir_planos_da_plataforma(db)
    plano = (
        await db.execute(select(PlatformPlan).where(PlatformPlan.codigo == "essencial"))
    ).scalar_one()
    plano.preco_mensal_brl = Decimal("1.00")
    await db.flush()

    await garantir_planos_da_plataforma(db)

    await db.refresh(plano)
    assert plano.preco_mensal_brl == Decimal("1.00")
