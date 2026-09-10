"""Assinatura de plano de recarga.

O plano entrega desconto, franquia de kWh e isencao de taxa - tudo pelo mesmo
`Beneficio` que as campanhas usam. O que se guarda aqui e' o que o motor NAO
resolve: quem tem direito, por quanto tempo, e o que acontece quando assinatura
e campanha valem ao mesmo tempo.

O encontro das duas e' a parte que erra sozinha. Somar produz desconto sem teto;
deixar a campanha vencer tira do assinante o que ele pagou. A regra e' o melhor
de cada componente, e ha teste para as duas armadilhas.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.errors import Conflict, PaymentError
from app.models.billing import Invoice
from app.models.campaign import Campaign
from app.models.enums import AuthMethod, SessionState, StopReason
from app.models.subscription import DriverPlan, DriverSubscription
from app.services import (
    benefit_service,
    billing_service,
    session_service,
    subscription_service,
)
from app.services.tariff_engine import Beneficio

AGORA = datetime.now(UTC)


async def _plano(db, **kwargs) -> DriverPlan:
    dados = dict(
        codigo="mensal",
        nome="Plano Mensal",
        preco_mensal_brl=Decimal("29.90"),
        desconto_pct=Decimal("15"),
        kwh_inclusos=Decimal("0"),
        isenta_taxa_de_conexao=False,
        ativo=True,
    )
    dados.update(kwargs)
    plano = DriverPlan(**dados)
    db.add(plano)
    await db.flush()
    return plano


async def _sessao_faturada(db, ponto, motorista, energia=10.0):
    sessao = await session_service.authorize(
        db, ponto, user=motorista, auth_method=AuthMethod.OPERATOR
    )
    await session_service.start(db, sessao, ponto)
    sessao.energy_kwh = energia
    sessao.duration_s = 3600
    sessao.state = SessionState.FINISHED
    sessao.stop_reason = StopReason.REMOTE
    await db.flush()
    return await billing_service.bill_session(db, sessao)


# ------------------------------------------------------------------ assinar


async def test_assinar_cria_e_cobra_a_primeira_mensalidade(db, motorista):
    plano = await _plano(db)
    saldo_antes = Decimal(str(motorista.wallet_balance))

    await subscription_service.assinar(db, motorista, plano.codigo)

    await db.refresh(motorista)
    assert Decimal(str(motorista.wallet_balance)) == saldo_antes - Decimal("29.90")

    fatura = (
        await db.execute(
            select(Invoice)
            .where(Invoice.user_id == motorista.id)
            # `selectinload` obrigatorio: `lines` e' lazy, e toca-la em contexto
            # assincrono sem carregar antes levanta MissingGreenlet.
            .options(selectinload(Invoice.lines))
        )
    ).scalar_one()
    assert float(fatura.total) == pytest.approx(29.90)
    # Sem site: a assinatura e' da rede, e atribui-la a uma praca inflaria o
    # faturamento de um estabelecimento com dinheiro que ele nao recebeu.
    assert fatura.site_id is None
    assert fatura.session_id is None
    assert any(linha.kind == "assinatura" for linha in fatura.lines)


async def test_sem_saldo_nao_fica_assinatura_orfa(db, motorista):
    """Assinatura ativa sem pagamento daria desconto de graca a quem nao pagou."""
    plano = await _plano(db, preco_mensal_brl=Decimal("9999"))

    with pytest.raises(PaymentError):
        await subscription_service.assinar(db, motorista, plano.codigo)

    assert await subscription_service.ativa_de(db, motorista) is None


async def test_duas_assinaturas_ativas_sao_recusadas(db, motorista):
    plano = await _plano(db)
    await subscription_service.assinar(db, motorista, plano.codigo)

    with pytest.raises(Conflict):
        await subscription_service.assinar(db, motorista, plano.codigo)


async def test_banco_recusa_duas_ativas_por_baixo_do_servico(db, motorista):
    """O indice unico parcial e' a garantia real.

    A checagem da aplicacao e' um SELECT seguido de INSERT, e dois toques
    simultaneos a atravessam juntos.
    """
    plano = await _plano(db)
    for _ in range(2):
        db.add(
            DriverSubscription(
                user_id=motorista.id,
                plan_id=plano.id,
                estado="ativa",
                started_at=AGORA,
                current_period_start=AGORA.date(),
                current_period_end=(AGORA + timedelta(days=30)).date(),
            )
        )
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_cancelar_exige_dizer_quando(db, motorista):
    """Sem a marca, "esta recarga tinha desconto?" fica sem resposta."""
    plano = await _plano(db)
    db.add(
        DriverSubscription(
            user_id=motorista.id,
            plan_id=plano.id,
            estado="cancelada",  # sem canceled_at
            started_at=AGORA,
            current_period_start=AGORA.date(),
            current_period_end=(AGORA + timedelta(days=30)).date(),
        )
    )
    with pytest.raises(IntegrityError):
        await db.flush()


# ---------------------------------------------------------------- beneficio


async def test_o_desconto_do_plano_chega_na_fatura(db, ponto, motorista, tarifa):
    plano = await _plano(db, desconto_pct=Decimal("15"))
    await subscription_service.assinar(db, motorista, plano.codigo)

    fatura = await _sessao_faturada(db, ponto, motorista, energia=10.0)

    assert float(fatura.discount) > 0
    linha = next(x for x in fatura.lines if x.kind == "desconto")
    assert "Plano Mensal" in linha.description


async def test_quem_nao_assina_paga_o_de_sempre(db, ponto, motorista, tarifa):
    await _plano(db)
    fatura = await _sessao_faturada(db, ponto, motorista, energia=10.0)
    assert float(fatura.discount) == 0.0


async def test_franquia_e_consumida_ao_longo_do_mes(db, ponto, motorista, tarifa):
    """A franquia se gasta na ordem em que as recargas acontecem."""
    plano = await _plano(db, desconto_pct=Decimal("0"), kwh_inclusos=Decimal("15"))
    await subscription_service.assinar(db, motorista, plano.codigo)

    primeira = await _sessao_faturada(db, ponto, motorista, energia=10.0)
    linha = next(x for x in primeira.lines if x.kind == "plano")
    assert float(linha.quantity) == pytest.approx(10.0), "abateu menos do que podia"

    # Restam 5 kWh de franquia para uma recarga de 10.
    segunda = await _sessao_faturada(db, ponto, motorista, energia=10.0)
    linha = next(x for x in segunda.lines if x.kind == "plano")
    assert float(linha.quantity) == pytest.approx(5.0)

    # Terceira recarga: franquia esgotada, nenhuma linha de plano.
    terceira = await _sessao_faturada(db, ponto, motorista, energia=10.0)
    assert not any(x.kind == "plano" for x in terceira.lines)


async def test_a_sessao_que_esta_sendo_faturada_nao_consome_a_propria_franquia(
    db, ponto, motorista, tarifa
):
    """Regressao esperada se alguem inverter a ordem em `bill_session`.

    O beneficio e' resolvido ANTES de a sessao virar BILLED, e a franquia conta
    so' o que ja esta BILLED. Com a ordem trocada, a primeira recarga do mes
    abateria zero - ela ja teria "consumido" a propria franquia.
    """
    plano = await _plano(db, desconto_pct=Decimal("0"), kwh_inclusos=Decimal("50"))
    await subscription_service.assinar(db, motorista, plano.codigo)

    fatura = await _sessao_faturada(db, ponto, motorista, energia=10.0)
    linha = next(x for x in fatura.lines if x.kind == "plano")
    assert float(linha.quantity) == pytest.approx(10.0)


async def test_cancelada_continua_valendo_ate_o_fim_do_mes_pago(db, ponto, motorista, tarifa):
    """Cancelar interrompe a renovacao, nao o mes ja pago.

    Cortar no ato seria cobrar o mes inteiro e entregar cinco dias. Quem cancela
    no dia 2 pagaria pelos 28 restantes sem receber nada.
    """
    plano = await _plano(db, desconto_pct=Decimal("15"))
    await subscription_service.assinar(db, motorista, plano.codigo)
    await subscription_service.cancelar(db, motorista)

    fatura = await _sessao_faturada(db, ponto, motorista, energia=10.0)
    assert float(fatura.discount) > 0, "o mes pago deixou de valer no ato do cancelamento"

    # Mas nao pode assinar de novo enquanto o periodo corre.
    estado = await subscription_service.minha_assinatura(db, motorista)
    assert estado["assinante"] is True
    assert estado["renova"] is False


async def test_periodo_vencido_deixa_de_dar_desconto(db, ponto, motorista, tarifa):
    plano = await _plano(db, desconto_pct=Decimal("15"))
    assinatura = await subscription_service.assinar(db, motorista, plano.codigo)
    assinatura.estado = "cancelada"
    assinatura.canceled_at = AGORA
    # O periodo inteiro anda para tras: `ck_driver_subscriptions_periodo` exige
    # fim depois do inicio, e recuar so' o fim inverteria o intervalo.
    assinatura.current_period_start = (AGORA - timedelta(days=31)).date()
    assinatura.current_period_end = (AGORA - timedelta(days=1)).date()
    await db.flush()

    fatura = await _sessao_faturada(db, ponto, motorista, energia=10.0)
    assert float(fatura.discount) == 0.0


# ------------------------------------------------- encontro com a campanha


def test_o_melhor_de_cada_componente_vence():
    """Somar produziria 45% de desconto que ninguem orcou."""
    plano = Beneficio("Plano", desconto_pct=Decimal("20"), kwh_inclusos=Decimal("10"))
    campanha = Beneficio("Setembro", desconto_pct=Decimal("25"))

    junto = benefit_service.combinar(plano, campanha)

    assert junto.desconto_pct == Decimal("25"), "somou em vez de escolher"
    assert junto.desconto_pct != Decimal("45")
    # A franquia vem do plano: campanha nao oferece kWh, entao nao ha o que
    # duplicar.
    assert junto.kwh_inclusos == Decimal("10")
    assert "Setembro" in junto.rotulo


def test_a_campanha_nao_tira_do_assinante_o_que_ele_pagou():
    """Se a promocao aberta a todos anula o plano, ele pagou por nada."""
    plano = Beneficio("Plano", desconto_pct=Decimal("20"), isenta_session_fee=True)
    campanha = Beneficio("Fraca", desconto_pct=Decimal("5"))

    junto = benefit_service.combinar(plano, campanha)

    assert junto.desconto_pct == Decimal("20")
    assert junto.isenta_session_fee is True
    assert "Plano" in junto.rotulo


def test_sem_fonte_nenhuma_nao_ha_beneficio():
    assert benefit_service.combinar(None, None) is None


def test_uma_fonte_so_passa_direto():
    plano = Beneficio("Plano", desconto_pct=Decimal("10"))
    assert benefit_service.combinar(plano, None) is plano
    assert benefit_service.combinar(None, plano) is plano


async def test_assinante_em_campanha_recebe_o_maior_e_nao_a_soma(
    db, ponto, motorista, tarifa
):
    """O mesmo, agora pelo caminho real: fatura emitida."""
    plano = await _plano(db, desconto_pct=Decimal("20"))
    await subscription_service.assinar(db, motorista, plano.codigo)
    db.add(
        Campaign(
            patrocinador="rede",
            nome="Setembro",
            starts_at=AGORA - timedelta(days=1),
            ends_at=AGORA + timedelta(days=30),
            ativa=True,
            beneficio_tipo="desconto_pct",
            beneficio_valor=Decimal("25"),
            orcamento_brl=Decimal("1000"),
        )
    )
    await db.flush()

    fatura = await _sessao_faturada(db, ponto, motorista, energia=10.0)

    # 10 kWh x R$ 2,00 = R$ 20. 25% = R$ 5, e nao os R$ 9 de 45%.
    assert float(fatura.discount) == pytest.approx(5.0)


# ---------------------------------------------------------------- cobranca


async def test_cobranca_mensal_e_idempotente_por_periodo(db, motorista):
    """O defeito classico de cobranca recorrente, e o unico que machuca."""
    plano = await _plano(db, preco_mensal_brl=Decimal("10"))
    assinatura = await subscription_service.assinar(db, motorista, plano.codigo)

    assinatura.current_period_start = (AGORA - timedelta(days=31)).date()
    assinatura.current_period_end = (AGORA - timedelta(days=1)).date()
    await db.flush()

    assert await subscription_service.cobrar_mensalidades(db) == 1
    # Segunda passada do worker no mesmo periodo nao pode cobrar de novo.
    cobradas = await subscription_service.cobrar_mensalidades(db)
    assert cobradas == 0

    faturas = (
        (await db.execute(select(Invoice).where(Invoice.user_id == motorista.id)))
        .scalars()
        .all()
    )
    assert len(faturas) == 2, "primeira mensalidade + uma renovacao"


async def test_worker_que_morre_antes_de_avancar_o_periodo_nao_recobra(db, motorista):
    """A checagem de idempotencia protege ESTE caso, e nao o retry comum.

    Achado por teste de mutacao: remover a checagem nao quebrava nada, porque o
    teste anterior e' idempotente por outro motivo - o periodo avanca e a
    assinatura deixa de ser encontrada.

    O caso real e' o worker morrer entre a cobranca e o avanco do periodo. Na
    proxima passada a assinatura ainda aparece como vencida. `charge_invoice`
    protege a carteira pela chave, mas a fatura ja teria sido criada: sobraria
    uma cobranca ABERTA que ninguem emitiu de proposito, no extrato do motorista.
    """
    plano = await _plano(db, preco_mensal_brl=Decimal("10"))
    assinatura = await subscription_service.assinar(db, motorista, plano.codigo)
    assinatura.current_period_start = (AGORA - timedelta(days=31)).date()
    assinatura.current_period_end = (AGORA - timedelta(days=1)).date()
    await db.flush()

    vencido_em = assinatura.current_period_end
    await subscription_service.cobrar_mensalidades(db)
    depois_da_primeira = len(
        (await db.execute(select(Invoice).where(Invoice.user_id == motorista.id)))
        .scalars()
        .all()
    )

    # O worker morreu antes de gravar o avanco: o periodo volta ao que era.
    assinatura.current_period_start = (AGORA - timedelta(days=31)).date()
    assinatura.current_period_end = vencido_em
    await db.flush()

    await subscription_service.cobrar_mensalidades(db)

    faturas = (
        (await db.execute(select(Invoice).where(Invoice.user_id == motorista.id)))
        .scalars()
        .all()
    )
    assert len(faturas) == depois_da_primeira, "sobrou fatura aberta que ninguem emitiu"


async def test_sem_saldo_a_assinatura_fica_inadimplente(db, motorista):
    """Apagar perderia desde quando ele assina; ele pode recarregar e voltar."""
    plano = await _plano(db, preco_mensal_brl=Decimal("10"))
    assinatura = await subscription_service.assinar(db, motorista, plano.codigo)
    assinatura.current_period_start = (AGORA - timedelta(days=31)).date()
    assinatura.current_period_end = (AGORA - timedelta(days=1)).date()
    motorista.wallet_balance = 0
    await db.flush()

    await subscription_service.cobrar_mensalidades(db)

    await db.refresh(assinatura)
    assert assinatura.estado == "inadimplente"


async def test_plano_que_nao_entrega_nada_e_recusado(db):
    """Mensalidade sem contrapartida. Descobrir depois exigiria estornar."""
    with pytest.raises(IntegrityError):
        await _plano(
            db,
            codigo="vazio",
            desconto_pct=Decimal("0"),
            kwh_inclusos=Decimal("0"),
            isenta_taxa_de_conexao=False,
        )
