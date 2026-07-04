# Phase 2 Premium UI / RTL Regression Report

Run date: 2026-07-04
Scope: Chunk 2 only - Phase 2 browser/real-use validation

Branch tested: `main`
HEAD SHA tested: `bdd23485c9c174fff96130fdd2a0cb2bc9c8f28f`

## Summary

PR #188 is merged. Phase 2 backend gates and frontend/e2e harness gates were
already clean before this browser run.

The real-use browser run stopped at the first required Phase 2 user-flow
blocker. UI login as the configured local admin succeeded, but after New Chat
the prompt was disabled with the user-visible placeholder:

`Please add a database connection first.`

That blocks prompt focus/draft entry, session creation, real Gemini query
submission, response-card validation, history validation, session isolation,
delete/undo, follow-up context, feedback, settings, and Arabic RTL browser
checks. No product code, test harness code, Phase 3-6 work, T-905, or freeze
tasks were started.

## Regression Task Matrix

| Task | Status | Evidence |
|---|---|---|
| New Chat creates a session, focuses prompt input, and stores preview text. | Fail | Browser login passed, but New Chat showed a disabled prompt requiring a database connection. See `screenshots/phase2-02-disabled-prompt-no-connection.png`. |
| Sidebar switches sessions, groups by Today / Previous 7 Days / Older, and supports delete with a 5-second undo window. | Blocked | Blocked before first session could be created. |
| Follow-up questions include the last N completed attempts according to admin context cap. | Blocked | Blocked before initial query submission. |
| Response card renders highlighted SQL, result table, copy/regenerate actions, thumbs feedback, implicit feedback, and saved state. | Blocked | Blocked before query submission/response card creation. |
| Admin settings can read/update LLM context cap in range 0-10. | Blocked | Not run after first required browser-flow blocker. |
| Arabic locale sets `dir="rtl"` and mirrors sidebar, bubbles, prompt input, forms, icons, and response chrome while SQL code remains LTR. | Blocked | Not run after first required browser-flow blocker. |
| LLM wire-format contract tests cover happy path, 429, 5xx, malformed response, and oversized schema context. | Pass | Backend precondition from PR #187: contract coverage included in `35 passed`. |
| Lifecycle invariant framework detects lock, feedback, and session-touch leaks. | Pass | Backend precondition from PR #187: lifecycle/session/feedback coverage included in backend gates. |

Task counts after browser run: Pass 2, Fail 1, Skipped 0, Blocked 5.

## Preflight

| Check | Status | Evidence |
|---|---|---|
| `rtk git status --short --branch` | Pass | `main...origin/main`; only old untracked Phase 1 evidence and new Phase 2 screenshots are present. |
| `rtk git rev-parse HEAD` | Pass | `bdd23485c9c174fff96130fdd2a0cb2bc9c8f28f`. |
| `docker compose -f docker-compose.dev.yml ps` | Pass | Backend/frontend up; data services healthy where applicable. |
| Confirm ports 5173 and 8000 listening | Pass | `ss -ltnp` showed `*:5173` and `*:8000` listening. |

## Browser Flows

| Task | Status | Evidence |
|---|---|---|
| Open frontend and sign in through UI. | Pass | Signed in as configured local admin. Screenshot: `screenshots/phase2-01-signed-in-workspace.png`. |
| Create a new chat/session and verify prompt focus and draft/preview behavior. | Fail | Prompt textarea was disabled after New Chat with placeholder requiring a database connection. Screenshot: `screenshots/phase2-02-disabled-prompt-no-connection.png`. |
| Submit a benign real query using the configured Gemini provider where applicable. | Blocked | Blocked by disabled prompt/no available database connection. |
| Verify response card: SQL display, result table, copy action, regenerate/reject/accept controls, saved state. | Blocked | Blocked before query submission. |
| Verify accepted query appears in History. | Blocked | Blocked before query submission. |
| Create a second session and switch between sessions; verify isolation. | Blocked | Blocked before first session could be created. |
| Verify sidebar grouping enough to identify current/recent sessions. | Blocked | Blocked before session creation. |
| Delete a session and use undo within the toast window. | Blocked | Blocked before session creation. |
| Submit a follow-up question and verify prior context behavior is functional. | Blocked | Blocked before initial query submission. |
| Use feedback controls if present. | Blocked | Blocked before response card creation. |
| Visit admin settings and verify LLM context cap read/update behavior if exposed. | Blocked | Not run after first required browser-flow blocker. |
| Switch to Arabic locale and verify RTL mirroring while SQL/code remains LTR. | Blocked | Not run after first required browser-flow blocker. |

## Real LLM Result

Blocked. `.env` is configured for Gemini with a Gemini key present, but live
Gemini query submission was not reached because the real app had no available
database connection and disabled the prompt.

## Evidence Files

- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-2-premium-ui-rtl-report.md`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-2-browser-smoke-evidence.json`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase2-01-signed-in-workspace.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase2-02-disabled-prompt-no-connection.png`

## Security and Privacy Notes

No secrets, cookies, passwords, full auth payloads, raw hostile prompts, raw
sensitive request bodies, or Playwright trace zips were stored in evidence.

Chunk 2 is not complete. Chunk 3 remains blocked until the Phase 2 real-use
browser/LLM flow can submit queries against an available database connection and
complete the remaining required checks.

## Blocker Triage Update - 2026-07-04

Branch: `fix/phase2-real-use-connection-seed`
HEAD SHA tested: `bdd23485c9c174fff96130fdd2a0cb2bc9c8f28f`

Root cause: stale dev platform DB state after RBAC/source-connection hardening.
The configured `source_analytics` row existed, but was `active` / `untested`
with schema introspection status `none`, zero schema entries, and no built-in
Admin `role_connection_policies` row. The `dbTest`-backed source Postgres DB
was reachable and populated: 29 public tables, `actor=200`, `customer=599`,
`film=1000`.

Fix: updated `backend/src/seed_e2e_connection.py`, the existing local E2E seed
support script, so it repairs the configured source connection from backend
environment, runs the normal connection health and schema refresh service
methods, and seeds the built-in Admin role policy from introspected schema
entries. No product behavior, RBAC checks, or frontend disabled-prompt behavior
was changed.

The patched support script was copied into the running backend container and
executed there so the repair used the same Compose network and environment as
the real app. After repair, `source_analytics` was `active` / `healthy`, schema
introspection was `success`, 171 schema entries were present, and the Admin
policy count was 1.

| Task | Status | Evidence |
|---|---|---|
| Verify Docker services and ports. | Pass | Docker compose services were running; required source/platform services were reachable. |
| Verify signed-in admin auth. | Pass | Real API sign-in returned 200 for the configured local admin; no secrets stored. |
| Verify `/api/v1/connections` for signed-in admin. | Pass | Returned one usable connection: `source_analytics`. |
| Inspect platform DB connection and RBAC state. | Pass | Before fix: one stale `source_analytics` row, no schema entries, no Admin policy. After fix: healthy/introspected with Admin policy present. |
| Verify `dbTest` source Postgres is reachable and populated. | Pass | 29 public tables; sampled counts matched expected Pagila data. |
| Repair deterministic dev/regression seed path. | Pass | `backend/src/seed_e2e_connection.py` now repairs the configured source connection and Admin policy idempotently. |
| Browser confirmation: New Chat prompt enabled. | Pass | Screenshot: `screenshots/phase2-03-prompt-enabled-after-seed.png`. |
| Browser confirmation: benign real query submits. | Pass | Response card rendered with result `count=200`; generated SQL was persisted. Screenshot: `screenshots/phase2-04-benign-query-after-seed.png`. |
| Focused backend checks. | Pass | `73 passed`: connection listing, admin connection lifecycle, connection service, role-policy model/endpoints. |
| `rtk git diff --check`. | Pass | No whitespace errors. |

Chunk 2 browser/LLM validation can resume after this support-code fix merges.
The full Phase 2 browser flow still needs to be rerun; this triage run only
cleared the no-available-connection blocker.
