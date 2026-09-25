"""Faixa desenhada cuja cobertura nao foi medida tem de dizer isso.

O CASO, e ele apareceu no ambiente e nao no teste. Disparado o job em staging, o card
saiu com faixa (p10 3.187,5 / p90 4.604,4), `cobertura_declarada_pct = 80,0` e
`cobertura_medida_pct = 81,2` - e o log do backtest dizia
`cobertura_p10_p90_mensal: None`.

As duas coisas conviviam porque sao calibracoes diferentes. Os FATORES da faixa mensal
saem de toda a janela walk-forward (18 meses x 3 pracas = 54 residuos, acima do minimo
de 30); a COBERTURA e' medida com calibracao rolante de 6 meses (6 x 3 = 18, abaixo).
A faixa existe e e' calibrada; a cobertura dela nunca foi medida.

O 81,2 era a cobertura DIARIA, emprestada por um `or` no exportador que nao distinguia
"artefato antigo sem a metrica" de "artefato novo onde ela nao pode ser medida". O card
anunciava cobertura aferida sobre uma faixa que ninguem aferiu, com numero de outro
grao.

Consertado em tres lugares - `exportar.py` para de emprestar, `bandaConfiavel` deixa de
tratar ausencia como aprovacao, e a API passa a AVISAR. Este arquivo prende o terceiro.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from app.models.forecast import SiteForecast
from app.services import forecast_service

COMPETENCIA = date(2026, 10, 1)
BUCKET = datetime(2026, 10, 1, tzinfo=UTC)

SEM_MEDICAO = "não foi medida"


async def _previsao(db, site, **campos):
    dados = dict(
        site_id=site.id,
        granularidade="mes",
        bucket_inicio=BUCKET,
        competencia=COMPETENCIA,
        gerado_em=datetime.now(UTC),
        kwh_previsto=Decimal("3810.35"),
        kwh_p10=Decimal("3187.54"),
        kwh_p90=Decimal("4604.36"),
        media_diaria_28d=Decimal("123.0"),
        modelo_aplicavel=True,
        fonte="modelo",
        modelo_versao="2.0.0",
        cobertura_declarada_pct=Decimal("80"),
        cobertura_medida_pct=None,
        wape_modelo_pct=Decimal("12.25"),
        wape_baseline_pct=Decimal("14.41"),
    )
    dados.update(campos)
    linha = SiteForecast(**dados)
    db.add(linha)
    await db.flush()
    return linha


async def _avisos(db, site, **campos) -> list[dict]:
    await _previsao(db, site, **campos)
    return (await forecast_service.previsao_do_site(db, site.id))["avisos"]


async def test_faixa_sem_cobertura_medida_avisa(db, site):
    """O assert central: faixa presente + cobertura nula -> aviso.

    Sem ele o operador ve' uma faixa que nao se distingue de uma aferida.
    """
    avisos = await _avisos(db, site)
    assert any(SEM_MEDICAO in a["texto"] for a in avisos), avisos


async def test_o_aviso_nao_desqualifica_a_faixa(db, site):
    """Ela E' a melhor estimativa disponivel - o que falta e' a afericao.

    Nivel medio, e nao alto: alto e' para quando nao ha' o que oferecer. E o texto
    diz que a faixa continua valendo, porque dizer so' "nao foi medida" faria o
    operador descartar uma informacao boa.
    """
    aviso = next(a for a in await _avisos(db, site) if SEM_MEDICAO in a["texto"])
    assert aviso["nivel"] == "medio"
    assert "melhor estimativa" in aviso["texto"]


async def test_com_cobertura_medida_nao_avisa(db, site):
    """O caminho normal fica calado.

    Um aviso que aparece sempre e' ruido, e ruido faz o aviso seguinte ser ignorado.
    """
    avisos = await _avisos(db, site, cobertura_medida_pct=Decimal("79.6"))
    assert not any(SEM_MEDICAO in a["texto"] for a in avisos), avisos


async def test_sem_faixa_nao_avisa_sobre_faixa(db, site):
    """Linha servida por regua nao tem faixa, e nao ha' o que aferir.

    Avisar ali sobre cobertura de algo que o operador nao esta' vendo e' ruido - e' o
    mesmo motivo pelo qual o aviso de faixa estreita so' sai quando a faixa aparece.
    """
    avisos = await _avisos(
        db, site, fonte="ano_a_ano", kwh_p10=None, kwh_p90=None, cobertura_medida_pct=None
    )
    assert not any(SEM_MEDICAO in a["texto"] for a in avisos), avisos


async def test_faixa_estreita_continua_avisando(db, site):
    """O aviso novo nao pode ter substituido o antigo.

    Sao dois casos diferentes: cobertura MEDIDA e abaixo do declarado, e cobertura nao
    medida. Cada um pede um texto, e o segundo nao cobre o primeiro.
    """
    avisos = await _avisos(db, site, cobertura_medida_pct=Decimal("60.5"))
    assert any("mais estreita do que deveria" in a["texto"] for a in avisos), avisos
    assert not any(SEM_MEDICAO in a["texto"] for a in avisos), avisos
