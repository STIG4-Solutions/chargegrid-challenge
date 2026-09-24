"""A leitura da previsao de demanda, e as guardas que a acompanham.

A API nao calcula nada aqui - o job de `apps/forecast` e' que escreve. O que se
testa e' a tradução para a tela, e ela tem uma responsabilidade unica: nao
deixar um numero sair sem a sua incerteza.

Tres avisos, tres perguntas diferentes. Um numero de previsao que perde de uma
media movel, ou uma faixa que cobre 56% quando promete 80%, e' pior que numero
nenhum quando aparece sozinho: parece confiavel.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.forecast import SiteForecast
from app.services import forecast_service

COMPETENCIA = date(2026, 10, 1)
# O inicio do bucket, agora obrigatorio. Na janela mensal ele e' o primeiro
# instante da competencia; nas outras e' o que diz QUAL hora, dia ou semana.
BUCKET = datetime(2026, 10, 1, tzinfo=UTC)


async def _previsao(db, site, **kwargs):
    dados = dict(
        site_id=None if site is None else site.id,
        granularidade="mes",
        bucket_inicio=BUCKET,
        competencia=COMPETENCIA,
        gerado_em=datetime.now(UTC),
        kwh_previsto=Decimal("8283.0"),
        kwh_p10=Decimal("5215.0"),
        kwh_p90=Decimal("10005.0"),
        faturamento_previsto_brl=Decimal("11596.20"),
        media_diaria_28d=Decimal("265.0"),
        modelo_aplicavel=True,
        fonte="modelo",
        modelo_versao="1.0.0",
        dias_de_historico=713,
        cobertura_declarada_pct=Decimal("80"),
        cobertura_medida_pct=Decimal("80"),
        wape_modelo_pct=Decimal("7.5"),
        wape_baseline_pct=Decimal("10.4"),
    )
    dados.update(kwargs)
    # Na janela mensal `bucket_inicio` e `competencia` falam da MESMA coisa, e
    # tem de concordar: um teste que troca so' a competencia esperava duas linhas
    # distintas e ganhava duas iguais, colidindo na chave unica. Quem quiser
    # dissocia-los passa `bucket_inicio` explicito - e' o caso das outras janelas.
    if "bucket_inicio" not in kwargs:
        dados["bucket_inicio"] = datetime.combine(
            dados["competencia"], datetime.min.time(), tzinfo=UTC
        )
    linha = SiteForecast(**dados)
    db.add(linha)
    await db.flush()
    return linha


# --------------------------------------------------------------- disponibilidade


async def test_sem_linha_a_resposta_diz_que_nao_ha_previsao(db, site):
    """Tabela vazia e' estado normal, nao erro.

    A tela precisa distinguir "ainda nao calculamos" de "calculamos e deu zero".
    """
    saida = await forecast_service.previsao_do_site(db, site.id)
    assert saida["disponivel"] is False
    assert "motivo" in saida
    assert "kwh_previsto" not in saida


async def test_com_linha_a_resposta_traz_os_numeros(db, site):
    await _previsao(db, site)
    saida = await forecast_service.previsao_do_site(db, site.id)

    assert saida["disponivel"] is True
    assert saida["kwh_previsto"] == pytest.approx(8283.0)
    assert saida["kwh_p10"] == pytest.approx(5215.0)
    assert saida["competencia"] == "2026-10-01"
    assert saida["avisos"] == [], saida["avisos"]


async def test_a_previsao_mais_recente_vence(db, site):
    await _previsao(db, site, competencia=date(2026, 8, 1), kwh_previsto=Decimal("1"))
    await _previsao(db, site, competencia=COMPETENCIA, kwh_previsto=Decimal("999"))

    saida = await forecast_service.previsao_do_site(db, site.id)
    assert saida["kwh_previsto"] == pytest.approx(999.0)


# --------------------------------------------------------------------- avisos


async def test_fallback_avisa_que_nao_e_previsao(db, site):
    """Media movel de 28 dias nao pode ser apresentada como previsao."""
    await _previsao(
        db, site, modelo_aplicavel=False, fonte="media_movel", kwh_p10=None, kwh_p90=None
    )

    saida = await forecast_service.previsao_do_site(db, site.id)
    assert saida["modelo_aplicavel"] is False
    assert saida["kwh_p10"] is None, "banda desenhada em cima de uma media movel"
    assert any("média dos últimos 28 dias" in a["texto"] for a in saida["avisos"])


async def test_faixa_sub_calibrada_e_anunciada(db, site):
    """O caso real medido: 63% de cobertura numa faixa que promete 80%."""
    await _previsao(db, site, fonte="modelo", cobertura_medida_pct=Decimal("56.5"))

    saida = await forecast_service.previsao_do_site(db, site.id)
    aviso = next(a for a in saida["avisos"] if "estreita" in a["texto"])
    assert "56%" in aviso["texto"]
    assert "80%" in aviso["texto"]


async def test_diferenca_pequena_de_cobertura_nao_vira_alarme(db, site):
    """Backtest de tres meses tem ruido; acusar por um ponto so' geraria alarme."""
    await _previsao(db, site, fonte="modelo", cobertura_medida_pct=Decimal("77"))

    saida = await forecast_service.previsao_do_site(db, site.id)
    assert not any("estreita" in a["texto"] for a in saida["avisos"])


async def test_sem_banda_na_tela_nao_se_avisa_sobre_a_banda(db, site):
    """Aviso sobre algo que o operador nao esta vendo e' ruido.

    E ruido faz o aviso seguinte - o que explica de onde veio o numero - ser
    ignorado junto.
    """
    await _previsao(
        db,
        site,
        fonte="media_movel",
        kwh_p10=None,
        kwh_p90=None,
        cobertura_medida_pct=Decimal("56.5"),
    )

    saida = await forecast_service.previsao_do_site(db, site.id)
    assert not any("estreita" in a["texto"] for a in saida["avisos"])


async def test_modelo_que_perde_da_regua_entrega_a_regua(db, site):
    """O resultado real medido: o modelo perde no mensal, entao nao e' ele que sai.

    Apresentar como previsao um numero que erra mais que uma media movel de tres
    linhas seria pior que nao ter modelo nenhum - o operador contrataria demanda
    por ele. O job grava a regua, e `fonte` diz isso.
    """
    await _previsao(
        db,
        site,
        fonte="media_movel",
        kwh_p10=None,
        kwh_p90=None,
        wape_modelo_pct=Decimal("9.05"),
        wape_baseline_pct=Decimal("7.61"),
    )

    saida = await forecast_service.previsao_do_site(db, site.id)

    assert saida["fonte"] == "media_movel"
    assert saida["modelo_aplicavel"] is True, "o modelo conhece o local; ele e' que perde"
    aviso = next(a for a in saida["avisos"] if "média dos últimos 28 dias" in a["texto"])
    assert "9.1%" in aviso["texto"] and "7.6%" in aviso["texto"]
    # Nivel medio, e nao alto: o numero entregue e' o BOM. O alto fica para
    # quando falta historico, que e' quando nao ha o que oferecer.
    assert aviso["nivel"] == "medio"


async def test_os_dois_fallbacks_dizem_coisas_diferentes(db, site, segundo_site):
    """Mesmo numero, motivos opostos.

    Falta de historico e' "ainda nao da' para prever"; modelo pior que a regua e'
    "da' para prever e a previsao nao ajuda". Juntar os dois faria o operador
    achar que falta dado quando o que falta e' modelo melhor.
    """
    await _previsao(
        db, site, modelo_aplicavel=False, fonte="media_movel", kwh_p10=None, kwh_p90=None
    )
    sem_historico = await forecast_service.previsao_do_site(db, site.id)

    await _previsao(
        db,
        segundo_site,
        fonte="media_movel",
        kwh_p10=None,
        kwh_p90=None,
        wape_modelo_pct=Decimal("9.05"),
        wape_baseline_pct=Decimal("7.61"),
    )
    modelo_pior = await forecast_service.previsao_do_site(db, segundo_site.id)

    assert sem_historico["avisos"][0]["texto"] != modelo_pior["avisos"][0]["texto"]
    assert "Sem histórico" in sem_historico["avisos"][0]["texto"]
    assert "não supera" in modelo_pior["avisos"][0]["texto"]


async def test_modelo_que_ganha_da_regua_e_usado(db, site):
    await _previsao(
        db,
        site,
        fonte="modelo",
        wape_modelo_pct=Decimal("7.5"),
        wape_baseline_pct=Decimal("10.4"),
    )

    saida = await forecast_service.previsao_do_site(db, site.id)
    assert saida["fonte"] == "modelo"
    assert saida["kwh_p10"] is not None, "previsao de verdade vem com banda"
    assert not any("não supera" in a["texto"] for a in saida["avisos"])


# ------------------------------------------------------------------ o banco


async def test_banco_recusa_banda_pela_metade(db, site):
    """Meio intervalo mente sobre a incerteza que o modelo declarou."""
    with pytest.raises(IntegrityError):
        await _previsao(db, site, kwh_p90=None)


async def test_banco_recusa_banda_em_fallback(db, site):
    """Incerteza em volta de uma media movel daria ares de previsao a uma conta."""
    with pytest.raises(IntegrityError):
        await _previsao(db, site, fonte="media_movel")


async def test_banco_recusa_fonte_desconhecida(db, site):
    with pytest.raises(IntegrityError):
        await _previsao(db, site, fonte="chute")


async def test_banco_recusa_duas_previsoes_da_mesma_janela(db, site):
    """A previsao vigente de uma janela e' uma so'.

    Reexecutar o job atualiza a linha; sem esta guarda ele empilharia versoes e
    ninguem saberia qual vale.
    """
    await _previsao(db, site)
    with pytest.raises(IntegrityError):
        await _previsao(db, site)


async def test_janelas_diferentes_da_mesma_praca_convivem(db, site):
    """Cinco janelas por praca e' o ponto inteiro da tabela nova.

    Enquanto a chave era `(site_id, competencia)`, a segunda janela do mesmo mes
    colidia na primeira gravacao.
    """
    await _previsao(db, site, granularidade="mes")
    await _previsao(db, site, granularidade="dia", fonte="media_dow", kwh_p10=None, kwh_p90=None)
    await _previsao(db, site, granularidade="hora", fonte="perfil_hora")
    # Nenhuma das tres levantou: a chave agora inclui a granularidade.


async def test_o_banco_recusa_duas_linhas_da_REDE_na_mesma_janela(db, site):
    """`site_id IS NULL` significa a rede toda - e NULL tem de conflitar com NULL.

    E' o motivo de a chave ser `UNIQUE NULLS NOT DISTINCT`. No padrao do SQL dois
    NULL nunca conflitam, logo esta segunda insercao passaria e cada execucao do
    job empilharia uma versao da previsao da rede.
    """
    await _previsao(db, None)
    with pytest.raises(IntegrityError):
        await _previsao(db, None)


async def test_a_linha_da_rede_nao_colide_com_a_da_praca(db, site):
    """Mesma janela, escopos diferentes: sao duas previsoes legitimas."""
    await _previsao(db, site)
    await _previsao(db, None)


async def test_banco_recusa_granularidade_desconhecida(db, site):
    with pytest.raises(IntegrityError):
        await _previsao(db, site, granularidade="quinzena")


async def test_a_faixa_e_permitida_no_perfil_horario(db, site):
    """Na janela de uma HORA a faixa e' o produto.

    Medido: a melhor regua horaria erra 50,17% na rede e a referencia que usa o
    futuro erra 50,22% - folga de -0,05 ponto. O erro e' ruido de contagem, e o
    numero honesto ali nao e' um ponto. O CHECK antigo exigia `fonte = 'modelo'`
    e proibiria justamente o caso que mais precisa de banda.
    """
    await _previsao(db, site, granularidade="hora", fonte="perfil_hora")


async def test_a_media_por_dia_da_semana_continua_sem_faixa(db, site):
    """Media nao declara quantil. Desenhar incerteza em volta dela seria invencao."""
    with pytest.raises(IntegrityError):
        await _previsao(db, site, fonte="media_dow")


# ------------------------------------------------------- a janela que a rota le'


async def test_a_rota_mensal_ignora_as_outras_janelas(db, site):
    """O defeito latente que a tabela nova criaria, se ninguem filtrasse.

    `previsao_do_site` fazia `order_by(competencia desc, gerado_em desc).limit(1)`
    sem dizer a granularidade. Com cinco janelas gravadas, a linha mais recente e'
    quase sempre uma HORA - e a aba de demanda contratada mostraria o consumo de
    uma hora onde deveria estar o do mes. Sem erro em lugar nenhum.

    Aqui a linha horaria tem competencia POSTERIOR de proposito: sem o filtro ela
    venceria a ordenacao, e o teste morre.
    """
    await _previsao(db, site, granularidade="mes", kwh_previsto=Decimal("8283.0"))
    await _previsao(
        db,
        site,
        granularidade="hora",
        fonte="perfil_hora",
        competencia=date(2026, 11, 1),
        bucket_inicio=datetime(2026, 11, 1, 20, tzinfo=UTC),
        kwh_previsto=Decimal("41.0"),
    )

    saida = await forecast_service.previsao_do_site(db, site.id)
    assert saida["disponivel"] is True
    assert saida["kwh_previsto"] == pytest.approx(8283.0)
    assert saida["competencia"] == "2026-10-01"


async def test_a_rota_da_praca_nao_devolve_a_linha_da_rede(db, site):
    """A previsao da rede e' de administrador, e nao cabe na tela de uma praca.

    `site_id == :id` ja' exclui NULL por definicao do SQL, e este teste existe
    para que isso continue verdadeiro se alguem trocar o filtro por um `in_`.
    """
    await _previsao(db, None, kwh_previsto=Decimal("99999.0"))

    saida = await forecast_service.previsao_do_site(db, site.id)
    assert saida["disponivel"] is False


# ------------------------------------------------------------------- isolamento


async def test_operador_nao_le_a_previsao_do_vizinho(db, site, segundo_site):
    """Previsao de faturamento e' informacao comercial do estabelecimento."""
    await _previsao(db, segundo_site, kwh_previsto=Decimal("777"))

    saida = await forecast_service.previsao_do_site(db, site.id)
    assert saida["disponivel"] is False


async def test_rota_responde_e_respeita_o_papel(
    api, db, site, como_operador_do_site, como_motorista
):
    await _previsao(db, site)

    ok = await api.get("/api/v1/power/demand/energy-forecast", headers=como_operador_do_site)
    assert ok.status_code == 200
    assert ok.json()["disponivel"] is True

    negado = await api.get("/api/v1/power/demand/energy-forecast", headers=como_motorista)
    assert negado.status_code == 403


async def test_rota_nao_vaza_previsao_do_vizinho(api, db, segundo_site, como_operador_do_site):
    await _previsao(db, segundo_site, kwh_previsto=Decimal("777"))

    r = await api.get("/api/v1/power/demand/energy-forecast", headers=como_operador_do_site)
    assert r.status_code == 200
    assert r.json()["disponivel"] is False
