"""Verify PostgresMemoryRepository wraps driver failures cleanly.

Connects to a closed local port so these fail fast (no live Postgres
required) while still exercising the real `psycopg.Error` handling path.
"""

from datetime import UTC, datetime

import pytest

from app.memory.models import MemoryProvenance, MemoryRecord, MemoryScope
from app.stores.database import MemoryRepositoryError, PostgresMemoryRepository

UNREACHABLE_DSN = "postgresql://baduser:secret-password@127.0.0.1:1/nonexistent"


@pytest.fixture
def repository() -> PostgresMemoryRepository:
    return PostgresMemoryRepository(UNREACHABLE_DSN, dimensions=8)


def _sample_record() -> MemoryRecord:
    return MemoryRecord(
        memory_id="mem_test",
        type="fact",
        scope=MemoryScope(tenant_id="home", project_id="henley"),
        content="test content",
        provenance=MemoryProvenance(source_type="agent_run"),
        confidence=1.0,
        created_at=datetime.now(UTC),
        expires_at=None,
        supersedes=None,
        sensitivity="internal",
        write_status="approved",
    )


def test_initialize_raises_clean_error_and_hides_credentials(
    repository: PostgresMemoryRepository,
) -> None:
    with pytest.raises(MemoryRepositoryError) as excinfo:
        repository.initialize()
    assert "secret-password" not in str(excinfo.value)


def test_create_raises_clean_error(repository: PostgresMemoryRepository) -> None:
    with pytest.raises(MemoryRepositoryError) as excinfo:
        repository.create(_sample_record(), embedding=[0.1] * 8)
    assert "secret-password" not in str(excinfo.value)


def test_get_raises_clean_error(repository: PostgresMemoryRepository) -> None:
    with pytest.raises(MemoryRepositoryError) as excinfo:
        repository.get("mem_test", tenant_id="home", project_id="henley")
    assert "secret-password" not in str(excinfo.value)


def test_search_raises_clean_error(repository: PostgresMemoryRepository) -> None:
    with pytest.raises(MemoryRepositoryError) as excinfo:
        repository.search(
            scope=MemoryScope(tenant_id="home", project_id="henley"),
            query_embedding=[0.1] * 8,
            top_k=5,
            types=None,
            include_pending=False,
        )
    assert "secret-password" not in str(excinfo.value)


def test_health_returns_false_instead_of_raising(
    repository: PostgresMemoryRepository,
) -> None:
    assert repository.health() is False
