"""O que o motorista leva nesta recarga, quando ha mais de uma fonte.

Duas coisas podem conceder beneficio ao mesmo tempo: a ASSINATURA que ele paga e
a CAMPANHA que o estabelecimento ou a rede esta rodando. Este modulo existe para
decidir o que acontece nesse encontro, e a decisao nao e' obvia.

A REGRA: o melhor de cada componente, nunca a soma.

Somar seria o caminho curto e produz desconto sem teto - um plano de 20% durante
uma campanha de 25% viraria 45%, e ninguem planejou margem para isso. Pior:
campanhas se acumulariam sobre campanhas ao longo do tempo, e o operador
descobriria pelo extrato.

Deixar so' a campanha vencer tambem esta errado, e por um motivo diferente: quem
assinou PAGOU pelo beneficio. Se uma promocao aberta a todos anula o que ele
comprou, ele pagou por nada naquele mes - e vai cancelar.

Entao: percentual e' o MAIOR dos dois; kWh inclusos e isencao de taxa vem do
plano, porque campanha nao oferece nenhum dos dois. O assinante nunca recebe
menos do que contratou, e o desconto nunca passa do maior anunciado.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import ChargingSession
from app.models.user import User
from app.services.tariff_engine import Beneficio


def combinar(plano: Beneficio | None, campanha: Beneficio | None) -> Beneficio | None:
    """O melhor de cada componente. `None` quando nao ha fonte nenhuma."""
    if plano is None and campanha is None:
        return None
    if plano is None:
        return campanha
    if campanha is None:
        return plano

    pct_plano = Decimal(str(plano.desconto_pct))
    pct_campanha = Decimal(str(campanha.desconto_pct))
    vence_a_campanha = pct_campanha > pct_plano

    # O rotulo segue quem deu o percentual: e' o que o motorista ve na fatura, e
    # dizer "Plano Mensal" num desconto que veio da campanha esconderia dele que
    # havia uma promocao - e do operador, que ela foi usada.
    rotulo = campanha.rotulo if vence_a_campanha else plano.rotulo
    if pct_campanha > 0 and pct_plano > 0 and pct_campanha != pct_plano:
        rotulo = f"{rotulo} (maior benefício)"

    return Beneficio(
        rotulo=rotulo,
        desconto_pct=max(pct_plano, pct_campanha),
        # Campanha nao concede franquia nem isencao de taxa; os dois vem sempre
        # do plano, e por isso somam sem risco de duplicar nada.
        kwh_inclusos=plano.kwh_inclusos,
        isenta_session_fee=plano.isenta_session_fee,
    )


async def resolver(
    db: AsyncSession, sessao: ChargingSession, momento: datetime | None = None
) -> Beneficio | None:
    """O beneficio final desta sessao, pronto para o motor de tarifacao.

    Import tardio dos dois servicos: `campaign_service` e `subscription_service`
    leem o motor, e importa-los no topo daqui fecharia o ciclo.
    """
    if sessao.user_id is None:
        return None

    from app.services import campaign_service, subscription_service

    dono = (await db.get(User, sessao.user_id)) if sessao.user_id else None
    plano = await subscription_service.beneficio_do_plano(db, dono) if dono else None
    campanha = await campaign_service.resolver_beneficio(db, sessao, momento)
    return combinar(plano, campanha)
