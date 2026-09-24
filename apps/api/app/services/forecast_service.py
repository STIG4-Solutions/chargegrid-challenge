"""Leitura da previsao de demanda. A API nunca a calcula.

Quem calcula e' `apps/forecast`, um job que roda fora deste processo. Aqui so' se
le a linha mais recente e se traduz para a tela - incluindo as guardas de
honestidade, que sao a parte que nao pode ser esquecida.

DE ONDE VEIO O NUMERO. `kwh_previsto` tem duas origens possiveis, e `fonte` diz
qual. O job so' usa o modelo quando ele MEDE melhor que a media movel de 28 dias
no backtest; caso contrario grava a propria media movel. Nao e' desistir do
modelo - quando ele passar a ganhar, o backtest inverte a escolha sozinho.

Isso produz tres estados, e o aviso muda em cada um:

  aplicavel=False, fonte=media_movel  -> historico curto demais para o modelo
  aplicavel=True,  fonte=media_movel  -> o modelo conhece o local e perde da regua
  aplicavel=True,  fonte=modelo       -> previsao de verdade, com banda

Os dois primeiros entregam o MESMO numero por motivos diferentes, e juntar os
dois faria o operador achar que falta dado quando o que falta e' modelo melhor.

A faixa p10-p90 tem aviso proprio: ela cobre menos do que promete, e tratar os
extremos como piores casos e' otimismo.

Nada disso e' escondido. O projeto ja faz isso em `demand_service`
(`confiavel`) e em `maintenance_service` (`so_humano`), e pela mesma razao: um
numero sem a sua incerteza e' pior que numero nenhum, porque parece confiavel.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.forecast import SiteForecast

# Quanto a faixa p10-p90 promete conter. E' a definicao dos quantis, nao opiniao.
COBERTURA_ESPERADA = Decimal("80")

# Folga antes de acusar sub-calibracao. Backtest de tres meses tem ruido de
# amostragem; acusar por um ponto de diferenca so' geraria alarme.
TOLERANCIA_DE_COBERTURA = Decimal("5")


def _float(valor) -> float | None:
    return None if valor is None else float(valor)


def _avisos(linha: SiteForecast) -> list[dict]:
    """O que o operador precisa saber antes de usar este numero."""
    avisos: list[dict] = []

    # Tres casos, tres textos. O numero pode ser o mesmo - a media movel - por
    # dois motivos completamente diferentes, e juntar os dois faria o operador
    # achar que falta dado quando na verdade o modelo e' que nao entrega.
    if not linha.modelo_aplicavel:
        avisos.append(
            {
                "nivel": "alto",
                "texto": (
                    "Sem histórico suficiente para o modelo neste ponto. O valor "
                    "abaixo é a média dos últimos 28 dias, não uma previsão."
                ),
            }
        )
    elif linha.fonte == "media_movel":
        modelo, regua = linha.wape_modelo_pct, linha.wape_baseline_pct
        detalhe = ""
        if modelo is not None and regua is not None:
            detalhe = f" — ele erra {float(modelo):.1f}% contra {float(regua):.1f}% dela"
        avisos.append(
            {
                "nivel": "medio",
                "texto": (
                    "Este número é a média dos últimos 28 dias. O modelo existe e "
                    f"conhece este ponto, mas não supera essa régua no teste{detalhe}. "
                    "Ele volta sozinho quando passar a acertar mais."
                ),
            }
        )

    # So' quando ha faixa NA TELA. Com `fonte = media_movel` nao se desenha
    # banda nenhuma, e avisar sobre a calibracao de algo que o operador nao esta
    # vendo e' ruido - e ruido faz o aviso seguinte, que importa, ser ignorado.
    medida, declarada = linha.cobertura_medida_pct, linha.cobertura_declarada_pct
    if linha.fonte == "modelo" and medida is not None and declarada is not None:
        if Decimal(str(medida)) < Decimal(str(declarada)) - TOLERANCIA_DE_COBERTURA:
            avisos.append(
                {
                    "nivel": "medio",
                    "texto": (
                        f"A faixa é mais estreita do que deveria: no teste ela conteve "
                        f"o valor real em {float(medida):.0f}% dos casos, e não nos "
                        f"{float(declarada):.0f}% que promete. Trate os extremos como otimistas."
                    ),
                }
            )

    return avisos


async def previsao_do_site(db: AsyncSession, site_id: uuid.UUID) -> dict:
    """A previsao mais recente deste site, ou a declaracao de que nao ha.

    `disponivel: false` nao e' erro. A tabela vazia e' o estado normal de quem
    nunca rodou o job, e a tela precisa saber a diferenca entre "ainda nao
    calculamos" e "calculamos e deu zero".
    """
    linha = (
        await db.execute(
            select(SiteForecast)
            .where(SiteForecast.site_id == site_id)
            # `granularidade` EXPLICITA. Esta rota sempre falou do total do mes, e
            # ate' existir uma segunda janela o filtro era desnecessario. Agora
            # existem cinco: sem ele, `order_by ... limit 1` devolveria a linha
            # mais recente de QUALQUER janela - uma hora, provavelmente - e a tela
            # de demanda contratada mostraria o consumo de uma hora como se fosse
            # o do mes. Nao daria erro em lugar nenhum.
            .where(SiteForecast.granularidade == "mes")
            .order_by(SiteForecast.competencia.desc(), SiteForecast.gerado_em.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if linha is None:
        return {
            "disponivel": False,
            "motivo": (
                "Nenhuma previsão calculada para este ponto ainda. "
                "O cálculo roda fora da API, uma vez por mês."
            ),
        }

    return {
        "disponivel": True,
        "competencia": linha.competencia.isoformat(),
        "gerado_em": linha.gerado_em.isoformat(),
        "kwh_previsto": _float(linha.kwh_previsto),
        # Sem banda quando o modelo nao se aplica. O `None` aqui e' o que faz a
        # tela nao desenhar incerteza em volta de uma media movel.
        "kwh_p10": _float(linha.kwh_p10),
        "kwh_p90": _float(linha.kwh_p90),
        "faturamento_previsto_brl": _float(linha.faturamento_previsto_brl),
        "fat_p10_brl": _float(linha.fat_p10_brl),
        "fat_p90_brl": _float(linha.fat_p90_brl),
        "media_diaria_28d": _float(linha.media_diaria_28d),
        "modelo_aplicavel": linha.modelo_aplicavel,
        # De onde veio o numero que esta em `kwh_previsto`. A tela desenha a
        # banda so' quando e' "modelo".
        "fonte": linha.fonte,
        "modelo_versao": linha.modelo_versao,
        "dias_de_historico": linha.dias_de_historico,
        "cobertura_declarada_pct": _float(linha.cobertura_declarada_pct),
        "cobertura_medida_pct": _float(linha.cobertura_medida_pct),
        "wape_modelo_pct": _float(linha.wape_modelo_pct),
        "wape_baseline_pct": _float(linha.wape_baseline_pct),
        "avisos": _avisos(linha),
    }
