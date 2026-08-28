"""Autenticacao e usuarios."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8)
    role: UserRole = UserRole.DRIVER
    phone: str | None = None
    document: str | None = None
    site_id: uuid.UUID | None = None


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    phone: str | None
    document: str | None
    site_id: uuid.UUID | None
    wallet_balance: float
    created_at: datetime


class VehicleCreate(BaseModel):
    model: str = Field(max_length=80)
    plate: str | None = None
    vin: str | None = None
    battery_kwh: float | None = Field(default=None, ge=0)
    max_ac_kw: float | None = Field(default=None, ge=0)


class VehicleOut(ORMModel):
    id: uuid.UUID
    model: str
    plate: str | None
    vin: str | None
    battery_kwh: float | None
    max_ac_kw: float | None


class RfidCardCreate(BaseModel):
    uid: str = Field(min_length=4, max_length=14)
    label: str | None = None
    user_id: uuid.UUID | None = None
    tariff_id: uuid.UUID | None = None


class RfidCardOut(ORMModel):
    id: uuid.UUID
    uid: str
    label: str | None
    is_active: bool
    user_id: uuid.UUID | None
    tariff_id: uuid.UUID | None
    synced_to_hardware: bool


class WalletTopUpIn(BaseModel):
    """Corpo do credito na carteira.

    O valor era um parametro de query, e float. Dinheiro nao anda na URL - ela
    vaza para log de servidor, historico e referer - e todo o resto do dominio
    usa Decimal. Aqui ele volta a ser Decimal, com duas casas.
    """

    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    idempotency_key: str | None = Field(default=None, max_length=80)
