# Agent Memory Platform

Long-term agent memory, policy-gated writes, and pgvector-backed semantic
retrieval for the HomeAIassistant platform. This is the fourth platform
service described in `plan.md`:

```text
fastapi-openai-agents-runtime-framework   Agent execution, tools, session memory
fastapi-openai-agents-langfuse            Observability, traces, evaluation
document-processing-platform              Documents -> DocumentIR -> chunks
fastapi-openai-agent-memory-platform      Long-term memory + retrieval (this repo)
```

Runtime/control state (idempotency, approvals, audit) and per-conversation
session history stay in the runtime framework. Document parsing stays in
`document-processing-platform`. This repository owns everything that survives
a session, a container replacement, or a workflow change: agent-generated
facts, preferences, decisions, and (eventually) document-derived knowledge.

## Current capability (Phase B — service skeleton)

- FastAPI service with bearer authentication, `/health`, and `/ready`.
- PostgreSQL + pgvector storage, tenant/project/user/agent scoped.
- A memory record contract (`type`, `scope`, `content`, `provenance`,
  `confidence`, `lifecycle`, `policy`) matching `plan.md`.
- A deterministic write path: `POST /memories` validates `type` and
  `sensitivity` against `config/policy.yaml`, resolves `write_status`
  (`approved` or `pending_approval`), and stores the record. There is no
  unrestricted `remember(anything)` tool.
- A scoped vector search path: `POST /memories/search` embeds the query,
  ranks by cosine similarity within the requested scope, and excludes
  `pending_approval` records by default.
- A pluggable `EmbeddingProvider`: a deterministic offline provider for local
  development/CI, and an OpenAI provider for real semantic embeddings.

Not yet implemented (see `plan.md` Phases C-F and `AGENTS.md`):
deduplication, supersession, expiration sweeps, hybrid/lexical search,
reranking, citations, ingestion from `document-processing-platform`, and any
autonomous memory generation.

## Quickstart

Requires Docker and Docker Compose.

```bash
make env-init          # generate .env with a bearer token and DB password
make up                # build the image, start postgres + api, wait healthy
make health             # curl /health and /ready
```

Propose a memory:

```bash
curl -sS http://127.0.0.1:8200/memories \
  -H "Authorization: Bearer $(grep MEMORY_API_TOKEN .env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "preference",
    "scope": {"tenant_id": "home", "project_id": "henley"},
    "content": "User prefers operational summaries with explicit next actions.",
    "provenance": {"source_type": "agent_run", "run_id": "run_123"},
    "confidence": 0.92,
    "sensitivity": "internal"
  }'
```

Search:

```bash
curl -sS http://127.0.0.1:8200/memories/search \
  -H "Authorization: Bearer $(grep MEMORY_API_TOKEN .env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{
    "scope": {"tenant_id": "home", "project_id": "henley"},
    "query": "How does the user like reports formatted?",
    "top_k": 5
  }'
```

More examples: `docs/api-examples.md`.

## Local development

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
make style-check   # ruff lint + format check
make unit           # pytest against an in-memory repository (no Docker needed)
make validate        # style-check + unit
```

Unit tests use an in-memory `MemoryRepository` and the deterministic embedding
provider, so `make unit` needs no database. Exercising the real Postgres/pgvector
path requires `make up` and a running `postgres` service; see `Makefile`.

## Architecture

```text
POST /memories          -> validate contract -> policy (type/sensitivity) ->
                            embed -> INSERT -> MemoryRecord
POST /memories/search   -> embed query -> scoped cosine search
                            (approved only, unless include_pending=true)
```

See `app/memory/policy.py` and `config/policy.yaml` for the write policy, and
`app/stores/database.py` for the `MemoryRepository` interface (Postgres and
in-memory implementations) and `app/stores/embeddings.py` for the
`EmbeddingProvider` interface.

## Documentation

| Document | Read this for |
| --- | --- |
| [`docs/overview.md`](docs/overview.md) | What this service is, where it fits in the platform, current phase, what's not built yet. Start here. |
| [`docs/architecture.md`](docs/architecture.md) | Request flow, the memory record contract, database schema, policy model, error-handling model, security notes. |
| [`docs/instructions.md`](docs/instructions.md) | Setup, local development, deployment, adding a memory type, credential rotation. |
| [`docs/api-examples.md`](docs/api-examples.md) | curl examples for every endpoint, including error responses. |
| [`docs/make-commands.md`](docs/make-commands.md) | Every `Makefile` target. |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | HTTP error reference and diagnosis steps. |
| [`docs/README.md`](docs/README.md) | Full documentation index. |
