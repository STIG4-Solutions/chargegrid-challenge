"""A regua de ano-a-ano tem nome proprio, e a tela diz qual regua serviu o numero.

POR QUE UMA FONTE NOVA (migracao 0029). Ate aqui havia uma regua mensal so' - a
media movel de 28 dias - e `media_movel` a nomeava. Agora ha' duas, e a nova e' muito
melhor. Medido no banco local com walk-forward de 12 meses, n=84 registros mensais:

    media movel de 28 dias                   13,95%
    mesmo mes um ano antes x crescimento      8,67%

5,3 pontos entre duas coisas que `fonte = 'media_movel'` chamaria pelo mesmo nome.

DOIS DEFEITOS QUE ESTES TESTES PRENDEM, e o segundo e' o pior:

  1. O painel cairia no `?? String(fonte)` e mostraria `ano_a_ano` cru ao operador.
  2. `forecast_service` montava o aviso num `elif fonte == "media_movel"`. Uma linha
     servida pela regua nova nao casava, e saia SEM AVISO NENHUM - a tela deixava de
     dizer que o numero nao veio do modelo. Silencio parece confirmacao, e e' pior
     que um texto errado.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.forecast import SiteForecast
from app.services import forecast_service

COMPETENCIA = date(2026, 10, 1)
BUCKET = datetime(2026, 10, 1, tzinfo=UTC)


async def _previsao(db, site, **campos):
    dados = dict(
        site_id=site.id,
        granularidade="mes",
        bucket_inicio=BUCKET,
        competencia=COMPETENCIA,
        gerado_em=datetime.now(UTC),
        kwh_previsto=Decimal("8283.0"),
        kwh_p10=None,
        kwh_p90=None,
        faturamento_previsto_brl=Decimal("11596.20"),
        media_diaria_28d=Decimal("265.0"),
        modelo_aplicavel=True,
        fonte="ano_a_ano",
        modelo_versao="2.0.0",
        dias_de_historico=1437,
        cobertura_declarada_pct=Decimal("80"),
        cobertura_medida_pct=Decimal("76.2"),
        wape_modelo_pct=Decimal("8.06"),
        wape_baseline_pct=Decimal("8.67"),
    )
    dados.update(campos)
    linha = SiteForecast(**dados)
    db.add(linha)
    await db.flush()
    return linha


async def test_o_banco_aceita_a_fonte_nova(db, site):
    """A migracao 0029 acrescentou `ano_a_ano` ao CHECK `fonte_conhecida`.

    Sem ela o job de previsao falharia na gravacao - depois de treinar, e com a
    tabela metade escrita.
    """
    linha = await _previsao(db, site)
    assert linha.fonte == "ano_a_ano"


async def test_o_banco_continua_recusando_fonte_inventada(db, site):
    """O CHECK nao pode ter sido afrouxado de passagem.

    Ele existe para que um valor novo em `fonte` seja uma DECISAO com migracao, e nao
    um texto qualquer que o job passou a gravar - e a tela promove a modelo, ou nao,
    com base nesse campo.
    """
    with pytest.raises(IntegrityError):
        await _previsao(db, site, fonte="chute_novo")


async def test_a_regua_de_ano_a_ano_gera_aviso(db, site):
    """O defeito 2: a linha saia sem aviso nenhum.

    O `elif` cobria so' `media_movel`. Com a regua nova, o operador via um numero sem
    nada dizendo que ele nao veio do modelo.
    """
    await _previsao(db, site)

    saida = await forecast_service.previsao_do_site(db, site.id)

    assert saida["fonte"] == "ano_a_ano"
    avisos = [a for a in saida["avisos"] if a["nivel"] == "medio"]
    assert avisos, "a regua de ano-a-ano ficou sem aviso"
    texto = avisos[0]["texto"]
    # Nomeia a regua CERTA - e nao "média dos últimos 28 dias", que era o texto
    # unico de antes e seria falso aqui.
    assert "ano anterior" in texto, texto
    assert "28 dias" not in texto, texto
    # E traz os dois numeros, que e' o que deixa o operador julgar a diferenca.
    assert "8.1%" in texto and "8.7%" in texto, texto


async def test_a_media_movel_continua_com_o_texto_dela(db, site):
    """Cobrir a fonte nova nao pode ter trocado o texto da antiga.

    Sao duas contas diferentes: uma olha os ultimos 28 dias, a outra olha o mesmo mes
    do ano anterior. Um texto so' para as duas diria algo falso sobre metade dos
    casos.
    """
    await _previsao(db, site, fonte="media_movel")

    saida = await forecast_service.previsao_do_site(db, site.id)

    texto = next(a["texto"] for a in saida["avisos"] if a["nivel"] == "medio")
    assert "últimos 28 dias" in texto, texto
    assert "ano anterior" not in texto, texto


async def test_historico_curto_vence_a_escolha_da_regua(db, site):
    """Sem historico, o aviso e' ALTO e fala de falta de dado, nao de regua.

    Os dois casos entregam um numero que nao e' do modelo, e juntar os textos faria o
    operador achar que falta dado quando o modelo e' que nao entrega - ou o
    contrario, que e' pior: esperar o modelo melhorar numa praca que so' precisa de
    tempo.
    """
    await _previsao(db, site, modelo_aplicavel=False, fonte="media_movel")

    saida = await forecast_service.previsao_do_site(db, site.id)

    altos = [a for a in saida["avisos"] if a["nivel"] == "alto"]
    assert altos, "falta de historico tem de gerar aviso alto"
    assert "Sem histórico suficiente" in altos[0]["texto"]
    assert not [a for a in saida["avisos"] if a["nivel"] == "medio"], (
        "com historico curto nao se fala de o modelo perder da regua - ele nem correu"
    )


async def test_regua_nao_desenha_faixa(db, site):
    """`banda_com_quantil` nao mudou, e nao deve mudar.

    Os fatores conformes da faixa sao calibrados nos residuos DO MODELO; aplica-los a
    uma regua seria emprestar a incerteza de um previsor para outro.
    """
    with pytest.raises(IntegrityError):
        await _previsao(db, site, kwh_p10=Decimal("7000"), kwh_p90=Decimal("9000"))
