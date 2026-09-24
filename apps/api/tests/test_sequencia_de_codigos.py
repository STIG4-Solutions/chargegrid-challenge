"""A reserva de codigos quando a sequencia esta' ATRAS do que a tabela tem.

Aconteceu no staging, gerando historico: `nextval('invoice_code_seq')` devolveu
2001 e `INV-2001` ja' existia. O UNIQUE `ix_invoices_code` derrubou a execucao
depois de cinco minutos montando linhas - e o log terminava num traceback do
asyncpg, sem dizer que o problema era a sequencia.

A causa e' historica: os codigos do seed saiam de um intervalo escolhido a mao
(INV-2001 em diante) antes de passarem a vir da sequencia, e `invoice_code_seq`
comeca em 1001. Um banco povoado naquela epoca ficou com codigos ACIMA da
sequencia, e nada nunca os reconciliou.

O que se testa aqui e' a reconciliacao, nao o caminho felizmente comum: num banco
limpo a sequencia sempre esta' a frente, e o defeito nao aparece.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text

from app.models.billing import Invoice
from app.models.session import ChargingSession
from app.seed import _reservar_codigos


async def _sequencia_em(db, sequencia: str, valor: int) -> None:
    """Coloca a sequencia num valor mais BAIXO que o codigo que vamos gravar."""
    await db.execute(text(f"SELECT setval('{sequencia}', :v)"), {"v": valor})


async def test_reserva_passa_do_maior_codigo_ja_gravado(db, site, ponto, motorista):
    """A regressao do staging, com os numeros daquela execucao.

    Uma fatura com `INV-2001` no banco e a sequencia em 1500: sem reconciliar, a
    proxima reserva devolveria 1501 e caminharia direto para a colisao em 2001.
    """
    sessao = ChargingSession(
        site_id=site.id,
        charge_point_id=ponto.id,
        user_id=motorista.id,
        code="SES-20500",
        state="BILLED",
        started_at=datetime.now(UTC) - timedelta(days=1),
        ended_at=datetime.now(UTC) - timedelta(days=1) + timedelta(hours=1),
        energy_kwh=10,
    )
    db.add(sessao)
    await db.flush()
    db.add(
        Invoice(
            code="INV-2001",
            site_id=site.id,
            session_id=sessao.id,
            user_id=motorista.id,
            status="PAID",
            currency="BRL",
            subtotal=26,
            discount=0,
            total=26,
            issued_on=datetime.now(UTC).date(),
        )
    )
    await db.flush()

    await _sequencia_em(db, "invoice_code_seq", 1500)

    primeiro = await _reservar_codigos(db, "invoice_code_seq", 10, "invoices")

    # Passa do 2001 que existe, e nao do 1500 em que a sequencia estava.
    assert primeiro > 2001, primeiro


async def test_reserva_respeita_a_sequencia_quando_ela_esta_na_frente(db, site):
    """O caminho comum nao pode ser prejudicado pela reconciliacao.

    Num banco sem fatura nenhuma, a sequencia manda - e puxar o maximo de uma
    tabela vazia daria zero, que jogaria os codigos para tras.
    """
    await _sequencia_em(db, "invoice_code_seq", 9000)

    primeiro = await _reservar_codigos(db, "invoice_code_seq", 5, "invoices")

    assert primeiro > 9000, primeiro


async def test_o_bloco_reservado_e_continuo_e_nao_se_repete(db, site):
    """Duas reservas seguidas nao podem se sobrepor.

    Os codigos saem de `primeiro + indice`, entao um bloco curto demais faria a
    segunda reserva reemitir codigos da primeira - e o UNIQUE derrubaria a
    gravacao no meio.
    """
    primeiro = await _reservar_codigos(db, "invoice_code_seq", 50, "invoices")
    segundo = await _reservar_codigos(db, "invoice_code_seq", 50, "invoices")

    assert segundo >= primeiro + 50, (primeiro, segundo)


async def test_reconcilia_a_sequencia_de_sessoes_tambem(db, site, ponto, motorista):
    """O mesmo defeito vale para `session_code_seq`, e pela mesma razao."""
    db.add(
        ChargingSession(
            site_id=site.id,
            charge_point_id=ponto.id,
            user_id=motorista.id,
            code="SES-99999",
            state="BILLED",
            started_at=datetime.now(UTC) - timedelta(days=2),
            ended_at=datetime.now(UTC) - timedelta(days=2) + timedelta(hours=1),
            energy_kwh=10,
        )
    )
    await db.flush()
    await _sequencia_em(db, "session_code_seq", 20001)

    primeiro = await _reservar_codigos(db, "session_code_seq", 10, "charging_sessions")

    assert primeiro > 99999, primeiro


async def test_codigo_sem_numero_nao_derruba_a_reconciliacao(db, site, ponto, motorista):
    """Um codigo fora do padrao nao pode fazer o cast de inteiro explodir.

    `regexp_replace` de "INV-MANUAL" devolve string vazia, e `''::bigint` e' erro
    no Postgres. O `NULLIF` e' o que impede isso, e este teste e' o que o prende.
    """
    sessao = ChargingSession(
        site_id=site.id,
        charge_point_id=ponto.id,
        user_id=motorista.id,
        code="SES-SEM-NUMERO",
        state="BILLED",
        started_at=datetime.now(UTC) - timedelta(days=1),
        ended_at=datetime.now(UTC) - timedelta(days=1) + timedelta(hours=1),
        energy_kwh=10,
    )
    db.add(sessao)
    await db.flush()

    primeiro = await _reservar_codigos(db, "session_code_seq", 5, "charging_sessions")

    assert primeiro > 0
    # E a sessao estranha continua la': reconciliar nao apaga nada.
    total = (
        await db.execute(
            select(func.count(ChargingSession.id)).where(ChargingSession.code == "SES-SEM-NUMERO")
        )
    ).scalar_one()
    assert total == 1
