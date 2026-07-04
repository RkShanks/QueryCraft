# Phase 2 Premium UI / RTL Regression Report

Run date: 2026-07-04
Scope: Chunk 2 only - Phase 2 premium UI / RTL / sessions

Branch tested: `fix/phase2-auth-fixture-sync`
Base HEAD SHA tested: `0ff7f8a2b2d2eb06409fed80428f1537c1edb7ab`

## Summary

The Phase 2 backend gate blocker is fixed in the test harness. The original
failure was shared fixture drift: global `authenticated_client` did not sync the
built-in local admin before sign-in, while the Phase 1 acceptance-specific
fixture already did. After adding the sync dependency and updating stale Phase 2
integration fixtures for the current Phase 5/6 auth/RBAC/query-service
contracts, the required Phase 2 backend acceptance/integration/contract command
passes.

Per the current fix scope, Phase 2 browser/LLM validation was not run. Phases
3-6 and T-905 were not started. No product code was edited.

## Regression Task Matrix

| Task | Status | Evidence |
|---|---|---|
| New Chat creates a session, focuses prompt input, and stores preview text. | Pass | `tests/acceptance/test_session_conversation.py` and `tests/integration/test_sessions.py` passed in `logs/phase2-backend-acceptance-integration-contract.log`. Browser UI smoke remains to resume after merge. |
| Sidebar switches sessions, groups by Today / Previous 7 Days / Older, and supports delete with a 5-second undo window. | Blocked | Backend session API coverage passed; browser sidebar/delete/undo smoke was intentionally not run in this fix. |
| Follow-up questions include the last N completed attempts according to admin context cap. | Pass | Session conversation acceptance and admin settings integration coverage passed; live browser follow-up smoke remains to resume after merge. |
| Response card renders highlighted SQL, result table, copy/regenerate actions, thumbs feedback, implicit feedback, and saved state. | Pass | Backend feedback and session conversation tests passed; browser response-card smoke was intentionally not run in this fix. |
| Admin settings can read/update LLM context cap in range 0-10. | Pass | `tests/integration/test_admin_settings.py` and `tests/unit/test_admin_settings_unit.py` passed. |
| Arabic locale sets `dir="rtl"` and mirrors sidebar, bubbles, prompt input, forms, icons, and response chrome while SQL code remains LTR. | Blocked | Frontend RTL gates/browser smoke were intentionally not run in this backend-only fix. |
| LLM wire-format contract tests cover happy path, 429, 5xx, malformed response, and oversized schema context. | Pass | `tests/contract/test_gemini_contract.py` and `tests/unit/llm/test_gemini_adapter.py` passed. |
| Lifecycle invariant framework detects lock, feedback, and session-touch leaks. | Pass | `tests/integration/test_f011_lock_leak.py`, `tests/integration/test_feedback.py`, and `tests/unit/llm/test_adapter_lifecycle.py` passed. |

Task counts after backend fix: Pass 6, Fail 0, Skipped 0, Blocked 2.

## Commands Run

| Command | Exit | Notes |
|---|---:|---|
| `rtk git status --short --branch` | 0 | Started on `main`; switched to `fix/phase2-auth-fixture-sync` for edits. |
| `rtk git rev-parse HEAD` | 0 | Base tested before edits: `0ff7f8a2b2d2eb06409fed80428f1537c1edb7ab`. |
| `rtk docker compose -f docker-compose.dev.yml ps` | 0 | Compose stack running; backend/frontend up and data services healthy. |
| `cd backend && rtk uv run pytest tests/acceptance/test_session_conversation.py tests/integration/test_sessions.py tests/integration/test_feedback.py tests/integration/test_admin_settings.py tests/integration/test_f011_lock_leak.py tests/contract/test_gemini_contract.py -x --tb=short` | 0 | 35 passed. See `logs/phase2-backend-acceptance-integration-contract.log`. |
| `cd backend && rtk uv run pytest tests/unit/test_admin_settings_unit.py tests/unit/test_session_repository.py tests/unit/test_session_extension.py tests/unit/test_feedback_router.py tests/unit/llm/test_gemini_adapter.py tests/unit/llm/test_adapter_lifecycle.py -x --tb=short` | 0 | 40 passed. See `logs/phase2-backend-unit.log`. |
| `cd backend && rtk uv run ruff check src tests` | 0 | Passed. See `logs/phase2-backend-ruff-check.log`. |
| `cd backend && rtk uv run ruff format --check src tests` | 0 | Passed. See `logs/phase2-backend-ruff-format.log`. |
| `rtk git diff --check` | 0 | Passed. |

Not run by request:

- Phase 2 frontend unit/lint/typecheck/build/style/e2e gates.
- Phase 2 browser smoke.
- Real Gemini follow-up conversation smoke.
- Phases 3-6 and T-905.

## Browser Flows

| Flow | Status | Evidence |
|---|---|---|
| Open frontend and sign in through UI. | Blocked | Backend gate is now clean; browser validation intentionally deferred until after merge. |
| Create new chat/session and submit benign question. | Blocked | Browser validation intentionally deferred until after merge. |
| Verify response card controls. | Blocked | Browser validation intentionally deferred until after merge. |
| Create second session and verify session isolation. | Blocked | Browser validation intentionally deferred until after merge. |
| Verify sidebar grouping. | Blocked | Browser validation intentionally deferred until after merge. |
| Delete session and undo. | Blocked | Browser validation intentionally deferred until after merge. |
| Submit follow-up and verify context behavior. | Blocked | Browser validation intentionally deferred until after merge. |
| Use feedback controls. | Blocked | Browser validation intentionally deferred until after merge. |
| Visit admin settings and verify context cap behavior. | Blocked | Browser validation intentionally deferred until after merge. |
| Switch to Arabic and inspect RTL behavior. | Blocked | Browser validation intentionally deferred until after merge. |

## Real LLM Result

Blocked by scope. The backend contract/unit checks passed, but the live Gemini
follow-up conversation smoke was intentionally not run during this backend
test-harness fix. No provider secrets were printed or stored.

## Evidence Files

- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-2-premium-ui-rtl-report.md`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-2-browser-smoke-evidence.json`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/phase2-backend-acceptance-integration-contract.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/phase2-backend-unit.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/phase2-backend-ruff-check.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/phase2-backend-ruff-format.log`

No Phase 2 screenshots were captured because browser validation did not run.

## Security and Privacy Notes

No secrets, cookies, passwords, full auth payloads, or raw sensitive request
bodies were stored in Phase 2 evidence. The original auth failure and subsequent
test-harness checks used sanitized errors only.

Chunk 2 backend validation is clean. Chunk 2 browser/LLM validation can resume
after this fix merges. Chunk 3 remains blocked until the remaining Chunk 2
frontend/browser/LLM validation completes.
