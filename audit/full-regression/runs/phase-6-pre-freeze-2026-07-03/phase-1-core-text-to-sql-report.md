# Phase 1 Core Text-to-SQL Regression Report

Run date: 2026-07-03
Scope: Chunk 1 only - Phase 1 core text-to-SQL

## Summary

Branch tested: `main`
HEAD SHA tested: `5c4b855a977da85008b9b5d64c55721af14a40f3`

Result: Chunk 1 stopped at the first required backend gate. The acceptance test setup could not sign in as local admin and received `401 {"error":"unauthorized","message_key":"error.unauthorized"}`. Per the full regression runbook stop conditions, no Phase 2-6 checks were run and no product code was edited.

Chunk 2 status: blocked until the Phase 1 local-admin sign-in failure is resolved or explicitly classified as an environment-only issue by the owner.

## Regression Task Matrix

| Task | Status | Evidence |
|---|---|---|
| Local admin login and session expiry behavior. | Fail | Backend acceptance gate failed during `authenticated_acceptance_client` setup: local admin sign-in returned 401 unauthorized. See `logs/backend-phase1-integration.log`. Session expiry was not reached. |
| Unauthenticated users redirected away from platform features. | Blocked | Not run because the first backend gate stopped at local admin sign-in failure. |
| Question validation rejects empty and over-length prompts. | Blocked | Not run because the first backend gate stopped at local admin sign-in failure. |
| LLM provider selection follows config and receives schema context. | Blocked | Not run because the first backend gate stopped at local admin sign-in failure. |
| Evaluator blocks empty SQL, write/DDL SQL, unsafe PostgreSQL functions, multi-statement SQL, and missing schema objects. | Blocked | The selected test file started on data-modifying SQL coverage, but setup failed before the evaluator assertion ran. See `logs/backend-phase1-integration.log`. |
| Read-only source execution handles success, timeout, and zero-row results. | Blocked | Not run because the first backend gate stopped at local admin sign-in failure. |
| Accept persists accepted query and history; rejected/evaluator-rejected SQL is not durable history. | Blocked | Not run because the first backend gate stopped at local admin sign-in failure. |
| Reject/regenerate allows one distinct retry and blocks byte-identical retry. | Blocked | Not run because the first backend gate stopped at local admin sign-in failure. |
| History list/detail/filter behavior works from UI and API. | Blocked | Not run because the first backend gate stopped at local admin sign-in failure. |
| User-facing strings and component styles remain i18n/RTL-ready. | Blocked | Not run because the first backend gate stopped at local admin sign-in failure. |

Task counts: Pass 0, Fail 1, Skipped 0, Blocked 9.

## Commands Run

Pre-flight:

| Command | Exit | Notes |
|---|---:|---|
| `rtk git status --short --branch` | 0 | `main...origin/main`, clean before evidence folder creation. |
| `rtk git rev-parse HEAD` | 0 | `5c4b855a977da85008b9b5d64c55721af14a40f3`. |
| `rtk docker ps` | 1 | Initial sandboxed attempt could not access Docker socket. |
| `rtk docker compose -f docker-compose.dev.yml ps` | 1 | Initial sandboxed attempt could not access Docker socket. |
| `rtk ss -ltnp` | 0 | Sandboxed attempt could not open netlink socket and showed no useful port detail. |
| `rtk npm run` from `frontend/` | 0 | Listed frontend scripts. |
| `rtk npm exec playwright -- --version` from `frontend/` | 0 | Playwright 1.59.1. |
| `rtk docker ps` with escalation | 0 | Before startup, only unrelated `local-atlas-hybrid` container was present. |
| `rtk docker compose -f docker-compose.dev.yml ps` with escalation | 0 | Before startup, QueryCraft compose list was empty. |
| `rtk ss -ltnp` with escalation | 0 | Before startup, QueryCraft app/database ports were not listening. |
| `rtk docker compose -f docker-compose.dev.yml up -d` with escalation | 0 | Started QueryCraft stack. Platform Postgres, source Postgres, MySQL, MSSQL, and Redis reported healthy; backend and frontend started. |
| `rtk docker ps` with escalation | 0 | QueryCraft backend, frontend, platform/source DBs, Redis, MySQL, and MSSQL running; unrelated `local-atlas-hybrid` still restarting. |
| `rtk docker compose -f docker-compose.dev.yml ps` with escalation | 0 | QueryCraft services running; data services healthy. |
| `rtk ss -ltnp` with escalation | 0 | Ports `8000`, `5173`, `5433`, `5434`, `6379`, `3306`, and `1433` listening. |
| Safe shell env presence check | 0 | Runtime variables missing from current shell. |
| Safe `.env` presence check | 0 | Required QueryCraft runtime values set in `.env`; Anthropic/OpenAI keys empty; Gemini key set. No secret values printed. |

Chunk 1:

| Command | Exit | Notes |
|---|---:|---|
| `rtk mkdir -p audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots` | 0 | Created evidence directories. |
| Backend integration/acceptance pytest command, sandboxed | 2 | Did not reach tests because `uv` could not create a cache temp file under `/home/avril/.cache/uv` in sandbox. Rerun with escalation. |
| `cd backend && rtk uv run pytest tests/acceptance tests/integration/test_api_auth.py tests/integration/test_api_query.py tests/integration/test_api_history.py tests/integration/test_accept_only_persistence.py tests/integration/test_regenerate_then_accept.py tests/integration/test_evaluator_gate.py tests/integration/test_us5_provider_switch.py tests/integration/test_us5_reconfigured_provider.py -x --tb=short` with escalation | 1 | Collected 54 items, stopped on first error: local admin sign-in returned 401 in `tests/acceptance/conftest.py`. Log: `logs/backend-phase1-integration.log`. |
| `rtk git diff --check` | 0 | Passed. Log: `logs/git-diff-check.log`. |

Not run due stop condition:

- Phase 1 backend unit pytest command.
- Phase 1 backend `ruff check`.
- Phase 1 backend `ruff format --check`.
- Phase 1 frontend unit/lint/typecheck/build/style gates.
- Phase 1 Playwright e2e command.
- Real-use manual/browser Playwright smoke.
- Real LLM text-to-SQL smoke.

## Browser Flows Actually Completed

None. The runbook requires stopping after the failed backend foundation gate. The real frontend was started through Docker and port `5173` was listening, but no browser interaction was performed after the backend gate failed.

## Real LLM Result

Skipped. `.env` has `LLM_PROVIDER`, `LLM_API_KEY_GEMINI`, and `LLM_MODEL_NAME` set, but the live LLM smoke was not run because Chunk 1 stopped at the required backend acceptance gate before browser/API smoke execution.

## Evidence Files

- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-1-core-text-to-sql-report.md`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/backend-phase1-integration.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/git-diff-check.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/` (created, empty because browser smoke did not run)

## Security and Privacy Notes

No browser/API smoke reached user-visible error screens. The captured backend failure response was sanitized (`error.unauthorized`, `message_key: error.unauthorized`) and did not expose credentials, stack traces, or provider keys.
