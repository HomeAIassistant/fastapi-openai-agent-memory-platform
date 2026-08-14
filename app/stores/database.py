"""PostgreSQL + pgvector persistence and a deterministic in-memory test double.

`MemoryRepository` is a narrow Protocol so `PostgresMemoryRepository` can
later be supplemented or replaced (for example by Qdrant) without changing
the API or policy layers, and so unit tests can run against
`InMemoryMemoryRepository` without a live database.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row

from ..memory.models import MemoryProvenance, MemoryRecord, MemoryScope

logger = logging.getLogger(__name__)


class MemoryRepositoryError(RuntimeError):
    """Raised when a storage operation fails.

    The message is always a safe, generic diagnostic; it never includes the
    connection string, query text, or the underlying driver exception text,
    since psycopg error messages can echo back connection parameters. The
    real exception is chained (`raise ... from exc`) and logged server-side
    for operators, not returned to callers.
    """


def schema_sql(dimensions: int) -> str:
    """Return the idempotent service schema for the given embedding width.

    `dimensions` always comes from validated process settings (never request
    input), so interpolating it into DDL here is safe.
    """

    return f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memories (
  memory_id text PRIMARY KEY,
  type text NOT NULL,
  tenant_id text NOT NULL,
  project_id text NOT NULL,
  user_id text,
  agent_id text,
  content text NOT NULL,
  source_type text NOT NULL,
  run_id text,
  source_id text,
  confidence double precision NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  created_at timestamptz NOT NULL,
  expires_at timestamptz,
  supersedes text,
  sensitivity text NOT NULL,
  write_status text NOT NULL,
  embedding vector({dimensions}) NOT NULL
);

CREATE INDEX IF NOT EXISTS memories_scope_idx
  ON memories (tenant_id, project_id, agent_id);

CREATE INDEX IF NOT EXISTS memories_embedding_idx
  ON memories USING hnsw (embedding vector_cosine_ops);
"""


def _vector_literal(embedding: list[float]) -> str:
    """Render a vector as the text literal pgvector's input parser accepts."""

    return "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"


def _row_to_record(row: dict[str, Any]) -> MemoryRecord:
    """Map one `memories` row (as returned by `dict_row`) to a `MemoryRecord`."""

    return MemoryRecord(
        memory_id=row["memory_id"],
        type=row["type"],
        scope=MemoryScope(
            tenant_id=row["tenant_id"],
            project_id=row["project_id"],
            user_id=row["user_id"],
            agent_id=row["agent_id"],
        ),
        content=row["content"],
        provenance=MemoryProvenance(
            source_type=row["source_type"],
            run_id=row["run_id"],
            source_id=row["source_id"],
        ),
        confidence=row["confidence"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        supersedes=row["supersedes"],
        sensitivity=row["sensitivity"],
        write_status=row["write_status"],
    )


class MemoryRepository(Protocol):
    """Storage boundary for long-term memory records.

    `initialize`, `create`, `get`, and `search` raise `MemoryRepositoryError`
    on a storage failure; `health` never raises and instead returns `False`,
    since it exists specifically to be safe to call from `/ready`.
    """

    def initialize(self) -> None:
        """Apply the idempotent service schema.

        Raises:
            MemoryRepositoryError: If the schema could not be applied.
        """
        ...

    def health(self) -> bool:
        """Verify a minimal round trip to the backing store; never raises."""
        ...

    def create(self, record: MemoryRecord, *, embedding: list[float]) -> None:
        """Durably store one already-validated, policy-resolved record.

        Raises:
            MemoryRepositoryError: If the record could not be stored.
        """
        ...

    def get(
        self, memory_id: str, *, tenant_id: str, project_id: str
    ) -> MemoryRecord | None:
        """Fetch one record, scoped to the caller's tenant/project.

        Raises:
            MemoryRepositoryError: If the lookup could not be performed.
        """
        ...

    def search(
        self,
        *,
        scope: MemoryScope,
        query_embedding: list[float],
        top_k: int,
        types: list[str] | None,
        include_pending: bool,
    ) -> list[tuple[MemoryRecord, float]]:
        """Return the top-k records in scope ranked by descending similarity.

        Raises:
            MemoryRepositoryError: If the search could not be performed.
        """
        ...


#: Bounds how long a connection attempt or a per-request statement may take,
#: so a down/unresponsive Postgres fails a write/read/search within seconds
#: (as a MemoryRepositoryError, translated to a 503) instead of hanging the
#: request indefinitely. `/ready` is unaffected by this doc note: it calls
#: `health()`, which catches `psycopg.Error` itself and returns `False`
#: rather than raising.
_CONNECT_TIMEOUT_SECONDS = 5
_STATEMENT_TIMEOUT_MS = 10_000

#: `initialize()` runs `CREATE INDEX ... USING hnsw`, which — unlike a
#: per-request query — can legitimately take much longer than
#: `_STATEMENT_TIMEOUT_MS` once the table holds many rows (first startup
#: against an existing large table, or a rebuild after a pgvector
#: upgrade/restore). It still needs a bound so a truly stuck statement
#: doesn't hang startup forever, just a much more generous one.
_SCHEMA_STATEMENT_TIMEOUT_MS = 300_000


class PostgresMemoryRepository:
    """PostgreSQL + pgvector implementation with scope predicates on every query."""

    def __init__(self, database_url: str, *, dimensions: int) -> None:
        """Store the DSN and embedding width without opening a connection."""

        self._database_url = database_url
        self._dimensions = dimensions

    def _connect(
        self, *, statement_timeout_ms: int = _STATEMENT_TIMEOUT_MS
    ) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(
            self._database_url,
            row_factory=dict_row,
            connect_timeout=_CONNECT_TIMEOUT_SECONDS,
            options=f"-c statement_timeout={statement_timeout_ms}",
        )

    @contextmanager
    def _operation(
        self,
        *,
        log_message: str,
        error_message: str,
        log_args: tuple[object, ...] = (),
        statement_timeout_ms: int = _STATEMENT_TIMEOUT_MS,
    ) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        """Yield a connection; translate any `psycopg.Error` into `MemoryRepositoryError`.

        Centralizes the connect/except/log/raise pattern every operation
        below needs, so a new method can't accidentally skip it and leak a
        raw driver exception to a caller.
        """

        try:
            with self._connect(statement_timeout_ms=statement_timeout_ms) as connection:
                yield connection
        except psycopg.Error as exc:
            logger.exception(log_message, *log_args)
            raise MemoryRepositoryError(error_message) from exc

    def initialize(self) -> None:
        """Apply the idempotent service schema."""

        with self._operation(
            log_message="Failed to apply the memory service schema",
            error_message=(
                "failed to apply the memory database schema; "
                "check that Postgres is reachable and the pgvector "
                "extension is installable"
            ),
            statement_timeout_ms=_SCHEMA_STATEMENT_TIMEOUT_MS,
        ) as connection:
            connection.execute(schema_sql(self._dimensions))

    def health(self) -> bool:
        """Verify a minimal database round trip; never raises."""

        try:
            with self._connect() as connection:
                return connection.execute("SELECT 1 AS ready").fetchone() == {
                    "ready": 1
                }
        except psycopg.Error as exc:
            # Deliberately swallowed: /ready must report `False`, not 500.
            logger.warning("Database health check failed: %s", exc)
            return False

    def create(self, record: MemoryRecord, *, embedding: list[float]) -> None:
        """Insert one record, casting its embedding to `vector` server-side."""

        with self._operation(
            log_message="Failed to store memory %s",
            log_args=(record.memory_id,),
            error_message=(
                "failed to store the memory; the database may be unavailable "
                "or the record may violate a storage constraint"
            ),
        ) as connection:
            connection.execute(
                """INSERT INTO memories (
                     memory_id, type, tenant_id, project_id, user_id, agent_id,
                     content, source_type, run_id, source_id, confidence,
                     created_at, expires_at, supersedes, sensitivity,
                     write_status, embedding
                   ) VALUES (
                     %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector
                   )""",
                (
                    record.memory_id,
                    record.type,
                    record.scope.tenant_id,
                    record.scope.project_id,
                    record.scope.user_id,
                    record.scope.agent_id,
                    record.content,
                    record.provenance.source_type,
                    record.provenance.run_id,
                    record.provenance.source_id,
                    record.confidence,
                    record.created_at,
                    record.expires_at,
                    record.supersedes,
                    record.sensitivity,
                    record.write_status,
                    _vector_literal(embedding),
                ),
            )

    def get(
        self, memory_id: str, *, tenant_id: str, project_id: str
    ) -> MemoryRecord | None:
        """Fetch one record, scoped to the caller's tenant/project."""

        with self._operation(
            log_message="Failed to fetch memory %s",
            log_args=(memory_id,),
            error_message="failed to fetch the memory; the database may be unavailable",
        ) as connection:
            row = connection.execute(
                """SELECT * FROM memories
                   WHERE memory_id=%s AND tenant_id=%s AND project_id=%s""",
                (memory_id, tenant_id, project_id),
            ).fetchone()
        return _row_to_record(row) if row is not None else None

    def search(
        self,
        *,
        scope: MemoryScope,
        query_embedding: list[float],
        top_k: int,
        types: list[str] | None,
        include_pending: bool,
    ) -> list[tuple[MemoryRecord, float]]:
        """Rank scoped, non-expired records by ascending pgvector cosine distance."""

        # `clauses` only ever contains fixed column-comparison strings chosen
        # by this method (never caller-supplied text); every actual value,
        # including `types`, is passed through `params` and bound with `%s`.
        clauses = ["tenant_id=%s", "project_id=%s"]
        params: list[Any] = [scope.tenant_id, scope.project_id]
        if scope.user_id is not None:
            clauses.append("user_id=%s")
            params.append(scope.user_id)
        if scope.agent_id is not None:
            clauses.append("agent_id=%s")
            params.append(scope.agent_id)
        if types:
            clauses.append("type = ANY(%s)")
            params.append(list(types))
        if not include_pending:
            clauses.append("write_status='approved'")
        clauses.append("(expires_at IS NULL OR expires_at > now())")

        query_vector = _vector_literal(query_embedding)
        sql = f"""
            SELECT *, (embedding <=> %s::vector) AS distance
            FROM memories
            WHERE {" AND ".join(clauses)}
            ORDER BY embedding <=> %s::vector ASC
            LIMIT %s
        """
        with self._operation(
            log_message="Failed to search memories",
            error_message="failed to search memories; the database may be unavailable",
        ) as connection:
            rows = connection.execute(
                sql, [query_vector, *params, query_vector, top_k]
            ).fetchall()
        # pgvector's `<=>` is cosine *distance* in [0, 2]; convert to a
        # similarity score so higher is better, matching the in-memory
        # repository and the public API contract.
        return [(_row_to_record(row), 1.0 - row["distance"]) for row in rows]


class InMemoryMemoryRepository:
    """Deterministic in-process repository for tests; no external services."""

    def __init__(self) -> None:
        """Start with an empty store."""

        self._rows: dict[str, tuple[MemoryRecord, list[float]]] = {}

    def initialize(self) -> None:
        """No schema to apply for an in-process dictionary."""

        return None

    def health(self) -> bool:
        """Always healthy; there is no external dependency to fail."""

        return True

    def create(self, record: MemoryRecord, *, embedding: list[float]) -> None:
        """Store one record and its embedding by id."""

        self._rows[record.memory_id] = (record, embedding)

    def get(
        self, memory_id: str, *, tenant_id: str, project_id: str
    ) -> MemoryRecord | None:
        """Fetch one record, scoped to the caller's tenant/project."""

        entry = self._rows.get(memory_id)
        if entry is None:
            return None
        record, _ = entry
        if record.scope.tenant_id != tenant_id or record.scope.project_id != project_id:
            return None
        return record

    def search(
        self,
        *,
        scope: MemoryScope,
        query_embedding: list[float],
        top_k: int,
        types: list[str] | None,
        include_pending: bool,
    ) -> list[tuple[MemoryRecord, float]]:
        """Rank scoped, non-expired records by descending cosine similarity."""

        now = datetime.now(UTC)
        candidates: list[tuple[MemoryRecord, float]] = []
        for record, embedding in self._rows.values():
            if record.scope.tenant_id != scope.tenant_id:
                continue
            if record.scope.project_id != scope.project_id:
                continue
            if scope.user_id is not None and record.scope.user_id != scope.user_id:
                continue
            if scope.agent_id is not None and record.scope.agent_id != scope.agent_id:
                continue
            if types is not None and record.type not in types:
                continue
            if not include_pending and record.write_status != "approved":
                continue
            if record.expires_at is not None and record.expires_at <= now:
                continue
            candidates.append((record, _cosine_similarity(query_embedding, embedding)))
        candidates.sort(key=lambda item: item[1], reverse=True)
        return candidates[:top_k]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return cosine similarity in [-1, 1]; 0.0 for a degenerate zero vector.

    Mirrors `1.0 - cosine_distance` from pgvector's `<=>` operator so
    `InMemoryMemoryRepository.search` ranks identically to the Postgres
    implementation.
    """

    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)
