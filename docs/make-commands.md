# Make Command Reference

The root `Makefile` is the supported interface for local validation and
deployment. Run `make help` for the same list with one-line descriptions.
Running `make` with no target is not equivalent to `make help` — always name
a target explicitly.

## Recommended workflows

Before committing:

```bash
make validate
```

First deployment or local setup:

```bash
make env-init
make up
make health
```

Update an already-running deployment:

```bash
git pull origin main
make validate
make up
make health
```

## Reference

| Command | Changes state? | Requires Docker? | Purpose |
| --- | --- | --- | --- |
| `make help` | No | No | Print the command reference with descriptions, generated from this Makefile's `##` comments. |
| `make env-init` | Creates `.env` | No | Copy `.env.example` to `.env`, generate `MEMORY_API_TOKEN` and `MEMORY_POSTGRES_PASSWORD` with `openssl rand`, and optionally set `MEMORY_API_BIND_ADDRESS` from `LXC_HOST_IP=...`. Refuses to run if `.env` already exists. |
| `make env-check` | No | No | Verify `.env` exists and contains no leftover `GENERATE_ME` placeholder. Run automatically by `make up`. |
| `make style-check` | No | No (host Python) | `ruff check .` and `ruff format --check .`. |
| `make unit` | No | No (host Python) | Run the pytest suite (`InMemoryMemoryRepository` + `DeterministicEmbeddingProvider`; no database needed). |
| `make test` | No | No | Alias for `make unit`. |
| `make validate` | No | No | `style-check` then `unit`. The standard pre-commit gate. |
| `make build` | Builds an image | Yes | `docker compose build api`. Does not start anything. |
| `make up` | Starts/recreates containers | Yes | `env-check`, then `docker compose up -d --build --wait`. Builds the `api` image, starts `postgres` and `api`, and blocks until both report healthy. |
| `make down` | Stops containers | Yes | `docker compose down`. The named Postgres volume is preserved. |
| `make restart` | Restarts containers | Yes | `docker compose restart`. Does **not** rebuild the image — use `make up` after an image-affecting change. |
| `make logs` | No | Yes | `docker compose logs -f --tail=200`. |
| `make ps` | No | Yes | `docker compose ps`. |
| `make health` | No | Yes (service must be running) | `curl --fail` against `/health` and `/ready` using the bind address/port from `.env`. |

## Notes

- `style-check` and `unit` activate `.venv/bin/activate` if present, but
  fall back to whatever `ruff`/`pytest` is on `PATH` otherwise — they do not
  create or require a virtualenv themselves. Set one up per
  `docs/instructions.md`.
- There is no `make ci` aggregate target in this repository yet;
  `.github/workflows/ci.yml` runs `style-check`/`unit` equivalents directly
  plus a separate container job that boots the real stack. See that
  workflow file for the exact CI sequence.
- There is no `make clean`, `make lint` (alias), or `make coverage` target
  yet — this Makefile intentionally stays small for the current Phase B
  scope. Add targets here (and to this table) as the repository grows,
  rather than running ad hoc commands that aren't captured anywhere.
