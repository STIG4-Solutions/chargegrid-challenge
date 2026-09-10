"""Leitura da previsao de demanda. A API nunca a calcula.

Quem calcula e' `apps/forecast`, um job que roda fora deste processo. Aqui so' se
le a linha mais recente e se traduz para a tela - incluindo as guardas de
honestidade, que sao a parte que nao pode ser esquecida.

TRES AVISOS, e cada um responde a uma pergunta diferente:

- `modelo_aplicavel = false` -> o modelo nao conhece este local, ou o historico e'
  curto demais. O numero e' media movel de 28 dias, e chamar isso de previsao
  seria mentira.
- a faixa p10-p90 cobre menos do que promete -> ela e' mais estreita do que
  anuncia, e tratar os extremos como piores casos e' otimismo.
- o modelo nao supera a regua -> uma media movel de tres linhas erra menos que
  ele. A previsao vale como referencia, nao como base de decisao.

Nenhum dos tres e' escondido. O projeto ja faz isso em `demand_service`
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

    medida, declarada = linha.cobertura_medida_pct, linha.cobertura_declarada_pct
    if medida is not None and declarada is not None:
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

    modelo, regua = linha.wape_modelo_pct, linha.wape_baseline_pct
    if modelo is not None and regua is not None and Decimal(str(modelo)) >= Decimal(str(regua)):
        avisos.append(
            {
                "nivel": "alto",
                "texto": (
                    f"Este modelo não superou a régua: erra {float(modelo):.1f}% contra "
                    f"{float(regua):.1f}% de uma média móvel de 28 dias. Use como "
                    "referência, não como base para contratar demanda."
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
        "modelo_versao": linha.modelo_versao,
        "dias_de_historico": linha.dias_de_historico,
        "cobertura_declarada_pct": _float(linha.cobertura_declarada_pct),
        "cobertura_medida_pct": _float(linha.cobertura_medida_pct),
        "wape_modelo_pct": _float(linha.wape_modelo_pct),
        "wape_baseline_pct": _float(linha.wape_baseline_pct),
        "avisos": _avisos(linha),
    }
