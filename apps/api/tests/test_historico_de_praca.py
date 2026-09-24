"""O job que gera historico para uma praca que ja' existe.

O `seed()` desiste inteiro na primeira praca que encontra - tudo ou nada, e o
"nada" e' o caso de todo ambiente que ja' rodou uma vez. Desde que o painel ganhou
"Nova praca", uma praca pode nascer pelo produto e ficar sem historico para sempre:
nao ha rota que recue sessoes, e a simulacao so' anda para frente em tempo real.

Aconteceu no staging: tres pracas, a mais antiga com treze dias. Nem as reguas de
previsao funcionam ali - a media movel pede 28 dias e o modelo pede 150.

O que estes testes prendem, em ordem de gravidade:

1. Gera de verdade, com fatura - sem fatura a receita da tela sai zero enquanto a
   energia aparece.
2. NAO E' DESTRUTIVO: sessao que ja' existia continua lá.
3. RECUSA em vez de estragar, quando falta ponto, falta tarifa, ou quando a praca
   ja' tem operacao real.
4. E' reprodutivel. A primeira versao usava `hash()` de string, que e' aleatorizado
   por processo - duas execucoes davam historicos diferentes enquanto o comentario
   prometia o contrario.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.historico import _semente, gerar
from app.models.billing import Invoice
from app.models.session import ChargingSession

CARATER = "shopping"


async def _com_tarifa(db, site, tarifa):
    site.default_tariff_id = tarifa.id
    await db.flush()


async def _quantas_sessoes(db, site_id) -> int:
    return (
        await db.execute(
            select(func.count(ChargingSession.id)).where(ChargingSession.site_id == site_id)
        )
    ).scalar_one()


async def _quantas_faturas(db, site_id) -> int:
    return (
        await db.execute(
            select(func.count(Invoice.id))
            .join(ChargingSession, ChargingSession.id == Invoice.session_id)
            .where(ChargingSession.site_id == site_id)
        )
    ).scalar_one()


# ------------------------------------------------------------------ gera mesmo


async def test_gera_sessoes_e_faturas(db, site, ponto, tarifa):
    """Energia sem fatura faria a receita da tela sair zero com o gráfico cheio."""
    await _com_tarifa(db, site, tarifa)

    gravadas = await gerar(db, site.slug, CARATER, dias=200, forcar=False)

    assert gravadas > 0
    assert await _quantas_sessoes(db, site.id) == gravadas
    # Uma fatura por sessao: e' o que `_gravar_historico` promete.
    assert await _quantas_faturas(db, site.id) == gravadas


async def test_recua_o_nascimento_da_praca(db, site, ponto, tarifa):
    """`dias_operacao` e' feature do modelo.

    Uma praca nascida hoje com dois anos de sessoes e' a contradicao que o proprio
    pipeline de previsao detecta - e, pior, `banco._grade_completa` descartaria a
    praca inteira por ter aberto depois do corte do treino.
    """
    await _com_tarifa(db, site, tarifa)
    antes = site.created_at

    await gerar(db, site.slug, CARATER, dias=300, forcar=False)

    assert site.created_at < antes
    idade = (datetime.now(UTC) - site.created_at).days
    assert 299 <= idade <= 301


async def test_o_historico_cobre_a_janela_pedida(db, site, ponto, tarifa):
    """Sem isto, "300 dias" poderia gerar trinta e ninguem notaria."""
    await _com_tarifa(db, site, tarifa)

    await gerar(db, site.slug, CARATER, dias=300, forcar=False)

    inicio = (
        await db.execute(
            select(func.min(ChargingSession.started_at)).where(ChargingSession.site_id == site.id)
        )
    ).scalar_one()
    assert (datetime.now(UTC) - inicio).days > 250


# --------------------------------------------------------------- nao destroi


async def test_nao_apaga_sessao_que_ja_existia(db, site, ponto, tarifa, motorista):
    """A praca de staging tinha 16 sessoes reais. Elas nao podem desaparecer."""
    antiga = ChargingSession(
        site_id=site.id,
        charge_point_id=ponto.id,
        user_id=motorista.id,
        code="SES-ANTIGA-1",
        state="BILLED",
        started_at=datetime.now(UTC) - timedelta(days=3),
        ended_at=datetime.now(UTC) - timedelta(days=3) + timedelta(hours=1),
        energy_kwh=12.5,
    )
    db.add(antiga)
    await db.flush()

    await gerar(db, site.slug, CARATER, dias=200, forcar=False)

    ainda_la = (
        await db.execute(select(ChargingSession).where(ChargingSession.code == "SES-ANTIGA-1"))
    ).scalar_one_or_none()
    assert ainda_la is not None
    assert float(ainda_la.energy_kwh) == pytest.approx(12.5)


# ------------------------------------------------------- recusa em vez de errar


async def test_recusa_praca_que_nao_existe(db, site):
    with pytest.raises(SystemExit, match="nao existe"):
        await gerar(db, "praca-que-nunca-houve", CARATER, dias=200, forcar=False)


async def test_recusa_praca_sem_ponto_de_recarga(db, site, tarifa):
    """`charging_sessions.charge_point_id` e' NOT NULL: sem ponto nao ha sessao.

    Recusar com a razao e' melhor que estourar numa violacao de constraint depois
    de montar milhares de linhas.
    """
    await _com_tarifa(db, site, tarifa)

    with pytest.raises(SystemExit, match="nao tem ponto"):
        await gerar(db, site.slug, CARATER, dias=200, forcar=False)


async def test_recusa_praca_sem_tarifa(db, site):
    """Sem preco nao ha fatura, e a receita sairia zero com a energia aparecendo.

    O ponto e' construido a mao, e nao pela fixture `ponto`: aquela depende de
    `tarifa`, entao pedi-la criaria justamente a tarifa que este teste precisa NAO
    existir. E' o caso real de uma praca criada pelo produto, onde alguem cadastrou
    os pontos e ainda nao cadastrou preco.
    """
    from app.models.charge_point import ChargePoint
    from app.models.enums import ChargePointStatus, ConnectorType, PhaseType

    db.add(
        ChargePoint(
            site_id=site.id,
            code="CP-SEM-PRECO",
            name="Ponto sem preco",
            connector=ConnectorType.TYPE2,
            phase_type=PhaseType.THREE,
            rated_kw=22,
            min_kw=4.2,
            limit_kw=22,
            status=ChargePointStatus.AVAILABLE,
        )
    )
    await db.flush()

    with pytest.raises(SystemExit, match="nao tem tarifa"):
        await gerar(db, site.slug, CARATER, dias=200, forcar=False)


async def test_recusa_praca_que_ja_tem_operacao(db, site, ponto, tarifa):
    """Gerar por cima empilharia historico inventado sobre operacao real."""
    await _com_tarifa(db, site, tarifa)
    await gerar(db, site.slug, CARATER, dias=200, forcar=False)

    with pytest.raises(SystemExit, match="ja' tem"):
        await gerar(db, site.slug, CARATER, dias=200, forcar=False)


async def test_forcar_atravessa_a_guarda(db, site, ponto, tarifa):
    """A guarda protege de acidente, nao de decisao."""
    await _com_tarifa(db, site, tarifa)
    primeira = await gerar(db, site.slug, CARATER, dias=200, forcar=False)

    segunda = await gerar(db, site.slug, CARATER, dias=200, forcar=True)
    assert segunda > 0
    assert await _quantas_sessoes(db, site.id) == primeira + segunda


# ----------------------------------------------------------- reprodutibilidade


def test_a_semente_e_estavel_entre_processos():
    """A primeira versao usava `hash()` de string.

    `hash()` de string e' aleatorizado por PYTHONHASHSEED, entao duas execucoes
    produziriam historicos diferentes - enquanto o comentario prometia o contrario.
    """
    assert _semente("estabelecimento-a") == _semente("estabelecimento-a")
    assert _semente("estabelecimento-a") != _semente("estabelecimento-b")
    # E o valor NAO depende do processo: conferido contra o numero que `crc32`
    # produz, que e' fixo por definicao.
    import zlib

    from app.seed import SEMENTE_DO_HISTORICO

    esperado = SEMENTE_DO_HISTORICO + zlib.crc32(b"estabelecimento-a") % 10_000
    assert _semente("estabelecimento-a") == esperado
