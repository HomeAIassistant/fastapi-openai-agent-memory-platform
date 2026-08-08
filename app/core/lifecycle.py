"""FastAPI lifespan initialization for the memory service graph."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..memory.policy import load_write_policy
from ..stores.database import MemoryRepository, PostgresMemoryRepository
from ..stores.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from .settings import Settings

logger = logging.getLogger(__name__)


def _build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "openai":
        assert settings.openai_api_key is not None  # enforced by Settings validation
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    return DeterministicEmbeddingProvider(dimensions=settings.embedding_dimensions)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load policy, construct the repository/embedding graph, and apply schema."""

    settings: Settings = app.state.settings
    policy = load_write_policy(settings.policy_path)
    embeddings = _build_embedding_provider(settings)
    repository: MemoryRepository = PostgresMemoryRepository(
        settings.database_url, dimensions=settings.embedding_dimensions
    )
    repository.initialize()

    app.state.policy = policy
    app.state.embeddings = embeddings
    app.state.repository = repository
    logger.info(
        "Loaded write policy (%d allowed types) and %s embedding provider",
        len(policy.allowed_types),
        settings.embedding_provider,
    )
    yield
