"""Contrato do estabelecimento com a plataforma.

Dinheiro na direcao oposta ao resto do sistema: aqui o estabelecimento paga a
rede. Tres coisas sao guardadas, e cada uma erra de um jeito diferente:

- A COBRANCA nao pode sair duas vezes no mesmo mes. E' o defeito classico de
  cobranca recorrente, e o unico que o cliente sente na hora.
- A MULTA nao pode ser negativa nem existir fora do prazo minimo. Sem o piso em
  zero, rescindir depois do prazo viraria credito - a rede pagaria para o
  cliente sair.
- A RENOVACAO nao pode estender o prazo minimo. Prender por mais doze meses quem
  so' deixou o contrato correr e' abusivo, e o modelo nao se sustenta com isso.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import Conflict
from app.models.platform import PlatformInvoice, PlatformPlan, SiteSubscription
from app.services import platform_service

HOJE = date.today()


async def _plano(db, **kwargs) -> PlatformPlan:
    dados = dict(
        codigo="essencial",
        nome="Essencial",
        preco_mensal_brl=Decimal("149.00"),
        preco_por_ponto_brl=Decimal("35.00"),
        pontos_inclusos=2,
        fee_percent_transacao=Decimal("3.5"),
        meses_minimos=12,
        ativo=True,
    )
    dados.update(kwargs)
    plano = PlatformPlan(**dados)
    db.add(plano)
    await db.flush()
    return plano


# ------------------------------------------------------------ funcoes puras


def test_meses_restantes_nunca_e_negativo():
    """Sem o piso em zero, a multa vira credito e a rede paga para o cliente sair."""
    venceu = HOJE - timedelta(days=400)
    assert platform_service.meses_restantes(HOJE, venceu) == 0

    futuro = date(HOJE.year + 1, HOJE.month, HOJE.day)
    assert platform_service.meses_restantes(HOJE, futuro) == 12


def test_multa_e_proporcional_ao_que_faltava():
    """Cobrar 100% seria cobrar o contrato sem prestar o servico."""
    multa = platform_service.multa_por_rescisao(Decimal("100"), 6, Decimal("30"))
    assert multa == Decimal("180.00")  # 6 x 100 x 30%


def test_sem_meses_restantes_nao_ha_multa():
    assert platform_service.multa_por_rescisao(Decimal("100"), 0, Decimal("30")) == Decimal(
        "0.00"
    )


def test_multa_zerada_no_contrato_nao_cobra_nada():
    """Percentual zero e' uma escolha comercial legitima, nao um bug."""
    assert platform_service.multa_por_rescisao(Decimal("100"), 6, Decimal("0")) == Decimal(
        "0.00"
    )


# --------------------------------------------------------------- contratar


async def test_contratar_define_o_prazo_minimo(db, site):
    plano = await _plano(db, meses_minimos=12)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)

    assert contrato.estado == "ativa"
    assert contrato.minimo_ate > contrato.starts_on
    assert platform_service.meses_restantes(HOJE, contrato.minimo_ate) == 12


async def test_dois_contratos_vivos_sao_recusados(db, site):
    plano = await _plano(db)
    await platform_service.contratar(db, site.id, plano.codigo)

    with pytest.raises(Conflict):
        await platform_service.contratar(db, site.id, plano.codigo)


async def test_banco_recusa_dois_contratos_vivos(db, site):
    """O indice unico parcial e' a garantia real."""
    plano = await _plano(db)
    for _ in range(2):
        db.add(
            SiteSubscription(
                site_id=site.id,
                plan_id=plano.id,
                estado="ativa",
                starts_on=HOJE,
                minimo_ate=HOJE + timedelta(days=365),
                renova_em=HOJE + timedelta(days=30),
            )
        )
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_contrato_encerrado_permite_contratar_de_novo(db, site):
    """Barrar isso obrigaria o estabelecimento a apagar o proprio historico."""
    plano = await _plano(db)
    db.add(
        SiteSubscription(
            site_id=site.id,
            plan_id=plano.id,
            estado="encerrada",
            starts_on=HOJE - timedelta(days=400),
            minimo_ate=HOJE - timedelta(days=35),
            renova_em=HOJE - timedelta(days=35),
            encerra_em=HOJE - timedelta(days=30),
        )
    )
    await db.flush()

    novo = await platform_service.contratar(db, site.id, plano.codigo)
    assert novo.estado == "ativa"


async def test_encerrar_exige_dizer_quando(db, site):
    plano = await _plano(db)
    db.add(
        SiteSubscription(
            site_id=site.id,
            plan_id=plano.id,
            estado="encerrada",  # sem encerra_em
            starts_on=HOJE,
            minimo_ate=HOJE + timedelta(days=365),
            renova_em=HOJE + timedelta(days=30),
        )
    )
    with pytest.raises(IntegrityError):
        await db.flush()


# ----------------------------------------------------------------- rescisao


async def test_rescindir_dentro_do_prazo_emite_multa(db, site):
    plano = await _plano(db, preco_mensal_brl=Decimal("100"), meses_minimos=12)
    await platform_service.contratar(db, site.id, plano.codigo, Decimal("30"))

    saida = await platform_service.rescindir(db, site.id)

    assert saida["meses_restantes"] == 12
    assert saida["multa_brl"] == pytest.approx(360.0)  # 12 x 100 x 30%
    assert saida["cobranca_da_multa"] is not None

    cobranca = (
        await db.execute(
            select(PlatformInvoice).where(
                PlatformInvoice.id == uuid_de(saida["cobranca_da_multa"])
            )
        )
    ).scalar_one()
    # So' a multa: nao se cobra mensalidade e taxa junto de quem esta saindo no
    # mesmo ato - essas vem pela emissao normal da competencia.
    assert float(cobranca.multa_brl) == pytest.approx(360.0)
    assert float(cobranca.assinatura_brl) == 0.0


def uuid_de(texto: str):
    import uuid

    return uuid.UUID(texto)


async def test_rescindir_depois_do_prazo_nao_cobra_multa(db, site):
    """Passado o prazo minimo, sair e' livre."""
    plano = await _plano(db, preco_mensal_brl=Decimal("100"))
    contrato = await platform_service.contratar(db, site.id, plano.codigo, Decimal("30"))
    # O periodo inteiro anda para tras: `minimo_ate >= starts_on` e' constraint,
    # e recuar so' o fim inverteria o intervalo.
    contrato.starts_on = HOJE - timedelta(days=400)
    contrato.minimo_ate = HOJE - timedelta(days=1)
    await db.flush()

    saida = await platform_service.rescindir(db, site.id)

    assert saida["meses_restantes"] == 0
    assert saida["multa_brl"] == 0.0
    assert saida["cobranca_da_multa"] is None


async def test_rescindir_nao_encerra_no_ato(db, site):
    """O mes corrente ja foi cobrado; cortar entregaria menos do que se cobrou."""
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)

    saida = await platform_service.rescindir(db, site.id)

    await db.refresh(contrato)
    assert contrato.estado == "em_aviso_previo"
    assert contrato.encerra_em is not None
    assert saida["encerra_em"] == contrato.renova_em.isoformat()
    assert contrato.renovacao_automatica is False


async def test_rescindir_duas_vezes_e_recusado(db, site):
    plano = await _plano(db)
    await platform_service.contratar(db, site.id, plano.codigo)
    await platform_service.rescindir(db, site.id)

    with pytest.raises(Conflict):
        await platform_service.rescindir(db, site.id)


# ---------------------------------------------------------------- renovacao


async def test_renovacao_automatica_nao_estende_o_prazo_minimo(db, site):
    """Prender por mais um prazo minimo quem so' deixou o contrato correr e' abusivo."""
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    minimo_original = contrato.minimo_ate
    contrato.renova_em = HOJE - timedelta(days=1)
    await db.flush()

    assert await platform_service.renovar_vencidos(db) == 1

    await db.refresh(contrato)
    assert contrato.minimo_ate == minimo_original, "a renovacao prendeu o cliente de novo"
    assert contrato.renova_em > HOJE


async def test_contrato_em_aviso_previo_nao_renova(db, site):
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    await platform_service.rescindir(db, site.id)
    contrato.renova_em = HOJE - timedelta(days=1)
    await db.flush()

    assert await platform_service.renovar_vencidos(db) == 0


# ----------------------------------------------------------------- cobranca


async def test_emitir_duas_vezes_no_mesmo_mes_nao_dobra(db, site):
    """O defeito classico de cobranca recorrente."""
    plano = await _plano(db)
    await platform_service.contratar(db, site.id, plano.codigo)

    assert await platform_service.emitir_competencia(db) == 1
    assert await platform_service.emitir_competencia(db) == 0

    cobrancas = (
        (await db.execute(select(PlatformInvoice))).scalars().all()
    )
    assert len(cobrancas) == 1


async def test_banco_recusa_duas_cobrancas_da_mesma_competencia(db, site):
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    competencia = platform_service.primeiro_do_mes(HOJE)

    for _ in range(2):
        db.add(
            PlatformInvoice(
                site_subscription_id=contrato.id,
                competencia=competencia,
                emitida_em=HOJE,
                vence_em=HOJE + timedelta(days=10),
                total_brl=Decimal("149"),
            )
        )
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_a_cobranca_separa_as_tres_parcelas(db, site, ponto, segundo_ponto):
    """"R$ 480" nao explica nada; o lojista confere cada parcela."""
    plano = await _plano(
        db,
        preco_mensal_brl=Decimal("149"),
        preco_por_ponto_brl=Decimal("35"),
        pontos_inclusos=1,
        fee_percent_transacao=Decimal("3.5"),
    )
    await platform_service.contratar(db, site.id, plano.codigo)

    await platform_service.emitir_competencia(db)

    cobranca = (await db.execute(select(PlatformInvoice))).scalar_one()
    assert float(cobranca.assinatura_brl) == pytest.approx(149.0)
    # Dois pontos no site, um incluso: cobra um excedente.
    assert cobranca.pontos_cobrados == 2
    assert float(cobranca.pontos_brl) == pytest.approx(35.0)
    assert float(cobranca.total_brl) == pytest.approx(
        float(cobranca.assinatura_brl)
        + float(cobranca.pontos_brl)
        + float(cobranca.transacao_brl)
    )


async def test_declarar_paga_exige_dizer_quando(db, site):
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    db.add(
        PlatformInvoice(
            site_subscription_id=contrato.id,
            competencia=platform_service.primeiro_do_mes(HOJE),
            emitida_em=HOJE,
            vence_em=HOJE + timedelta(days=10),
            total_brl=Decimal("149"),
            estado="paga",  # sem paga_em
        )
    )
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_baixa_manual_marca_a_data(db, site):
    plano = await _plano(db)
    await platform_service.contratar(db, site.id, plano.codigo)
    await platform_service.emitir_competencia(db)
    cobranca = (await db.execute(select(PlatformInvoice))).scalar_one()

    paga = await platform_service.marcar_como_paga(db, cobranca.id)

    assert paga.estado == "paga"
    assert paga.paga_em is not None


async def test_a_leitura_declara_que_nao_ha_liquidacao_automatica(db, site):
    """Cobranca que parece liquidada sem liquidacao e' pior que a limitacao."""
    plano = await _plano(db)
    await platform_service.contratar(db, site.id, plano.codigo)

    saida = await platform_service.contrato_do_site(db, site.id)
    assert saida["liquidacao_automatica"] is False


async def test_site_sem_contrato_responde_que_nao_ha(db, site):
    saida = await platform_service.contrato_do_site(db, site.id)
    assert saida["contratado"] is False
