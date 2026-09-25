"""Guardas do assistente que NAO dependem do modelo se comportar.

O system prompt pede que o modelo fique no assunto, nao invente numero e nao
revele instrucoes - e um modelo pode ser convencido a desobedecer qualquer uma
dessas. As guardas deste modulo valem mesmo quando ele desobedece:

- somente leitura: a ferramenta roda numa transacao READ ONLY; escrever falha
  no Postgres, nao na boa vontade de quem escreveu a ferramenta;
- cota por usuario: conta no banco, entao vale entre workers e reinicios;
- canario: uma marca aleatoria no system prompt que, se aparecer na saida,
  prova que o prompt vazou - e a resposta e' barrada;
- a aba de origem e' validada por formato antes de entrar no prompt: e' texto
  que vem do cliente, e o cliente pode mandar qualquer coisa.

O filtro de conteudo (violencia, odio, jailbreak) e' o do deployment no Azure;
`client.py` traduz o bloqueio dele.
"""

from __future__ import annotations

import re
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.assistant import AssistantConversation, AssistantMessage

# Por processo, e nao fixo no codigo: um canario publicado no repositorio seria
# exatamente o texto que um ataque pediria para o modelo omitir.
CANARIO = f"cg-{secrets.token_hex(6)}"

_ABA = re.compile(r"^/[a-z0-9/_-]{0,60}$")


def validar_texto(texto: str, settings: Settings) -> str:
    limpo = texto.strip()
    if not limpo:
        raise HTTPException(status_code=422, detail="a mensagem está vazia")
    if len(limpo) > settings.assistant_max_input_chars:
        raise HTTPException(
            status_code=422,
            detail=(
                f"a mensagem tem {len(limpo)} caracteres; o limite é "
                f"{settings.assistant_max_input_chars}"
            ),
        )
    return limpo


def aba_segura(aba: str | None) -> str | None:
    """Rota do painel, ou None. Nada alem de um caminho entra no prompt."""
    if aba and _ABA.fullmatch(aba):
        return aba
    return None


async def conferir_cota(db: AsyncSession, user_id: uuid.UUID, settings: Settings) -> None:
    """429 quando o usuario passou da cota por minuto ou por dia.

    Conta mensagens de USUARIO, e nao chamadas ao modelo: e' o que a pessoa
    controla, e o numero que a mensagem de erro consegue explicar.
    """
    agora = datetime.now(UTC)

    async def enviadas_desde(inicio: datetime) -> int:
        return (
            await db.execute(
                select(func.count(AssistantMessage.id))
                .join(
                    AssistantConversation, AssistantConversation.id == AssistantMessage.conversa_id
                )
                .where(
                    AssistantConversation.user_id == user_id,
                    AssistantMessage.papel == "user",
                    AssistantMessage.created_at >= inicio,
                )
            )
        ).scalar_one()

    if await enviadas_desde(agora - timedelta(minutes=1)) >= settings.assistant_rate_per_min:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"limite de {settings.assistant_rate_per_min} mensagens por minuto; "
            "aguarde um instante",
            headers={"Retry-After": "60"},
        )
    if await enviadas_desde(agora - timedelta(days=1)) >= settings.assistant_rate_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"limite de {settings.assistant_rate_per_day} mensagens por dia atingido",
        )
    await conferir_orcamento_de_tokens(db, user_id, settings, agora=agora)


async def conferir_orcamento_de_tokens(
    db: AsyncSession, user_id: uuid.UUID, settings: Settings, *, agora: datetime
) -> None:
    """429 quando o consumo das ultimas 24 h passou do teto do usuario ou da instalacao.

    Soma o que ja' esta' gravado em `assistant_messages` - o mesmo numero que o
    Azure cobrou, lido do `usage` de cada resposta. Janela movel de 24 h, e nao
    "desde a meia-noite": com virada fixa, quem esgotou as 23h59 teria a cota
    inteira de volta um minuto depois.

    O teto e' conferido ANTES da pergunta, com o que ja' foi gasto. A pergunta que
    cruza o teto termina; a seguinte e' que e' recusada - cortar uma resposta no
    meio gastaria os tokens e nao entregaria nada.
    """
    consumo = func.coalesce(
        func.sum(
            func.coalesce(AssistantMessage.tokens_entrada, 0)
            + func.coalesce(AssistantMessage.tokens_saida, 0)
        ),
        0,
    )
    desde = agora - timedelta(days=1)
    base = (
        select(consumo)
        .join(AssistantConversation, AssistantConversation.id == AssistantMessage.conversa_id)
        .where(AssistantMessage.papel == "assistant", AssistantMessage.created_at >= desde)
    )

    total = (await db.execute(base)).scalar_one()
    if total >= settings.assistant_daily_tokens_total:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="o assistente atingiu o limite diário de uso desta instalação; "
            "tente novamente mais tarde",
        )
    do_usuario = (
        await db.execute(base.where(AssistantConversation.user_id == user_id))
    ).scalar_one()
    if do_usuario >= settings.assistant_daily_tokens_per_user:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="você atingiu o limite diário de uso do assistente; "
            "ele volta a responder ao longo das próximas 24 horas",
        )


@asynccontextmanager
async def somente_leitura(db: AsyncSession, timeout_s: float):
    """Savepoint READ ONLY com tempo maximo por consulta, sempre desfeito.

    Savepoint, e nao uma sessao nova: a mesma transacao continua viva para
    gravar a mensagem depois. `SET TRANSACTION READ ONLY` dentro do savepoint e'
    permitido (o Postgres so' recusa o caminho inverso), e o ROLLBACK TO
    SAVEPOINT devolve a transacao ao modo de escrita e o `statement_timeout` ao
    valor anterior. Desfazer sempre, e nao so' em erro: nada do que aconteceu
    aqui dentro deveria sobrar.
    """
    ponto = await db.begin_nested()
    try:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        # Inteiro formatado por nos, nunca texto do cliente: SET nao aceita bind.
        await db.execute(text(f"SET LOCAL statement_timeout = {int(timeout_s * 1000)}"))
        yield
    finally:
        # Incondicional: depois de um erro do banco o savepoint fica INATIVO, e
        # e' justamente o rollback que devolve a sessao a um estado utilizavel.
        await ponto.rollback()


def vazou_o_prompt(texto: str) -> bool:
    return CANARIO in texto
