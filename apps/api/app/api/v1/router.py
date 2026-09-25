"""Agregador das rotas da v1."""

from fastapi import APIRouter

from app.api.v1 import (
    assistant,
    auth,
    campaigns,
    infra,
    mobile,
    platform,
    power,
    sessions,
    tariffs,
    users,
    ws,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(power.router)
api_router.include_router(campaigns.router)
api_router.include_router(platform.router)
api_router.include_router(sessions.router)
api_router.include_router(tariffs.router)
api_router.include_router(mobile.router)
api_router.include_router(ws.router)
api_router.include_router(assistant.router)
api_router.include_router(infra.router)
