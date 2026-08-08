# Instructions

Step-by-step setup, development, deployment, and operation instructions.
For *why* things are structured this way, see `docs/overview.md` and
`docs/architecture.md`. For error messages, see `docs/troubleshooting.md`.

## Prerequisites

- Docker Engine and Docker Compose v2 (required for `make up` and anything
  that touches Postgres).
- Python 3.13 and a virtual environment, only for host-side linting/tests
  (`make style-check`, `make unit` run against a `.venv` if one is active).
- `openssl`, `curl` (used by `make env-init` / `make health`).
- Git, with push access to
  `git@github.com:HomeAIassistant/fastapi-openai-agent-memory-platform.git`
  if you intend to push.

## First-time setup

```bash
git clone git@github.com:HomeAIassistant/fastapi-openai-agent-memory-platform.git
cd fastapi-openai-agent-memory-platform

python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

make env-init      # writes .env with a generated MEMORY_API_TOKEN and
                    # MEMORY_POSTGRES_PASSWORD; refuses to overwrite an
                    # existing .env
```

`make env-init` binds the API to `127.0.0.1` by default. For the documented
HomeAIassistant LXC, pass the trusted address explicitly:

```bash
make env-init LXC_HOST_IP=10.10.20.18
```

Never commit `.env` — it's gitignored, and `env-init` refuses to overwrite
one that already exists specifically so a re-run can't silently regenerate
credentials another process is using.

## Local development loop

Run the unit suite and static checks without Docker — they run against
`InMemoryMemoryRepository` and `DeterministicEmbeddingProvider`, so no
database is needed:

```bash
make style-check   # ruff check + ruff format --check
make unit           # pytest (34 tests as of Phase B)
make validate        # style-check + unit; run this before every commit
```

To exercise the real Postgres + pgvector path (schema application, the
`vector` extension, the `<=>` cosine-distance query), you need Docker:

```bash
make up
make health          # curl /health and /ready
```

Then use `docs/api-examples.md` to exercise create/get/search against the
running service, or:

```bash
make logs             # follow both services' logs
make ps                # service status
make down              # stop; the Postgres volume is preserved
```

### Making a code change

1. Write the change and its test(s). Every new public function needs a
   docstring; every external I/O call needs a caught, safe-message error
   path (see `docs/architecture.md`'s error-handling model and
   `AGENTS.md`).
2. `make validate`.
3. If you touched Postgres queries, the schema, or Docker/Compose
   configuration, also run `make up` and exercise the change for real — the
   in-memory test double does not catch every SQL or container issue (a
   missing `connect_timeout` was caught exactly this way; see
   `docs/troubleshooting.md`).
4. Update the relevant doc in the same change: `README.md` for
   user-visible capability changes, `docs/architecture.md` for structural
   changes, `docs/api-examples.md` for new/changed endpoints,
   `docs/make-commands.md` for new Make targets, `CHANGELOG.md` always.
5. Commit. Don't amend published commits; open a new commit per the
   Git Safety Protocol in your assistant's instructions if you're using one.

### Adding a new memory type or sensitivity tier

This is a **config change**, not a code change:

```bash
# config/policy.yaml
long_term:
  write:
    allowed_types: [preference, fact, decision, workflow_lesson, NEW_TYPE]
```

Restart the running service to pick it up (the file is bind-mounted
read-only into the container, so no image rebuild is required):

```bash
make restart
```

Add a test in `tests/test_policy.py` or `tests/test_memories.py` asserting
the new type is accepted (and, if relevant, that an invalid one is still
rejected).

## Deployment (HomeAIassistant LXC)

The documented deployment target is a single LXC at `10.10.20.18`, matching
the sibling platform repositories.

```bash
cd /root/repos/home-ai-assistant/fastapi-openai-agent-memory-platform

git pull origin main
make env-init LXC_HOST_IP=10.10.20.18   # first deployment only
make validate                            # style-check + unit
make up                                    # build, start, wait healthy
make health                                 # curl /health and /ready
```

For a subsequent update on an already-initialized LXC (`.env` already
exists):

```bash
git pull origin main
make validate
make up            # docker compose up -d --build --wait; recreates on image change
make health
```

`make up` runs `env-check` first and fails fast with a clear message if
`.env` is missing or still contains a `GENERATE_ME` placeholder — it will
not silently start with bad credentials.

### Ports

| Variable | Default | Notes |
| --- | --- | --- |
| `MEMORY_API_BIND_ADDRESS` | `127.0.0.1` | Set to `10.10.20.18` for LXC deployment |
| `MEMORY_API_PORT` | `8200` | Chosen to avoid the documented socket inventory (8080 document-processing-platform, 8100 runtime framework, 3100/9190 langfuse) |

Postgres is **never** published to the host; only the `api` service reaches
it over the internal Compose network (see `docs/architecture.md`).

### Enabling real semantic search

By default `MEMORY_EMBEDDING_PROVIDER=deterministic` — safe for local/CI,
but not semantically meaningful. For real retrieval quality:

```bash
# .env
MEMORY_EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

Then `make restart`. Existing records keep their old (deterministic)
embeddings — there is no automatic re-embedding path yet, so switching
providers on a database with existing data means old and new records are
not comparable until Phase C/E tooling exists. On a fresh deployment this is
a non-issue.

### Rotating the bearer token or database password

There is no in-place rotation command yet. To rotate manually:

```bash
# Edit .env directly, or:
new_token="$(openssl rand -hex 32)"
sed -i "s/^MEMORY_API_TOKEN=.*/MEMORY_API_TOKEN=$new_token/" .env
make restart
```

Rotating `MEMORY_POSTGRES_PASSWORD` after the volume already has a database
requires updating the password inside Postgres too (`ALTER USER ... PASSWORD
...`) before restarting the `api` service with the new `.env` value, or the
`api` service will fail `/ready` with `storage_unavailable`.

## Service lifecycle reference

```bash
make up          # build, start, wait for both services healthy
make down         # stop; Postgres volume preserved
make restart       # docker compose restart (does NOT rebuild the image)
make logs           # follow logs
make ps               # service status
make health             # curl /health and /ready
```

Use `make up` (not `make restart`) after an image-affecting change (code,
`Dockerfile`, `requirements.txt`) — `restart` only restarts existing
containers from their current image.

Full Make target reference: `docs/make-commands.md`.

## Review checklist

A change is ready when:

- `make validate` passes.
- If Postgres/Docker/Compose was touched: `make up` succeeds and
  `make health` reports both `/health` and `/ready` as healthy.
- New/changed endpoints are reflected in `docs/api-examples.md`.
- Structural changes are reflected in `docs/architecture.md`.
- `CHANGELOG.md` has an entry.
- No `.env`, credentials, or generated secrets are staged
  (`git status` after `git add`, per the Git Safety Protocol).
