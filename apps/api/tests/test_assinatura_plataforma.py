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
    assert platform_service.multa_por_rescisao(Decimal("100"), 0, Decimal("30")) == Decimal("0.00")


def test_multa_zerada_no_contrato_nao_cobra_nada():
    """Percentual zero e' uma escolha comercial legitima, nao um bug."""
    assert platform_service.multa_por_rescisao(Decimal("100"), 6, Decimal("0")) == Decimal("0.00")


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
            select(PlatformInvoice).where(PlatformInvoice.id == uuid_de(saida["cobranca_da_multa"]))
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

    cobrancas = (await db.execute(select(PlatformInvoice))).scalars().all()
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
    """ "R$ 480" nao explica nada; o lojista confere cada parcela."""
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
        float(cobranca.assinatura_brl) + float(cobranca.pontos_brl) + float(cobranca.transacao_brl)
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


# --------------------------------------------------------------- vencimento
#
# A decisao de escopo por tras destes testes: NAO ha liquidacao bancaria B2B -
# cobrar o estabelecimento por Pix exigiria credencial de PSP da plataforma, que
# nao existe. O que existe e' o CICLO, que nao depende de banco nenhum: a
# cobranca vence, o contrato fica inadimplente, para de renovar, e a baixa
# manual desfaz os dois.
#
# Antes disto `vence_em` era escrita e nunca lida, e `inadimplente` estava no
# CHECK e no badge do painel sem que nada jamais o atribuisse.


async def _cobranca_vencida(db, contrato, dias=1, total="149.00", mes=0) -> PlatformInvoice:
    """Uma cobranca com `dias` de atraso.

    `mes` desloca a competencia para tras: a UNIQUE (contrato, competencia)
    recusa duas cobrancas do mesmo mes, e `rescindir` ja emite uma no mes
    corrente - entao quem precisa de duas dividas tem de dizer de que meses sao.
    """
    competencia = platform_service.primeiro_do_mes(HOJE)
    for _ in range(mes):
        competencia = platform_service.primeiro_do_mes(competencia - timedelta(days=1))
    cobranca = PlatformInvoice(
        site_subscription_id=contrato.id,
        competencia=competencia,
        emitida_em=HOJE - timedelta(days=dias + 10),
        vence_em=HOJE - timedelta(days=dias),
        total_brl=Decimal(total),
        estado="aberta",
    )
    db.add(cobranca)
    await db.flush()
    return cobranca


async def test_cobranca_passada_do_prazo_vence(db, site):
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    cobranca = await _cobranca_vencida(db, contrato)

    resultado = await platform_service.marcar_vencidas(db)

    assert resultado["cobrancas_vencidas"] == 1
    await db.refresh(cobranca)
    assert cobranca.estado == "vencida"


async def test_cobranca_dentro_do_prazo_nao_vence(db, site):
    """O prazo e' de dez dias, e vencer no dia da emissao seria cobrar juros do nada."""
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    cobranca = PlatformInvoice(
        site_subscription_id=contrato.id,
        competencia=platform_service.primeiro_do_mes(HOJE),
        emitida_em=HOJE,
        vence_em=HOJE + timedelta(days=platform_service.DIAS_PARA_VENCER),
        total_brl=Decimal("149.00"),
        estado="aberta",
    )
    db.add(cobranca)
    await db.flush()

    await platform_service.marcar_vencidas(db)

    await db.refresh(cobranca)
    assert cobranca.estado == "aberta"


async def test_cobranca_que_vence_hoje_ainda_nao_venceu(db, site):
    """O dia do vencimento e' do devedor. Vencer as 00h01 de `vence_em` tiraria
    um dia inteiro de quem tem ate o fim dele para pagar."""
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    cobranca = await _cobranca_vencida(db, contrato, dias=0)

    await platform_service.marcar_vencidas(db)

    await db.refresh(cobranca)
    assert cobranca.estado == "aberta"


async def test_contrato_com_cobranca_vencida_fica_inadimplente(db, site):
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    await _cobranca_vencida(db, contrato)

    resultado = await platform_service.marcar_vencidas(db)

    assert resultado["contratos_inadimplentes"] == 1
    await db.refresh(contrato)
    assert contrato.estado == "inadimplente"


async def test_inadimplencia_acontece_na_mesma_passada(db, site):
    """A cobranca vence e o contrato cai juntos, nao em ciclos diferentes.

    Sem o flush entre os dois passos, a consulta que procura contrato com divida
    nao enxergaria as cobrancas recem-vencidas - elas ainda estariam so' na
    sessao -, e a tela mostraria cobranca vencida num contrato "ativa" ate o
    worker rodar de novo.
    """
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    await _cobranca_vencida(db, contrato)

    resultado = await platform_service.marcar_vencidas(db)

    assert resultado == {"cobrancas_vencidas": 1, "contratos_inadimplentes": 1}


async def test_passar_de_novo_nao_muda_nada(db, site):
    """O worker chama isto a cada ciclo. Idempotencia nao e' opcional."""
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    await _cobranca_vencida(db, contrato)

    await platform_service.marcar_vencidas(db)
    segunda = await platform_service.marcar_vencidas(db)

    assert segunda == {"cobrancas_vencidas": 0, "contratos_inadimplentes": 0}


async def test_contrato_em_aviso_previo_nao_vira_inadimplente(db, site):
    """Quem ja pediu rescisao esta de saida: o desfecho nao muda, e sobrescrever
    o estado apagaria a data em que o contrato acaba."""
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    await platform_service.rescindir(db, site.id)
    await _cobranca_vencida(db, contrato, mes=1)

    await platform_service.marcar_vencidas(db)

    await db.refresh(contrato)
    assert contrato.estado == "em_aviso_previo"
    assert contrato.encerra_em is not None


async def test_o_servico_nao_e_cortado(db, site):
    """A consequencia da inadimplencia NAO e' desligar o eletroposto.

    Quem deixou de pagar foi o estabelecimento; quem ficaria sem recarregar
    seria o motorista, que nao tem nada com isso. Este teste existe para que
    ligar o corte seja uma decisao deliberada, e nao algo que entre de carona.
    """
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    await _cobranca_vencida(db, contrato)

    await platform_service.marcar_vencidas(db)

    from app.models.charge_point import ChargePoint

    pontos = (
        (await db.execute(select(ChargePoint).where(ChargePoint.site_id == site.id)))
        .scalars()
        .all()
    )
    assert all(p.enabled for p in pontos), "inadimplencia desligou ponto de recarga"


# ------------------------------------------------------- voltar ao normal


async def test_pagar_a_ultima_divida_regulariza_o_contrato(db, site):
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    cobranca = await _cobranca_vencida(db, contrato)
    await platform_service.marcar_vencidas(db)

    await platform_service.marcar_como_paga(db, cobranca.id)

    await db.refresh(contrato)
    assert contrato.estado == "ativa"


async def test_pagar_uma_de_duas_nao_regulariza(db, site):
    """Quitar parte da divida nao tira ninguem da inadimplencia."""
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    primeira = await _cobranca_vencida(db, contrato, dias=40, mes=1)
    await _cobranca_vencida(db, contrato, dias=10)
    await platform_service.marcar_vencidas(db)

    await platform_service.marcar_como_paga(db, primeira.id)

    await db.refresh(contrato)
    assert contrato.estado == "inadimplente"


async def test_baixa_nao_ressuscita_contrato_encerrado(db, site):
    """O pagamento quita a divida, nao desfaz a rescisao."""
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    cobranca = await _cobranca_vencida(db, contrato)
    await platform_service.marcar_vencidas(db)
    # `encerrada` exige `encerra_em`: o CHECK `encerramento_completo` recusa um
    # contrato que se declara encerrado sem dizer quando.
    contrato.estado = "encerrada"
    contrato.encerra_em = HOJE
    await db.flush()

    await platform_service.marcar_como_paga(db, cobranca.id)

    await db.refresh(contrato)
    assert contrato.estado == "encerrada"


async def test_inadimplente_nao_renova_sozinho(db, site):
    """A consequencia pratica da inadimplencia.

    `renovar_vencidos` so' olha contratos `ativa`. Nao e' coincidencia: estender
    por mais um ciclo um contrato que nao esta sendo pago e' aumentar a divida
    em vez de cobra-la.
    """
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    await _cobranca_vencida(db, contrato)
    await platform_service.marcar_vencidas(db)

    contrato.renova_em = HOJE - timedelta(days=1)
    await db.flush()
    renovados = await platform_service.renovar_vencidos(db)

    assert renovados == 0
    await db.refresh(contrato)
    assert contrato.renova_em == HOJE - timedelta(days=1)


# ------------------------------------------------------------- o que a tela ve


async def test_o_contrato_publica_a_divida(db, site):
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    await _cobranca_vencida(db, contrato, dias=40, total="149.00", mes=1)
    await _cobranca_vencida(db, contrato, dias=10, total="200.00")
    await platform_service.marcar_vencidas(db)

    visao = await platform_service.contrato_do_site(db, site.id)

    assert visao["estado"] == "inadimplente"
    assert visao["em_atraso"]["cobrancas"] == 2
    assert visao["em_atraso"]["total_brl"] == 349.0
    assert visao["em_atraso"]["desde"] == (HOJE - timedelta(days=40)).isoformat()


async def test_contrato_em_dia_nao_tem_atraso(db, site):
    plano = await _plano(db)
    await platform_service.contratar(db, site.id, plano.codigo)

    visao = await platform_service.contrato_do_site(db, site.id)

    assert visao["em_atraso"] == {"cobrancas": 0, "total_brl": 0.0, "desde": None}


async def test_a_divida_nao_depende_da_janela_de_doze_meses(db, site):
    """`cobrancas` vem limitada as 12 competencias mais recentes.

    Um contrato parado ha' mais de um ano teria a cobranca mais antiga fora da
    janela, e somar a lista daria um total menor que o real - justamente no caso
    em que ele e' maior. Dai a consulta propria.
    """
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    competencia = platform_service.primeiro_do_mes(HOJE)
    for _ in range(15):
        db.add(
            PlatformInvoice(
                site_subscription_id=contrato.id,
                competencia=competencia,
                emitida_em=HOJE - timedelta(days=400),
                vence_em=HOJE - timedelta(days=390),
                total_brl=Decimal("100.00"),
                estado="aberta",
            )
        )
        competencia = platform_service.mes_seguinte(competencia)
    await db.flush()
    await platform_service.marcar_vencidas(db)

    visao = await platform_service.contrato_do_site(db, site.id)

    assert len(visao["cobrancas"]) == 12, "a lista continua paginada"
    assert visao["em_atraso"]["cobrancas"] == 15
    assert visao["em_atraso"]["total_brl"] == 1500.0


async def test_banco_recusa_estado_de_cobranca_desconhecido(db, site):
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    db.add(
        PlatformInvoice(
            site_subscription_id=contrato.id,
            competencia=platform_service.primeiro_do_mes(HOJE),
            emitida_em=HOJE,
            vence_em=HOJE,
            total_brl=Decimal("10.00"),
            estado="atrasada",
        )
    )
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


# ----------------------------------------------------------- encerramento
#
# `rescindir` punha o contrato em `em_aviso_previo` e gravava `encerra_em` - e
# NADA nunca o levava a `encerrada`. O estado estava no CHECK e no badge do
# painel desde a 0019, alcancavel so' por teste que montava a linha a mao.
#
# Nao era cosmetico: `vigente_do_site` filtra `estado <> 'encerrada'` e
# `contratar` recusa quem ja tem vigente, entao quem rescindia ficava SEM SAIDA
# - sem ser faturado, marcado como "em aviso previo" para sempre, e sem poder
# assinar outro plano.


async def _em_aviso(db, site, dias_ate_encerrar=-1):
    """Contrato rescindido cujo aviso previo termina em `dias_ate_encerrar`."""
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    await platform_service.rescindir(db, site.id)
    contrato.encerra_em = HOJE + timedelta(days=dias_ate_encerrar)
    await db.flush()
    return contrato


async def test_aviso_previo_vencido_encerra(db, site):
    contrato = await _em_aviso(db, site)

    assert await platform_service.encerrar_vencidos(db) == 1

    await db.refresh(contrato)
    assert contrato.estado == "encerrada"


async def test_aviso_previo_que_termina_hoje_ja_encerra(db, site):
    """`encerra_em` e' o primeiro dia SEM servico - o ciclo pago acabou ontem."""
    contrato = await _em_aviso(db, site, dias_ate_encerrar=0)

    await platform_service.encerrar_vencidos(db)

    await db.refresh(contrato)
    assert contrato.estado == "encerrada"


async def test_aviso_previo_em_curso_nao_encerra(db, site):
    """O mes ja pago vale ate o fim: cortar antes entrega menos do que se cobrou."""
    contrato = await _em_aviso(db, site, dias_ate_encerrar=15)

    assert await platform_service.encerrar_vencidos(db) == 0

    await db.refresh(contrato)
    assert contrato.estado == "em_aviso_previo"


async def test_contrato_ativo_nao_e_encerrado(db, site):
    """Sem rescisao pedida nao ha o que encerrar, por mais velho que seja."""
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)

    await platform_service.encerrar_vencidos(db)

    await db.refresh(contrato)
    assert contrato.estado == "ativa"


async def test_so_encerra_quem_pediu_rescisao(db, site):
    """`encerra_em` no passado nao basta: o contrato precisa estar EM AVISO.

    Hoje as duas condicoes andam juntas, porque so' `rescindir` grava a data -
    e o teste de mutacao mostrou isso: trocar o filtro de estado por
    `("ativa", "em_aviso_previo")` nao quebrava nada. Este teste e' o que separa
    as duas, montando o estado que o codigo atual nao produz mas o schema
    aceita.

    A regra que ele fixa: encerrar fecha quem PEDIU para sair. Um contrato ativo
    com data antiga em `encerra_em` e' um dado inconsistente - o certo e'
    ignora-lo, nao desligar o cliente por causa dele.
    """
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    contrato.encerra_em = HOJE - timedelta(days=30)
    await db.flush()

    assert await platform_service.encerrar_vencidos(db) == 0

    await db.refresh(contrato)
    assert contrato.estado == "ativa"


async def test_passar_de_novo_nao_encerra_nada(db, site):
    """O worker chama a cada ciclo."""
    await _em_aviso(db, site)

    await platform_service.encerrar_vencidos(db)

    assert await platform_service.encerrar_vencidos(db) == 0


async def test_encerrado_libera_o_site_para_contratar_de_novo(db, site):
    """A razao de tudo isto. Sem o encerramento, `contratar` recusa para sempre."""
    contrato = await _em_aviso(db, site)
    codigo = contrato.plan.codigo  # o mesmo plano: `codigo` e' UNIQUE

    with pytest.raises(Conflict):
        await platform_service.contratar(db, site.id, codigo)

    await platform_service.encerrar_vencidos(db)

    novo = await platform_service.contratar(db, site.id, codigo)
    assert novo.estado == "ativa"
    assert novo.id != contrato.id


async def test_encerrado_deixa_de_ser_faturado(db, site):
    plano = await _plano(db)
    contrato = await platform_service.contratar(db, site.id, plano.codigo)
    await platform_service.rescindir(db, site.id)
    contrato.encerra_em = HOJE - timedelta(days=1)
    await db.flush()
    await platform_service.encerrar_vencidos(db)

    emitidas = await platform_service.emitir_competencia(
        db, platform_service.mes_seguinte(platform_service.primeiro_do_mes(HOJE))
    )

    assert emitidas == 0


# ------------------------------------------------- encerrar nao some com a divida


async def test_divida_continua_na_tela_depois_de_encerrar(db, site):
    """Encerrar nao pode virar um jeito de sumir com o que ficou devendo.

    `contrato_do_site` lia so' o VIGENTE. Com o contrato encerrado, devolveria
    `contratado: false` e as cobrancas em aberto sairiam da tela junto - quem
    deve deixaria de ver o que deve.
    """
    contrato = await _em_aviso(db, site)
    await _cobranca_vencida(db, contrato, dias=40, total="149.00", mes=1)
    await platform_service.marcar_vencidas(db)
    await platform_service.encerrar_vencidos(db)

    visao = await platform_service.contrato_do_site(db, site.id)

    assert visao["contratado"] is True
    assert visao["estado"] == "encerrada"
    assert visao["em_atraso"]["cobrancas"] == 1
    assert visao["em_atraso"]["total_brl"] == 149.0


async def test_site_que_nunca_contratou_continua_sem_contrato(db, site):
    visao = await platform_service.contrato_do_site(db, site.id)
    assert visao == {"contratado": False}


async def test_a_tela_ve_o_encerrado_mas_contratar_nao(db, site):
    """As duas leituras respondem perguntas diferentes, e misturar volta o bug.

    `ultimo_do_site` serve a tela; `vigente_do_site` decide se cabe contratar.
    Se `contratar` passasse a usar o primeiro, um contrato encerrado voltaria a
    bloquear o proximo - exatamente o defeito que este trabalho desfez.
    """
    await _em_aviso(db, site)
    await platform_service.encerrar_vencidos(db)

    assert await platform_service.ultimo_do_site(db, site.id) is not None
    assert await platform_service.vigente_do_site(db, site.id) is None


# --------------------------------------- recontratar tambem nao some com a divida


async def _encerrado_devendo(db, site, total="149.00"):
    """Site que encerrou um contrato devendo, e ja' pode assinar outro."""
    contrato = await _em_aviso(db, site)
    await _cobranca_vencida(db, contrato, dias=40, total=total, mes=1)
    await platform_service.marcar_vencidas(db)
    await platform_service.encerrar_vencidos(db)
    return contrato


async def test_recontratar_nao_some_com_a_divida_anterior(db, site):
    """O mesmo defeito de `encerrar`, entrando por outra porta.

    `contrato_do_site` lia as cobrancas do CONTRATO exibido, e `ultimo_do_site`
    devolve o vigente quando ha' um. Entao bastava assinar de novo para a divida
    do contrato anterior sair da tela - quem devia parava de ver o que devia, e
    desta vez sem nem precisar encerrar nada.
    """
    antigo = await _encerrado_devendo(db, site)
    antes = await platform_service.contrato_do_site(db, site.id)
    assert antes["em_atraso"]["total_brl"] == 149.0, "cenario nao montou"

    novo = await platform_service.contratar(db, site.id, "essencial")

    depois = await platform_service.contrato_do_site(db, site.id)
    assert novo.id != antigo.id
    assert depois["em_atraso"]["cobrancas"] == 1
    assert depois["em_atraso"]["total_brl"] == 149.0


async def test_a_cobranca_herdada_aparece_na_lista(db, site):
    """Nao so' o agregado: a LINHA tem de continuar na tela.

    Herda tudo que ficou do contrato anterior - o atraso e a multa de rescisao,
    que `rescindir` emite no mes corrente. As duas sao divida do site, e sumir
    com a multa seria tao errado quanto sumir com o atraso.
    """
    await _encerrado_devendo(db, site)
    await platform_service.contratar(db, site.id, "essencial")

    visao = await platform_service.contrato_do_site(db, site.id)

    herdadas = {c["total_brl"] for c in visao["cobrancas"] if c["contrato_anterior"]}
    assert 149.0 in herdadas, "a cobranca vencida do contrato encerrado sumiu da lista"
    assert 536.4 in herdadas, "a multa de rescisao sumiu junto"


async def test_cobranca_do_contrato_vigente_nao_e_marcada_como_anterior(db, site):
    """O campo tem de SEPARAR, e nao carimbar tudo.

    Marcar toda linha como herdada faria a tela avisar "contrato anterior" na
    cobranca que acabou de ser emitida - ruido no lugar de informacao.
    """
    await _encerrado_devendo(db, site)
    novo = await platform_service.contratar(db, site.id, "essencial")
    await _cobranca_vencida(db, novo, dias=2, total="99.00", mes=3)

    visao = await platform_service.contrato_do_site(db, site.id)

    por_valor = {c["total_brl"]: c["contrato_anterior"] for c in visao["cobrancas"]}
    assert por_valor[99.0] is False
    assert por_valor[149.0] is True


async def test_divida_do_vizinho_nao_entra(db, site, segundo_site):
    """O escopo virou o SITE, e um JOIN mal escrito somaria a rede inteira."""
    await _encerrado_devendo(db, site, total="149.00")
    vizinho = await platform_service.contratar(db, segundo_site.id, "essencial")
    await _cobranca_vencida(db, vizinho, dias=40, total="777.00", mes=1)
    await platform_service.marcar_vencidas(db)

    visao = await platform_service.contrato_do_site(db, site.id)

    assert visao["em_atraso"]["total_brl"] == 149.0
    assert 777.0 not in [c["total_brl"] for c in visao["cobrancas"]]
