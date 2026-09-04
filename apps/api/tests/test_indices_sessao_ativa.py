"""As duas guardas de sessao ativa, no nivel do banco.

A checagem da aplicacao e' um SELECT seguido de um INSERT: duas requisicoes
simultaneas atravessam o SELECT juntas, as duas o consideram livre e as duas
inserem. So um indice unico decide quem chegou primeiro.

O indice do ponto existia desde a 0005 e nunca protegeu nada: o predicado
filtrava os VALORES do StrEnum ('charging') enquanto a coluna guarda os NOMES
('CHARGING'). Zero linhas casavam. A guarda por motorista nunca teve indice.

Estes testes falam com o banco por baixo da aplicacao de proposito - e' a
constraint que esta sendo verificada, nao o servico.
"""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models.enums import AuthMethod, SessionState
from app.models.session import ChargingSession
from app.services import session_service


async def _sessao_crua(db, ponto, *, user_id=None, state=SessionState.CHARGING):
    """Insere direto, sem passar pela guarda do servico."""
    sessao = ChargingSession(
        id=uuid.uuid4(),
        code=f"X-{uuid.uuid4().hex[:6]}",
        site_id=ponto.site_id,
        charge_point_id=ponto.id,
        user_id=user_id,
        state=state,
        auth_method=AuthMethod.APP,
    )
    db.add(sessao)
    await db.flush()
    return sessao


async def test_o_predicado_do_indice_casa_com_o_que_a_aplicacao_grava(db, ponto, motorista):
    """A raiz do defeito: nome do membro, nao valor do enum."""
    await session_service.authorize(db, ponto, user=motorista)

    coberto = (
        await db.execute(
            text(
                "SELECT count(*) FROM charging_sessions WHERE state IN "
                "('AUTHORIZING','QUEUED','STARTING','CHARGING','SUSPENDED','FINISHING')"
            )
        )
    ).scalar_one()
    assert coberto >= 1, "o predicado do índice não casa com o estado gravado"


async def test_banco_recusa_duas_sessoes_no_mesmo_ponto(db, ponto, motorista):
    await session_service.authorize(db, ponto, user=motorista)

    with pytest.raises(IntegrityError):
        await _sessao_crua(db, ponto)


async def test_banco_recusa_duas_sessoes_do_mesmo_motorista(db, ponto, segundo_ponto, motorista):
    """Pontos diferentes, mesmo motorista: a guarda nova."""
    await session_service.authorize(db, ponto, user=motorista)

    with pytest.raises(IntegrityError):
        await _sessao_crua(db, segundo_ponto, user_id=motorista.id)


async def test_cartoes_sem_usuario_nao_colidem_entre_si(db, ponto, segundo_ponto):
    """user_id nulo: o Postgres trata NULLs como distintos, que e' o desejado."""
    await _sessao_crua(db, ponto, user_id=None)
    await _sessao_crua(db, segundo_ponto, user_id=None)


async def test_sessao_encerrada_libera_o_ponto_e_o_motorista(db, ponto, motorista):
    """O indice e' parcial: estado terminal sai dele."""
    sessao = await _sessao_crua(db, ponto, user_id=motorista.id)
    sessao.state = SessionState.BILLED
    await db.flush()

    nova = await _sessao_crua(db, ponto, user_id=motorista.id)
    assert nova.id != sessao.id


async def test_motoristas_diferentes_no_mesmo_site_convivem(db, ponto, segundo_ponto, motorista):
    outro_id = uuid.uuid4()
    from app.models.enums import UserRole
    from app.models.user import User

    db.add(
        User(
            id=outro_id,
            email=f"o-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Outro",
            hashed_password="x",
            role=UserRole.DRIVER,
        )
    )
    await db.flush()

    await _sessao_crua(db, ponto, user_id=motorista.id)
    await _sessao_crua(db, segundo_ponto, user_id=outro_id)

    ativas = (
        await db.execute(
            select(ChargingSession).where(ChargingSession.state == SessionState.CHARGING)
        )
    ).scalars().all()
    assert len(ativas) == 2
