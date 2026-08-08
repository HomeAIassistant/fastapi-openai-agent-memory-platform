# API examples

All examples assume the service is running (`make up`) and `MEMORY_API_TOKEN`
is exported from `.env`:

```bash
set -a; . .env; set +a
BASE="http://${MEMORY_API_BIND_ADDRESS:-127.0.0.1}:${MEMORY_API_PORT:-8200}"
AUTH="Authorization: Bearer $MEMORY_API_TOKEN"
```

## Health and readiness (no auth)

```bash
curl -sS "$BASE/health"
curl -sS "$BASE/ready"
```

## Propose a memory

`type` and `sensitivity` are validated against `config/policy.yaml`.
`sensitivity` values in `require_approval` come back with
`write_status=pending_approval` and are excluded from search by default.

```bash
curl -sS "$BASE/memories" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "type": "preference",
    "scope": {"tenant_id": "home", "project_id": "henley"},
    "content": "User prefers operational summaries with explicit next actions.",
    "provenance": {"source_type": "agent_run", "run_id": "run_123"},
    "confidence": 0.92,
    "sensitivity": "internal"
  }'
```

A rejected type:

```bash
curl -sS "$BASE/memories" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "type": "not-a-real-type",
    "scope": {"tenant_id": "home", "project_id": "henley"},
    "content": "x",
    "provenance": {"source_type": "agent_run"}
  }'
# -> 422 {"detail": {"code": "policy_rejected", "message": "..."}}
```

## Fetch a memory by id and scope

```bash
curl -sS "$BASE/memories/mem_...?tenant_id=home&project_id=henley" -H "$AUTH"
```

## Search

```bash
curl -sS "$BASE/memories/search" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "scope": {"tenant_id": "home", "project_id": "henley"},
    "query": "How does the user like reports formatted?",
    "top_k": 5
  }'
```

Include `pending_approval` records explicitly (only for callers authorized to
see unreviewed content):

```bash
curl -sS "$BASE/memories/search" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "scope": {"tenant_id": "home", "project_id": "henley"},
    "query": "How does the user like reports formatted?",
    "include_pending": true
  }'
```

## Notes

- `MEMORY_EMBEDDING_PROVIDER=deterministic` (the default) produces a hashed,
  non-semantic vector — useful for exercising the API and storage path, not
  for real retrieval quality. Set `MEMORY_EMBEDDING_PROVIDER=openai` and
  `OPENAI_API_KEY` for real semantic search.
- Every read/write is scoped by `tenant_id`/`project_id` (and optionally
  `user_id`/`agent_id`); there is no cross-scope query.
