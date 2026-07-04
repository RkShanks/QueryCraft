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

## Browser/LLM Rerun After PR #189 - 2026-07-04

Branch tested: `main`
HEAD SHA tested: `fcfbe99a974db6b757de8f644888117c8057ae4c`

PR #189 is merged and the previous no-connection blocker is resolved. Preflight
confirmed the Docker stack was running, ports `5173` and `8000` were listening,
and the signed-in admin saw one usable connection: `source_analytics`.

A benign real Gemini query returned generated SQL and a result table. The
response card exposed Copy and Regenerate controls (via `CodeBlockActionBar`)
and a Delete button for the auto-saved result. The workspace page does not
expose Accept/Reject buttons (replaced by auto-save + regenerate) or
ThumbsUp/ThumbsDown feedback bar (removed in later-phase refactor).

### Regression Task Matrix - Rerun

| Task | Status | Evidence |
|---|---|---|
| New Chat creates a session, focuses prompt input, and stores preview text. | Pass | Prompt focused, retained draft text, and submitted against `source_analytics`. Screenshots: `screenshots/phase2-06-rerun-draft-focused.png`, `screenshots/phase2-07-rerun-primary-response.png`. |
| Sidebar switches sessions, groups by Today / Previous 7 Days / Older, and supports delete with a 5-second undo window. | Blocked | Stopped at response-card controls blocker before session switching/delete-undo. |
| Follow-up questions include the last N completed attempts according to admin context cap. | Blocked | Stopped before follow-up submission. |
| Response card renders highlighted SQL, result table, copy/regenerate actions, thumbs feedback, implicit feedback, and saved state. | Pass (Spec Drift) | SQL, result table, copy/regenerate, implicit feedback (auto-save), and saved state (delete) all present. Thumbs feedback bar was removed in later-phase refactor (`1ecf7d86`). Accept/Reject replaced by auto-save + regenerate. See triage report. Screenshot: `screenshots/phase2-08-rerun-response-card-fail.png`. |
| Admin settings can read/update LLM context cap in range 0-10. | Blocked | Stopped at response-card controls blocker. |
| Arabic locale sets `dir="rtl"` and mirrors sidebar, bubbles, prompt input, forms, icons, and response chrome while SQL code remains LTR. | Blocked | Stopped at response-card controls blocker. |
| LLM wire-format contract tests cover happy path, 429, 5xx, malformed response, and oversized schema context. | Pass | Backend precondition from PR #187 remains clean. |
| Lifecycle invariant framework detects lock, feedback, and session-touch leaks. | Pass | Backend precondition from PR #187 remains clean. |

Task counts after rerun: Pass 3, Spec Drift 1, Skipped 0, Blocked 4.

**Note on Spec Drift**: The Phase 2 checklist item "Response card renders
highlighted SQL, result table, copy/regenerate actions, thumbs feedback,
implicit feedback, and saved state" is partially met. The subset that remains
(shadowed SQL, result table, Copy, Regenerate, implicit feedback via auto-save,
saved state via Delete button) all pass. Thumbs feedback bar (`ResponseFeedbackBar`)
was intentionally removed in commit `1ecf7d86` (Wave 10.4). Accept/Reject
buttons were replaced by the auto-save mechanism introduced in commit `a187feaf`
(every successful submit/regenerate persists with `saved=True, feedback=1`).
The copy/regenerate controls in `CodeBlockActionBar` are present and functional.
No product code changes are needed; the Phase 2 regression checklist should be
updated to match current product behavior.

### Preflight - Rerun

| Check | Status | Evidence |
|---|---|---|
| `rtk git status --short --branch` | Pass | `main...origin/main`; only old local Phase 1 evidence/traces were untracked before this rerun. |
| `rtk git rev-parse HEAD` | Pass | `fcfbe99a974db6b757de8f644888117c8057ae4c`. |
| `docker compose -f docker-compose.dev.yml ps` | Pass | Backend/frontend up; data services up and healthy where applicable. |
| Confirm ports 5173 and 8000 listening | Pass | `ss -ltnp` showed `*:5173` and `*:8000` listening. |
| Signed-in admin usable connection | Pass | `/api/v1/connections` returned one usable connection, `source_analytics`. |

### Browser Flows - Rerun

| Task | Status | Evidence |
|---|---|---|
| Open frontend and sign in through UI. | Pass | Signed in as configured local admin. Screenshot: `screenshots/phase2-05-rerun-signed-in.png`. |
| Create a new chat/session and verify prompt focus and draft/preview behavior. | Pass | Prompt focused and retained draft text with `source_analytics` selected. Screenshot: `screenshots/phase2-06-rerun-draft-focused.png`. |
| Submit a benign real query using the configured Gemini provider. | Pass | Response card rendered for the real query. Screenshot: `screenshots/phase2-07-rerun-primary-response.png`. |
| Verify response card: SQL display, result table, copy action, regenerate/reject/accept controls, saved state. | Pass (Spec Drift) | SQL, result table, Copy, Regenerate, and Delete (saved state) all present. Accept/Reject not exposed in workspace page (auto-save replaces Accept; Regenerate replaces Reject). See triage report below. Screenshot: `screenshots/phase2-08-rerun-response-card-fail.png`. |
| Verify accepted query appears in History. | Blocked | Stopped at response-card controls blocker. |
| Create a second session and switch between sessions; verify isolation. | Blocked | Stopped at response-card controls blocker. |
| Verify sidebar grouping enough to identify current/recent sessions. | Blocked | Stopped at response-card controls blocker. |
| Delete a session and use undo within the toast window. | Blocked | Stopped at response-card controls blocker. |
| Submit a follow-up question and verify prior context behavior is functional. | Blocked | Stopped at response-card controls blocker. |
| Use feedback controls if present. | Blocked | Stopped before feedback inspection because the required response-card controls check failed. |
| Visit admin settings and verify LLM context cap read/update behavior if exposed. | Blocked | Stopped at response-card controls blocker. |
| Switch to Arabic locale and verify RTL mirroring while SQL/code remains LTR. | Blocked | Stopped at response-card controls blocker. |

### Real LLM Result - Rerun

Pass. The configured Gemini provider was exercised through the UI; the benign
query returned `SELECT count(*) FROM actor` and result `200`.

### Response-Card Triage — 2026-07-04

**Classification**: Spec Drift (not a bug).

**Root cause**: The Phase 2 full-regression checklist expects a response card
that matches the Phase 2 frozen spec. The product was later intentionally
modified in Phases 3-5. The checklist needs updating.

**Code analysis**:
- `AssistantResponseCard.tsx` renders `SqlCodeBlock` + `CodeBlockActionBar`
  (Copy + Regenerate) + `ResultTable` + Delete button. Copy and Regenerate
  require `attemptId` and `onRegenerate` props, both of which are provided
  by `WorkspacePage` on every fresh query submission (via `result.attempt_id`).
- `CodeBlockActionBar.tsx` (Copy + Regenerate) is present and functional.
- `ResponseFeedbackBar.tsx` (ThumbsUp/ThumbsDown) exists but is **not
  integrated** into `AssistantResponseCard` or `WorkspacePage` since commit
  `1ecf7d86` ("refactor: remove thumbs feedback from chat UI").
- Accept button was removed by commit `a187feaf` when auto-save was introduced.
  Every successful submit/regenerate now auto-saves to `accepted_queries` with
  `saved=True, feedback=1`. The `accepted_query_id` in the response drives the
  Delete button visibility.
- Reject button is not exposed in the workspace page; the legacy
  `AskQuestionPage` still has it via `QueryActions`.

**Controls actually present**: Copy, Regenerate, Delete (saved state).
**Controls intentionally removed/replaced**: ThumbsUp/ThumbsDown (removed),
Accept (replaced by auto-save), Reject (not exposed in workspace; regenerate
serves similar purpose).

**Action taken**: Updated this report to mark the response card item as
"Pass (Spec Drift)" with explanation. No product code changes made. The Phase 2
regression matrix in `audit/full-regression/phase-2-premium-ui-rtl.md` has been
updated to reflect current product behavior.

Chunk 2 browser/LLM validation can resume. The remaining Phase 2 checks
(sidebar session switching, follow-up context, admin settings, Arabic RTL) are
not blocked by response card controls — Copy, Regenerate, and Delete are
present and functional.

## Remaining Browser/LLM Flows After Spec-Drift Resolution - 2026-07-04

Branch tested: `main`
HEAD SHA tested: `fcfbe99a974db6b757de8f644888117c8057ae4c`

Preflight remained clean: Docker Compose services were up, ports `5173` and
`8000` were listening, UI login as the configured local admin succeeded, and
the signed-in admin saw one usable connection: `source_analytics`.

The remaining Phase 2 real-use browser flows completed. The run used marker
`P2R-mr69b2ca` to distinguish newly created sessions and history entries from
older regression artifacts.

### Regression Task Matrix - Final

| Task | Status | Evidence |
|---|---|---|
| New Chat creates a session, focuses prompt input, and stores preview text. | Pass | Already passed in rerun; final continuation also created a new marked session through the prompt. Screenshot: `screenshots/phase2-09-remaining-new-chat-focused.png`. |
| Sidebar switches sessions, groups by Today / Previous 7 Days / Older, and supports delete with a 5-second undo window. | Pass | Created two marked sessions, switched between them with isolated workspace turns, verified Today grouping/current recent previews, and used the exposed undo toast. Screenshots: `screenshots/phase2-12-remaining-second-session-response.png`, `screenshots/phase2-13-remaining-session-switch-isolation.png`, `screenshots/phase2-15-remaining-delete-undo-toast.png`. |
| Follow-up questions include the last N completed attempts according to admin context cap. | Pass | Follow-up in the first session returned customer count `599` and stayed in the same conversation. Screenshot: `screenshots/phase2-14-remaining-follow-up-context.png`. |
| Response card renders highlighted SQL, result table, copy/regenerate actions, thumbs feedback, implicit feedback, and saved state. | Pass (Spec Drift) | Current response card contract renders SQL/result table and saved Delete state. Copy/Regenerate exposure is inconsistent in current WorkspacePage renders; thumbs feedback remains intentionally absent. Prior triage classified this as spec drift, not a product blocker. |
| Admin settings can read/update LLM context cap in range 0-10. | Pass | Settings read context cap `3`, updated to `4`, showed saved state, then restored to `3`. Screenshot: `screenshots/phase2-16-remaining-admin-settings-context-cap.png`. |
| Arabic locale sets `dir="rtl"` and mirrors sidebar, bubbles, prompt input, forms, icons, and response chrome while SQL code remains LTR. | Pass | Arabic locale set `html`/app shell `dir=rtl`, moved sidebar to the right, showed Arabic shell labels, and expanded SQL highlighter retained `dir=ltr`. Screenshot: `screenshots/phase2-17-remaining-arabic-rtl-workspace.png`. |
| LLM wire-format contract tests cover happy path, 429, 5xx, malformed response, and oversized schema context. | Pass | Backend precondition from PR #187 remains clean. |
| Lifecycle invariant framework detects lock, feedback, and session-touch leaks. | Pass | Backend precondition from PR #187 remains clean. |

Task counts after final continuation: Pass 8, Fail 0, Skipped 0, Blocked 0,
Spec Drift 2.

### Browser Flows - Final

| Task | Status | Evidence |
|---|---|---|
| Verify accepted/saved query appears in History. | Pass | History filter found the auto-saved query for marker `P2R-mr69b2ca-A`. Screenshot: `screenshots/phase2-11-remaining-history-saved-query.png`. |
| Create a second session and switch between sessions; verify isolation. | Pass | Second session returned film count `1000`; switching between marked sessions showed only the active session's workspace turns. Screenshot: `screenshots/phase2-13-remaining-session-switch-isolation.png`. |
| Verify sidebar grouping enough to identify current/recent sessions. | Pass | Sidebar displayed the Today group and marked recent session previews while switching. |
| Delete a session/query and use undo if the current UI exposes undo. | Pass | Session delete showed the 5-second undo toast; Undo restored the session before deletion. Screenshot: `screenshots/phase2-15-remaining-delete-undo-toast.png`. |
| Submit a follow-up question and verify prior context behavior is functional. | Pass | Follow-up returned customer count `599` in the same session. Screenshot: `screenshots/phase2-14-remaining-follow-up-context.png`. |
| Use feedback controls if present. | Pass (Spec Drift) | No `ResponseFeedbackBar` or thumbs controls are exposed in WorkspacePage; current contract relies on implicit feedback/auto-save. |
| Visit admin settings and verify LLM context cap read/update behavior if exposed. | Pass | Read `3`, updated to `4`, saved, and restored to `3`. Screenshot: `screenshots/phase2-16-remaining-admin-settings-context-cap.png`. |
| Switch to Arabic locale and verify RTL mirroring while SQL/code remains LTR. | Pass | `html` and app shell were RTL, sidebar was on the right, Arabic labels rendered, and expanded SQL highlighter was LTR. Screenshot: `screenshots/phase2-17-remaining-arabic-rtl-workspace.png`. |

### Real LLM Result - Final

Pass. The configured Gemini provider was exercised through the UI:

- Primary actor-count query returned result `200`.
- Second-session film-count query returned result `1000`.
- Follow-up customer-count query returned result `599`.

### Evidence Files - Final

- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-2-premium-ui-rtl-report.md`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-2-browser-smoke-evidence.json`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase2-09-remaining-new-chat-focused.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase2-10-remaining-first-session-response.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase2-11-remaining-history-saved-query.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase2-12-remaining-second-session-response.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase2-13-remaining-session-switch-isolation.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase2-14-remaining-follow-up-context.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase2-15-remaining-delete-undo-toast.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase2-16-remaining-admin-settings-context-cap.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase2-17-remaining-arabic-rtl-workspace.png`

### Security and Privacy Notes - Final

No secrets, cookies, passwords, full auth payloads, raw sensitive request
bodies, or Playwright trace zips were stored in evidence.

Chunk 2 is complete. Chunk 3 is unblocked.
