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


async def _previsao(db, site, **kwargs):
    dados = dict(
        site_id=site.id,
        competencia=COMPETENCIA,
        gerado_em=datetime.now(UTC),
        kwh_previsto=Decimal("8283.0"),
        kwh_p10=Decimal("5215.0"),
        kwh_p90=Decimal("10005.0"),
        faturamento_previsto_brl=Decimal("11596.20"),
        media_diaria_28d=Decimal("265.0"),
        modelo_aplicavel=True,
        modelo_versao="1.0.0",
        dias_de_historico=713,
        cobertura_declarada_pct=Decimal("80"),
        cobertura_medida_pct=Decimal("80"),
        wape_modelo_pct=Decimal("7.5"),
        wape_baseline_pct=Decimal("10.4"),
    )
    dados.update(kwargs)
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
    await _previsao(db, site, modelo_aplicavel=False, kwh_p10=None, kwh_p90=None)

    saida = await forecast_service.previsao_do_site(db, site.id)
    assert saida["modelo_aplicavel"] is False
    assert saida["kwh_p10"] is None, "banda desenhada em cima de uma media movel"
    assert any("média dos últimos 28 dias" in a["texto"] for a in saida["avisos"])


async def test_faixa_sub_calibrada_e_anunciada(db, site):
    """O caso real medido: 56% de cobertura numa faixa que promete 80%."""
    await _previsao(db, site, cobertura_medida_pct=Decimal("56.5"))

    saida = await forecast_service.previsao_do_site(db, site.id)
    aviso = next(a for a in saida["avisos"] if "estreita" in a["texto"])
    assert "56%" in aviso["texto"]
    assert "80%" in aviso["texto"]


async def test_diferenca_pequena_de_cobertura_nao_vira_alarme(db, site):
    """Backtest de tres meses tem ruido; acusar por um ponto so' geraria alarme."""
    await _previsao(db, site, cobertura_medida_pct=Decimal("77"))

    saida = await forecast_service.previsao_do_site(db, site.id)
    assert not any("estreita" in a["texto"] for a in saida["avisos"])


async def test_modelo_que_perde_da_regua_e_anunciado(db, site):
    """O resultado real do primeiro retreino: 12,36% contra 9,45% da media movel.

    Sem este aviso, a tela apresentaria como base de decisao um numero que erra
    mais que tres linhas de codigo - e o operador contrataria demanda por ele.
    """
    await _previsao(
        db, site, wape_modelo_pct=Decimal("12.36"), wape_baseline_pct=Decimal("9.45")
    )

    saida = await forecast_service.previsao_do_site(db, site.id)
    aviso = next(a for a in saida["avisos"] if "régua" in a["texto"])
    assert "12.4%" in aviso["texto"] or "12.4" in aviso["texto"]
    assert aviso["nivel"] == "alto"


async def test_modelo_que_ganha_da_regua_nao_gera_aviso(db, site):
    await _previsao(db, site, wape_modelo_pct=Decimal("7.5"), wape_baseline_pct=Decimal("10.4"))

    saida = await forecast_service.previsao_do_site(db, site.id)
    assert not any("régua" in a["texto"] for a in saida["avisos"])


# ------------------------------------------------------------------ o banco


async def test_banco_recusa_banda_pela_metade(db, site):
    """Meio intervalo mente sobre a incerteza que o modelo declarou."""
    with pytest.raises(IntegrityError):
        await _previsao(db, site, kwh_p90=None)


async def test_banco_recusa_banda_em_fallback(db, site):
    """Incerteza em volta de uma media movel daria ares de previsao a uma conta."""
    with pytest.raises(IntegrityError):
        await _previsao(db, site, modelo_aplicavel=False)


async def test_banco_recusa_duas_previsoes_da_mesma_competencia(db, site):
    """A previsao vigente de um mes e' uma so'."""
    await _previsao(db, site)
    with pytest.raises(IntegrityError):
        await _previsao(db, site)


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


async def test_rota_nao_vaza_previsao_do_vizinho(
    api, db, segundo_site, como_operador_do_site
):
    await _previsao(db, segundo_site, kwh_previsto=Decimal("777"))

    r = await api.get("/api/v1/power/demand/energy-forecast", headers=como_operador_do_site)
    assert r.status_code == 200
    assert r.json()["disponivel"] is False
