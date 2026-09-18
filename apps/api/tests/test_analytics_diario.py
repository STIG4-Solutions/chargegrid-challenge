"""A serie diaria que alimenta a aba de Analytics.

O que se testa aqui nao e' "a soma bate". E' o que faz um grafico MENTIR:

- dia sem sessao omitido encosta segunda em quinta e some com a queda;
- agrupamento em UTC joga a sessao das 22h para o dia seguinte, e o perfil da
  semana sai torto;
- media diaria dividida pelos dias PEDIDOS, e nao pelos dias que existiram,
  afunda o numero de um site novo;
- receita a receber somada com a recebida chama de receita dinheiro que ainda
  pode nao entrar.

Cada um desses passa despercebido numa revisao: o grafico desenha bonito e o
numero parece plausivel.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.billing import Invoice
from app.models.enums import InvoiceStatus, SessionState
from app.models.session import ChargingSession
from app.services import analytics_service

FUSO_DO_SITE = "America/Sao_Paulo"


async def _sessao(db, site, ponto, *, quando: datetime, kwh: float = 10.0, verde: float = 4.0):
    sessao = ChargingSession(
        code=f"S-{quando.timestamp():.6f}",
        site_id=site.id,
        charge_point_id=ponto.id,
        state=SessionState.FINISHED,
        started_at=quando,
        ended_at=quando + timedelta(hours=1),
        energy_kwh=kwh,
        green_energy_kwh=verde,
        duration_s=3600,
    )
    db.add(sessao)
    await db.flush()
    return sessao


async def _fatura(db, site, sessao, *, total: str, status: InvoiceStatus):
    db.add(
        Invoice(
            code=f"F-{sessao.code}",
            site_id=site.id,
            session_id=sessao.id,
            status=status,
            total=Decimal(total),
            subtotal=Decimal(total),
            net_amount=Decimal(total),
            issued_on=sessao.started_at.date(),
        )
    )
    await db.flush()


@pytest.fixture
def ontem() -> datetime:
    return datetime.now(UTC) - timedelta(days=1)


async def test_dia_sem_sessao_aparece_com_zero(db, site, ponto, ontem):
    """O buraco tem de estar na serie.

    Omitir o dia parado faz a linha do grafico passar reto por cima dele - a
    queda vira uma reta, que e' o contrario do que o executivo precisa ver.
    """
    await _sessao(db, site, ponto, quando=ontem - timedelta(days=4))
    await _sessao(db, site, ponto, quando=ontem)

    dados = await analytics_service.serie_diaria(db, site.id, dias=7)

    # CONTIGUIDADE e' a propriedade, nao o tamanho: a janela encolhe de forma
    # legitima quando o site e' mais novo que ela. O que nao pode e' pular dia
    # NO MEIO - e' isso que faz a linha passar reto por cima da queda.
    dias = [date.fromisoformat(d["dia"]) for d in dados["serie"]]
    assert dias == sorted(dias), "a serie tem de sair em ordem cronologica"
    assert all(b - a == timedelta(days=1) for a, b in zip(dias, dias[1:], strict=False)), (
        "ha buraco na serie: o grafico desenharia uma reta por cima dele"
    )
    vazios = [d for d in dados["serie"] if d["sessoes"] == 0]
    assert vazios, "os dias parados sumiram da serie"
    assert all(d["energia_kwh"] == 0 for d in vazios)


async def test_agrupa_no_fuso_do_site_e_nao_em_utc(db, site, ponto):
    """Sessao das 22h em Sao Paulo pertence ao dia de Sao Paulo.

    Em UTC ela cai no dia seguinte (UTC-3), e o dia inteiro escorrega.
    """
    assert site.timezone == FUSO_DO_SITE
    # 2h UTC de um dia = 23h do dia ANTERIOR no site.
    momento = datetime.now(UTC).replace(hour=2, minute=0, second=0, microsecond=0) - timedelta(
        days=1
    )
    await _sessao(db, site, ponto, quando=momento)

    dados = await analytics_service.serie_diaria(db, site.id, dias=7)

    dia_local = momento.astimezone(analytics_service.ZoneInfo(FUSO_DO_SITE)).date().isoformat()
    com_movimento = [d for d in dados["serie"] if d["sessoes"] > 0]
    assert len(com_movimento) == 1
    assert com_movimento[0]["dia"] == dia_local
    assert com_movimento[0]["dia"] != momento.date().isoformat()


async def test_a_janela_nao_passa_da_idade_do_site(db, site, ponto, ontem):
    """Dias anteriores a primeira sessao nao sao dias parados - nao existiram.

    Trata-los como zero afunda toda media e faz a operacao parecer pior do que e'.
    """
    await _sessao(db, site, ponto, quando=ontem)

    dados = await analytics_service.serie_diaria(db, site.id, dias=90)

    assert dados["janela_completa"] is False
    assert dados["dias_na_serie"] < 90
    assert dados["dias"] == 90, "o que foi PEDIDO continua declarado"


async def test_media_diaria_usa_os_dias_que_existiram(db, site, ponto, ontem):
    await _sessao(db, site, ponto, quando=ontem, kwh=30.0)

    dados = await analytics_service.serie_diaria(db, site.id, dias=90)

    # Dois dias de serie (ontem e hoje), 30 kWh -> 15, e nao 30/90.
    assert dados["totais"]["media_diaria_kwh"] == pytest.approx(
        30.0 / dados["dias_na_serie"], abs=0.01
    )
    assert dados["totais"]["media_diaria_kwh"] > 30.0 / 90


async def test_receita_paga_e_a_receber_nao_se_misturam(db, site, ponto, ontem):
    """Somar as duas chamaria de receita dinheiro que ainda pode nao entrar."""
    paga = await _sessao(db, site, ponto, quando=ontem)
    aberta = await _sessao(db, site, ponto, quando=ontem - timedelta(hours=2))
    await _fatura(db, site, paga, total="100.00", status=InvoiceStatus.PAID)
    await _fatura(db, site, aberta, total="40.00", status=InvoiceStatus.OPEN)

    dados = await analytics_service.serie_diaria(db, site.id, dias=7)

    assert dados["totais"]["receita_brl"] == 100.0
    assert dados["totais"]["a_receber_brl"] == 40.0


async def test_receita_segue_o_dia_da_sessao_e_nao_o_da_emissao(db, site, ponto):
    """Fatura emitida hoje por recarga de tres dias atras pertence aquele dia."""
    antiga = datetime.now(UTC) - timedelta(days=3)
    sessao = await _sessao(db, site, ponto, quando=antiga)
    fatura = Invoice(
        code="F-atrasada",
        site_id=site.id,
        session_id=sessao.id,
        status=InvoiceStatus.PAID,
        total=Decimal("77.00"),
        subtotal=Decimal("77.00"),
        net_amount=Decimal("77.00"),
        issued_on=datetime.now(UTC).date(),  # emitida HOJE
    )
    db.add(fatura)
    await db.flush()

    dados = await analytics_service.serie_diaria(db, site.id, dias=7)

    dia_da_sessao = antiga.astimezone(analytics_service.ZoneInfo(FUSO_DO_SITE)).date().isoformat()
    linha = next(d for d in dados["serie"] if d["dia"] == dia_da_sessao)
    assert linha["receita_brl"] == 77.0
    hoje = next(d for d in dados["serie"] if d["dia"] == dados["ate"])
    assert hoje["receita_brl"] == 0.0


async def test_site_sem_sessao_nenhuma_devolve_serie_e_nao_estoura(db, site):
    dados = await analytics_service.serie_diaria(db, site.id, dias=7)

    assert dados["dias_na_serie"] == 7
    assert dados["totais"]["sessoes"] == 0
    assert dados["totais"]["media_diaria_kwh"] == 0.0
    assert dados["totais"]["ticket_medio_brl"] == 0.0
    assert dados["totais"]["verde_pct"] == 0.0
