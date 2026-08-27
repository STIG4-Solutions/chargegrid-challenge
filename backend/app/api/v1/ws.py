"""WebSocket do dashboard: telemetria e plano de potencia em tempo real."""

from __future__ import annotations

import asyncio
import uuid

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.core.logging import get_logger
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.user import User
from app.services import events

log = get_logger(__name__)
router = APIRouter(tags=["tempo real"])

# Sem trafego, um ping periodico mantem proxies e balanceadores de matar a conexao.
PING_INTERVAL_S = 25


@router.websocket("/ws/site")
async def site_stream(websocket: WebSocket, token: str = Query(...)) -> None:
    """Assina os eventos do site do operador.

    O token vai na query string porque a API de WebSocket do navegador nao
    permite cabecalhos customizados no handshake.
    """
    try:
        claims = decode_token(token)
        user_id = uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is None or not user.is_active or user.site_id is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        site_id = user.site_id

    await websocket.accept()
    topic = events.site_topic(site_id)
    queue = events.bus.subscribe(topic)
    log.info("ws.connected", user=user.email, topic=topic)

    try:
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=PING_INTERVAL_S)
            except TimeoutError:
                await websocket.send_json({"type": "ping"})
                continue
            await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        events.bus.unsubscribe(topic, queue)
        log.info("ws.disconnected", user=user.email, topic=topic)
