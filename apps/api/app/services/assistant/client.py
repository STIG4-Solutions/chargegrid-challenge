"""Cliente do modelo: Azure OpenAI atras de uma interface de duas pecas.

O orquestrador so' conhece `ClienteLlm.rodada()`, que devolve um fluxo de
`TextoDelta` terminado por um `FimDaRodada`. Tudo que e' especifico do Azure -
formato do chunk de streaming, acumulo dos pedacos de tool call, os dois jeitos
de o filtro de conteudo se manifestar - fica aqui. E' isso que deixa o teste
trocar o modelo por um roteiro deterministico sem tocar no resto.

O SDK `openai` e' importado DENTRO do construtor. O processo da API tambem roda
os workers de potencia, e um import quebrado no topo do modulo derrubaria o
rebalanceamento junto - o mesmo motivo que mantem o LightGBM fora daqui.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass(slots=True)
class TextoDelta:
    texto: str


@dataclass(slots=True)
class ChamadaDeFerramenta:
    id: str
    nome: str
    # Texto cru: o modelo pode mandar JSON invalido, e quem decide o que fazer
    # com isso e' o registro de ferramentas, nao o cliente.
    argumentos: str


@dataclass(slots=True)
class FimDaRodada:
    motivo: str | None
    chamadas: list[ChamadaDeFerramenta] = field(default_factory=list)
    tokens_entrada: int = 0
    tokens_saida: int = 0
    # Parte de `tokens_entrada` que veio do cache de prompt do Azure (cobrada
    # com desconto). Zero quando o deployment nao informa.
    tokens_em_cache: int = 0


Evento = TextoDelta | FimDaRodada


class ConteudoBloqueado(Exception):
    """O filtro de conteudo do Azure barrou a entrada ou a saida.

    `categoria` e' o que o Azure apontou (jailbreak, hate, violence...) quando
    ele diz; senao, o lado que foi barrado.
    """

    def __init__(self, categoria: str):
        super().__init__(categoria)
        self.categoria = categoria


class FalhaDoModelo(Exception):
    """O modelo nao respondeu: timeout, cota do Azure, credencial, rede."""


class ClienteLlm(Protocol):
    def rodada(
        self,
        mensagens: list[dict[str, Any]],
        ferramentas: list[dict[str, Any]] | None,
    ) -> AsyncIterator[Evento]: ...


def _categoria_do_filtro(resultados: Any) -> str | None:
    """Primeira categoria marcada como filtrada num `content_filter_result(s)`."""
    if isinstance(resultados, list):
        for item in resultados:
            achada = _categoria_do_filtro(
                (item or {}).get("content_filter_results") if isinstance(item, dict) else None
            )
            if achada:
                return achada
        return None
    if not isinstance(resultados, dict):
        return None
    for nome, detalhe in resultados.items():
        if isinstance(detalhe, dict) and (detalhe.get("filtered") or detalhe.get("detected")):
            return nome
    return None


def _categoria_do_erro(corpo: Any) -> str | None:
    """Categoria de um 400 `content_filter` do Azure, ou None se nao for isso.

    O corpo varia: `{"error": {"code": "content_filter", "innererror":
    {"content_filter_result": {...}}}}` na forma documentada, e o SDK as vezes ja
    entrega o objeto `error` desembrulhado.
    """
    if not isinstance(corpo, dict):
        return None
    erro = corpo.get("error", corpo)
    if not isinstance(erro, dict) or erro.get("code") != "content_filter":
        return None
    interno = erro.get("innererror") or {}
    return _categoria_do_filtro(interno.get("content_filter_result")) or "entrada"


class ClienteAzure:
    """`ClienteLlm` sobre o Azure OpenAI, com streaming e tool calling."""

    # Tentativas extras em 429/5xx/timeout. Poucas de proposito: o operador esta
    # olhando o indicador de "pensando", e dez tentativas silenciosas sao um
    # minuto de tela parada antes do erro que ia chegar de qualquer jeito.
    TENTATIVAS = 2

    def __init__(self, settings: Settings):
        from openai import AsyncAzureOpenAI

        self._settings = settings
        self._cliente = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            timeout=settings.azure_openai_timeout_s,
            max_retries=0,
        )

    async def _abrir(self, mensagens, ferramentas):
        import openai

        s = self._settings
        parametros: dict[str, Any] = {
            "model": s.azure_openai_deployment,
            "messages": mensagens,
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_completion_tokens": s.assistant_max_output_tokens,
        }
        if s.azure_openai_temperature is not None:
            parametros["temperature"] = s.azure_openai_temperature
        if ferramentas:
            parametros["tools"] = ferramentas
            parametros["parallel_tool_calls"] = True

        espera = 1.0
        for tentativa in range(self.TENTATIVAS + 1):
            try:
                return await self._cliente.chat.completions.create(**parametros)
            except openai.BadRequestError as exc:
                categoria = _categoria_do_erro(exc.body)
                if categoria:
                    raise ConteudoBloqueado(categoria) from exc
                raise FalhaDoModelo(f"requisição recusada pelo modelo: {exc.message}") from exc
            except (
                openai.RateLimitError,
                openai.APITimeoutError,
                openai.APIConnectionError,
                openai.InternalServerError,
            ) as exc:
                if tentativa == self.TENTATIVAS:
                    raise FalhaDoModelo(type(exc).__name__) from exc
                log.warning("assistente.azure.retentativa", erro=type(exc).__name__)
                await asyncio.sleep(espera)
                espera *= 2
            except openai.APIError as exc:
                # Credencial errada, deployment inexistente: repetir nao conserta.
                raise FalhaDoModelo(type(exc).__name__) from exc
        raise FalhaDoModelo("sem resposta")  # inalcancavel; satisfaz o verificador

    async def rodada(self, mensagens, ferramentas) -> AsyncIterator[Evento]:
        import openai

        fluxo = await self._abrir(mensagens, ferramentas)
        motivo: str | None = None
        entrada = saida = em_cache = 0
        # Tool calls chegam em pedacos indexados: o id e o nome no primeiro, os
        # argumentos espalhados pelos seguintes.
        parciais: dict[int, dict[str, str]] = {}

        try:
            async for chunk in fluxo:
                if chunk.usage:
                    entrada = chunk.usage.prompt_tokens or 0
                    saida = chunk.usage.completion_tokens or 0
                    detalhes = getattr(chunk.usage, "prompt_tokens_details", None)
                    em_cache = (getattr(detalhes, "cached_tokens", None) or 0) if detalhes else 0
                for escolha in chunk.choices or []:
                    delta = escolha.delta
                    if delta is not None and delta.content:
                        yield TextoDelta(delta.content)
                    for tc in (delta.tool_calls if delta is not None else None) or []:
                        atual = parciais.setdefault(tc.index, {"id": "", "nome": "", "args": ""})
                        if tc.id:
                            atual["id"] = tc.id
                        if tc.function is not None:
                            if tc.function.name:
                                atual["nome"] += tc.function.name
                            if tc.function.arguments:
                                atual["args"] += tc.function.arguments
                    if escolha.finish_reason:
                        motivo = escolha.finish_reason
        except openai.APIError as exc:
            raise FalhaDoModelo(type(exc).__name__) from exc

        if motivo == "content_filter":
            # Saida barrada no meio do streaming. O texto parcial ja foi
            # emitido; quem recebe o bloqueio descarta o que mostrou.
            raise ConteudoBloqueado("saida")

        chamadas = [
            ChamadaDeFerramenta(id=p["id"], nome=p["nome"], argumentos=p["args"] or "{}")
            for _, p in sorted(parciais.items())
            if p["nome"]
        ]
        yield FimDaRodada(
            motivo=motivo,
            chamadas=chamadas,
            tokens_entrada=entrada,
            tokens_saida=saida,
            tokens_em_cache=em_cache,
        )


def argumentos_como_dict(texto: str) -> dict[str, Any] | None:
    """JSON do modelo -> dict, ou None se nao for um objeto JSON."""
    try:
        valor = json.loads(texto or "{}")
    except json.JSONDecodeError:
        return None
    return valor if isinstance(valor, dict) else None
