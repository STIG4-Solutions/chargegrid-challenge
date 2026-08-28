"""Uma vaga por motorista de cada vez.

A guarda que existia era do ponto: impedia duas sessoes na mesma vaga, mas nao
o mesmo motorista ocupando varias. Cada uma carregava sua pre-autorizacao e
negava vaga a outra pessoa - e o app so mostra uma recarga em andamento, entao
as demais ficavam invisiveis para quem as abriu.
"""

import pytest

from app.services import session_service
from app.services.session_service import Conflict


async def test_motorista_nao_ocupa_duas_vagas(db, ponto, segundo_ponto, motorista):
    await session_service.authorize(db, ponto, user=motorista)

    with pytest.raises(Conflict, match="recarga em andamento"):
        await session_service.authorize(db, segundo_ponto, user=motorista)


async def test_o_conflito_diz_qual_sessao_esta_aberta(db, ponto, segundo_ponto, motorista):
    """Sem o codigo, o motorista nao sabe o que precisa encerrar."""
    aberta = await session_service.authorize(db, ponto, user=motorista)

    with pytest.raises(Conflict) as erro:
        await session_service.authorize(db, segundo_ponto, user=motorista)
    assert aberta.code in str(erro.value)


async def test_motoristas_diferentes_ocupam_vagas_diferentes(
    db, ponto, segundo_ponto, motorista
):
    import uuid

    from app.models.enums import UserRole
    from app.models.user import User

    outro = User(
        id=uuid.uuid4(),
        email=f"outro-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Outro",
        hashed_password="x",
        role=UserRole.DRIVER,
    )
    db.add(outro)
    await db.flush()

    await session_service.authorize(db, ponto, user=motorista)
    await session_service.authorize(db, segundo_ponto, user=outro)


async def test_apos_encerrar_pode_iniciar_de_novo(db, ponto, segundo_ponto, motorista):
    from app.models.enums import StopReason

    sessao = await session_service.authorize(db, ponto, user=motorista)
    sessao = await session_service.start(db, sessao, ponto)
    await session_service.stop(db, sessao, ponto, reason=StopReason.REMOTE)

    await session_service.authorize(db, segundo_ponto, user=motorista)


async def test_sessao_na_fila_tambem_conta_como_aberta(db, ponto, segundo_ponto, motorista):
    """QUEUED e' o motorista parado na vaga esperando - a vaga esta ocupada."""
    from app.models.enums import SessionState

    sessao = await session_service.authorize(db, ponto, user=motorista)
    sessao.state = SessionState.QUEUED
    await db.flush()

    with pytest.raises(Conflict, match="recarga em andamento"):
        await session_service.authorize(db, segundo_ponto, user=motorista)


async def test_cartao_rfid_sem_usuario_nao_e_agrupado(db, ponto, segundo_ponto):
    """Sem usuario nao ha como agrupar; a guarda do ponto ja cobre o caso."""
    from app.models.enums import AuthMethod

    await session_service.authorize(db, ponto, auth_method=AuthMethod.RFID)
    await session_service.authorize(db, segundo_ponto, auth_method=AuthMethod.RFID)
