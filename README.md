# log-whisperer

Paste a Python traceback or log. log-whisperer finds the likely cause, the culprit line and a fix.

## Quick start

Needs Docker with Compose v2.

```bash
cp .env.example .env
make up
```

| Service | URL |
|---|---|
| Web app | http://localhost:5173 |
| API | http://localhost:8000 (health: `/healthz`) |

Stop the stack with `make down`.

## Configuration

Compose reads these values from `.env`.

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `fake` | `fake` gives a deterministic diagnosis. `anthropic` calls the model API. |
| `ANTHROPIC_API_KEY` | empty | Required when `LLM_PROVIDER=anthropic`. The backend does not start without it. |
| `RATE_LIMIT_PER_MINUTE` | `10` | Requests per minute per client IP. Must be a positive integer. |

## Architecture

The backend uses ports and adapters. Imports point inward only, and `lint-imports` enforces this.

```
bootstrap ──► adapters ──► application ──► domain
(settings,    (FastAPI,     (AnalyzeLog     (Redactor, TracebackParser,
 wiring)       LLM)          use case)       GroundingPolicy, ports)
```

| Path | Contents |
|---|---|
| `backend/` | Python 3.12, FastAPI, uv |
| `frontend/` | Vite, React, TypeScript, Tailwind, TanStack Query |
| `SPEC.md` | Product and implementation spec |

## Commands

| Command | Result |
|---|---|
| `make install` | Installs backend and frontend dependencies. |
| `make up` / `make down` | Starts or stops the Compose stack. |
| `make lint` | Runs ruff, mypy, lint-imports, eslint and tsc. |
| `make test` | Runs pytest and vitest with coverage. |
| `make check-api` | Fails when the OpenAPI file or frontend API types are out of date. |
| `make fixtures` | Runs `backend/fixtures_src` under Python 3.10 to 3.13 and rewrites the fixtures. Needs uv 0.13.7 or later. |
| `uv run python scripts/perf_check.py` | Prints redactor and parser timings on adversarial input. Run it from `backend/`. It does not run in CI. |
| `make e2e` | Starts Compose with the fake provider and runs Playwright. |

## Conventions

- Frontend API types come from the backend OpenAPI file. Run `pnpm gen:api`; never edit `schema.ts`.
- Run `make lint && make test` before each pull request.
- Traceback fixtures come from real runs. Never edit a generated fixture; run `make fixtures`.
- No committed file holds a key-shaped string. `F11_secrets.txt` uses `{{secret:N}}`, and `expected.json` holds each secret in parts.
- Set `PW_CHROMIUM_PATH` to use a local Chromium for Playwright.

## Limits

| Limit | Value |
|---|---|
| Scope | Local Compose and CI only. No auth, database or cloud deploy. |
