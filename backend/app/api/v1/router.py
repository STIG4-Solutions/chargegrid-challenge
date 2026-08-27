"""Agregador das rotas da v1."""

from fastapi import APIRouter

from app.api.v1 import auth, mobile, power, sessions, tariffs, ws

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(power.router)
api_router.include_router(sessions.router)
api_router.include_router(tariffs.router)
api_router.include_router(mobile.router)
api_router.include_router(ws.router)
