"""Laco do assistente: modelo -> ferramentas -> modelo, emitindo eventos.

Cada resposta e' uma sequencia de RODADAS. Numa rodada o modelo ou escreve a
resposta, ou pede ferramentas; pedindo, elas rodam e o resultado volta para a
rodada seguinte. A ultima rodada permitida vai SEM ferramentas, o que obriga o
modelo a responder com o que ja' consultou em vez de consultar para sempre.

Eventos emitidos (o router os transforma em SSE):

    delta       {"texto"}                               pedaco da resposta
    ferramenta  {"nome","rotulo","estado","ok"?}        inicio/fim de consulta
    bloqueado   {"motivo","mensagem"}                   descarta o texto parcial
    erro        {"mensagem"}                            o modelo nao respondeu
    fim         {"mensagem_id","tokens_entrada","tokens_saida"}

A mensagem de usuario ja chega gravada pelo router; aqui se grava o resto -
cada chamada de ferramenta e a resposta final, inclusive quando ela foi barrada
ou interrompida, porque o rastro de uma resposta barrada e' o que mais importa
auditar.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.assistant import AssistantConversation, AssistantMessage
from app.models.site import Site
from app.models.user import User
from app.services.assistant import prompts
from app.services.assistant.client import (
    ChamadaDeFerramenta,
    ClienteLlm,
    ConteudoBloqueado,
    FalhaDoModelo,
    FimDaRodada,
    TextoDelta,
    argumentos_como_dict,
)
from app.services.assistant.guardrails import somente_leitura, vazou_o_prompt
from app.services.assistant.tools import POR_NOME, Contexto, Resultado, executar, permitidas

log = get_logger(__name__)

AVISO_ENTRADA_BARRADA = (
    "Essa mensagem foi barrada pelo filtro de conteúdo e não chegou a ser respondida. "
    "Reformule a pergunta sobre a operação da praça."
)
AVISO_SAIDA_BARRADA = (
    "A resposta foi barrada pelas regras de segurança do assistente. "
    "Tente perguntar de outro jeito."
)
AVISO_FALHA = "O assistente não conseguiu responder agora. Tente de novo em instantes."


async def historico(db: AsyncSession, conversa_id: uuid.UUID, limite: int) -> list[dict]:
    """Ultimas mensagens de usuario e assistente, na ordem, para o modelo.

    Fica de fora o que foi BARRADO: reenviar a cada pergunta uma mensagem que o
    filtro recusou faria a conversa inteira ser recusada dali em diante. E ficam
    de fora as chamadas de ferramenta - o dado de ontem nao deve responder a
    pergunta de hoje; o modelo consulta de novo.
    """
    if limite <= 0:
        return []
    linhas = (
        await db.execute(
            select(AssistantMessage.papel, AssistantMessage.conteudo)
            .where(
                AssistantMessage.conversa_id == conversa_id,
                AssistantMessage.papel.in_(("user", "assistant")),
                AssistantMessage.conteudo.is_not(None),
                AssistantMessage.bloqueio.is_(None),
            )
            .order_by(AssistantMessage.created_at.desc(), AssistantMessage.id.desc())
            .limit(limite)
        )
    ).all()
    mensagens = [{"role": papel, "content": conteudo} for papel, conteudo in reversed(linhas)]
    # Cortar pelo limite pode deixar uma resposta sem a pergunta dela no topo.
    while mensagens and mensagens[0]["role"] != "user":
        mensagens.pop(0)
    return mensagens


async def _consultar(ctx: Contexto, chamada: ChamadaDeFerramenta, settings: Settings) -> Resultado:
    argumentos = argumentos_como_dict(chamada.argumentos)
    try:
        async with somente_leitura(ctx.db, settings.assistant_tool_timeout_s):
            return await executar(
                ctx, chamada.nome, argumentos, limite=settings.assistant_tool_result_max_chars
            )
    except DBAPIError as exc:
        # Timeout de consulta, ou uma leitura que tentou gravar e o READ ONLY
        # barrou. As duas sao defeito nosso, nao do operador.
        log.warning("assistente.ferramenta.banco", ferramenta=chamada.nome, erro=type(exc).__name__)
        return Resultado(
            False,
            '{"erro":"a consulta ao banco falhou ou demorou demais"}',
            argumentos,
        )
    except Exception:
        log.exception("assistente.ferramenta.falha", ferramenta=chamada.nome)
        return Resultado(False, '{"erro":"falha interna ao consultar"}', argumentos)


async def responder(
    db: AsyncSession,
    llm: ClienteLlm,
    settings: Settings,
    *,
    conversa_id: uuid.UUID,
    mensagem_do_usuario_id: uuid.UUID,
    user_id: uuid.UUID,
    site_id: uuid.UUID,
    aba: str | None,
) -> AsyncIterator[dict[str, Any]]:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    site = (await db.execute(select(Site).where(Site.id == site_id))).scalar_one()
    # Copiados agora: as ferramentas rodam em savepoints desfeitos, e nada que
    # dependa de atributo carregado deve ser lido depois delas.
    papel = user.role

    mensagens: list[dict[str, Any]] = [
        *prompts.mensagens_de_sistema(
            nome_da_praca=site.name,
            fuso=site.timezone,
            papel=str(papel),
            nome_do_usuario=user.full_name,
            aba=aba,
            agora=datetime.now(UTC),
        ),
        *await historico(db, conversa_id, settings.assistant_history_messages),
    ]
    schemas = [f.schema() for f in permitidas(papel)]
    ctx = Contexto(db=db, site_id=site_id, user=user)

    inicio = time.monotonic()
    texto: list[str] = []
    entrada = saida = em_cache = 0
    motivo: str | None = None
    rodada = 0

    async def gravar_resposta(**campos) -> uuid.UUID:
        resposta = AssistantMessage(
            id=uuid.uuid4(),
            conversa_id=conversa_id,
            papel="assistant",
            tokens_entrada=entrada or None,
            tokens_saida=saida or None,
            tokens_em_cache=em_cache or None,
            latencia_ms=int((time.monotonic() - inicio) * 1000),
            **campos,
        )
        db.add(resposta)
        await db.execute(
            update(AssistantConversation)
            .where(AssistantConversation.id == conversa_id)
            .values(updated_at=func.now())
        )
        await db.commit()
        return resposta.id

    try:
        for rodada in range(settings.assistant_max_tool_iterations + 1):
            # Cada rodada reenvia TUDO: instrucoes, ferramentas, historico e os
            # resultados acumulados. O custo cresce com o quadrado das rodadas, e
            # uma pergunta que puxa consulta atras de consulta pode sozinha gastar
            # o que cem perguntas comuns gastam. Passou do teto, a proxima rodada
            # vai sem ferramentas e o modelo responde com o que ja' tem.
            dentro_do_orcamento = entrada < settings.assistant_max_input_tokens_per_answer
            com_ferramentas = (
                bool(schemas)
                and rodada < settings.assistant_max_tool_iterations
                and dentro_do_orcamento
            )
            texto_da_rodada: list[str] = []
            fim: FimDaRodada | None = None

            async for evento in llm.rodada(mensagens, schemas if com_ferramentas else None):
                if isinstance(evento, TextoDelta):
                    texto.append(evento.texto)
                    texto_da_rodada.append(evento.texto)
                    if vazou_o_prompt("".join(texto)):
                        raise ConteudoBloqueado("vazamento_do_prompt")
                    yield {"tipo": "delta", "texto": evento.texto}
                else:
                    fim = evento

            if fim is None:
                raise FalhaDoModelo("rodada sem fim")
            entrada += fim.tokens_entrada
            saida += fim.tokens_saida
            em_cache += fim.tokens_em_cache
            motivo = fim.motivo
            if not (com_ferramentas and fim.chamadas):
                break

            mensagens.append(
                {
                    "role": "assistant",
                    "content": "".join(texto_da_rodada) or None,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.nome, "arguments": c.argumentos},
                        }
                        for c in fim.chamadas
                    ],
                }
            )
            for indice, chamada in enumerate(fim.chamadas):
                # Toda tool call precisa de uma resposta com o mesmo id, senao a
                # proxima rodada e' recusada pela API. As que passam do teto
                # recebem um erro em vez de serem descartadas.
                if indice >= settings.assistant_max_tool_calls_per_round:
                    mensagens.append(
                        {
                            "role": "tool",
                            "tool_call_id": chamada.id,
                            "content": '{"erro":"limite de consultas por rodada; '
                            'peça só o necessário"}',
                        }
                    )
                    continue

                ferramenta = POR_NOME.get(chamada.nome)
                rotulo = (
                    ferramenta.rotulo
                    if ferramenta is not None and papel in ferramenta.papeis
                    else "Consultando"
                )
                yield {
                    "tipo": "ferramenta",
                    "nome": chamada.nome,
                    "rotulo": rotulo,
                    "estado": "inicio",
                }

                t0 = time.monotonic()
                resultado = await _consultar(ctx, chamada, settings)
                db.add(
                    AssistantMessage(
                        id=uuid.uuid4(),
                        conversa_id=conversa_id,
                        papel="tool",
                        ferramenta=chamada.nome[:64] or "?",
                        argumentos=resultado.argumentos,
                        resultado=resultado.conteudo,
                        latencia_ms=int((time.monotonic() - t0) * 1000),
                        fim="ok" if resultado.ok else "erro",
                    )
                )
                mensagens.append(
                    {"role": "tool", "tool_call_id": chamada.id, "content": resultado.conteudo}
                )
                yield {
                    "tipo": "ferramenta",
                    "nome": chamada.nome,
                    "rotulo": rotulo,
                    "estado": "fim",
                    "ok": resultado.ok,
                }

    except ConteudoBloqueado as exc:
        na_entrada = exc.categoria not in ("saida", "vazamento_do_prompt")
        if na_entrada and rodada == 0:
            # A pergunta em si foi barrada: marca-la tira ela do historico, senao
            # toda mensagem seguinte da conversa seria barrada junto.
            await db.execute(
                update(AssistantMessage)
                .where(AssistantMessage.id == mensagem_do_usuario_id)
                .values(bloqueio=f"filtro:{exc.categoria}"[:64])
            )
        aviso = AVISO_ENTRADA_BARRADA if na_entrada else AVISO_SAIDA_BARRADA
        # Grava o aviso, e nao o texto parcial: o parcial e' justamente o que foi
        # barrado. O que o modelo chegou a escrever fica so' no log de quem opera.
        await gravar_resposta(conteudo=aviso, fim="bloqueado", bloqueio=exc.categoria[:64])
        log.warning("assistente.bloqueado", categoria=exc.categoria, rodada=rodada)
        yield {"tipo": "bloqueado", "motivo": exc.categoria, "mensagem": aviso}
        return

    except FalhaDoModelo as exc:
        await gravar_resposta(conteudo="".join(texto) or None, fim="erro")
        log.warning("assistente.falha_do_modelo", erro=str(exc))
        yield {"tipo": "erro", "mensagem": AVISO_FALHA}
        return

    except (asyncio.CancelledError, GeneratorExit):
        # O operador clicou em parar, ou fechou a aba. Guarda o que ja' tinha
        # saido: a conversa retomada mostra a resposta cortada, e nao um buraco.
        try:
            await gravar_resposta(conteudo="".join(texto) or None, fim="interrompida")
        except Exception:  # noqa: BLE001 - nao pode mascarar o cancelamento
            log.warning("assistente.interrompida.nao_gravada")
        raise

    mensagem_id = await gravar_resposta(conteudo="".join(texto), fim=motivo)
    log.info(
        "assistente.respondeu",
        rodadas=rodada + 1,
        tokens_entrada=entrada,
        tokens_em_cache=em_cache,
        tokens_saida=saida,
        papel=str(papel),
    )
    yield {
        "tipo": "fim",
        "mensagem_id": str(mensagem_id),
        "tokens_entrada": entrada,
        "tokens_saida": saida,
    }
