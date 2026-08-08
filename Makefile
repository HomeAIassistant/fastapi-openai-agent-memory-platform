SHELL := /bin/bash
.PHONY: help env-init env-check style-check unit validate build up down restart logs ps health test

help: ## Show this command reference.
	@grep -E '^[a-zA-Z0-9_.-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

env-init: ## Create .env from .env.example, generating the bearer token and DB password.
	@if [ -f .env ]; then \
		echo ".env already exists; refusing to overwrite. Edit it directly or use env-check." >&2; \
		exit 1; \
	fi
	@cp .env.example .env
	@token="$$(openssl rand -hex 32)"; \
	password="$$(openssl rand -hex 24)"; \
	sed -i "s/^MEMORY_API_TOKEN=.*/MEMORY_API_TOKEN=$$token/" .env; \
	sed -i "s/^MEMORY_POSTGRES_PASSWORD=.*/MEMORY_POSTGRES_PASSWORD=$$password/" .env
	@if [ -n "$(LXC_HOST_IP)" ]; then \
		sed -i "s/^MEMORY_API_BIND_ADDRESS=.*/MEMORY_API_BIND_ADDRESS=$(LXC_HOST_IP)/" .env; \
	fi
	@echo "Wrote .env with a generated MEMORY_API_TOKEN and MEMORY_POSTGRES_PASSWORD."

env-check: ## Verify .env exists and contains no unresolved placeholders.
	@test -f .env || { echo ".env is missing; run 'make env-init' first." >&2; exit 1; }
	@! grep -q 'GENERATE_ME' .env || { echo ".env still contains a GENERATE_ME placeholder." >&2; exit 1; }
	@echo ".env is present and has no unresolved placeholders."

style-check: ## Run Ruff lint and format checks.
	@. .venv/bin/activate 2>/dev/null || true; \
	ruff check . && ruff format --check .

unit: ## Run the pytest suite against the in-memory repository (no Docker needed).
	@. .venv/bin/activate 2>/dev/null || true; \
	pytest -q

test: unit ## Alias for `make unit`.

validate: style-check unit ## Run static checks and the unit test suite.

build: ## Build the production API image.
	docker compose build api

up: env-check ## Build, start postgres + api, and wait for both to become healthy.
	docker compose up -d --build --wait

down: ## Stop the deployment while preserving the Postgres volume.
	docker compose down

restart: ## Restart the running deployment.
	docker compose restart

logs: ## Follow logs for the running deployment.
	docker compose logs -f --tail=200

ps: ## Show the running deployment's service status.
	docker compose ps

health: ## Curl /health and /ready on the running deployment.
	@set -a; . .env; set +a; \
	base="http://$${MEMORY_API_BIND_ADDRESS:-127.0.0.1}:$${MEMORY_API_PORT:-8200}"; \
	curl --fail --show-error "$$base/health" && echo; \
	curl --fail --show-error "$$base/ready" && echo
