"""Contrato HTTP do assistente do operador.

O fluxo da resposta NAO esta aqui: ele sai como `text/event-stream`, e o
OpenAPI nao descreve eventos. Os tipos dos eventos estao em
`orchestrator.py` e, do lado do cliente, em `packages/sdk/src/types.ts`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AssistenteStatus(BaseModel):
    habilitado: bool
    limite_de_caracteres: int


class ConversaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    titulo: str | None
    created_at: datetime
    updated_at: datetime


class MensagemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    papel: Literal["user", "assistant"]
    conteudo: str | None
    # Preenchido quando uma guarda barrou: o cliente mostra o aviso com outra cor.
    bloqueio: str | None
    created_at: datetime


class ConversaDetalhe(ConversaOut):
    mensagens: list[MensagemOut]


class MensagemIn(BaseModel):
    # O teto de verdade e' ASSISTANT_MAX_INPUT_CHARS, conferido na rota com uma
    # mensagem que diz o limite. Este aqui so' impede um corpo absurdo de chegar
    # ate' la'.
    texto: str = Field(min_length=1, max_length=20000)
    aba: str | None = Field(default=None, max_length=80, description="rota do painel aberta")
