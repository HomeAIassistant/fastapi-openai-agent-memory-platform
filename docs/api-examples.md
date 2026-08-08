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

A wrong scope or an unknown id both return the same `404` (see
`docs/architecture.md` for why):

```bash
curl -sS -w "\n%{http_code}\n" \
  "$BASE/memories/mem_does_not_exist?tenant_id=home&project_id=henley" -H "$AUTH"
# -> 404 {"detail": {"code": "not_found", "message": "..."}}
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

## Missing or bad auth

```bash
curl -sS -w "\n%{http_code}\n" "$BASE/memories" -X POST -d '{}'
# -> 401 {"detail": {"code": "unauthorized", "message": "Invalid bearer token."}}
```

## Error responses

| Status | `code` | When |
| --- | --- | --- |
| `401` | `unauthorized` | Missing/wrong bearer token |
| `404` | `not_found` | Unknown `memory_id`, or right id but wrong scope |
| `422` | `policy_rejected` | `type`/`sensitivity` not allowed by `config/policy.yaml` |
| `422` | *(none)* | Request body failed schema validation (e.g. `confidence` out of `0.0-1.0`) |
| `503` | `storage_unavailable` | Postgres unreachable or a query failed |
| `503` | `embedding_unavailable` | Embedding provider unreachable or returned a bad response |

Full explanations and how to diagnose each one: `docs/troubleshooting.md`.

## Notes

- `MEMORY_EMBEDDING_PROVIDER=deterministic` (the default) produces a hashed,
  non-semantic vector — useful for exercising the API and storage path, not
  for real retrieval quality. Set `MEMORY_EMBEDDING_PROVIDER=openai` and
  `OPENAI_API_KEY` for real semantic search.
- Every read/write is scoped by `tenant_id`/`project_id` (and optionally
  `user_id`/`agent_id`); there is no cross-scope query.
- `503` messages are intentionally generic; the real cause is in the server
  logs (`make logs`), never in the response body — see
  `docs/troubleshooting.md`.
