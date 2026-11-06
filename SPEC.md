# log-whisperer — Implementation Spec

## 1. Context

**Product.** A developer pastes a Python stack trace or application log. log-whisperer identifies the likely cause, explains the failure, and suggests a fix.

**Users.** Backend developers in the middle of an incident. They need the culprit line and a concrete fix in seconds. They will act on what we say, so a confident wrong answer is worse than "low confidence".

**What "good" means for this product.**
1. **Grounded:** every file, line and function we cite exists in the pasted input. Never invented.
2. **Correct culprit:** we point at the user-code frame that actually caused the failure, not a library frame.
3. **Calibrated:** confidence is "low" when the input has no traceback or is ambiguous.
4. **Safe:** secrets in the pasted log are masked before anything leaves the server, and raw input is never stored or logged.
5. **Fast to scan:** culprit and fix are visible without scrolling on a laptop.

**Scope (v1).** Single-page web app + API. Local via Docker Compose and CI only. No auth, no database, no analytics, no cloud deploy.

## 2. Decisions already made (do not change)

| Area | Decision |
|---|---|
| Repo | Monorepo: `/backend`, `/frontend`, root `docker-compose.yml`, `Makefile`, `SPEC.md` (this file) |
| Backend | Python 3.12, FastAPI, uv, ruff, mypy `--strict`, pytest, pytest-cov, hypothesis, import-linter |
| Architecture | DDD + hexagonal (ports & adapters), see §3 |
| LLM | Anthropic Python SDK, model `claude-sonnet-5-5`. Structured output through one tool, `report_diagnosis`, with `strict: true` and `tool_choice: auto` (§6.1) |
| Default provider | `fake`. v1 is complete with the fake provider; the real-model eval (§7.5) runs when an API key exists |
| Frontend | Vite + React + TypeScript strict, pnpm, Tailwind + shadcn/ui, TanStack Query, Shiki, Vitest + Testing Library, Playwright |
| API types (FE) | Generated from backend OpenAPI via `openapi-typescript` — never hand-written |
| Runtime | Docker Compose (backend :8000, frontend :5173) |
| CI | GitHub Actions running `make lint`, `make check-api`, `make test`, `make e2e` |
| Fixture tooling | uv ≥ 0.13.7 (older uv has no downloads for the pinned Python patch versions) |

**Reference material**
- Python traceback format: https://docs.python.org/3/library/traceback.html
- Exception chaining (`__cause__` vs `__context__`): https://docs.python.org/3/library/exceptions.html
- Tool use (Messages API): https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview
- Hexagonal architecture contracts: https://import-linter.readthedocs.io/

## 3. Architecture

### 3.1 Backend layout

```
backend/
  pyproject.toml
  src/log_whisperer/
    domain/                 # pure Python: stdlib + dataclasses only
      model.py              # value objects, aggregates
      redaction.py          # Redactor (domain service)
      parsing.py            # TracebackParser (domain service)
      grounding.py          # GroundingPolicy (domain rule)
      ports.py              # DiagnosisGenerator Protocol
      errors.py             # DiagnosisUnavailable, etc.
    application/
      analyze_log.py        # AnalyzeLog use case
      dto.py                # AnalysisResult
    adapters/
      inbound/http/         # FastAPI app, Pydantic schemas, rate_limit.py, body_limit.py
      outbound/llm/
        anthropic_generator.py
        fake_generator.py   # deterministic, for tests + E2E
    bootstrap/
      container.py          # composition root; selects adapters from settings
      settings.py
  fixtures_src/             # tiny fake app that really raises errors (see §7.2)
  scripts/
    generate_fixtures.py
    eval.py
    export_openapi.py
    perf_check.py           # manual timing report, never in CI
  tests/
    domain/  application/  adapters/  fixtures/
```

### 3.2 Dependency rule (enforced)

`adapters → application → domain`. Never the reverse.

import-linter contracts in `backend/pyproject.toml`:
1. **Layers:** `bootstrap` > `adapters` > `application` > `domain`.
2. **Domain is pure:** `domain` must not import `fastapi`, `pydantic`, `anthropic`, `httpx`, `starlette`, or anything in `application`, `adapters`, `bootstrap`.
3. **Application is framework-free:** `application` must not import `fastapi`, `anthropic`, `pydantic`.

`lint-imports` is part of `make lint`. Contracts must never be weakened to make a check pass.

### 3.3 Frontend layout

```
frontend/src/
  api/schema.ts             # generated (pnpm gen:api)
  api/client.ts
  features/analyze/
    api/  components/  hooks/
  app/App.tsx
```

### 3.4 Request flow

```
HTTP POST /api/analyze
  → body cap (ASGI, before parsing) → rate limit (before parsing) → size / emptiness checks
  → AnalyzeLog use case
      RawLog → Redactor → RedactedLog
             → TracebackParser → ParsedLog
             → focus(RedactedLog) → FocusedLog (a RedactedLog)
             → DiagnosisGenerator port (Anthropic or Fake adapter) → Diagnosis
             → GroundingPolicy.enforce(Diagnosis, FocusedLog, kind) → GroundingResult
  → AnalysisResult DTO → JSON response
```

## 4. Domain model

All value objects are frozen dataclasses. No `Any` in `domain/`.

```text
RawLog(text: str)
RedactedLog(text: str, redaction_count: int)
Frame(file: str, line: int, func: str, code: str | None, is_user_code: bool)
ExceptionBlock(type: str, message: str, frames: tuple[Frame, ...],
               chain_reason: Literal["cause", "context"] | None)
ParsedLog(kind: Literal["python_traceback", "generic_log", "unknown"],
          exceptions: tuple[ExceptionBlock, ...],
          root_cause_index: int | None,
          culprit: Frame | None,
          log_levels: Mapping[str, int],
          truncated: bool)
Confidence = Enum(high, medium, low)
Fix(steps: tuple[str, ...], code_snippet: str | None, language: str | None)   # 1–6 steps
CulpritRef(file: str, line: int, func: str)
Diagnosis(summary: str,             # ≤ 200 chars
          likely_cause: str,
          confidence: Confidence,
          explanation: str,
          culprit: CulpritRef | None,
          fix: Fix,
          alternative_causes: tuple[str, ...],
          follow_up_checks: tuple[str, ...])
```

### 4.1 Redactor

`redact(RawLog) -> RedactedLog`. Replace matches with `[REDACTED:<type>]`:

| Type | Examples |
|---|---|
| aws_key | `AKIA[0-9A-Z]{16}` |
| bearer / jwt | `Bearer <token>`, `eyJ…\.eyJ…\.…` |
| api_key | `sk-…`, `pk-…`, `sk_live_…`, `sk_test_…` |
| url_credentials | `scheme://user:pass@host` (mask `user:pass` only) |
| email | standard email pattern |
| ipv4 | dotted quad |
| high_entropy | hex/base64 strings > 32 chars |

- Rules apply in the order of the table. A match is never re-matched by a later rule.
- **Linear time.** No pattern may scan to the end of the input from every start position. Bound each repetition before an anchor: URL scheme ≤ 32 chars, email local part found by matching one char + `@domain`, then extending left over local-part chars. `scripts/perf_check.py` reports adversarial 200 KB inputs (`aaaa…`, `a@a@…`, `a://…`, `a.a.…`); each must finish well under 1 s.
- Matches must not depend on what precedes them: `1xredis+tls://a:b@c` masks `a:b`; `x.y@ex.org%me@mail.example.com` masks both emails.

### 4.2 TracebackParser

`parse(RedactedLog) -> ParsedLog`. Rules:
- Detect tracebacks by `Traceback (most recent call last):` and the final `<Type>: <message>` line.
- Handle chaining: "The above exception was the direct cause of the following exception:" → `cause`; "During handling of the above exception, another exception occurred:" → `context`. Preserve order; `root_cause_index` = the first exception in the chain.
- `culprit` = deepest `is_user_code` frame of the root-cause exception. If the root cause has no user frames, use the deepest user frame of any exception in the chain; else `None`.
- `is_user_code = False` when the path contains `site-packages`, `dist-packages`, `/lib/python3.`, `<frozen`, `<string>`.
- Strip common log-line prefixes (timestamps, level, logger name, e.g. `2026-11-05 10:00:01,123 ERROR app.worker - `) before parsing.
- The exception message continues on following non-blank lines only while they carry the **same** stripped prefix as the exception line (both none, or identical). A new log record after a traceback never joins the message. Multi-line messages (SQLAlchemy) still parse.
- Ignore Python 3.11+ caret lines (`^^^^`, `~~~~`).
- Collapse `[Previous line repeated N more times]`; must finish in < 100 ms on RecursionError output.
- No traceback found: count `DEBUG/INFO/WARNING/ERROR/CRITICAL` → `kind="generic_log"` if any level found, else `"unknown"`.
- Input > 60,000 chars: keep all traceback blocks + the last 200 lines; `truncated=True`. `focus(RedactedLog) -> RedactedLog` returns exactly those kept lines (or the input unchanged when ≤ 60,000 chars). One helper computes the kept lines for both.
- **Never raises** on any input.

### 4.3 GroundingPolicy

`enforce(Diagnosis, RedactedLog, kind) -> GroundingResult(diagnosis, stripped)`:
- Remove any file path mentioned in `culprit`, `likely_cause`, `explanation`, `fix.steps` that does not appear verbatim in the redacted log (for prose fields, drop the sentence containing it).
- If `culprit` is removed → `culprit=None`, `confidence=low`.
- If `ParsedLog.kind != "python_traceback"` → cap confidence at `low`.
- `stripped` counts the removed items (culprit + sentences), exposed for eval metrics.
- A culprit is grounded only when its file and func appear and `file", line N` (or `file:N`) appears.

### 4.4 Port

```python
class DiagnosisGenerator(Protocol):
    def generate(self, redacted: RedactedLog, parsed: ParsedLog) -> Diagnosis: ...
```

Raises `DiagnosisUnavailable` on unrecoverable failure.

## 5. Application layer

`AnalyzeLog.execute(RawLog) -> AnalysisResult`

```text
AnalysisResult(diagnosis: Diagnosis, kind: str, truncated: bool,
               redaction_count: int, grounding_stripped: int)
```

Pipeline exactly as in §3.4. The generator only ever receives the focused `RedactedLog` and the `ParsedLog` — never `RawLog`. Grounding checks against the same focused text the generator saw.

## 6. Adapters

### 6.1 Anthropic adapter

- Model `claude-sonnet-5-5`; one tool `report_diagnosis` whose `input_schema` mirrors `Diagnosis`, with `strict: true`.
- `tool_choice: {"type": "auto"}`. This model rejects `tool` and `any` with HTTP 400. The system prompt tells the model to call `report_diagnosis` exactly once. A response with no `report_diagnosis` tool call (text reply, refusal) counts as invalid output.
- Strict schemas drop `maxLength`/`minItems`, so summary ≤ 200 chars and 1–6 fix steps are checked by Pydantic on our side.
- User message contains: the redacted log and the `ParsedLog` as JSON.
- System prompt must instruct:
  - Use the provided culprit unless the log clearly contradicts it; if you disagree, say why in `explanation`.
  - Only reference files, lines and functions that appear in the log.
  - Set `confidence: "low"` unless `kind` is `python_traceback` and the cause is clear.
  - Fix steps must be concrete and actionable (code-level), max 6.
- Validate tool output with Pydantic, map to domain `Diagnosis`. On invalid output retry once; then raise `DiagnosisUnavailable`.
- SDK client: `timeout=30`, `max_retries=0`. Any API error raises `DiagnosisUnavailable` at once; the message holds the error class and status only.
- API key from `ANTHROPIC_API_KEY`. `LLM_PROVIDER=anthropic` without a non-blank key fails at startup, not per request.

### 6.2 Fake adapter

Deterministic `Diagnosis` built from `ParsedLog`: culprit = parser culprit; `likely_cause` = root-cause type and first message line, plus `(surfaced as <later chain types>)` so F04 names `requests.exceptions.ConnectionError`; `code_snippet` = culprit source line; confidence high for tracebacks, low otherwise. Used by tests and E2E. Selected with `LLM_PROVIDER=fake` (the default).

### 6.3 HTTP API

`GET /healthz` → `200 {"status":"ok"}`

`POST /api/analyze`
Request: `{ "input": string }`

| Case | Status | Body |
|---|---|---|
| Success | 200 | `AnalysisResponse` (below) |
| Empty / whitespace | 400 | `{ "error": "Input is empty" }` |
| > 200 KB (204,800 bytes) | 413 | `{ "error": "Input too large" }` |
| Invalid body (missing `input`, wrong type, bad JSON) | 400 | `{ "error": "Invalid request" }` — never echo the input |
| > `RATE_LIMIT_PER_MINUTE` req/min per IP (default 10) | 429 | `{ "error": "Rate limit exceeded" }` |
| `DiagnosisUnavailable` / timeout | 502 | `{ "error": "Analysis failed" }` — no stack trace |
| Any other error | 500 | `{ "error": "Internal error" }` — no stack trace |

```json
AnalysisResponse {
  "diagnosis": {
    "summary": "string",
    "likely_cause": "string",
    "confidence": "high|medium|low",
    "explanation": "string",
    "culprit": { "file": "string", "line": 0, "func": "string" } | null,
    "fix": { "steps": ["string"], "code_snippet": "string|null", "language": "string|null" },
    "alternative_causes": ["string"],
    "follow_up_checks": ["string"]
  },
  "kind": "python_traceback|generic_log|unknown",
  "truncated": false,
  "redaction_count": 0
}
```

Rules:
- The 413 limit counts UTF-8 bytes of `input`. An ASGI middleware also caps the raw body (6 × 204,800 + 1 KB, covering JSON escapes) before parsing, including chunked bodies with no `Content-Length`.
- The rate limit runs before body parsing, so malformed requests count too. Sliding window per `request.client.host`, in memory; idle clients are evicted once per window so memory stays bounded.
- OpenAPI documents 200, 400, 413, 429, 502 with `ErrorResponse`, and does **not** document FastAPI's default 422.
- Logging: never log request bodies, raw input or the URL path. Log only request id, status, latency, kind, redaction_count. Uvicorn runs with `--no-access-log`.

## 7. Test strategy — what a good test is here

**Principles**
- Every check is **observable pass/fail**. "It works" is not a test.
- Assert **exact values** (exception type, culprit file *and* line, chain reason, status codes, counts). "Does not raise" alone only counts for the garbage-input case.
- **Deterministic layers get exact tests; the AI gets an eval** that checks structured fields, never wording.
- Tests are written against **real tracebacks generated by running real code**, not hand-typed imitations.
- Run `make lint && make test` after every change and before every PR.
- Never edit thresholds, `expected.json`, or import-linter contracts to make something pass.

### 7.1 Commands

| Command | Does |
|---|---|
| `make up` / `make down` | Compose stack |
| `make lint` | ruff, mypy --strict, lint-imports, eslint, tsc --noEmit |
| `make test` | pytest --cov (backend), vitest --coverage (frontend) |
| `make fixtures` | regenerate fixtures (§7.2) |
| `make check-api` | regenerate OpenAPI + FE types and fail if they differ from the committed files |
| `make eval` | run AI eval (§7.5), needs real API key |
| `make e2e` | compose up with `LLM_PROVIDER=fake RATE_LIMIT_PER_MINUTE=600`, Playwright, compose down |

### 7.2 Fixtures (generated from real code)

`backend/fixtures_src/` is a tiny fake app (`app/services/user.py`, `app/api/orders.py`, `app/clients/http.py`, `app/db/repo.py`, `app/worker.py`, `app/errors.py`) whose functions really raise each error. A fixtures-only dependency group installs `requests` and `sqlalchemy` so library frames are real.

`scripts/generate_fixtures.py` runs each scenario under Python **3.10, 3.11, 3.12, 3.13** (`uv python install`), captures stderr to `tests/fixtures/<ID>_py<ver>.txt`, and writes `tests/fixtures/expected.json` from the actual run (type, message, culprit file:line, chain length, chain reasons). Only F10–F12 are hand-written. Generated fixtures are never hand-edited.

| ID | Scenario | Key expectations |
|---|---|---|
| F01 | `KeyError: 'email'` in `app/services/user.py` `get_profile` | type KeyError; culprit that file:line |
| F02 | `AttributeError: 'NoneType' object has no attribute 'id'` in `app/api/orders.py` | culprit that file:line |
| F03 | `ModuleNotFoundError` for an uninstalled module imported in `app/clients/http.py` | culprit the import line |
| F04 | `requests.exceptions.ConnectionError` (to `localhost:1`) re-raised `from e` as `app.errors.UpstreamUnavailable` | Real requests/urllib3 give a 5-exception chain (`ConnectionRefusedError` → `NewConnectionError` → `MaxRetryError` → `requests…ConnectionError` → `UpstreamUnavailable`); last link `chain_reason="cause"`; `requests…ConnectionError` directly before it; `root_cause_index=0`; culprit = user frame that called requests |
| F05 | Same as F04 without `from` | last link `chain_reason="context"` |
| F06 | `RecursionError` | parses < 100 ms; repeated frames collapsed |
| F07 | SQLAlchemy `IntegrityError` (SQLite unique violation) | culprit = `app/db/repo.py` frame, not a library frame |
| F08 | F01 output with every line prefixed `2026-11-05 10:00:01,123 ERROR app.worker - ` | ParsedLog identical to F01 |
| F09 | `asyncio.TimeoutError` via `asyncio.wait_for` in a user coroutine | culprit user coroutine frame |
| F10 | *(hand-written)* JSON-lines log, 3 ERROR lines, no traceback | `generic_log`; `log_levels["ERROR"]==3`; culprit None |
| F11 | *(hand-written)* fake `AKIA…`, Bearer JWT, `sk-test_…`, `postgres://user:pass@host`, an email | `redaction_count==5`; none of the 5 originals remain. See key-shaped secrets below |
| F12 | *(hand-written)* `""`, `"hello world"`, 1 MB random bytes | `unknown`; never raises |

**Key-shaped secrets.** No committed file may hold a string that matches a secret scanner (`AKIA[0-9A-Z]{16}`, `sk-[A-Za-z0-9_-]{20,}`, …), not even a fake one. `F11_secrets.txt` holds `{{secret:N}}` placeholders; `expected.json` holds `F11.secret_parts`, each secret split into parts (`["AKIA", "FAKE…"]`). One loader (`fixture_text`) joins the parts and fills the placeholders; backend tests, `eval.py` and the Playwright spec all use it (or its one TypeScript twin). Inline test keys are built the same way (`"AKIA" + "…"`).

`generate_fixtures.py` pins exact Python patch versions and normalises machine-specific prefixes, so a rerun is byte-identical. sqlalchemy is pinned `<2.1` in the fixtures group (2.1 dropped Python 3.10).

`expected.json` also holds per-fixture **fix keywords** for the eval, e.g. F01 `[".get(", " in ", "KeyError"]`, F03 `["pip install", "requirements"]`, F07 `["unique", "duplicate", "upsert"]`, F04 `["retry", "timeout", "connection", "reachable"]`.

### 7.3 Backend tests

**Domain** (`tests/domain/`) — parametrized over every fixture × Python version:
- Exact type, message, culprit file+line, chain reasons, root cause index.
- Redaction: F11 count and absence of every original secret; no false positives on F01–F09 (Python file paths and line numbers untouched).
- GroundingPolicy: a Diagnosis citing `app/fake/nowhere.py:10` against F01 → stripped, culprit None, confidence low, `stripped == 1`.
- Property test (hypothesis): `parse()` never raises on arbitrary text; `redact()` output never contains a generated AWS-key-shaped string.
- Coverage: `domain/` ≥ **95%** lines and branches.

**Application** (`tests/application/`):
- **Secret leak test (most important):** spy `DiagnosisGenerator`; for F11 the `RedactedLog` it receives contains none of the 5 secrets.
- Hallucination test: generator returns a non-existent path → result culprit None, confidence low.
- Generator raises `DiagnosisUnavailable` → propagates as a domain error.

**Adapters** (`tests/adapters/`):
- Anthropic adapter with mocked SDK client: invalid then valid → success with 2 calls; invalid twice → `DiagnosisUnavailable`; request payload contains no raw secrets for F11.
- HTTP (TestClient + fake generator): 200 shape for F01; 400 empty and 400 invalid body; 200 at exactly 204,800 bytes and 413 at 204,801 (also UTF-8 multi-byte, and a chunked oversized body); 429 on the 11th request/min, malformed requests included; 502 body has no traceback; `/healthz` 200; OpenAPI response set is exactly 200/400/413/429/502.
- Rate limiter: window slides; idle clients are evicted.
- Settings: provider `anthropic` without key fails; `RATE_LIMIT_PER_MINUTE` rejects non-positive values.
- Captured app logs never contain any fixture's raw text or the request path.

**Architecture:** `lint-imports` all contracts KEPT. Prove the guardrail once: temporarily add `import fastapi` in `domain/__init__.py`, show `lint-imports` FAILS, revert — paste both outputs in the PR.

**Every new test must fail without the change it covers.** For a refactor, compare old and new behaviour on the same inputs (the redactor change in this spec was checked on 23,000+ inputs).

Overall backend coverage ≥ **90%**.

### 7.4 Frontend tests

- Component tests (Vitest + Testing Library) for each results card, textarea/counter, example selector, error state. Coverage on `src/features/analyze` ≥ **80%**, enforced as a Vitest threshold.
- A test checks the bundled examples are byte-identical to the backend fixtures.
- Test setup stubs `hasPointerCapture`, `releasePointerCapture`, `scrollIntoView` (jsdom lacks them; Radix Select calls them).
- E2E (Playwright) against the full Compose stack with `LLM_PROVIDER=fake`:

| ID | Flow | Expected |
|---|---|---|
| E1 | Load `/` → pick example F01 → Analyze | spinner shows and button disabled while in flight; Summary, Culprit (contains `app/services/user.py`), Fix render; Copy puts the snippet on the clipboard |
| E2 | Paste F04 → Ctrl/Cmd+Enter | results render; likely cause references ConnectionError |
| E3 | Paste F11 | "Masked 5 secrets before analysis" visible |
| E4 | Backend 502 (route intercepted) | inline error; textarea content kept; retry succeeds |
| E5 | Empty input; 204,801 chars | button disabled; counter red at limit |

- Visual checks: zero console errors on load and after analysis; screenshots at **1440px** and **375px**; no horizontal page scroll at 375px (code blocks scroll internally); Culprit + Fix above the fold at 1440px for F01.
- Record a video of E1 (fake provider is accepted for v1; real model when a key exists).
- Playwright saves the 1440px and 375px screenshots with `testInfo.outputPath`, so CI uploads them in `playwright-report`.
- `playwright.config.ts` reads an optional `PW_CHROMIUM_PATH` for a system Chromium; CI leaves it unset.

### 7.5 AI eval (`make eval`)

Runs every fixture (py3.12 variants + F10–F12) through `AnalyzeLog` with the real Anthropic adapter, **twice**, and prints a fixture × check table. Assert on fields, never wording.

| Check | Threshold |
|---|---|
| Schema valid | 12/12 |
| Grounding: paths not in input, *before* GroundingPolicy | 0 (report `grounding_stripped` total) |
| Culprit agrees with parser (F01–F09) | ≥ 8/9 |
| `likely_cause` or `explanation` names the exception type (F01–F09) | 9/9 |
| Fix relevance: `fix.steps` contains ≥ 1 expected keyword | ≥ 8/9 |
| Calibration: F10, F12 confidence `low` | 2/2 |
| Stability: run 1 and run 2 agree on culprit (F01–F09) | ≥ 8/9 |

If a threshold is missed: iterate on the system prompt (not the thresholds), max 3 iterations, and record each change and its effect.

The eval is a manual script outside the test suite; it never gates CI. Without an API key it is deferred, and v1 ships on the fake provider.

## 8. UI spec

No design file. Use shadcn/ui (`Card`, `Badge`, `Button`, `Textarea`, `Collapsible`, `Select`) with Tailwind defaults.

**Layout:** below `lg`, results follow the input. At `lg` and wider, input and results sit side by side, so Culprit and Fix stay above the fold at 1440 × 900.

**Input area**
- Title "log-whisperer" + tagline "Paste a Python traceback or log. Get the cause and a fix."
- Monospace `Textarea`, min 12 rows, no line wrap, placeholder showing a 3-line traceback.
- Example selector: F01, F04, F10 (loaded from bundled copies). Picking the same example again after an edit reloads it.
- Analyze button; Ctrl/Cmd+Enter shortcut; disabled when empty, over limit, or in flight.
- Counter `x / 200 KB` counts UTF-8 bytes (same rule as the backend), turns red over limit.

**Results (in order)**
1. **Summary** card with confidence badge (high = green, medium = amber, low = grey).
2. **Culprit** card: `file:line in func` (monospace). Hidden if null; show "No specific line identified" instead.
3. **Fix** card: numbered steps + Shiki-highlighted `code_snippet` with Copy button. Shiki loads on demand (core, JS regex engine, one theme); each grammar is its own chunk; unknown languages render as plain text; snippet HTML is escaped (tested with `<script>` input).
4. **Explanation** card.
5. Collapsibles: "Other possible causes", "What to check next".

**Notices**
- `redaction_count > 0` → "Masked N secrets before analysis".
- `truncated` → "Log was truncated to the relevant parts".

**States:** loading skeleton; spinner in the button while in flight; inline error with retry (retry resends the failed input); textarea content preserved on error. Network failure shows "Could not reach the server."; an error body without `error` shows `Request failed (<status>)`.

## 9. Infrastructure

- `docker-compose.yml`: `backend` (uvicorn on 8000, healthcheck `/healthz`), `frontend` (Vite dev on 5173, proxy `/api` → backend, `depends_on: backend: condition: service_healthy`).
- `.env.example`: `ANTHROPIC_API_KEY=`, `LLM_PROVIDER=fake`, `RATE_LIMIT_PER_MINUTE=10`. `.env` git-ignored.
- Compose passes `RATE_LIMIT_PER_MINUTE` through (default 10).
- `docker compose up -d` → both services healthy within 60 s.
- GitHub Actions: `make lint`, `make check-api`, `make test`, `make e2e` on every PR, and uploads `playwright-report`.
- Frontend `tsconfig.app.json` and `tsconfig.node.json` set `noEmit: true` (otherwise `tsc -b` writes `.js` beside sources and Vite resolves them before `.tsx`).
- `vite.config.ts`: `optimizeDeps.include` lists `shiki/core`, `shiki/engine/javascript`, `shiki/langs` (otherwise the dev server re-optimises and reloads the page mid-session); `server.watch.ignored` excludes `playwright-report` and `test-results`; `server.fs.allow` adds `../backend/tests/fixtures` only when `VITEST` is set.

## 10. Rules

- Run `make lint && make test` after every change and before every PR.
- Never weaken an import-linter contract, eval threshold, or expected.json to make a check pass.
- Never log, store, or send unredacted user input.

**Forbidden**
- Committing secrets or `.env`; real secrets in fixtures (use obviously fake values).
- Any Anthropic call or API key in the frontend.
- Framework/SDK imports in `domain/` or `application/`.
- Hand-editing generated fixtures or hand-writing FE API types.
- Adding auth, a database, analytics, or a cloud deploy.
- Editing thresholds, `expected.json` expectations, or import-linter contracts to force a pass.
- Committing any key-shaped string (§7.2).

## 11. Delivery

| Stage | Scope | Done when |
|---|---|---|
| 1 Scaffold | §2, §3 layout, §9, `/healthz`, health page, import-linter, Makefile, CI | Compose healthy; `make lint` green incl. lint-imports; guardrail proof in the PR; CI green |
| 2 Domain | §4, §7.2, §7.3 domain tests | All fixtures × 4 Python versions pass; domain coverage ≥ 95% |
| 3 Application, adapters, API, eval script | §5, §6, §7.3, §7.5 script | Backend coverage ≥ 90%; `make check-api` clean |
| 4 Frontend and E2E | §3.3, §8, §7.4 | `make e2e` green in CI; screenshots in the CI artifact |

- Each stage is one PR to `main`, squash-merged when CI is green.
- Public text (commits, PR titles and bodies, comments, docs, code comments) says what the system does and why. It names no tool, assistant or session, and carries no co-author trailer. Squash merges use an explicit message.
- The README holds: what it is, quick start, configuration table, architecture, commands, conventions, limits.
- Each decision that departs from this spec is written in the PR that makes it.
