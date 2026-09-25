"""O aviso diz QUE conta produziu o numero, e quanta evidencia ele tem.

DOIS DEFEITOS, e o primeiro e' pior que silencio.

1. O TEXTO DESCREVIA OUTRA CONTA. `_avisos` tinha um ramo para
   `modelo_aplicavel = False` cujo texto era "O valor abaixo e' a media dos ultimos
   28 dias, nao uma previsao". A janela de ANO grava `modelo_aplicavel = False` com
   `fonte = 'tendencia'`, entao ela caia nesse ramo - e o aviso afirmava que
   1.797.490 kWh para 2028 eram uma media de 28 dias, quando sao uma reta esticada.

   Um operador que le "media dos ultimos 28 dias" e ve o salto de 54% entre 2027 e
   2028 conclui que a media esta' subindo, e nao que uma reta foi tracada por dois
   pontos. Silencio ele questionaria; um texto plausivel e errado ele acredita.

2. NAO HAVIA AVISO SOBRE n=2. Quatro anos de historico dao DUAS observacoes anuais
   completas. Uma reta por dois pontos passa exata pelos dois e nao diz nada sobre o
   terceiro - e o numero na tela tinha a mesma cara de um que foi aferido.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from app.models.forecast import SiteForecast
from app.services import forecast_service
from app.services.forecast_service import O_QUE_E, POUCAS_OBSERVACOES

ANO = datetime(2028, 1, 1, tzinfo=UTC)


async def _linha(db, site, **campos):
    dados = dict(
        site_id=site.id,
        granularidade="ano",
        bucket_inicio=ANO,
        competencia=date(2028, 1, 1),
        gerado_em=datetime.now(UTC),
        kwh_previsto=Decimal("1797490.0"),
        kwh_p10=None,
        kwh_p90=None,
        media_diaria_28d=None,
        modelo_aplicavel=False,
        fonte="tendencia",
        modelo_versao="2.0.0",
    )
    dados.update(campos)
    linha = SiteForecast(**dados)
    db.add(linha)
    await db.flush()
    return linha


async def _avisos(db, site, janela: str = "ano", **campos) -> list[dict]:
    """Os avisos da serie daquela janela. A janela tem de ser a MESMA da linha.

    Pedir "ano" tendo gravado uma linha mensal devolve `disponivel: false`, que nem
    tem a chave `avisos` - e o teste falharia por um motivo que nao e' o dele.
    """
    await _linha(db, site, **campos)
    saida = await forecast_service.serie_por_janela(db, janela, site.id)
    assert saida["disponivel"], saida
    return saida["avisos"]


async def test_a_tendencia_nao_e_descrita_como_media_movel():
    """O defeito 1, sem tocar no banco: o mapa nao pode confundir as duas contas."""
    assert O_QUE_E["tendencia"] != O_QUE_E["media_movel"]
    assert "reta" in O_QUE_E["tendencia"]
    assert "28 dias" not in O_QUE_E["tendencia"]


async def test_o_aviso_da_janela_de_ano_fala_de_reta_e_nao_de_media(db, site):
    """O defeito 1 no caminho inteiro, da linha do banco ao texto da resposta."""
    avisos = await _avisos(db, site)
    texto = " ".join(a["texto"] for a in avisos)
    assert "reta" in texto, texto
    assert "28 dias" not in texto, texto


async def test_a_janela_de_ano_declara_que_sao_duas_observacoes(db, site):
    """O defeito 2. Sem isto o numero tem a mesma cara de um que foi aferido."""
    avisos = await _avisos(db, site)
    assert any("duas observações anuais" in a["texto"] for a in avisos), avisos
    # ALTO, e nao medio: aqui nao ha' previsor melhor esperando - a evidencia e' que
    # e' fina, e nenhum retreino conserta isso antes de passar mais um ano.
    assert all(a["nivel"] == "alto" for a in avisos if "duas observações" in a["texto"])


async def test_a_media_movel_continua_com_o_texto_dela(db, site):
    """Nomear a conta nao pode ter trocado o texto de quem ja' estava certo."""
    avisos = await _avisos(db, site, "mes", fonte="media_movel", granularidade="mes")
    texto = " ".join(a["texto"] for a in avisos)
    assert "últimos 28 dias" in texto, texto
    assert "reta" not in texto, texto


async def test_fonte_desconhecida_nao_ganha_a_descricao_de_outra_conta(db, site):
    """Um valor novo em `fonte` tem de aparecer VAGO, nao virar media movel.

    `.get` com um default generico e' o que impede que uma conta nova estreie na tela
    descrita como outra - que e' exatamente o defeito 1 acontecendo de novo.
    """
    assert "chute_novo" not in O_QUE_E
    generico = forecast_service.O_QUE_E.get("chute_novo", "uma conta simples sobre o histórico")
    assert "28 dias" not in generico
    assert "reta" not in generico


async def test_so_a_tendencia_declara_poucas_observacoes():
    """As outras janelas tem centenas de buckets de teste; a de ano tem dois.

    Espalhar o aviso por todas faria o que importa ser ignorado - e' o mesmo motivo
    pelo qual o aviso de cobertura só sai quando há faixa na tela.
    """
    assert set(POUCAS_OBSERVACOES) == {"tendencia"}
