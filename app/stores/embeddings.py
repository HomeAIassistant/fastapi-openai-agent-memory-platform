"""Pluggable embedding backends behind one narrow interface.

`EmbeddingProvider` lets a real semantic provider (OpenAI) and a network-free
deterministic provider used by tests and local development share one
interface and one vector length, so the storage and ranking code never knows
which backend produced a vector.
"""

from __future__ import annotations

import hashlib
import struct
from typing import Protocol

import httpx


class EmbeddingProvider(Protocol):
    """Turns text into a fixed-length vector for storage and search."""

    dimensions: int

    def embed(self, text: str) -> list[float]:
        """Return a `dimensions`-length vector for the given text."""
        ...


class DeterministicEmbeddingProvider:
    """Reproducible offline pseudo-embedding for tests and local development.

    This is not a semantic embedding: it carries no notion of meaning, so
    similarity search against it only exercises the storage and ranking code
    paths, never real retrieval quality. Production deployments must set
    MEMORY_EMBEDDING_PROVIDER=openai.
    """

    def __init__(self, dimensions: int = 1536) -> None:
        """Configure the vector length hashed content is expanded to."""

        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        """Hash `text` into a stable pseudo-random unit-range vector."""

        normalized = text.strip().lower().encode("utf-8")
        vector: list[float] = []
        counter = 0
        while len(vector) < self.dimensions:
            digest = hashlib.sha256(normalized + counter.to_bytes(4, "big")).digest()
            for offset in range(0, len(digest) - 3, 4):
                if len(vector) >= self.dimensions:
                    break
                (raw,) = struct.unpack_from(">I", digest, offset)
                vector.append((raw / 0xFFFFFFFF) * 2.0 - 1.0)
            counter += 1
        return vector


class OpenAIEmbeddingProvider:
    """Real semantic embeddings through the OpenAI embeddings API."""

    def __init__(self, *, api_key: str, model: str, dimensions: int) -> None:
        """Construct an authenticated client for the given model and width."""

        self.dimensions = dimensions
        self._model = model
        self._client = httpx.Client(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    def embed(self, text: str) -> list[float]:
        """Call the OpenAI embeddings API and return the resulting vector."""

        response = self._client.post(
            "/embeddings",
            json={"model": self._model, "input": text, "dimensions": self.dimensions},
        )
        response.raise_for_status()
        payload = response.json()
        embedding: list[float] = payload["data"][0]["embedding"]
        return embedding
