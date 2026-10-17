"""Porta de fila (ADR-0014). Entrega pelo menos uma vez, sem ordem; mensagens pequenas (IDs e chave do zip)."""
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass
class Message:
    id: str
    body: bytes  # JSON com schema_version
    attempt: int = 1


class Queue(Protocol):
    def publish(self, topic: str, body: bytes) -> None: ...

    def consume(self, topic: str, handle: Callable[[Message], None]) -> None:
        """Exceção no handler = reentrega (com backoff, no adaptador). Os adaptadores reais bloqueiam."""


class MemoryQueue:
    """Adaptador para testes. Diferente dos reais, `consume` retorna quando a fila esvazia.

    Mensagem que falha `max_attempts` vezes vai para `dead_letters` (a DLQ dos adaptadores reais).
    """

    def __init__(self, max_attempts=3):
        self.max_attempts = max_attempts
        self.dead_letters = defaultdict(list)
        self._topics = defaultdict(deque)
        self._seq = 0

    def publish(self, topic, body):
        self._seq += 1
        self._topics[topic].append(Message(id=str(self._seq), body=body))

    def consume(self, topic, handle):
        pending = self._topics[topic]
        while pending:
            msg = pending.popleft()
            try:
                handle(msg)
            except Exception:
                if msg.attempt >= self.max_attempts:
                    self.dead_letters[topic].append(msg)
                else:
                    pending.append(Message(msg.id, msg.body, msg.attempt + 1))
