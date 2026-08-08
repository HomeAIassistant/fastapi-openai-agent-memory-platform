"""Typed FastAPI dependencies for initialized service components."""

from fastapi import Request

from ..memory.policy import WritePolicy
from ..stores.database import MemoryRepository
from ..stores.embeddings import EmbeddingProvider


def get_repository(request: Request) -> MemoryRepository:
    """Return the initialized memory repository."""

    return request.app.state.repository


def get_policy(request: Request) -> WritePolicy:
    """Return the loaded write policy."""

    return request.app.state.policy


def get_embeddings(request: Request) -> EmbeddingProvider:
    """Return the configured embedding provider."""

    return request.app.state.embeddings
