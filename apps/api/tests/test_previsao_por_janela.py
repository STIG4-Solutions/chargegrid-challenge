"""A leitura da previsao em SERIE, por janela e por escopo.

A rota mensal responde um numero; estas respondem a curva. O que se testa aqui e'
o que separa as duas leituras e o que nao pode vazar entre elas:

1. `site_id IS NULL` significa A REDE, e nao pode vazar para a serie de uma praca
   nem o contrario. (Nota: o SQLAlchemy traduz `== None` para `IS NULL` sozinho -
   uma versao anterior deste arquivo afirmava que nao, e uma mutacao provou o
   contrario ao sobreviver.)
2. A serie sai em ordem CRESCENTE no tempo. Ao contrario da rota mensal, que quer
   a linha mais recente, uma serie de tras para frente nao e' grafico.
3. A rede e' de ADMINISTRADOR. Um total de rede com poucas pracas permite inferir
   o movimento das outras - com duas, por subtracao exata.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.forecast import SiteForecast
from app.services import forecast_service

INICIO = datetime(2026, 10, 1, tzinfo=UTC)
ROTA_SERIE = "/api/v1/power/demand/energy-forecast/series"
ROTA_REDE = "/api/v1/power/demand/energy-forecast/network"


async def _linha(db, site, janela="hora", passo=0, kwh="10.0", **kwargs):
    """Um bucket. `site=None` grava a linha da REDE."""
    delta = {
        "hora": timedelta(hours=passo),
        "dia": timedelta(days=passo),
        "semana": timedelta(weeks=passo),
        "mes": timedelta(days=31 * passo),
        "ano": timedelta(days=366 * passo),
    }[janela]
    bucket = INICIO + delta
    dados = dict(
        site_id=None if site is None else site.id,
        granularidade=janela,
        bucket_inicio=bucket,
        competencia=bucket.date().replace(day=1),
        gerado_em=datetime.now(UTC),
        kwh_previsto=Decimal(kwh),
        modelo_aplicavel=True,
        fonte="perfil_hora",
        kwh_p10=Decimal("5.0"),
        kwh_p90=Decimal("18.0"),
        modelo_versao="1.0.0",
        cobertura_declarada_pct=Decimal("80"),
        cobertura_medida_pct=Decimal("79"),
    )
    dados.update(kwargs)
    linha = SiteForecast(**dados)
    db.add(linha)
    await db.flush()
    return linha


# ------------------------------------------------------------ disponibilidade


async def test_sem_linha_a_serie_diz_que_nao_ha(db, site):
    """Tabela vazia e' estado normal. E a resposta diz de QUAL janela falta."""
    saida = await forecast_service.serie_por_janela(db, "hora", site.id)
    assert saida["disponivel"] is False
    assert saida["janela"] == "hora"
    assert saida["escopo"] == "praca"
    assert "buckets" not in saida


async def test_janela_desconhecida_e_recusada_no_servico(db, site):
    with pytest.raises(ValueError, match="janela desconhecida"):
        await forecast_service.serie_por_janela(db, "quinzena", site.id)


# --------------------------------------------------------- a serie, e a ordem


async def test_a_serie_sai_em_ordem_crescente_no_tempo(db, site):
    """Gravadas fora de ordem de proposito: quem ordena e' a consulta.

    Uma serie desenhada de tras para frente nao e' grafico, e o job nao promete
    ordem de insercao nenhuma.
    """
    for passo in (5, 0, 3, 1):
        await _linha(db, site, passo=passo, kwh=str(100 + passo))

    saida = await forecast_service.serie_por_janela(db, "hora", site.id)
    assert saida["disponivel"] is True
    horas = [b["bucket_inicio"] for b in saida["buckets"]]
    assert horas == sorted(horas)
    assert saida["buckets"][0]["kwh_previsto"] == pytest.approx(100.0)


async def test_a_serie_respeita_o_limite_pedido(db, site):
    for passo in range(6):
        await _linha(db, site, passo=passo)

    saida = await forecast_service.serie_por_janela(db, "hora", site.id, quantos=2)
    assert len(saida["buckets"]) == 2


async def test_o_limite_nao_passa_do_teto_da_janela(db, site):
    """Pedir 10 anos de janela mensal nao pode virar uma resposta de 120 linhas.

    O teto e' por janela: 48 horas sao dois dias de curva, 12 meses sao um ano de
    planejamento, e devolver 48 anos nao faria sentido.
    """
    teto = forecast_service.BUCKETS_MAXIMO["ano"]
    # MAIS linhas que o teto, senao o corte nao e' exercitado: com tres linhas
    # gravadas, pedir 999 devolve tres com ou sem o teto, e a mutacao que remove
    # o corte sobrevive. Foi o que aconteceu na primeira versao deste teste.
    for passo in range(teto + 2):
        await _linha(db, site, janela="ano", passo=passo)

    saida = await forecast_service.serie_por_janela(db, "ano", site.id, quantos=999)
    assert len(saida["buckets"]) == teto


async def test_cada_janela_le_so_as_linhas_dela(db, site):
    """Hora e mes na mesma praca: a serie de uma nao traz a outra."""
    await _linha(db, site, janela="hora", kwh="7.0")
    await _linha(db, site, janela="mes", kwh="5000.0", fonte="modelo")

    hora = await forecast_service.serie_por_janela(db, "hora", site.id)
    mes = await forecast_service.serie_por_janela(db, "mes", site.id)
    assert [b["kwh_previsto"] for b in hora["buckets"]] == [pytest.approx(7.0)]
    assert [b["kwh_previsto"] for b in mes["buckets"]] == [pytest.approx(5000.0)]


# ------------------------------------------------------------------- a rede


async def test_a_rede_e_lida_pelo_escopo_nulo(db, site):
    """`site_id IS NULL` e' o escopo da rede, e a resposta o declara.

    Este docstring ja' afirmou que `== None` no SQLAlchemy nao casaria com NULL.
    Nao e' verdade - ele traduz para `IS NULL` sozinho, e uma mutacao que trocava
    uma forma pela outra sobreviveu justamente por isso. `is_(None)` fica por
    clareza e pelo linter, nao por correcao.
    """
    await _linha(db, None, kwh="900.0")

    saida = await forecast_service.serie_por_janela(db, "hora", None)
    assert saida["disponivel"] is True
    assert saida["escopo"] == "rede"
    assert saida["buckets"][0]["kwh_previsto"] == pytest.approx(900.0)


async def test_a_serie_da_praca_nao_traz_a_linha_da_rede(db, site):
    await _linha(db, None, kwh="900.0")

    saida = await forecast_service.serie_por_janela(db, "hora", site.id)
    assert saida["disponivel"] is False


async def test_a_serie_da_rede_nao_traz_a_linha_da_praca(db, site):
    await _linha(db, site, kwh="7.0")

    saida = await forecast_service.serie_por_janela(db, "hora", None)
    assert saida["disponivel"] is False


async def test_a_serie_de_uma_praca_nao_traz_a_do_vizinho(db, site, segundo_site):
    await _linha(db, segundo_site, kwh="777.0")

    saida = await forecast_service.serie_por_janela(db, "hora", site.id)
    assert saida["disponivel"] is False


# ----------------------------------------------------------------- as rotas


async def test_a_rota_de_serie_responde_e_respeita_o_papel(
    db, site, como_operador_do_site, como_motorista, api
):
    await _linha(db, site)

    ok = await api.get(f"{ROTA_SERIE}?janela=hora", headers=como_operador_do_site)
    assert ok.status_code == 200
    assert ok.json()["disponivel"] is True

    negado = await api.get(ROTA_SERIE, headers=como_motorista)
    assert negado.status_code == 403


async def test_a_rota_de_serie_recusa_janela_invalida(db, site, como_operador_do_site, api):
    """A validacao e' do FastAPI, pelo `pattern` - 422, nao 500."""
    r = await api.get(f"{ROTA_SERIE}?janela=quinzena", headers=como_operador_do_site)
    assert r.status_code == 422


async def test_a_rota_da_rede_e_so_de_administrador(
    db, site, como_admin, como_operador_do_site, api
):
    """Operador ve' a praca dele, nao o total da rede.

    Com poucas pracas, um total de rede permite inferir o movimento das outras -
    com duas, por subtracao exata.
    """
    await _linha(db, None, kwh="900.0")

    ok = await api.get(f"{ROTA_REDE}?janela=hora", headers=como_admin)
    assert ok.status_code == 200
    assert ok.json()["escopo"] == "rede"

    negado = await api.get(f"{ROTA_REDE}?janela=hora", headers=como_operador_do_site)
    assert negado.status_code == 403


async def test_a_rota_mensal_antiga_nao_mudou(db, site, como_operador_do_site, api):
    """A aba de demanda contratada continua recebendo o formato plano.

    Este commit acrescenta janelas; nao muda a resposta que a tela ja' consome.
    """
    await _linha(
        db,
        site,
        janela="mes",
        kwh="8283.0",
        fonte="modelo",
        media_diaria_28d=Decimal("265.0"),
    )

    r = await api.get("/api/v1/power/demand/energy-forecast", headers=como_operador_do_site)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["disponivel"] is True
    assert corpo["kwh_previsto"] == pytest.approx(8283.0)
    # Formato PLANO, sem `buckets`: e' o contrato que a tela ja' consome.
    assert "buckets" not in corpo
    assert "competencia" in corpo
