# Documentation

Maintained documentation for the Agent Memory Platform. `README.md` at the
repository root is the quickstart; this directory is the complete reference.

| Document | Read this for |
| --- | --- |
| [Overview](overview.md) | What this service is, why it exists, where it fits in the four-repository platform, current phase, what's not built yet. Start here. |
| [Architecture](architecture.md) | Request flow, the memory record contract, the database schema, the policy model, the error-handling model, security notes. |
| [Instructions](instructions.md) | Setup, local development loop, deploying to the LXC, adding a memory type, rotating credentials, service lifecycle. |
| [API examples](api-examples.md) | curl examples for every endpoint, including error responses. |
| [Make command reference](make-commands.md) | Every `Makefile` target: what it does, whether it changes state, whether it needs Docker. |
| [Troubleshooting](troubleshooting.md) | HTTP error code reference and diagnosis steps for storage/embedding/startup failures. |

The repository root also has:

- `plan.md` — the original architecture recommendation this repository
  implements (kept as the source design document, not maintained
  documentation; see `overview.md` for the current, accurate phase status).
- `AGENTS.md` — standing engineering rules for this repository (scope
  boundaries, policy invariants, security constraints).
- `CHANGELOG.md` — chronological record of changes.
- `PROVENANCE.md` — where this repository came from.

## Source-of-truth order

When documentation and implementation disagree, trust in this order:

1. `app/` — the executable application code.
2. `compose.yaml`, `.env.example`, `config/policy.yaml`.
3. `Makefile`, `tests/`, `.github/workflows/`.
4. This documentation and `CHANGELOG.md`.

Fix the discrepancy in the same change that introduced it. A document is not
a substitute for `make validate` (and, for anything touching Postgres or
Docker, a real `make up` run) passing.

## Keeping docs in sync

A change is not complete until the documentation it affects is updated —
see the review checklist in `instructions.md`. In particular:

- New or changed endpoint -> `api-examples.md`.
- New/changed error path or status code -> `api-examples.md` and
  `troubleshooting.md`.
- New Make target -> `make-commands.md`.
- Structural change (schema, request flow, a new abstraction) ->
  `architecture.md`.
- Phase status change (a Phase C-F item gets implemented) -> `overview.md`
  and `README.md`.
