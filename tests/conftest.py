"""Shared fixtures: an app wired to in-memory, network-free test doubles.

Tests never start the real `lifespan` (which would connect to Postgres).
Instead `client` builds the app and sets `app.state` directly, so the whole
suite runs offline against `InMemoryMemoryRepository` and
`DeterministicEmbeddingProvider`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.factory import create_app
from app.core.settings import Settings
from app.memory.policy import load_write_policy
from app.stores.database import InMemoryMemoryRepository
from app.stores.embeddings import DeterministicEmbeddingProvider

TEST_TOKEN = "test-bearer-token-0123456789abcdefABCDEF"
POLICY_PATH = Path(__file__).resolve().parent.parent / "config" / "policy.yaml"


@pytest.fixture
def settings() -> Settings:
    """Return validated settings that never touch a real database or network."""

    return Settings(
        memory_api_token=TEST_TOKEN,
        database_url="postgresql://unused:unused@localhost/unused",
        embedding_provider="deterministic",
        embedding_dimensions=32,
        policy_path=POLICY_PATH,
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    """Return a TestClient wired to in-memory, network-free test doubles."""

    app = create_app(settings)
    app.state.policy = load_write_policy(settings.policy_path)
    app.state.repository = InMemoryMemoryRepository()
    app.state.embeddings = DeterministicEmbeddingProvider(
        dimensions=settings.embedding_dimensions
    )
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Return the bearer header matching `TEST_TOKEN`."""

    return {"Authorization": f"Bearer {TEST_TOKEN}"}
