SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

BACKEND := cd backend &&
FRONTEND := cd frontend &&
E2E_ENV := LLM_PROVIDER=fake RATE_LIMIT_PER_MINUTE=600

.PHONY: install up down lint test fixtures check-api eval e2e screenshots

install:
	$(BACKEND) uv sync --locked
	$(FRONTEND) pnpm install --frozen-lockfile

up:
	docker compose up -d --build --wait

down:
	docker compose down

lint:
	$(BACKEND) uv run ruff check .
	$(BACKEND) uv run ruff format --check .
	$(BACKEND) uv run mypy
	$(BACKEND) uv run lint-imports
	$(FRONTEND) pnpm lint
	$(FRONTEND) pnpm typecheck

test:
	$(BACKEND) uv run pytest --cov
	$(FRONTEND) pnpm test

fixtures:
	$(BACKEND) uv run python scripts/generate_fixtures.py

check-api:
	$(BACKEND) uv run python scripts/export_openapi.py openapi.json
	$(FRONTEND) pnpm gen:api
	git diff --exit-code -- backend/openapi.json frontend/src/api/schema.ts

eval:
	$(BACKEND) uv run python scripts/eval.py

e2e:
	$(E2E_ENV) docker compose up -d --build --wait
	$(FRONTEND) pnpm e2e || { mkdir -p frontend/test-results; docker compose logs --no-color > frontend/test-results/compose.log 2>&1 || true; docker compose down; exit 1; }
	docker compose down

screenshots:
	$(E2E_ENV) docker compose up -d --build --wait
	$(FRONTEND) README_SCREENSHOTS=1 pnpm exec playwright test e2e/readme-screenshots.spec.ts || { docker compose down; exit 1; }
	docker compose down
