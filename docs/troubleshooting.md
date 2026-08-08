# Troubleshooting

## HTTP error responses

Every non-2xx response from this service has the shape
`{"detail": {"code": "...", "message": "..."}}` (FastAPI's default `detail`
wrapping applies to `/health`'s and `/ready`'s payloads directly instead,
since those don't use the `code`/`message` convention — see the table).

| Status | `code` | Meaning | What to check |
| --- | --- | --- | --- |
| `401` | `unauthorized` | Missing or wrong `Authorization: Bearer <token>` header. | Confirm you're sending the value of `MEMORY_API_TOKEN` from `.env`, exactly, with the `Bearer ` prefix. |
| `404` | `not_found` | No memory with that id **in the scope you queried**. | Double-check `tenant_id`/`project_id` query params match the record's scope — a wrong scope and a genuinely missing id both return `404` on purpose (see `docs/architecture.md`). |
| `422` | `policy_rejected` | `type` or `sensitivity` isn't listed in `config/policy.yaml`. | Check the exact spelling against `allowed_types`/`allowed_sensitivities` in `config/policy.yaml`. Add the value there if it should be allowed (see `docs/instructions.md`). |
| `422` | (FastAPI validation, no `code`) | Request body failed Pydantic validation (e.g. `confidence` outside `0.0-1.0`, empty `content`, missing required field). | The response body lists the failing field(s) directly. |
| `503` | `storage_unavailable` | Postgres is unreachable, timed out, or a query/constraint failed. | `make ps` — is the `postgres` service healthy? `make logs`. See "Storage failures" below. |
| `503` | `embedding_unavailable` | The embedding provider failed (OpenAI unreachable, bad API key, malformed response). | Only possible with `MEMORY_EMBEDDING_PROVIDER=openai`. Check `OPENAI_API_KEY` and OpenAI's status. See "Embedding failures" below. |

`503` messages are deliberately generic — the real driver/HTTP exception is
never included in the response (it can otherwise echo back connection
strings or upstream error bodies). It's always in the container logs:

```bash
make logs
```

look for the `logger.exception(...)` entry immediately before the response
was returned; it includes the real `psycopg`/`httpx` exception and a full
traceback.

## `/ready` reports `not_ready`

```json
{"detail": {"status": "not_ready", "database": false}}
```

This means `MemoryRepository.health()` (a `SELECT 1`) failed. It never
raises — a failure always shows up as `database: false`, not a crashed
health check. Check:

```bash
make ps                 # is postgres "healthy"?
docker compose logs postgres --tail=50
```

## Storage failures (`503 storage_unavailable`)

Most common causes, roughly in likelihood order:

1. **Postgres isn't running or isn't healthy yet.** `make ps`. If it's
   still starting, `/ready` will report `not_ready` until its healthcheck
   passes (`pg_isready`).
2. **`.env`'s `MEMORY_POSTGRES_PASSWORD` doesn't match what Postgres was
   initialized with.** Postgres only applies `POSTGRES_PASSWORD` on first
   volume initialization; changing `.env` afterward doesn't change the
   database. See "Rotating credentials" in `docs/instructions.md`.
3. **A genuinely down/unreachable database.** As of the fix below, this
   resolves to `503` within about 5 seconds, not a hang.
4. **A storage constraint violation** — for example, attempting to insert a
   duplicate `memory_id` (practically unreachable since it's a
   server-generated UUID, but the `create` error message covers it: "the
   record may violate a storage constraint").

### Known-fixed: requests used to hang instead of failing

Earlier revisions of `PostgresMemoryRepository._connect()` called
`psycopg.connect()` with no `connect_timeout`. When Postgres was stopped
while the `api` container was already running, requests against `/ready` and
`POST /memories` hung for roughly two minutes (the OS-level TCP timeout)
instead of returning a `503`. This was caught by killing the `postgres`
container mid-request against a live Compose deployment, not by the unit
suite (the in-memory test double can't reproduce a network hang).

Fixed by adding a 5-second `connect_timeout` and a 10-second
`statement_timeout` (`app/stores/database.py`). If you see a request hang
for longer than ~5-10 seconds against a real deployment, that's a
regression — check that `_CONNECT_TIMEOUT_SECONDS`/`_STATEMENT_TIMEOUT_MS`
are still being passed to `psycopg.connect()`.

## Embedding failures (`503 embedding_unavailable`)

Only reachable with `MEMORY_EMBEDDING_PROVIDER=openai`. Causes:

- `OPENAI_API_KEY` unset, revoked, or lacking embeddings access — surfaces
  as an HTTP error from OpenAI, wrapped into `embedding_unavailable`.
- Network egress to `api.openai.com` blocked from the container/LXC.
- OpenAI outage or rate limiting.
- A response body that doesn't match the expected
  `{"data": [{"embedding": [...]}]}` shape (defensive handling for an API
  contract change; see `app/stores/embeddings.py`).

Switch back to `MEMORY_EMBEDDING_PROVIDER=deterministic` and `make restart`
to unblock local development while investigating — this restores a working
(non-semantic) write/search path immediately.

## Application fails to start

Look for `ERROR:    Application startup failed. Exiting.` in
`docker compose logs api`. The lifespan (`app/core/lifecycle.py`) logs which
stage failed before re-raising:

- `"Startup failed while loading the write policy"` — `config/policy.yaml`
  is missing, unreadable, invalid YAML, or internally inconsistent (a
  `require_approval` entry not present in `allowed_sensitivities`). The
  `PolicyConfigError` message states which.
- `"Startup failed while applying the database schema"` — same causes as
  "Storage failures" above, but during `initialize()` rather than a request.

The process intentionally does not start partially — Docker's healthcheck
will never report the container healthy in this state, so it won't receive
traffic through a load balancer that respects health status.

## Settings validation fails at startup

Pydantic raises a per-field `ValidationError` listing exactly which
environment variable is missing or invalid — for example, `MEMORY_API_TOKEN`
still set to `GENERATE_ME`, or `DATABASE_URL` still containing an
unresolved `GENERATE_ME` (meaning `.env`'s `MEMORY_POSTGRES_PASSWORD` was
never generated — re-run `make env-init` on a fresh `.env`, or fill it in
manually). See `app/core/settings.py` for the complete field list.

## Tests pass locally but fail in CI (or vice versa)

- `make unit` never touches Postgres or the network — if a test fails only
  in the container CI job (`.github/workflows/ci.yml`'s `container` job),
  the issue is in the real Postgres/Docker path, not application logic.
  Reproduce with `make up` locally.
- If a test *depends on* a specific embedding value or ranking order,
  remember `DeterministicEmbeddingProvider` hashes text into a
  non-semantic vector — see `docs/architecture.md`. Tests should assert on
  scope/policy filtering, not on which result ranks higher when more than
  one candidate is genuinely unrelated text.

## Where to look next

- Technical design and the full error-handling model: `docs/architecture.md`.
- Setup/deploy/operate procedures: `docs/instructions.md`.
- Request/response examples including error cases: `docs/api-examples.md`.
