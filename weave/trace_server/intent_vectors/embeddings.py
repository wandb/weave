from __future__ import annotations

import math
import threading
from abc import ABC, abstractmethod
from collections import OrderedDict

from openai import OpenAI

from weave.trace_server.intent_vectors import config, metrics


def normalize_text(value: str) -> str:
    normalized = " ".join(value.lower().split())
    if not normalized:
        raise ValueError("text must not be empty after normalization")
    if len(normalized) > config.MAX_SIGNATURE_CHARS:
        raise ValueError(
            f"normalized text exceeds {config.MAX_SIGNATURE_CHARS} characters"
        )
    return normalized


def l2_normalize(vector: list[float]) -> list[float]:
    if len(vector) != config.EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"embedding has {len(vector)} dimensions; expected {config.EMBEDDING_DIMENSIONS}"
        )
    norm = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(norm) or norm == 0:
        raise ValueError("embedding must have a finite non-zero norm")
    return [float(value / norm) for value in vector]


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> dict[str, list[float]]: ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, client: OpenAI | None = None) -> None:
        self._client = client
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()

    def embed(self, texts: list[str]) -> dict[str, list[float]]:
        normalized = list(dict.fromkeys(normalize_text(text) for text in texts))
        vectors: dict[str, list[float]] = {}
        misses: list[str] = []
        with self._lock:
            for text in normalized:
                vector = self._cache.get(text)
                if vector is None:
                    misses.append(text)
                else:
                    self._cache.move_to_end(text)
                    vectors[text] = vector
        metrics.emit(
            "embedding_cache",
            hits=len(normalized) - len(misses),
            misses=len(misses),
        )
        for start in range(0, len(misses), config.EMBEDDING_BATCH_SIZE):
            batch = misses[start : start + config.EMBEDDING_BATCH_SIZE]
            client = self._client
            if client is None:
                client = OpenAI()
                self._client = client
            with metrics.timed("embedding_call", batch_size=len(batch)):
                response = client.embeddings.create(
                    model=config.EMBEDDING_MODEL,
                    input=batch,
                    dimensions=config.EMBEDDING_DIMENSIONS,
                )
            by_index = sorted(response.data, key=lambda item: item.index)
            if len(by_index) != len(batch):
                raise RuntimeError("embedding response length did not match request")
            for text, item in zip(batch, by_index, strict=True):
                vectors[text] = l2_normalize(item.embedding)
        with self._lock:
            for text in misses:
                self._cache[text] = vectors[text]
                self._cache.move_to_end(text)
            while len(self._cache) > config.EMBEDDING_CACHE_SIZE:
                self._cache.popitem(last=False)
        return vectors
