"""Porta de storage de objetos (ADR-0014). Os zips de coleta são imutáveis (ADR-0010): `put` nunca sobrescreve."""
import os
from typing import Protocol


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes) -> None:
        """Grava o objeto; FileExistsError se a chave já existe."""

    def get(self, key: str) -> bytes: ...


class FsStorage:
    """Adaptador de sistema de arquivos: chave = caminho relativo a `root`."""

    def __init__(self, root):
        self.root = os.path.abspath(root)

    def _path(self, key):
        path = os.path.abspath(os.path.join(self.root, key))
        if os.path.commonpath([self.root, path]) != self.root:
            raise ValueError(f"chave fora do storage: {key!r}")
        return path

    def put(self, key, data):
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "xb") as f:
            f.write(data)

    def get(self, key):
        with open(self._path(key), "rb") as f:
            return f.read()
