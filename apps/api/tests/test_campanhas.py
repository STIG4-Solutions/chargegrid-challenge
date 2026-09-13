"""Campanhas, missoes e progresso.

O que se guarda aqui e' a elegibilidade e a contagem. Quem paga, por quanto
tempo e sobre quais sessoes - errar qualquer um dos tres faz o operador pagar
por comportamento que ele nao pediu, ou o motorista cumprir missao que ninguem
prometeu.

A concessao do dinheiro fica em `test_recompensas.py`: aqui nada e' creditado.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.campaign import Campaign, Mission, MissionProgress
from app.models.enums import AuthMethod, SessionState, StopReason
from app.models.fleet import Fleet
from app.models.session import ChargingSession
from app.services import billing_service, campaign_service, session_service

AGORA = datetime.now(UTC)


async def _sessao_faturada(db, ponto, motorista, *, energia=10.0, verde=0.0):
    sessao = await session_service.authorize(
        db, ponto, user=motorista, auth_method=AuthMethod.OPERATOR
    )
    await session_service.start(db, sessao, ponto)
    sessao.energy_kwh = energia
    sessao.green_energy_kwh = verde
    sessao.duration_s = 3600
    sessao.state = SessionState.FINISHED
    sessao.stop_reason = StopReason.REMOTE
    await db.flush()
    return await billing_service.bill_session(db, sessao)


async def _campanha(db, **kwargs):
    dados = dict(
        patrocinador="rede",
        nome="Setembro Verde",
        starts_at=AGORA - timedelta(days=7),
        ends_at=AGORA + timedelta(days=7),
        ativa=True,
        beneficio_tipo="cashback_fixo",
        beneficio_valor=Decimal("5"),
        orcamento_brl=Decimal("1000"),
    )
    dados.update(kwargs)
    campanha = Campaign(**dados)
    db.add(campanha)
    await db.flush()
    return campanha


async def _missao(db, campanha, **kwargs):
    dados = dict(
        campaign_id=campanha.id,
        codigo="tres-recargas",
        titulo="Recarregue 3 vezes",
        metrica="sessoes",
        alvo=Decimal("3"),
        janela="campanha",
    )
    dados.update(kwargs)
    missao = Mission(**dados)
    db.add(missao)
    await db.flush()
    await db.refresh(campanha)
    return missao


async def _progresso(db, missao, motorista) -> MissionProgress | None:
    """Le o progresso do banco, ignorando o que ja esta em memoria.

    `populate_existing` nao e' enfeite. A sessao roda com `expire_on_commit=False`
    - em producao tambem -, entao um SELECT que reencontre um objeto ja carregado
    devolve a INSTANCIA CACHEADA, com o valor de antes. O progresso e' atualizado
    por `INSERT ... ON CONFLICT`, que escreve direto na tabela sem passar pelo
    ORM: sem isto o teste leria 1 onde o banco tem 2, e acusaria um defeito que
    nao existe.
    """
    return (
        await db.execute(
            select(MissionProgress)
            .where(
                MissionProgress.mission_id == missao.id,
                MissionProgress.user_id == motorista.id,
            )
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


# --------------------------------------------------------------- elegibilidade


async def test_campanha_de_site_so_conta_sessao_daquele_site(
    db, ponto, motorista, tarifa, segundo_site
):
    """Quem paga e' o estabelecimento; ele nao banca recarga feita no vizinho."""
    campanha = await _campanha(db, patrocinador="site", site_id=segundo_site.id)
    missao = await _missao(db, campanha)

    await _sessao_faturada(db, ponto, motorista)

    # A sessao aconteceu no site do fixture `ponto`, nao no `segundo_site`.
    assert await _progresso(db, missao, motorista) is None


async def test_campanha_de_rede_conta_qualquer_site(db, ponto, motorista, tarifa):
    campanha = await _campanha(db, patrocinador="rede")
    missao = await _missao(db, campanha)

    await _sessao_faturada(db, ponto, motorista)

    progresso = await _progresso(db, missao, motorista)
    assert progresso is not None
    assert float(progresso.valor) == 1.0


async def test_campanha_encerrada_nao_conta(db, ponto, motorista, tarifa):
    """Vigencia e' periodo, nao intencao: fora dela a campanha nao existe."""
    campanha = await _campanha(
        db, starts_at=AGORA - timedelta(days=30), ends_at=AGORA - timedelta(days=1)
    )
    missao = await _missao(db, campanha)

    await _sessao_faturada(db, ponto, motorista)

    assert await _progresso(db, missao, motorista) is None


async def test_campanha_inativa_nao_conta(db, ponto, motorista, tarifa):
    campanha = await _campanha(db, ativa=False)
    missao = await _missao(db, campanha)

    await _sessao_faturada(db, ponto, motorista)

    assert await _progresso(db, missao, motorista) is None


async def test_sessao_sem_dono_nao_gera_progresso(db, ponto, tarifa):
    """Recarga avulsa por RFID nao tem a quem creditar nada."""
    campanha = await _campanha(db)
    await _missao(db, campanha)

    sessao = await session_service.authorize(db, ponto, user=None, auth_method=AuthMethod.RFID)
    await session_service.start(db, sessao, ponto)
    sessao.energy_kwh = 10.0
    sessao.state = SessionState.FINISHED
    sessao.stop_reason = StopReason.REMOTE
    await db.flush()
    await billing_service.bill_session(db, sessao)

    linhas = (await db.execute(select(MissionProgress))).scalars().all()
    assert linhas == []


# ------------------------------------------------------------------- contagem


async def test_progresso_acumula_ate_o_alvo_e_conclui(db, ponto, motorista, tarifa):
    campanha = await _campanha(db)
    missao = await _missao(db, campanha, alvo=Decimal("3"))

    for esperado in (1.0, 2.0):
        await _sessao_faturada(db, ponto, motorista)
        progresso = await _progresso(db, missao, motorista)
        assert float(progresso.valor) == esperado
        assert progresso.concluida_em is None, "concluiu antes do alvo"

    await _sessao_faturada(db, ponto, motorista)
    progresso = await _progresso(db, missao, motorista)
    assert float(progresso.valor) == 3.0
    assert progresso.concluida_em is not None


async def test_faturar_a_mesma_sessao_duas_vezes_nao_dobra_o_progresso(
    db, ponto, motorista, tarifa
):
    """O progresso herda a idempotencia do faturamento - e nao depende dela.

    `bill_session` devolve a fatura existente sem reprocessar, entao a segunda
    chamada nem chega aqui. Mas o valor gravado e' ABSOLUTO, recalculado por
    consulta: mesmo que chegasse, a contagem seria a mesma. Sao duas protecoes,
    e este teste guarda a segunda.
    """
    campanha = await _campanha(db)
    missao = await _missao(db, campanha, alvo=Decimal("10"))

    fatura = await _sessao_faturada(db, ponto, motorista)
    sessao = (
        await db.execute(select(ChargingSession).where(ChargingSession.id == fatura.session_id))
    ).scalar_one()

    await billing_service.bill_session(db, sessao)
    await campaign_service.atualizar_progresso(db, sessao)

    progresso = await _progresso(db, missao, motorista)
    assert float(progresso.valor) == 1.0


async def test_energia_verde_conta_so_a_parcela_solar(db, ponto, motorista, tarifa):
    """A missao de energia limpa nao pode premiar recarga de madrugada."""
    campanha = await _campanha(db)
    missao = await _missao(
        db, campanha, codigo="verde", metrica="energia_verde_kwh", alvo=Decimal("5")
    )

    await _sessao_faturada(db, ponto, motorista, energia=20.0, verde=6.0)

    progresso = await _progresso(db, missao, motorista)
    assert float(progresso.valor) == pytest.approx(6.0)
    assert progresso.concluida_em is not None


async def test_conclusao_sobrevive_ao_alvo_subir(db, ponto, motorista, tarifa):
    """Conquista e' fato consumado.

    Se o operador subir o alvo depois que alguem cumpriu, o valor recalculado cai
    abaixo do novo alvo. Zerar a marca ali retiraria do motorista uma conclusao
    que o app ja comemorou - e que talvez ja tenha virado dinheiro.
    """
    campanha = await _campanha(db)
    missao = await _missao(db, campanha, alvo=Decimal("1"))

    await _sessao_faturada(db, ponto, motorista)
    progresso = await _progresso(db, missao, motorista)
    fechada_em = progresso.concluida_em
    assert fechada_em is not None

    missao.alvo = Decimal("99")
    await db.flush()
    await _sessao_faturada(db, ponto, motorista)

    await db.refresh(progresso)
    assert progresso.concluida_em == fechada_em, "a conclusao foi retirada"
    assert float(progresso.valor) == 2.0


async def test_campanha_de_desconto_nao_cria_missao_de_progresso(db, ponto, motorista, tarifa):
    """Desconto age na fatura, na hora. Nao ha o que acumular."""
    campanha = await _campanha(db, beneficio_tipo="desconto_pct", beneficio_valor=Decimal("10"))
    missao = await _missao(db, campanha)

    await _sessao_faturada(db, ponto, motorista)

    assert await _progresso(db, missao, motorista) is None


# -------------------------------------------------------- desconto na fatura


async def test_desconto_de_campanha_chega_na_fatura(db, ponto, motorista, tarifa):
    """O gancho que existia desde a primeira migration e nunca teve produtor."""
    await _campanha(db, beneficio_tipo="desconto_pct", beneficio_valor=Decimal("10"))

    fatura = await _sessao_faturada(db, ponto, motorista, energia=10.0)

    assert float(fatura.discount) > 0
    assert float(fatura.subtotal) - float(fatura.discount) == pytest.approx(float(fatura.total))
    assert any(linha.kind == "desconto" for linha in fatura.lines)


async def test_campanha_sem_orcamento_nao_desconta(db, ponto, motorista, tarifa):
    """Orcamento e' teto duro: gastar alem dele compromete dinheiro nao autorizado."""
    await _campanha(
        db,
        beneficio_tipo="desconto_pct",
        beneficio_valor=Decimal("10"),
        orcamento_brl=Decimal("100"),
        consumido_brl=Decimal("100"),
    )

    fatura = await _sessao_faturada(db, ponto, motorista)

    assert float(fatura.discount) == 0.0


async def test_entre_duas_campanhas_vence_a_melhor_para_o_motorista(db, ponto, motorista, tarifa):
    """Ele nao escolhe, entao a escolha e' a favor dele."""
    await _campanha(db, nome="Fraca", beneficio_tipo="desconto_pct", beneficio_valor=Decimal("5"))
    await _campanha(db, nome="Forte", beneficio_tipo="desconto_pct", beneficio_valor=Decimal("25"))

    fatura = await _sessao_faturada(db, ponto, motorista, energia=10.0)

    linha = next(x for x in fatura.lines if x.kind == "desconto")
    assert "Forte" in linha.description


# ------------------------------------------------------------------- frota
#
# A decisao de escopo resolvida na migration 0024: `patrocinador = 'frota'`
# SAIU, e `fleet_id` virou ELEGIBILIDADE.
#
# O motivo estava no proprio modelo: `patrocinador` nunca foi quem paga. O bolso
# e' determinado pelo TIPO DE BENEFICIO - desconto sai do estabelecimento,
# cashback sai da rede - e nao ha um terceiro. `frota` como patrocinador era um
# valor sem mecanismo atras: o schema aceitava, a validacao recusava com 422 e a
# consulta de elegibilidade filtrava fora. Inalcancavel pelos tres lados.
#
# Sobrou o que nao precisa de bolso nenhum: campanha que vale so' para os
# motoristas de uma frota, paga por quem sempre pagou.


async def _frota(db, nome="Logistica Teste") -> Fleet:
    frota = Fleet(name=nome, document="12345678000190", billing_email="fin@teste.com")
    db.add(frota)
    await db.flush()
    return frota


async def test_banco_recusa_patrocinador_frota(db):
    """O valor saiu do CHECK, e nao so' da validacao em Python.

    Dois CHECKs barram, e o teste de mutacao mostrou isso: reverter so' o
    `patrocinador` nao basta, porque `escopo_coerente` tambem nao tem ramo para
    `frota`. Defesa em profundidade de graca - as duas regras precisam voltar
    juntas para o valor existir de novo, e ai este teste quebra.
    """
    db.add(
        Campaign(
            patrocinador="frota",
            nome="Corporativa",
            starts_at=AGORA,
            ends_at=AGORA + timedelta(days=10),
            beneficio_tipo="cashback_fixo",
            beneficio_valor=Decimal("5"),
        )
    )
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


async def test_campanha_de_frota_conta_para_quem_e_da_frota(db, ponto, motorista, tarifa):
    frota = await _frota(db)
    motorista.fleet_id = frota.id
    await db.flush()
    campanha = await _campanha(db, fleet_id=frota.id)
    missao = await _missao(db, campanha)

    await _sessao_faturada(db, ponto, motorista)

    assert await _progresso(db, missao, motorista) is not None


async def test_campanha_de_frota_nao_conta_para_quem_nao_e(db, ponto, motorista, tarifa):
    """O ponto todo da elegibilidade. Sem isto seria campanha de rede."""
    frota = await _frota(db)
    campanha = await _campanha(db, fleet_id=frota.id)
    missao = await _missao(db, campanha)

    await _sessao_faturada(db, ponto, motorista)

    assert await _progresso(db, missao, motorista) is None


async def test_campanha_de_frota_nao_conta_para_outra_frota(db, ponto, motorista, tarifa):
    dona = await _frota(db, "Dona")
    outra = await _frota(db, "Outra")
    motorista.fleet_id = outra.id
    await db.flush()
    campanha = await _campanha(db, fleet_id=dona.id)
    missao = await _missao(db, campanha)

    await _sessao_faturada(db, ponto, motorista)

    assert await _progresso(db, missao, motorista) is None


async def test_campanha_sem_frota_conta_para_quem_tem_frota(db, ponto, motorista, tarifa):
    """`fleet_id` nulo nao exclui ninguem - inclusive quem pertence a uma frota."""
    frota = await _frota(db)
    motorista.fleet_id = frota.id
    await db.flush()
    campanha = await _campanha(db, fleet_id=None)
    missao = await _missao(db, campanha)

    await _sessao_faturada(db, ponto, motorista)

    assert await _progresso(db, missao, motorista) is not None


async def test_frota_combina_com_patrocinio_de_site(db, ponto, motorista, tarifa, site):
    """Um posto pode dirigir campanha a frota da empresa vizinha.

    E' o caso que o CHECK antigo proibia: `patrocinador='frota'` exigia
    `site_id IS NULL`, entao uma praca nao tinha como dirigir campanha a uma
    frota. Separar patrocinio de elegibilidade libera a combinacao.
    """
    frota = await _frota(db)
    motorista.fleet_id = frota.id
    await db.flush()
    campanha = await _campanha(db, patrocinador="site", site_id=site.id, fleet_id=frota.id)
    missao = await _missao(db, campanha)

    await _sessao_faturada(db, ponto, motorista)

    assert await _progresso(db, missao, motorista) is not None


async def test_a_tela_do_app_segue_a_mesma_regra(db, motorista):
    """A lista e a pontuacao nao podem discordar.

    Uma missao listada no app que nao pontua ao recarregar e' pior que nao
    lista-la: o motorista cumpre e nao ganha. Sao duas consultas diferentes, em
    funcoes diferentes, e e' por isso que este teste existe.
    """
    frota = await _frota(db)
    campanha = await _campanha(db, fleet_id=frota.id)
    await _missao(db, campanha)

    assert await campaign_service.missoes_do_motorista(db, motorista) == []

    motorista.fleet_id = frota.id
    await db.flush()
    assert len(await campaign_service.missoes_do_motorista(db, motorista)) == 1


async def test_apagar_a_frota_leva_a_campanha_junto(db):
    """CASCADE, e nao SET NULL: deixar a campanha viva sem frota a
    transformaria, em silencio, numa campanha para todo mundo - o oposto do que
    quem a criou pediu."""
    frota = await _frota(db)
    campanha = await _campanha(db, fleet_id=frota.id)

    await db.delete(frota)
    await db.flush()

    sobrou = (
        await db.execute(select(Campaign).where(Campaign.id == campanha.id))
    ).scalar_one_or_none()
    assert sobrou is None


# ------------------------------------------------ o seletor do formulario


async def test_rota_de_frotas_devolve_id_e_nome(api, como_operador, db):
    frota = await _frota(db, "Logistica ABC")

    r = await api.get("/api/v1/campaigns/fleets", headers=como_operador)

    assert r.status_code == 200, r.text
    linha = next(f for f in r.json() if f["id"] == str(frota.id))
    assert linha == {"id": str(frota.id), "nome": "Logistica ABC"}


async def test_rota_de_frotas_nao_vaza_cnpj_nem_email(api, como_operador, db):
    """`Fleet` tem CNPJ e e-mail de cobranca, e o operador nao precisa de
    nenhum dos dois para dirigir uma campanha - sao dados comerciais de uma
    empresa que nao e' cliente dele."""
    await _frota(db, "Logistica ABC")

    corpo = (await api.get("/api/v1/campaigns/fleets", headers=como_operador)).text

    assert "12345678000190" not in corpo
    assert "fin@teste.com" not in corpo


async def test_frota_inativa_nao_aparece_no_seletor(api, como_operador, db):
    """Oferecer frota desativada e' oferecer campanha que nasce sem publico."""
    ativa = await _frota(db, "Ativa")
    inativa = await _frota(db, "Inativa")
    inativa.active = False
    await db.flush()

    r = await api.get("/api/v1/campaigns/fleets", headers=como_operador)
    ids = {f["id"] for f in r.json()}

    assert str(ativa.id) in ids
    assert str(inativa.id) not in ids


async def test_frotas_saem_em_ordem_alfabetica(api, como_operador, db):
    """A lista vira `<option>` numa ordem que o operador tem de varrer com o
    olho. Ordem de insercao no banco nao ajuda ninguem."""
    await _frota(db, "Zeta Transportes")
    await _frota(db, "Alfa Logistica")

    r = await api.get("/api/v1/campaigns/fleets", headers=como_operador)
    nomes = [f["nome"] for f in r.json()]

    assert nomes == sorted(nomes)


async def test_motorista_nao_lista_frotas(api, como_motorista):
    r = await api.get("/api/v1/campaigns/fleets", headers=como_motorista)
    assert r.status_code == 403


async def test_a_rota_de_frotas_nao_engoliu_a_de_campanhas(api, como_operador_do_site):
    """`/campaigns/fleets` e `/campaigns/{id}/...` convivem no mesmo prefixo.

    Hoje nao ha `GET /campaigns/{id}`, entao nao ha colisao - mas o dia em que
    houver, `fleets` precisa continuar sendo tratada como rota, e nao como um
    id malformado. Declarar antes e' o que garante isso.

    Usa o operador COM site: `GET /campaigns` depende de `ScopedSiteId`, e o
    operador sem praca toma 404 por falta de escopo - o que nao tem nada a ver
    com a pergunta deste teste.
    """
    r = await api.get("/api/v1/campaigns", headers=como_operador_do_site)
    assert r.status_code == 200, r.text
    r = await api.get("/api/v1/campaigns/fleets", headers=como_operador_do_site)
    assert r.status_code == 200, r.text
