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
