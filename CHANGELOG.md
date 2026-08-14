# Changelog

## Unreleased — 0.1.0

### Fixed

- `initialize()` (which runs `CREATE INDEX ... USING hnsw`) no longer shares
  the 10s per-request `statement_timeout`; schema application now uses its
  own 300s timeout, since an index build can legitimately take longer than
  a per-request query once the table holds many rows — otherwise the service
  could fail to start on every restart once data grew past that bound.
- Centralized `MemoryValidationError`/`EmbeddingProviderError`/
  `MemoryRepositoryError` -> HTTP translation into app-wide exception
  handlers (`app/api/error_handlers.py`) instead of per-route `try`/`except`,
  so a new route cannot forget the translation and leak a raw driver/HTTP
  exception. Response bodies are unchanged.
- Deduplicated the connect/except/log/raise pattern in
  `PostgresMemoryRepository` behind one `_operation` helper
  (`app/stores/database.py`) instead of repeating it in `initialize`,
  `create`, `get`, and `search`.
- Corrected a misleading comment implying `/ready` raises
  `MemoryRepositoryError`; `health()` catches its own errors and returns
  `False` instead.

### Dependencies

- Bumped `fastapi` 0.139.2 -> 0.141.1, `psycopg` 3.2.10 -> 3.3.4, `uvicorn`
  0.51.0 -> 0.52.1, `actions/setup-python` v5 -> v7, and the Dockerfile base
  image `python:3.13-slim-bookworm` -> `python:3.14-slim-bookworm` (digest
  updated with the tag). Verified with the full unit suite, a Docker build,
  and a live Compose deployment (health/ready, non-root/read-only-fs checks,
  and a real memory write + search round trip against Postgres/pgvector).

### Added

- Initial Phase B service skeleton: FastAPI application factory, bearer
  authentication, `/health` and `/ready`.
- PostgreSQL + pgvector schema and `MemoryRepository` interface with
  `PostgresMemoryRepository` and `InMemoryMemoryRepository` implementations.
- `EmbeddingProvider` interface with a deterministic offline provider and an
  OpenAI embeddings provider.
- Policy-gated deterministic write path (`POST /memories`) validating `type`
  and `sensitivity` against `config/policy.yaml` and resolving `write_status`.
- Scoped vector search path (`POST /memories/search`) excluding
  `pending_approval` records by default.
- Docker Compose deployment (unpublished Postgres, published API), Makefile,
  and CI workflow.

### Fixed

- Bound Postgres connection/statement time (`connect_timeout`,
  `statement_timeout`) so a down or unreachable database fails within
  seconds instead of hanging requests indefinitely; caught live against the
  real Compose deployment.
- All Postgres operations (`initialize`, `create`, `get`, `search`) and the
  OpenAI embeddings call now catch their respective driver/HTTP exceptions
  and raise `MemoryRepositoryError`/`EmbeddingProviderError` with a safe,
  generic message; the real exception is logged server-side (never returned
  to callers, since raw driver/provider text can include connection or
  upstream details) and routes translate both into `503` with a stable
  `code`/`message` body instead of an unhandled `500`.
- `load_write_policy` now raises `PolicyConfigError` with a clear message on
  an unreadable file or invalid YAML instead of an unhandled exception.

### Documentation

- Added `docs/overview.md` (what/why/current phase), `docs/architecture.md`
  (request flow, memory record contract, database schema, policy model,
  error-handling model, security notes), `docs/instructions.md`
  (setup/development/deployment/operations), `docs/make-commands.md`
  (Makefile reference), `docs/troubleshooting.md` (HTTP error reference and
  diagnosis steps), and `docs/README.md` (documentation index).
- Expanded `docs/api-examples.md` with 404/401/503 examples and a
  status-code reference table.
- Cross-linked all documentation from `README.md` and added a doc-sync
  convention to `AGENTS.md`.
