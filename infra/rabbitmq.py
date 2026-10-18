"""Adaptador de fila sobre RabbitMQ (pika). Usa só filas duráveis na exchange padrão: nada de exchanges/routing keys na regra de negócio.

Cada tópico é uma fila durável `<topic>` com DLQ `<topic>.dlq`. Falha no handler = nova publicação com `x-attempt`
incrementado após backoff; ao estourar `max_attempts` a mensagem vai para a DLQ.
"""
import uuid

import pika

ATTEMPT_HEADER = "x-attempt"


def default_backoff(attempt):
    return min(2 ** attempt, 30)


class RabbitMQQueue:
    def __init__(self, url, max_attempts=5, backoff=default_backoff, idle_timeout=None, retry_delay=30):
        """`idle_timeout` (s): `consume` retorna após esse tempo sem mensagens; None = bloqueia para sempre (produção)."""
        self.params = pika.URLParameters(url)
        self.max_attempts = max_attempts
        self.backoff = backoff
        self.idle_timeout = idle_timeout
        self.retry_delay = retry_delay  # segundos na fila `<topic>.retry` antes de voltar (fixo por fila: mudar exige recriá-la)

    def _declare(self, channel, topic):
        channel.queue_declare(f"{topic}.dlq", durable=True)
        # Fila de adiamento (Defer): o TTL da fila + dead-letter de volta para `<topic>` faz o atraso sem plugin
        channel.queue_declare(f"{topic}.retry", durable=True, arguments={
            "x-message-ttl": int(self.retry_delay * 1000),
            "x-dead-letter-exchange": "", "x-dead-letter-routing-key": topic})
        channel.queue_declare(topic, durable=True, arguments={
            "x-dead-letter-exchange": "", "x-dead-letter-routing-key": f"{topic}.dlq"})

    def _publish(self, channel, topic, body, attempt, message_id=None):
        self._publish_to(channel, topic, topic, body, attempt, message_id)

    def _publish_to(self, channel, routing_key, topic, body, attempt, message_id=None):
        channel.basic_publish("", routing_key, body, pika.BasicProperties(
            delivery_mode=pika.DeliveryMode.Persistent, message_id=message_id or uuid.uuid4().hex,
            headers={ATTEMPT_HEADER: attempt}))

    def publish(self, topic, body):
        with pika.BlockingConnection(self.params) as conn:
            channel = conn.channel()
            self._declare(channel, topic)
            self._publish(channel, topic, body, attempt=1)

    def consume(self, topic, handle):
        from . import Defer, Message  # import tardio: evita ciclo com __init__
        with pika.BlockingConnection(self.params) as conn:
            channel = conn.channel()
            self._declare(channel, topic)
            channel.basic_qos(prefetch_count=1)
            for method, props, body in channel.consume(topic, inactivity_timeout=self.idle_timeout or 1):
                if method is None:  # inatividade
                    if self.idle_timeout is not None:
                        break
                    continue
                attempt = (props.headers or {}).get(ATTEMPT_HEADER, 1)
                msg = Message(id=props.message_id or str(method.delivery_tag), body=body, attempt=attempt)
                try:
                    handle(msg)
                except Defer:
                    # Não é falha: vai para `<topic>.retry` com a mesma tentativa e volta após `retry_delay`
                    self._publish_to(channel, f"{topic}.retry", topic, body, attempt, msg.id)
                    channel.basic_ack(method.delivery_tag)
                except Exception:
                    if attempt >= self.max_attempts:
                        channel.basic_nack(method.delivery_tag, requeue=False)  # vai para a DLQ
                    else:
                        conn.sleep(self.backoff(attempt))
                        self._publish(channel, topic, body, attempt + 1, msg.id)
                        channel.basic_ack(method.delivery_tag)
                else:
                    channel.basic_ack(method.delivery_tag)
            channel.cancel()
