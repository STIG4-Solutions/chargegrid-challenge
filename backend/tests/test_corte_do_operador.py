"""O corte manual do operador nao pode ser desfeito por uma sessao nova.

`operator_throttled` e' o corte de emergencia do painel, gravado no reg 10000.
O modelo diz, no proprio comentario, que ele existe porque sem persistir "o
botao do painel parecia funcionar e revertia sozinho".

Era o que acontecia: `promote_queue` respeitava o corte, mas `start()` - alcancado
direto por POST /sessions e POST /app/sessions - mandava
set_dispatch_throttle(throttled=False) sem olhar o banco. Depois disso o ponto
carregava em potencia plena e, como is_dispatchable continua falso, os ciclos
seguintes o excluiam do orcamento: o site passava do teto com o alocador
dizendo que estava tudo bem.
"""

import pytest

from app.services import power_manager, session_service
from app.services.session_service import Conflict


async def test_ponto_cortado_recusa_sessao_nova(db, ponto, motorista):
    ponto.operator_throttled = True
    await db.flush()

    with pytest.raises(Conflict, match="cortado manualmente"):
        await session_service.authorize(db, ponto, user=motorista)


async def test_ponto_cortado_nao_entra_no_rateio_nem_como_iniciante(db, ponto, site, tarifa):
    """`starting` contorna o is_dispatchable - mas nao pode contornar o corte."""
    ponto.operator_throttled = True
    await db.flush()

    plano = await power_manager.plan_for_site(db, site.id, starting_ids={str(ponto.id)})
    concedido = next(
        (a.granted_kw for a in plano.allocations if a.charge_point_id == str(ponto.id)), 0.0
    )
    assert concedido == 0.0, "o alocador deu potência a um ponto cortado"


async def test_destravar_devolve_o_ponto(db, ponto, motorista):
    """A guarda nao pode deixar o ponto preso depois que o operador libera."""
    ponto.operator_throttled = True
    await db.flush()
    with pytest.raises(Conflict):
        await session_service.authorize(db, ponto, user=motorista)

    ponto.operator_throttled = False
    await db.flush()
    sessao = await session_service.authorize(db, ponto, user=motorista)
    assert sessao is not None


async def test_start_nao_envia_liberacao_em_ponto_cortado(db, ponto, motorista, tarifa):
    """Defesa em profundidade: quem chamar start() direto tambem nao reverte."""
    from sqlalchemy import select

    from app.models.audit import CommandLog

    sessao = await session_service.authorize(db, ponto, user=motorista)
    ponto.operator_throttled = True
    await db.flush()

    await session_service.start(db, sessao, ponto)

    comandos = (
        (
            await db.execute(
                select(CommandLog).where(
                    CommandLog.charge_point_id == ponto.id,
                    CommandLog.command == "set_dispatch_throttle",
                )
            )
        )
        .scalars()
        .all()
    )
    liberacoes = [c for c in comandos if c.payload.get("throttled") is False]
    assert not liberacoes, "start() desfez o corte do operador"
