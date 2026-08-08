"""Verify storage/embedding failures surface as clean 503s, not raw 500s."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.factory import create_app
from app.core.settings import Settings
from app.memory.models import MemoryRecord, MemoryScope
from app.memory.policy import load_write_policy
from app.stores.database import MemoryRepositoryError
from app.stores.embeddings import EmbeddingProviderError

from .conftest import POLICY_PATH, TEST_TOKEN

BASE_PAYLOAD = {
    "type": "preference",
    "scope": {"tenant_id": "home", "project_id": "henley"},
    "content": "content",
    "provenance": {"source_type": "agent_run"},
}


class FailingRepository:
    """A MemoryRepository double whose every method raises MemoryRepositoryError."""

    def initialize(self) -> None:
        return None

    def health(self) -> bool:
        return False

    def create(self, record: MemoryRecord, *, embedding: list[float]) -> None:
        raise MemoryRepositoryError("failed to store the memory")

    def get(
        self, memory_id: str, *, tenant_id: str, project_id: str
    ) -> MemoryRecord | None:
        raise MemoryRepositoryError("failed to fetch the memory")

    def search(
        self,
        *,
        scope: MemoryScope,
        query_embedding: list[float],
        top_k: int,
        types: list[str] | None,
        include_pending: bool,
    ) -> list[tuple[MemoryRecord, float]]:
        raise MemoryRepositoryError("failed to search memories")


class FailingEmbeddingProvider:
    """An EmbeddingProvider double whose `embed` always raises."""

    dimensions = 8

    def embed(self, text: str) -> list[float]:
        raise EmbeddingProviderError(
            "the embedding provider is temporarily unavailable"
        )


class WorkingEmbeddingProvider:
    """A trivial EmbeddingProvider double that always succeeds."""

    dimensions = 8

    def embed(self, text: str) -> list[float]:
        return [0.1] * self.dimensions


@pytest.fixture
def settings() -> Settings:
    return Settings(
        memory_api_token=TEST_TOKEN,
        database_url="postgresql://unused:unused@localhost/unused",
        embedding_provider="deterministic",
        embedding_dimensions=8,
        policy_path=POLICY_PATH,
    )


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


def _client_with(
    settings: Settings, *, repository: object, embeddings: object
) -> TestClient:
    app = create_app(settings)
    app.state.policy = load_write_policy(settings.policy_path)
    app.state.repository = repository
    app.state.embeddings = embeddings
    return TestClient(app)


def test_create_memory_returns_503_when_storage_fails(
    settings: Settings, auth_headers: dict[str, str]
) -> None:
    client = _client_with(
        settings, repository=FailingRepository(), embeddings=WorkingEmbeddingProvider()
    )
    response = client.post("/memories", json=BASE_PAYLOAD, headers=auth_headers)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "storage_unavailable"


def test_create_memory_returns_503_when_embedding_fails(
    settings: Settings, auth_headers: dict[str, str]
) -> None:
    client = _client_with(
        settings, repository=FailingRepository(), embeddings=FailingEmbeddingProvider()
    )
    response = client.post("/memories", json=BASE_PAYLOAD, headers=auth_headers)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "embedding_unavailable"


def test_get_memory_returns_503_when_storage_fails(
    settings: Settings, auth_headers: dict[str, str]
) -> None:
    client = _client_with(
        settings, repository=FailingRepository(), embeddings=WorkingEmbeddingProvider()
    )
    response = client.get(
        "/memories/mem_x",
        params={"tenant_id": "home", "project_id": "henley"},
        headers=auth_headers,
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "storage_unavailable"


def test_search_returns_503_when_embedding_fails(
    settings: Settings, auth_headers: dict[str, str]
) -> None:
    client = _client_with(
        settings, repository=FailingRepository(), embeddings=FailingEmbeddingProvider()
    )
    response = client.post(
        "/memories/search",
        json={"scope": {"tenant_id": "home", "project_id": "henley"}, "query": "q"},
        headers=auth_headers,
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "embedding_unavailable"


def test_search_returns_503_when_storage_fails(
    settings: Settings, auth_headers: dict[str, str]
) -> None:
    client = _client_with(
        settings, repository=FailingRepository(), embeddings=WorkingEmbeddingProvider()
    )
    response = client.post(
        "/memories/search",
        json={"scope": {"tenant_id": "home", "project_id": "henley"}, "query": "q"},
        headers=auth_headers,
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "storage_unavailable"
