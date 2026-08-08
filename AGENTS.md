# Repository Instructions

This repository owns long-term agent memory, semantic retrieval, RAG indexing,
embeddings, and knowledge retrieval as a separate stateful service. It does not
own runtime/control state, conversation/session memory, or document parsing.

- Runtime/control state (idempotency, approvals, resumable run state, audit
  events) stays in `fastapi-openai-agents-runtime-framework`. Do not add it here.
- Conversation/session memory (per-turn chat history) stays in the runtime's
  Agents SDK `Session` adapter. Do not add it here.
- Document parsing and chunk generation stay in `document-processing-platform`.
  This repository consumes its index-ready records; it does not parse source
  documents itself.
- Long-term memory is never arbitrary agent-written text. Every write goes
  through `propose -> validate -> policy -> store`; there is no unrestricted
  `remember(anything)` path.
- `type` and `sensitivity` values are validated against `config/policy.yaml`,
  not a hardcoded enum. Do not bypass the policy loader.
- Writes whose `sensitivity` requires approval must be persisted with
  `write_status=pending_approval` and excluded from search results by default.
  Do not let an LLM decide ACLs, scope, or approval status.
- Every stored record and search query is scoped by `tenant_id`/`project_id`
  (and `user_id`/`agent_id` where applicable). Do not add an endpoint that
  reads or searches across scopes implicitly.
- Keep the `MemoryRepository` and `EmbeddingProvider` interfaces abstract
  (`app/stores/database.py`, `app/stores/embeddings.py`) so Postgres/pgvector
  can later be supplemented or replaced (e.g. by Qdrant) without changing the
  API or policy layers.
- Do not put embeddings, vector indexes, or memory tables in the runtime's
  `RuntimeStore`, and do not make this service execute agents, own prompts, or
  make Langfuse a memory database.
- Do not implement automatic/autonomous memory generation (writing memories
  without an explicit caller-supplied proposal). That is future Phase F work
  and requires its own review.
- Treat the root `Makefile` as the authoritative local and CI command
  interface.
- Never commit `.env`, environment backups, database credentials, or API keys.
- Give every module and public function a docstring, and catch every
  external I/O call (Postgres, an embedding provider's HTTP request) with a
  safe, generic error message — never return a raw driver/HTTP exception to
  a caller, since it can echo back connection strings or upstream details.
  Log the real exception server-side instead (see `docs/architecture.md`'s
  error-handling model).
- Keep `docs/` synchronized with the code in the same change: a new/changed
  endpoint or error path updates `docs/api-examples.md` (and
  `docs/troubleshooting.md` for a new error path), a new Make target updates
  `docs/make-commands.md`, a structural change updates
  `docs/architecture.md`, and a phase-status change updates `docs/overview.md`
  and `README.md`. See `docs/README.md` for the full index and source-of-truth
  order.

## Current phase

This repository currently implements Phase B (service skeleton: FastAPI,
Postgres + pgvector, auth, scoped memory schema, policy-gated deterministic
write API, vector search API) per the phased plan in `plan.md` at the
repository root. Deduplication, supersession, expiration sweeps,
hybrid/reranked retrieval, citations, and autonomous memory generation
(Phases C-F) are not yet implemented. See `docs/overview.md` for the current
detailed status.
