"""Fila e storage plugáveis (ADR-0014). Única parte do código que conhece os provedores é `new_queue`/`new_storage`.

O pacote não se chama `platform` (como no ADR) para não sombrear o módulo da stdlib que o Selenium importa.
"""
import os

from .messaging import MemoryQueue, Message, Queue
from .storage import FsStorage, ObjectStorage

__all__ = ["MemoryQueue", "Message", "Queue", "FsStorage", "ObjectStorage", "new_queue", "new_storage"]


def new_storage(env=os.environ):
    """`STORAGE_DRIVER` (padrão `fs`, raiz em `STORAGE_FS_ROOT`, padrão `./output`). `s3`/`gcs` ainda não implementados."""
    driver = env.get("STORAGE_DRIVER", "fs")
    if driver == "fs":
        return FsStorage(env.get("STORAGE_FS_ROOT", "./output"))
    raise ValueError(f"STORAGE_DRIVER={driver!r} não implementado (disponíveis: fs)")


def new_queue(env=os.environ):
    """`QUEUE_DRIVER`; sem ele devolve None (coleta sem publicar). `rabbitmq`/`sqs`/`pubsub` ainda não implementados."""
    driver = env.get("QUEUE_DRIVER")
    if not driver:
        return None
    if driver == "memory":
        return MemoryQueue()
    raise ValueError(f"QUEUE_DRIVER={driver!r} não implementado (disponíveis: memory)")
