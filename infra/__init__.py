"""Fila e storage plugáveis (ADR-0014). Única parte do código que conhece os provedores é `new_queue`/`new_storage`.

Adaptadores com dependências (`s3.py`, `rabbitmq.py`) só são importados quando o driver é escolhido; o resto é stdlib.

O pacote não se chama `platform` (como no ADR) para não sombrear o módulo da stdlib que o Selenium importa.
"""
import os

from .messaging import Defer, MemoryQueue, Message, Queue
from .storage import FsStorage, ObjectStorage

__all__ = ["Defer", "MemoryQueue", "Message", "Queue", "FsStorage", "ObjectStorage", "new_queue", "new_storage"]


def _required(env, *names):
    missing = [n for n in names if not env.get(n)]
    if missing:
        raise ValueError("variáveis obrigatórias ausentes: " + ", ".join(missing))
    return [env[n] for n in names]


def new_storage(env=os.environ):
    """`STORAGE_DRIVER`: `fs` (padrão; raiz em `STORAGE_FS_ROOT`, padrão `./output`) ou `s3`
    (`S3_BUCKET`, `S3_ENDPOINT` opcional p/ S3Mock/LocalStack, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`). `gcs` não implementado."""
    driver = env.get("STORAGE_DRIVER", "fs")
    if driver == "fs":
        return FsStorage(env.get("STORAGE_FS_ROOT", "./output"))
    if driver == "s3":
        (bucket,) = _required(env, "S3_BUCKET")
        from .s3 import S3Storage  # boto3 só é importado se o driver é usado
        return S3Storage(bucket, env.get("S3_ENDPOINT"), env.get("S3_ACCESS_KEY"), env.get("S3_SECRET_KEY"),
                         env.get("S3_REGION", "us-east-1"))
    raise ValueError(f"STORAGE_DRIVER={driver!r} não implementado (disponíveis: fs, s3)")


def new_queue(env=os.environ):
    """`QUEUE_DRIVER`; sem ele devolve None (coleta sem publicar). `memory` (testes) ou `rabbitmq` (`AMQP_URL`).
    `sqs`/`pubsub` não implementados."""
    driver = env.get("QUEUE_DRIVER")
    if not driver:
        return None
    if driver == "memory":
        return MemoryQueue()
    if driver == "rabbitmq":
        (url,) = _required(env, "AMQP_URL")
        from .rabbitmq import RabbitMQQueue  # pika só é importado se o driver é usado
        return RabbitMQQueue(url)
    raise ValueError(f"QUEUE_DRIVER={driver!r} não implementado (disponíveis: memory, rabbitmq)")
