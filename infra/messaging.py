"""Porta de fila (ADR-0014). Entrega pelo menos uma vez, sem ordem; mensagens pequenas (IDs e chave do zip)."""
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass
class Message:
    id: str
    body: bytes  # JSON com schema_version
    attempt: int = 1


class Defer(Exception):
    """O handler levanta para adiar a mensagem sem contar como falha (ex.: limite de ritmo da conta).

    Diferente de qualquer outra exceção, não incrementa `attempt` nem leva à DLQ: a mensagem volta à fila após `delay`
    segundos (aproximado nos adaptadores reais).
    """

    def __init__(self, delay, reason=""):
        super().__init__(reason or f"adiado por {delay:.0f}s")
        self.delay = delay


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
        self.deferred = defaultdict(list)  # topic -> [(Message, delay)]; `release_deferred` devolve à fila
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
            except Defer as d:
                self.deferred[topic].append((msg, d.delay))  # sem delay real: o teste libera com release_deferred
            except Exception:
                if msg.attempt >= self.max_attempts:
                    self.dead_letters[topic].append(msg)
                else:
                    pending.append(Message(msg.id, msg.body, msg.attempt + 1))

    def release_deferred(self, topic):
        """Simula o fim do atraso: as mensagens adiadas voltam à fila, com a mesma tentativa."""
        for msg, _ in self.deferred[topic]:
            self._topics[topic].append(msg)
        self.deferred[topic] = []
