"""Assistente do operador: conversas e resposta em streaming (SSE).

Tudo o que pode dar errado ANTES de o modelo ser chamado responde como HTTP
comum - 404, 409, 422, 429, 503 -, com o corpo `{"detail"}` de sempre. So'
depois dessas guardas a resposta vira `text/event-stream`: um erro no meio do
fluxo nao tem mais status HTTP para mudar, entao chega como evento.

A resposta abre a PROPRIA sessao de banco (`get_fabrica_de_sessao`). A sessao
da requisicao e' da dependencia `get_db`, e o que acontece com ela enquanto o
corpo ainda esta sendo transmitido mudou entre versoes do FastAPI - depender
disso seria depender da versao instalada.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import DbSession, OperatorUser, ScopedSiteId
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.assistant import AssistantConversation, AssistantMessage
from app.models.user import User
from app.schemas.assistente import (
    AssistenteStatus,
    ConversaDetalhe,
    ConversaOut,
    MensagemIn,
    MensagemOut,
)
from app.services.assistant import guardrails, orchestrator
from app.services.assistant.client import ClienteAzure, ClienteLlm

log = get_logger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistente"])

_cliente: ClienteLlm | None = None


def get_llm() -> ClienteLlm:
    """O cliente do Azure, criado na primeira conversa e reaproveitado.

    Criado sob demanda, e nao no arranque: com o assistente desligado o SDK
    nem e' importado.
    """
    global _cliente
    if not settings.assistente_configurado:
        raise HTTPException(status_code=503, detail="assistente desabilitado nesta instalação")
    if _cliente is None:
        _cliente = ClienteAzure(settings)
    return _cliente


def get_fabrica_de_sessao() -> Callable[[], Any]:
    return SessionLocal


def exigir_habilitado() -> None:
    if not settings.assistente_configurado:
        raise HTTPException(status_code=503, detail="assistente desabilitado nesta instalação")


Llm = Annotated[ClienteLlm, Depends(get_llm)]
FabricaDeSessao = Annotated[Callable[[], Any], Depends(get_fabrica_de_sessao)]
Habilitado = Annotated[None, Depends(exigir_habilitado)]


async def _conversa_do_usuario(db, conversa_id: uuid.UUID, user: User) -> AssistantConversation:
    """404 para conversa inexistente E para conversa de outra pessoa.

    Mesma resposta para os dois: um 403 confirmaria que o id existe. Admin nao
    le conversa de operador - conversa e' do usuario, nao da praca.
    """
    conversa = (
        await db.execute(
            select(AssistantConversation).where(
                AssistantConversation.id == conversa_id,
                AssistantConversation.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if conversa is None:
        raise HTTPException(status_code=404, detail="conversa não encontrada")
    return conversa


@router.get("/status", response_model=AssistenteStatus)
async def status(_: OperatorUser) -> AssistenteStatus:
    """O widget pergunta isto antes de aparecer: desligado, ele nem se mostra."""
    return AssistenteStatus(
        habilitado=settings.assistente_configurado,
        limite_de_caracteres=settings.assistant_max_input_chars,
    )


@router.post("/conversations", response_model=ConversaOut, status_code=201)
async def criar_conversa(
    db: DbSession, site_id: ScopedSiteId, user: OperatorUser, _: Habilitado
) -> AssistantConversation:
    conversa = AssistantConversation(id=uuid.uuid4(), user_id=user.id, site_id=site_id)
    db.add(conversa)
    await db.commit()
    await db.refresh(conversa)
    return conversa


@router.get("/conversations", response_model=list[ConversaOut])
async def listar_conversas(
    db: DbSession, site_id: ScopedSiteId, user: OperatorUser
) -> list[AssistantConversation]:
    """As conversas deste usuario NESTA praca, mais recentes primeiro."""
    return list(
        (
            await db.execute(
                select(AssistantConversation)
                .where(
                    AssistantConversation.user_id == user.id,
                    AssistantConversation.site_id == site_id,
                )
                .order_by(AssistantConversation.updated_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )


@router.get("/conversations/{conversa_id}", response_model=ConversaDetalhe)
async def ler_conversa(
    conversa_id: uuid.UUID, db: DbSession, user: OperatorUser
) -> ConversaDetalhe:
    conversa = await _conversa_do_usuario(db, conversa_id, user)
    mensagens = (
        (
            await db.execute(
                select(AssistantMessage)
                .where(
                    AssistantMessage.conversa_id == conversa.id,
                    AssistantMessage.papel.in_(("user", "assistant")),
                )
                .order_by(AssistantMessage.created_at, AssistantMessage.id)
            )
        )
        .scalars()
        .all()
    )
    return ConversaDetalhe(
        **ConversaOut.model_validate(conversa).model_dump(),
        mensagens=[MensagemOut.model_validate(m) for m in mensagens],
    )


def _sse(tipo: str, dados: dict[str, Any]) -> str:
    return f"event: {tipo}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


@router.post(
    "/conversations/{conversa_id}/messages",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "eventos SSE"}},
)
async def enviar_mensagem(
    conversa_id: uuid.UUID,
    payload: MensagemIn,
    db: DbSession,
    site_id: ScopedSiteId,
    user: OperatorUser,
    llm: Llm,
    fabrica: FabricaDeSessao,
) -> StreamingResponse:
    """Grava a pergunta e transmite a resposta como eventos SSE.

    Eventos: `meta`, `delta`, `ferramenta`, `bloqueado`, `erro`, `fim`.
    """
    conversa = await _conversa_do_usuario(db, conversa_id, user)
    if conversa.site_id != site_id:
        # Admin trocou de praca no seletor. Continuar misturaria os numeros de
        # dois estabelecimentos no mesmo historico.
        raise HTTPException(
            status_code=409, detail="esta conversa é de outra praça; abra uma conversa nova"
        )
    texto = guardrails.validar_texto(payload.texto, settings)
    await guardrails.conferir_cota(db, user.id, settings)

    pergunta = AssistantMessage(
        id=uuid.uuid4(), conversa_id=conversa.id, papel="user", conteudo=texto
    )
    db.add(pergunta)
    if conversa.titulo is None:
        conversa.titulo = texto[:80]
    await db.commit()

    ids = {
        "conversa_id": conversa.id,
        "mensagem_do_usuario_id": pergunta.id,
        "user_id": user.id,
        "site_id": site_id,
    }
    aba = guardrails.aba_segura(payload.aba)

    async def fluxo() -> AsyncIterator[str]:
        yield _sse(
            "meta",
            {
                "conversa_id": str(ids["conversa_id"]),
                "mensagem_id": str(ids["mensagem_do_usuario_id"]),
            },
        )
        try:
            async with fabrica() as sessao:
                async for evento in orchestrator.responder(sessao, llm, settings, aba=aba, **ids):
                    tipo = evento.pop("tipo")
                    yield _sse(tipo, evento)
        except Exception:
            # Defeito nosso no meio do fluxo. Sem este evento o cliente veria o
            # stream acabar sem `fim` e ficaria com o indicador girando.
            log.exception("assistente.fluxo.falha", conversa_id=str(ids["conversa_id"]))
            yield _sse("erro", {"mensagem": orchestrator.AVISO_FALHA})

    return StreamingResponse(
        fluxo(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
