"""FastAPI lifespan initialization for the memory service graph."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..memory.policy import PolicyConfigError, load_write_policy
from ..stores.database import (
    MemoryRepository,
    MemoryRepositoryError,
    PostgresMemoryRepository,
)
from ..stores.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from .settings import Settings

logger = logging.getLogger(__name__)


def _build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Select and construct the embedding provider named by `settings`."""

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
    """Load policy, construct the repository/embedding graph, and apply schema.

    Startup failures are logged with a clear stage label and then re-raised
    unchanged, so the process fails fast (and Docker's healthcheck never
    reports healthy) instead of serving requests against a half-built graph.
    """

    settings: Settings = app.state.settings

    try:
        policy = load_write_policy(settings.policy_path)
    except PolicyConfigError:
        logger.exception("Startup failed while loading the write policy")
        raise

    embeddings = _build_embedding_provider(settings)

    repository: MemoryRepository = PostgresMemoryRepository(
        settings.database_url, dimensions=settings.embedding_dimensions
    )
    try:
        repository.initialize()
    except MemoryRepositoryError:
        logger.exception("Startup failed while applying the database schema")
        raise

    app.state.policy = policy
    app.state.embeddings = embeddings
    app.state.repository = repository
    logger.info(
        "Loaded write policy (%d allowed types) and %s embedding provider",
        len(policy.allowed_types),
        settings.embedding_provider,
    )
    yield
