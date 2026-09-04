"""Faturamento: onde um erro vira dinheiro cobrado a mais ou a menos.

O motor de tarifacao ja tem testes proprios (test_tariff_engine). Aqui o
interesse e' o servico em volta dele: a idempotencia, a guarda de estado, as
linhas que compoem a fatura e a taxa do adquirente.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.errors import Conflict
from app.models.billing import Invoice
from app.models.enums import AuthMethod, PaymentMethodKind, SessionState, StopReason
from app.services import billing_service, session_service


async def _sessao_encerrada(db, ponto, motorista, *, energia=10.0, ocioso=0):
    """Uma sessao pronta para faturar, sem passar pelo stop (que ja fatura)."""
    sessao = await session_service.authorize(
        db, ponto, user=motorista, auth_method=AuthMethod.OPERATOR
    )
    await session_service.start(db, sessao, ponto)
    sessao.energy_kwh = energia
    sessao.idle_minutes = ocioso
    sessao.duration_s = 3600
    sessao.state = SessionState.FINISHED
    sessao.stop_reason = StopReason.REMOTE
    await db.flush()
    return sessao


# ------------------------------------------------------------------ idempotencia


async def test_faturar_duas_vezes_devolve_a_mesma_fatura(db, ponto, motorista, tarifa):
    """Sem isto, um duplo clique no painel cobraria o motorista duas vezes."""
    sessao = await _sessao_encerrada(db, ponto, motorista)

    primeira = await billing_service.bill_session(db, sessao)
    segunda = await billing_service.bill_session(db, sessao)

    assert primeira.id == segunda.id
    faturas = (
        (await db.execute(select(Invoice).where(Invoice.session_id == sessao.id))).scalars().all()
    )
    assert len(faturas) == 1


async def test_sessao_em_andamento_nao_pode_ser_faturada(db, ponto, motorista, tarifa):
    sessao = await session_service.authorize(
        db, ponto, user=motorista, auth_method=AuthMethod.OPERATOR
    )
    await session_service.start(db, sessao, ponto)

    with pytest.raises(Conflict):
        await billing_service.bill_session(db, sessao)


# -------------------------------------------------------------- linhas e valores


async def test_energia_vira_linha_com_quantidade_e_preco(db, ponto, motorista, tarifa):
    sessao = await _sessao_encerrada(db, ponto, motorista, energia=10.0)
    fatura = await billing_service.bill_session(db, sessao)

    energia = [linha for linha in fatura.lines if linha.kind == "energy"]
    assert len(energia) == 1
    assert float(energia[0].quantity) == pytest.approx(10.0)
    assert float(energia[0].unit_price) == pytest.approx(float(tarifa.price_per_kwh))
    assert float(energia[0].amount) == pytest.approx(20.0)  # 10 kWh x R$ 2


async def test_valor_minimo_entra_como_complemento(db, ponto, motorista, tarifa):
    """A tarifa tem minimo de R$ 5. Uma recarga de R$ 1 nao pode sair por R$ 1."""
    sessao = await _sessao_encerrada(db, ponto, motorista, energia=0.5)  # R$ 1,00
    fatura = await billing_service.bill_session(db, sessao)

    assert float(fatura.total) == pytest.approx(float(tarifa.min_charge))
    complemento = [linha for linha in fatura.lines if linha.kind == "min_charge"]
    assert len(complemento) == 1
    assert float(fatura.subtotal) < float(fatura.total)


async def test_ociosidade_dentro_da_tolerancia_nao_e_cobrada(db, ponto, motorista, tarifa):
    """A tarifa da 10 minutos livres; 8 nao podem virar linha."""
    sessao = await _sessao_encerrada(db, ponto, motorista, energia=10.0, ocioso=8)
    fatura = await billing_service.bill_session(db, sessao)

    assert [linha for linha in fatura.lines if linha.kind == "idle"] == []


async def test_soma_das_linhas_bate_com_o_subtotal(db, ponto, motorista, tarifa):
    """Divergencia aqui e' fatura que nao fecha - o pior tipo de defeito."""
    sessao = await _sessao_encerrada(db, ponto, motorista, energia=13.7, ocioso=30)
    fatura = await billing_service.bill_session(db, sessao)

    soma = sum(Decimal(str(linha.amount)) for linha in fatura.lines)
    assert soma == pytest.approx(Decimal(str(fatura.total)))


async def test_fatura_nasce_em_aberto_e_ligada_a_sessao(db, ponto, motorista, tarifa):
    sessao = await _sessao_encerrada(db, ponto, motorista)
    fatura = await billing_service.bill_session(db, sessao)

    assert fatura.session_id == sessao.id
    assert fatura.user_id == motorista.id
    assert fatura.code.startswith("INV-")
    assert float(fatura.net_amount) == pytest.approx(float(fatura.total))


# ------------------------------------------------------------ previa x faturado


async def test_previa_bate_com_o_que_sera_faturado(db, ponto, motorista, tarifa):
    """O app mostra a previa durante a recarga; se ela mentir, o motorista reclama."""
    sessao = await _sessao_encerrada(db, ponto, motorista, energia=9.25, ocioso=25)

    previa = await billing_service.preview_session(db, sessao)
    fatura = await billing_service.bill_session(db, sessao)

    assert float(previa["total"]) == pytest.approx(float(fatura.total))


# --------------------------------------------------------- taxa do adquirente


async def test_taxa_do_adquirente_sai_do_liquido(db, site, ponto, motorista, tarifa):
    from app.models.billing import SitePaymentMethod

    db.add(
        SitePaymentMethod(
            site_id=site.id,
            kind=PaymentMethodKind.CREDIT_CARD,
            label="Cartao",
            enabled=True,
            fee_percent=3.2,
            fee_fixed=0.39,
        )
    )
    await db.flush()

    sessao = await _sessao_encerrada(db, ponto, motorista, energia=10.0)  # R$ 20,00
    fatura = await billing_service.bill_session(db, sessao)
    await billing_service.apply_processing_fee(db, fatura, PaymentMethodKind.CREDIT_CARD)

    esperado = 20.0 * 0.032 + 0.39
    assert float(fatura.processing_fee) == pytest.approx(esperado, abs=0.01)
    assert float(fatura.net_amount) == pytest.approx(20.0 - esperado, abs=0.01)
    # O que o motorista paga nao muda: a taxa sai da receita do lojista.
    assert float(fatura.total) == pytest.approx(20.0)


async def test_meio_de_pagamento_nao_cadastrado_nao_desconta_nada(db, ponto, motorista, tarifa):
    sessao = await _sessao_encerrada(db, ponto, motorista, energia=10.0)
    fatura = await billing_service.bill_session(db, sessao)
    liquido_antes = float(fatura.net_amount)

    await billing_service.apply_processing_fee(db, fatura, PaymentMethodKind.PIX)

    assert float(fatura.net_amount) == pytest.approx(liquido_antes)
