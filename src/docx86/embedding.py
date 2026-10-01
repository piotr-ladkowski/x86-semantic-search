"""Text embedders. All return L2-normalised float32 vectors, so cosine similarity = dot product."""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

import numpy as np

from .config import Settings


class Embedder(Protocol):
    id: str  # recorded in the index; an index is only valid for the embedder that built it
    dim: int

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


def _normalise(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, dtype=np.float32)
    norms = np.linalg.norm(m, axis=-1, keepdims=True)
    return m / np.where(norms == 0, 1, norms)


class HashEmbedder:
    """Hashed bag of words + bigrams. Deterministic and dependency-free, but purely lexical.

    Exists so tests and offline development need no model download. Never deploy it.
    """

    dim = 512
    id = "hash:v1"

    @staticmethod
    def _tokens(text: str) -> list[str]:
        words = re.findall(r"[a-z0-9]+", text.lower())
        return words + [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for tok in self._tokens(text):
            h = int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "little")
            v[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        return v

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return _normalise(np.stack([self._vec(t) for t in texts]))

    def embed_query(self, text: str) -> np.ndarray:
        return _normalise(self._vec(text))


class FastEmbedEmbedder:
    """ONNX embeddings via fastembed (no PyTorch). Default model: BAAI/bge-small-en-v1.5."""

    def __init__(self, model_name: str, cache_dir: str, threads: int, offline: bool):
        from fastembed import TextEmbedding  # heavy import; keep it out of the hash path

        self._model = TextEmbedding(
            model_name=model_name,
            cache_dir=cache_dir,
            threads=threads,
            local_files_only=offline,
        )
        self.id = f"fastembed:{model_name}"
        self.dim = int(self._model.embedding_size)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return _normalise(np.stack(list(self._model.passage_embed(texts))))

    def embed_query(self, text: str) -> np.ndarray:
        return _normalise(next(iter(self._model.query_embed(text))))


def get_embedder(settings: Settings) -> Embedder:
    if settings.embedder == "hash":
        return HashEmbedder()
    return FastEmbedEmbedder(
        settings.model_name,
        str(settings.model_cache_dir),
        settings.embed_threads,
        settings.model_offline,
    )
