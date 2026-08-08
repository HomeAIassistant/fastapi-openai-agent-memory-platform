# Changelog

## Unreleased — 0.1.0

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
