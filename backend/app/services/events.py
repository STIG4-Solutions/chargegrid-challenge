"""Barramento de eventos em memoria para o WebSocket do dashboard.

O SEMS+ so oferece consulta (pull) - o operador ficaria olhando uma tela que so
atualiza no F5. Aqui o poller publica e o navegador recebe push.

Em producao com mais de uma instancia, trocar por Redis pub/sub: a interface
publish/subscribe permanece igual.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from app.core.logging import get_logger

log = get_logger(__name__)

# Fila pequena de proposito: cliente lento perde eventos antigos em vez de
# segurar memoria do servidor - o proximo snapshot ja traz o estado corrente.
QUEUE_SIZE = 32


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, topic: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._subscribers[topic].add(queue)
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        self._subscribers[topic].discard(queue)
        if not self._subscribers[topic]:
            self._subscribers.pop(topic, None)

    async def publish(self, topic: str, event_type: str, payload: dict[str, Any]) -> None:
        message = {"type": event_type, "topic": topic, "data": payload}
        for queue in list(self._subscribers.get(topic, ())):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()  # descarta o mais antigo
                    queue.put_nowait(message)
                except asyncio.QueueEmpty:  # pragma: no cover
                    pass

    @property
    def topics(self) -> list[str]:
        return list(self._subscribers)


bus = EventBus()


def site_topic(site_id) -> str:
    return f"site:{site_id}"
