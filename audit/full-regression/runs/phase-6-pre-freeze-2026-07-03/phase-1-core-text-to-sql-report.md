# Phase 1 Core Text-to-SQL Regression Report

Run date: 2026-07-03
Scope: Chunk 1 only - Phase 1 core text-to-SQL

## Summary

Original branch tested: `main`
Original HEAD SHA tested: `5c4b855a977da85008b9b5d64c55721af14a40f3`
Fix/evidence branch: `test/full-regression-phase-1`

Original result: Chunk 1 stopped at the first required backend gate. The acceptance test setup could not sign in as local admin and received `401 {"error":"unauthorized","message_key":"error.unauthorized"}`. Per the full regression runbook stop conditions, no Phase 2-6 checks were run and no product code was edited.

Current update: Docker is reachable and the QueryCraft compose stack is running. The Phase 1 backend acceptance/integration command now passes against the current PR branch after test-harness fixes. The stale `400` vs `422` failure in the previous rerun log is resolved; the latest `backend-phase1-integration-rerun.log` is passing evidence, not an unresolved failure.

Chunk 1 status: backend acceptance/integration and backend unit gates are unblocked. Browser and real-LLM validation were intentionally not resumed in this PR update.

Chunk 2 status: do not start yet. Chunk 1 browser/LLM validation can resume after PR #186 is merged or re-reviewed and approved.

## Regression Task Matrix

| Task | Status | Evidence |
|---|---|---|
| Local admin login and session expiry behavior. | Pass | Original failure reproduced in `logs/backend-phase1-integration.log`: acceptance sign-in returned 401. Current rerun passes `tests/acceptance/test_auth_fixture.py` inside the full Phase 1 backend command. |
| Unauthenticated users redirected away from platform features. | Pass | `tests/integration/test_api_auth.py` passed in `logs/backend-phase1-integration-rerun.log`. |
| Question validation rejects empty and over-length prompts. | Pass | `tests/integration/test_api_query.py` passed in `logs/backend-phase1-integration-rerun.log`. |
| LLM provider selection follows config and receives schema context. | Pass | `tests/integration/test_us5_provider_switch.py`, `tests/integration/test_us5_reconfigured_provider.py`, and Phase 1 LLM unit tests passed in current backend logs. |
| Evaluator blocks empty SQL, write/DDL SQL, unsafe PostgreSQL functions, multi-statement SQL, and missing schema objects. | Pass | `tests/acceptance/test_data_modifying_sql_blocked.py`, `test_multi_statement_blocked.py`, `test_schema_invalid_sql_blocked.py`, `test_unsafe_pattern_blocked.py`, and `tests/integration/test_evaluator_gate.py` passed in `logs/backend-phase1-integration-rerun.log`. |
| Read-only source execution handles success, timeout, and zero-row results. | Pass | `tests/acceptance/test_valid_select_passes.py` and `test_query_timeout.py` passed in `logs/backend-phase1-integration-rerun.log`. |
| Accept persists accepted query and history; rejected/evaluator-rejected SQL is not durable history. | Pass | `tests/integration/test_api_history.py`, `test_accept_only_persistence.py`, and acceptance evaluator rejection coverage passed in `logs/backend-phase1-integration-rerun.log`. |
| Reject/regenerate allows one distinct retry and blocks byte-identical retry. | Pass | `tests/integration/test_regenerate_then_accept.py` and `tests/unit/services/test_query_service_regenerate.py` passed in current backend logs. |
| History list/detail/filter behavior works from UI and API. | Pass | API history coverage passed in `logs/backend-phase1-integration-rerun.log`; browser history validation was not rerun in this PR update. |
| User-facing strings and component styles remain i18n/RTL-ready. | Skipped | Not part of this backend test-harness PR update; frontend/browser gates were intentionally not run. |

Task counts: Pass 9, Fail 0, Skipped 1, Blocked 0.

## Fix Branch Rerun Update

Root cause of the original 401: acceptance tests did not reseed/sync the local built-in admin after Phase 5 local-login/RBAC hardening. Integration tests had their own admin reseed, but acceptance tests signed in against the persistent test database state. When the password or role linkage drifted, `authenticated_acceptance_client` received the expected generic 401 from `AuthService`.

Root cause of the stale `400` vs `422` failure: the Phase 1 submit harness was stale for the current API/RBAC contract. Submit requests now require a valid `connection_id`, source connections must be healthy/introspected, and role-bearing users require `role_connection_policies`. Without a deterministic connection and Admin allow policy, the request can fail before reaching the evaluator path the old test expected. The current product contract remains fail-closed and sanitized; no product code change was required.

Fix applied:

- Added/reused test harness seeding so the built-in local admin signs in with the configured test password and Admin `role_id`.
- Added acceptance regression coverage for the authenticated acceptance client.
- Updated Phase 1 submit tests to use a shared `query_submit_payload()` fixture because the current API requires `connection_id`.
- Tightened `ensure_db_connection` to return a deterministic named healthy/introspected source connection.
- Seeded an Admin `role_connection_policies` row for the deterministic test connection, preserving Phase 5/6 fail-closed RBAC behavior.
- Updated stale acceptance expectations for current sanitized evaluator responses and current fail-fast rule ordering.
- Stubbed external LLM/source-execution boundaries in API integration tests where the test subject is router/service behavior, not live provider execution.

## Docker Status

| Command | Exit | Notes |
|---|---:|---|
| `rtk docker ps` | 0 | QueryCraft backend, frontend, platform/source Postgres, Redis, MySQL, and MSSQL containers running; data services healthy. |
| `rtk docker compose -f docker-compose.dev.yml ps` | 0 | QueryCraft compose stack running with backend on `8000`, frontend on `5173`, platform Postgres on `5433`, source Postgres on `5434`, Redis on `6379`, MySQL on `3306`, and MSSQL on `1433`. |

## Commands Run

Pre-flight and reproduction:

| Command | Exit | Notes |
|---|---:|---|
| `rtk git pull --ff-only` | 0 | Branch `test/full-regression-phase-1` already up to date before rerun work. |
| `rtk docker ps` | 0 | Docker reachable; QueryCraft services running. |
| `rtk docker compose -f docker-compose.dev.yml ps` | 0 | Compose stack reachable and running. |
| Phase 1 backend acceptance/integration command before fix | 1 | Reproduced local admin sign-in 401 in `logs/backend-phase1-integration.log`. |

Current gates:

| Command | Exit | Notes |
|---|---:|---|
| `cd backend && rtk uv run pytest tests/acceptance tests/integration/test_api_auth.py tests/integration/test_api_query.py tests/integration/test_api_history.py tests/integration/test_accept_only_persistence.py tests/integration/test_regenerate_then_accept.py tests/integration/test_evaluator_gate.py tests/integration/test_us5_provider_switch.py tests/integration/test_us5_reconfigured_provider.py -x --tb=short` | 0 | 55 passed in 14.52s. See `logs/backend-phase1-integration-rerun.log`. |
| `cd backend && rtk uv run pytest tests/unit/evaluator tests/unit/llm tests/unit/test_query_service_submit.py tests/unit/test_query_service_accept.py tests/unit/services/test_query_service_reject.py tests/unit/services/test_query_service_regenerate.py tests/unit/test_history_service.py tests/unit/test_schemas_query.py -x --tb=short` | 0 | 242 passed in 0.95s. See `logs/backend-phase1-unit-after-fix.log`. |
| `cd backend && rtk uv run ruff check src tests` | 0 | Passed. See `logs/backend-ruff-check-after-fix.log`. |
| `cd backend && rtk uv run ruff format --check src tests` | 0 | Passed. See `logs/backend-ruff-format-after-fix.log`. |
| `rtk git diff --check` | 0 | Passed. See `logs/git-diff-check-after-fix.log`. |

Not run in this PR update:

- Phase 1 frontend unit/lint/typecheck/build/style gates.
- Phase 1 Playwright e2e command.
- Real-use manual/browser Playwright smoke.
- Real LLM text-to-SQL smoke.
- Phases 2-6.

## Browser Flows Actually Completed

None in this PR update. The requested scope was to cleanly rerun and fix the Phase 1 backend acceptance/integration evidence only. Browser validation remains the next Chunk 1 activity after PR #186 is re-reviewed/merged.

## Real LLM Result

Skipped in this PR update. The previous Chunk 1 run found `.env` had real Gemini configuration present, but live LLM smoke was not resumed because this PR update was limited to backend test-harness evidence.

## Evidence Files

- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-1-core-text-to-sql-report.md`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/backend-phase1-integration.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/backend-phase1-integration-repro.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/backend-phase1-integration-rerun.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/backend-phase1-unit-after-fix.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/backend-ruff-check-after-fix.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/backend-ruff-format-after-fix.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/git-diff-check.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/git-diff-check-after-fix.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/` (created, empty because browser smoke did not run)

## Security and Privacy Notes

No secrets were printed. Captured auth failures are sanitized (`error.unauthorized`, `message_key: error.unauthorized`). Current evaluator/API responses used by the tests remain sanitized and do not echo unsafe SQL fragments or unknown schema identifiers.
