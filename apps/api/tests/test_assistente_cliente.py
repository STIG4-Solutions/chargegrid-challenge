"""O cliente do Azure: do chunk de streaming ao evento que o orquestrador le.

`test_assistente.py` troca o cliente inteiro por um roteiro, entao a traducao
do formato do Azure ficava sem teste - justamente a parte que depende de um
formato externo. Aqui o SDK `openai` e' o de verdade; so' a chamada de rede e'
substituida, e os chunks sao os tipos do proprio SDK
(`ChatCompletionChunk.model_validate`), entao um campo renomeado numa versao
nova quebra aqui e nao em producao.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.assistant.client import (
    ClienteAzure,
    ConteudoBloqueado,
    FalhaDoModelo,
    FimDaRodada,
    TextoDelta,
)

openai = pytest.importorskip("openai")
from openai.types.chat import ChatCompletionChunk  # noqa: E402


def _config() -> Settings:
    return Settings(
        env="test",
        assistant_enabled=True,
        azure_openai_endpoint="https://teste.openai.azure.com",
        azure_openai_api_key="chave",
        azure_openai_deployment="gpt-teste",
    )


def _chunk(choices, usage=None) -> ChatCompletionChunk:
    return ChatCompletionChunk.model_validate(
        {
            "id": "c",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "gpt-teste",
            "choices": choices,
            "usage": usage,
        }
    )


def _delta(indice=0, finish=None, **delta):
    return {"index": indice, "delta": delta, "finish_reason": finish}


class _Fluxo:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        item = self._chunks.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _cliente(resposta) -> tuple[ClienteAzure, list[dict]]:
    cliente = ClienteAzure(_config())
    pedidos: list[dict] = []

    async def create(**parametros):
        pedidos.append(parametros)
        if isinstance(resposta, BaseException):
            raise resposta
        return _Fluxo(resposta)

    cliente._cliente.chat.completions.create = create
    return cliente, pedidos


async def _eventos(cliente, ferramentas=None):
    return [e async for e in cliente.rodada([{"role": "user", "content": "oi"}], ferramentas)]


def _erro_400(body) -> Exception:
    # Construido sem passar pelo __init__: ele exige um Response do cliente HTTP
    # que o SDK usa, e esse cliente mudou entre majors (httpx -> httpx2). O que
    # `client.py` le do erro e' so' `body` e `message`.
    erro = openai.BadRequestError.__new__(openai.BadRequestError)
    erro.body = body
    erro.message = "recusado"
    return erro


async def test_texto_em_pedacos_e_uso_de_tokens():
    cliente, pedidos = _cliente(
        [
            # O Azure abre o fluxo com um chunk sem `choices` (resultado do filtro
            # do prompt). Nao pode virar evento nem quebrar.
            _chunk([]),
            _chunk([_delta(role="assistant", content="Pot")]),
            _chunk([_delta(content="ência ok.")]),
            _chunk([_delta(finish="stop")]),
            _chunk(
                [],
                usage={
                    "prompt_tokens": 120,
                    "completion_tokens": 8,
                    "total_tokens": 128,
                    "prompt_tokens_details": {"cached_tokens": 64},
                },
            ),
        ]
    )

    eventos = await _eventos(cliente)

    assert [e.texto for e in eventos if isinstance(e, TextoDelta)] == ["Pot", "ência ok."]
    fim = eventos[-1]
    assert isinstance(fim, FimDaRodada)
    assert (fim.motivo, fim.tokens_entrada, fim.tokens_saida) == ("stop", 120, 8)
    assert fim.tokens_em_cache == 64
    assert pedidos[0]["model"] == "gpt-teste"
    assert pedidos[0]["stream"] is True
    assert "tools" not in pedidos[0]


async def test_tool_calls_montadas_a_partir_dos_pedacos():
    tc = lambda indice, **campos: {"index": indice, **campos}  # noqa: E731
    cliente, pedidos = _cliente(
        [
            _chunk(
                [
                    _delta(
                        tool_calls=[
                            tc(
                                0,
                                id="call_a",
                                type="function",
                                function={"name": "tarifas", "arguments": ""},
                            )
                        ]
                    )
                ]
            ),
            _chunk(
                [
                    _delta(
                        tool_calls=[
                            tc(
                                1,
                                id="call_b",
                                type="function",
                                function={"name": "serie_", "arguments": '{"di'},
                            )
                        ]
                    )
                ]
            ),
            _chunk(
                [_delta(tool_calls=[tc(1, function={"name": "diaria", "arguments": 'as": 7}'})])]
            ),
            _chunk([_delta(finish="tool_calls")]),
        ]
    )

    eventos = await _eventos(cliente, ferramentas=[{"type": "function", "function": {"name": "x"}}])

    fim = eventos[-1]
    assert fim.motivo == "tool_calls"
    assert [(c.id, c.nome, c.argumentos) for c in fim.chamadas] == [
        ("call_a", "tarifas", "{}"),
        ("call_b", "serie_diaria", '{"dias": 7}'),
    ]
    assert pedidos[0]["tools"] and pedidos[0]["parallel_tool_calls"] is True


async def test_saida_barrada_no_meio_do_fluxo():
    cliente, _ = _cliente(
        [_chunk([_delta(content="parcial")]), _chunk([_delta(finish="content_filter")])]
    )
    with pytest.raises(ConteudoBloqueado) as exc:
        await _eventos(cliente)
    assert exc.value.categoria == "saida"


async def test_prompt_barrado_pelo_prompt_shield_diz_a_categoria():
    corpo = {
        "error": {
            "code": "content_filter",
            "message": "The response was filtered",
            "innererror": {
                "code": "ResponsibleAIPolicyViolation",
                "content_filter_result": {
                    "hate": {"filtered": False, "severity": "safe"},
                    "jailbreak": {"filtered": True, "detected": True},
                },
            },
        }
    }
    cliente, _ = _cliente(_erro_400(corpo))
    with pytest.raises(ConteudoBloqueado) as exc:
        await _eventos(cliente)
    assert exc.value.categoria == "jailbreak"


async def test_400_que_nao_e_filtro_vira_falha_do_modelo():
    cliente, _ = _cliente(_erro_400({"error": {"code": "invalid_request", "message": "x"}}))
    with pytest.raises(FalhaDoModelo):
        await _eventos(cliente)


async def test_temperatura_nula_nao_e_enviada(monkeypatch):
    cliente, pedidos = _cliente([_chunk([_delta(finish="stop")])])
    monkeypatch.setattr(cliente._settings, "azure_openai_temperature", None)
    await _eventos(cliente)
    assert "temperature" not in pedidos[0]
