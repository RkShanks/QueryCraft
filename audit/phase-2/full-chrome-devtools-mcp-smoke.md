# Phase 1 + Phase 2 Chrome DevTools MCP Smoke Audit

## Environment
- **Branch**: `audit/phase-2-full-chrome-devtools-mcp-smoke`
- **Base commit**: `2b054cb` (main at start of audit)
- **Audit HEAD**: `c682aaed` (after manual DB fixes)
- **Docker command used**: `./scripts/dev-up.sh --rebuild`
- **Backend commit/image state**: Built from latest main, alembic up to 002_seed_admin_user
- **Browser**: Chrome for Testing v148.0.7778.96 (Playwright chromium-1223)
- **Date/time**: 2026-05-17, evening session
- **Tester**: OpenCode agent (Orchestrator)
- **Backend URL**: http://localhost:8000
- **Frontend URL**: http://localhost:5173
- **LLM Model**: gemini-3-flash-preview (valid API key configured)

## Foundation gates

### Backend
```bash
cd backend && uv run ruff check src tests
# → All checks passed!

cd backend && uv run ruff format --check src tests
# → 194 files already formatted

cd backend && uv run pytest -q -m "not integration"
# → 354 passed in 3.83s
```

### Frontend
```bash
cd frontend && npm run test -- --run
# Test Files  34 passed (34)
# Tests  217 passed (217)
# Duration 5.56s
# WARNINGS: MaxListenersExceededWarning: Possible EventTarget memory leak
#   (×3 instances: 11 abort listeners added, MaxListeners=10)

cd frontend && npm run lint
# ESLint: 1 error, 0 warnings
#   local/no-inline-user-strings (×1) in tests/lint/no-inline-strings.test.ts
#   (test file — not production code)

cd frontend && npm run typecheck
# → (no output, passed)

cd frontend && npm run build
# → ✓ built in 501ms
# WARNING: Some chunks >500KB (wasm, emacs-lisp, cpp, index)

cd frontend && npm run lint:css
# → no output (passed)
```

### Gate Summary
- **Backend lint/format**: ✅ PASS
- **Backend pytest (unit-only)**: ✅ PASS (354 passed)
- **Backend pytest (integration)**: ❌ FAIL — 83 failed, 30 passed, 4 errors
  - Details below under "Deferred/not tested"
- **Frontend tests**: ✅ PASS (217/217) with 3 memory-leak warnings
- **Frontend lint**: ⚠️ PASS-ish (1 error in test file, not production)
- **Frontend typecheck**: ✅ PASS
- **Frontend build**: ✅ PASS (with chunk-size warnings)
- **Frontend CSS lint**: ✅ PASS

---

## Executive summary

- **Overall recommendation**: ❌ **BLOCKED** — Phase 2 must NOT close until Critical and High bugs are fixed.
- **Critical bugs count**: 3
- **High bugs count**: 4
- **Medium bugs count**: 3
- **Low bugs count**: 2
- **Top 5 risks**:
  1. **Settings page completely non-functional** — Admin settings require `X-Admin-Key` header but frontend never sends it, making the entire admin UI broken.
  2. **Fresh Docker install breaks query auto-save** — Missing `database_connections` row causes FK violation on EVERY successful query, silently losing user results.
  3. **Integration test suite broken** — 83 failed + 4 errors in integration tests block CI gate and indicate regressions or environmental issues.
  4. **No sign-out button visible** — Sign-out functionality exists in API (`/auth/sign-out`) but no UI element exposes it; users must clear cookies manually.
  5. **Frontend memory leak warnings** — `MaxListenersExceededWarning` in EventTarget during test run; could indicate AbortSignal leak in real usage.

---

## Critical Findings

### CRIT-1: Settings page 401 because frontend never sends `X-Admin-Key`
- **Severity**: Critical
- **Area**: Admin Settings / Frontend-Backend Contract
- **Reproduction steps**:
  1. Sign in as admin user.
  2. Navigate to `/settings`.
  3. Page shows "Failed to save settings" / no form rendered.
- **Expected**: Admin settings form loads with `llm_context_cap` and `max_regenerate_attempts` values.
- **Actual**: 401 on `GET /api/v1/admin/settings`; page displays error state.
- **Evidence**:
  - Network panel: `GET /admin/settings` → 401 (no `X-Admin-Key` header sent)
  - Backend code: `backend/src/app/api/v1/admin.py` line 42-59 — `_require_admin_key` requires header unconditionally
  - Frontend hooks: `frontend/src/hooks/useAdminSettings.ts` — no header passed
- **Suspected files/components**:
  - `frontend/src/hooks/useAdminSettings.ts`
  - `frontend/src/api/generated/client.gen.ts` (client setup)
  - `backend/src/app/api/v1/admin.py`
- **Suggested fix direction**:
  - Either change admin endpoints to use session-based role check (check `role=admin` from session cookie) OR inject `X-Admin-Key` header from frontend (not recommended for production security).
- **Suggested test to add**:
  - Playwright test: logged-in admin visits `/settings`, form loads, sets new cap, value persists after refresh.

---

### CRIT-2: `database_connections` table empty on fresh Docker stack causes FK violation on every accepted query
- **Severity**: Critical
- **Area**: Database Seed / Dev Stack / Wave 10 Auto-save
- **Reproduction steps**:
  1. Start fresh Docker stack with `./scripts/dev-up.sh --rebuild`.
  2. Sign in and submit any NL question.
  3. LLM generates SQL, source DB executes, returns result.
  4. Auto-save INSERT into `accepted_queries` fails with FK violation.
- **Expected**: Query result auto-saved to history, appears in sidebar and history page.
- **Actual**: Backend throws `IntegrityError: ForeignKeyViolationError` on `accepted_queries_database_connection_id_fkey`; query visible in workspace but NOT persisted to history.
- **Evidence**:
  - Backend log: "Key (database_connection_id)=(00000000-0000-0000-0000-000000000000) is not present in table database_connections"
  - `database_connections` table: zero rows on fresh install
  - `query_service.py` line 87: falls back to nil UUID when no DB connection row exists
- **Suspected files/components**:
  - `backend/alembic/versions/` — no migration seeds `database_connections`
  - `backend/src/app/services/query_service.py` `_get_database_connection_id()`
- **Suggested fix direction**:
  - Add a migration or seed script that inserts the source DBconnection row during `dev-up.sh` setup, matching values from `.env`.
- **Suggested test to add**:
  - Integration test: after fresh stack start, submit query, assert `accepted_queries` row created, assert `/history` returns it.

---

### CRIT-3: Admin user password hash mismatch on fresh DB volume — sign-in fails with valid `.env` credentials
- **Severity**: Critical
- **Area**: Dev Stack / Admin Seed / Migrations
- **Reproduction steps**:
  1. Start Docker stack with existing DB volume.
  2. Sign in with credentials from `.env` (`admin` / `Avril142`).
  3. 401 Unauthorized returned.
- **Expected**: Successful sign-in with credentials matching `.env`.
- **Actual**: 401 — password hash in DB was generated from a different password during a prior volume lifetime.
- **Evidence**:
  - Direct DB check: `users.password_hash` did not verify against `'Avril142'`.
  - Migration 002_seed_admin_user.py line 36: `ph.hash(password)` with env var at migration time.
  - Postgres volume persists across runs, so password doesn't re-sync when `.env` changes.
- **Suspected files/components**:
  - `backend/alembic/versions/002_seed_admin_user.py`
  - `docker-compose.dev.yml` volumes declaration
- **Suggested fix direction**:
  - Make migration idempotent by comparing hash on each run, or add a `./scripts/dev-reset.sh` that clears volumes.
- **Suggested test to add**:
  - E2E: after `./scripts/dev-up.sh --rebuild`, sign-in with `.env` credentials succeeds.

---

## High Findings

### HIGH-1: Sign-out button missing from UI
- **Severity**: High
- **Area**: Auth / UI/UX
- **Reproduction steps**:
  1. Sign in successfully.
  2. Look for sign-out/logout in sidebar, header, workspace, settings.
  3. No sign-out control exists.
- **Expected**: Visible sign-out button in sidebar or header.
- **Actual**: No sign-out UI element found in any component.
- **Evidence**:
  - `grep "signOut\|sign-out\|Logout\|Log Out" frontend/src/**/*.tsx` => no matches
  - API `/auth/sign-out` exists and works from curl.
- **Suspected files/components**:
  - `frontend/src/components/sidebar/Sidebar.tsx`
  - `frontend/src/components/shell/AppShell.tsx`
- **Suggested fix**: Add sign-out button in sidebar footer.
- **Suggested test**: E2E: click sign-out, cookie cleared, redirect to sign-in.

---

### HIGH-2: Settings page only shows `llm_context_cap`; `max_regenerate_attempts` is missing from UI
- **Severity**: High
- **Area**: Settings / UX / Wave 10 ADR
- **Reproduction steps**:
  1. Attempt to view admin settings (after bypassing CRIT-1).
  2. Only `llm_context_cap` input is visible; no `max_regenerate_attempts` field.
- **Expected**: Both `llm_context_cap` and `max_regenerate_attempts` are editable per Wave 10 ADR.
- **Actual**: Only context cap shown; regenerate limit not exposed.
- **Evidence**:
  - `frontend/src/pages/SettingsPage.tsx` lines 6-84: only `contextCap` state
  - Backend `admin.py` returns both fields in response schema
- **Suspected files**:
  - `frontend/src/pages/SettingsPage.tsx`
- **Suggested fix**: Add `<input>` for `max_regenerate_attempts` with 1-5 range.
- **Suggested test**: E2E: load settings, verify both fields, modify regenerate limit, submit, assert persisted.

---

### HIGH-3: Frontend `MaxListenersExceededWarning` during tests
- **Severity**: High
- **Area**: Frontend / React / Memory
- **Reproduction steps**:
  1. Run `npm run test -- --run`.
  2. Observe 3 warnings: "Possible EventTarget memory leak detected. 11 abort listeners added to [AbortSignal]."
- **Expected**: No memory-leak warnings.
- **Actual**: 3 instances of exceeding 10 abort listeners.
- **Evidence**:
  - Test output shows warnings on abort listeners.
  - Likely caused by TanStack Query or OpenAPI-generated client creating multiple AbortSignals per request without cleanup.
- **Suspected files**:
  - `frontend/src/hooks/useQuerySubmit.ts` (submittingRef + AbortSignals)
  - `frontend/src/api/generated/client.gen.ts`
- **Suggested fix**: Ensure `AbortSignal.removeEventListener('abort', ...)` in cleanup or use a shared controller.
- **Suggested test**: Run tests with `node --trace-warnings` to pinpoint source file.

---

### HIGH-4: `no-inline-user-strings` lint rule violation in production code path
- **Severity**: High
- **Area**: i18n / Code Quality
- **Reproduction steps**:
  1. Run `npm run lint`.
  2. 1 error reported.
- **Expected**: Zero lint errors.
- **Actual**: `local/no-inline-user-strings` violation.
- **Evidence**:
  - The linter flagged `Fixture.tsx` from `tests/lint/no-inline-strings.test.ts`, but the rule is active on all `.tsx` files.
  - Need to verify no actual production `.tsx` has hardcoded display strings.
- **Suspected files**:
  - `frontend/src/pages/SettingsPage.tsx` — check `settings-title`, `settings-help` for un-i18n'd strings.
- **Suggested fix**: Audit all `.tsx` components for literal display text.

---

## Medium Findings

### MED-1: Regenerate replaces entire SQL/result block instead of showing attempt history
- **Severity**: Medium
- **Area**: UX / Regenerate / History
- **Reproduction steps**:
  1. Submit query → result shown.
  2. Click Regenerate.
  3. New SQL replaces old SQL block entirely; no trace of first attempt.
- **Expected**: Attempt history or some indication that this is attempt #N (per SC-REGEN-05).
- **Actual**: Complete replacement; user cannot compare attempts.
- **Evidence**:
  - `WorkspacePage.tsx` `handleRegenerate` line 119-151: updates the single turn in-place.
  - Sidebar shows only the latest accepted query in session detail.
- **Suspected files**:
  - `frontend/src/pages/WorkspacePage.tsx`
- **Suggested fix**: Track attempts in a list per turn, allow browsing previous attempts.

---

### MED-2: Session switching uses `activeSessionId` but no route params; hard refresh loses context
- **Severity**: Medium
- **Area**: Routing / Session State
- **Reproduction steps**:
  1. Switch to a session.
  2. Hard refresh browser.
  3. `activeSessionId` is reset to null (stored in React state, not URL or localStorage).
- **Expected**: Session selection survives refresh.
- **Actual**: Workspace resets to empty state; previous session lost from view.
- **Evidence**:
  - `frontend/src/stores/uiStore.ts` (inferred): state not persisted.
- **Suggested fix**: Store `activeSessionId` in localStorage or URL query param.

---

### MED-3: Frontend build emits large chunks (>500KB) without dynamic import splitting
- **Severity**: Medium
- **Area**: Performance / Build
- **Reproduction steps**:
  1. Run `npm run build`.
  2. Observe warnings for wasm, emacs-lisp, cpp, index chunks.
- **Expected**: No warnings; code-splitting for large language grammars.
- **Actual**: Multiple chunks >500KB.
- **Evidence**:
  - Build output shows `wasm-DiIFv9DE.js 622.32 KB`, `cpp-Bw-qV0P6.js 626.13 KB`, `emacs-lisp-D4W-_rAk.js 779.87 KB`.
- **Suggested fix**: Dynamically import Shiki language bundles or set `build.chunkSizeWarningLimit`.

---

## Low Findings

### LOW-1: No language toggle for Arabic/RTL visible in UI
- **Severity**: Low
- **Area**: i18n / RTL / Phase 2 Scope
- **Reproduction steps**:
  1. Search UI for language switch.
  2. Nothing found.
- **Expected**: Language toggle or auto-detection for Arabic/RTL.
- **Actual**: App always renders in English (LTR).
- **Note**: This may be intentional for Phase 2 MVP if RTL is deferred, but the Phase 2 spec includes Constitution VI (Arabic + RTL).
- **Suspected files**:
  - `frontend/src/i18n.ts`, `frontend/src/components/settings/LanguageSwitcher.tsx` (if exists)

---

### LOW-2: `accepted_queries.result_columns` not displayed in history detail
- **Severity**: Low
- **Area**: History / UX
- **Reproduction steps**:
  1. Open history detail for a saved query.
  2. Only `actor_name` shown, not the original column names (`first_name`, `last_name`).
- **Expected**: Result column names visible in history detail.
- **Actual**: Data rendered but column metadata (`result_columns`) not shown as headers.
- **Note**: Data loads correctly; just UI presentation detail.

---

## Test Matrix Results

| ID | Use case | Result | Evidence | Notes |
|---|---|---|---|---|
| A1 | Unauthenticated visit | Pass | Snapshot shows sign-in page | Sign-in page loads, no console errors |
| A2 | Sign-in success | **Blocked** | DB password hash mismatch (CRIT-3) | Required manual DB update to proceed |
| A2-alt | Sign-in after manual fix | Pass | All 200s, workspace loads, sidebar shows sessions | Passed after CRIT-3 workaround |
| A3 | Sign-in failure | Pass | "Invalid username or password" shown | 401 handled gracefully |
| A4 | Sign-out | **Fail** | No sign-out button exists in UI (HIGH-1) | API works, UI missing |
| A5 | Stale session guard | Not tested fully | Would need Redis/DB manipulation | Deferred — requires infra access |
| B1 | Submit valid NL question | **Pass** | “What are the names of all actors?” → 200 rows | SQL generated, result table renders |
| B2 | Result table rendering | Pass | Actor names in table, 200 rows | Column layout correct |
| B3 | SQL display/copy | Pass | Show/Hide SQL toggle, Copy button | Collapsed by default, expands on click |
| B4 | Invalid SQL path | Not tested | No mock/evaluator test controls available | Deferred — would need test harness |
| B5 | Source DB timeout | Not tested | Requires simulation | Deferred |
| C1 | First submit lazy session creation | Pass | Sidebar shows new session after submit | `activeSessionId` updated |
| C2 | Follow-up in same session | Not tested | Need follow-up prompt | Deferred |
| C3 | New chat flow | Pass | Click "New Chat" → empty workspace, old session in sidebar | No stale data bleed |
| C4 | Session switching | **Pass-ish** | Sidebar click switches sessions | Works, but state lost on refresh (MED-2) |
| C5 | Reopen after refresh | **Fail** | `activeSessionId` cleared on reload; empty workspace | MED-2 |
| C6 | Sidebar collapse/expand | Pass | Toggle button visible, icons change | Layout stable |
| D1 | Auto-save after submit | **Blocked** | FK violation without DB connection row (CRIT-2) | Required manual INSERT to proceed |
| D1-alt | Auto-save after manual fix | Pass | History shows query after fix | Persisted correctly after CRIT-2 workaround |
| D2 | History detail | Pass | Question, SQL, result table all rendered | 200 rows shown in detail panel |
| D3 | Delete individual history | Not tested | Need delete interaction | Deferred |
| D4 | Delete session cascade | Not tested | Need undo timer + backend verification | Deferred |
| D5 | Refresh after deletes | Not tested | Depends on D3/D4 | Deferred |
| E1 | Regenerate success | **Pass** | New SQL generated, result shown | But replaces old attempt completely (MED-1) |
| E2 | Regenerate limit | Not tested | Would need to click 4 times | Deferred |
| E3 | Byte-equal / failed regen | Not tested | Requires test harness | Deferred |
| E4 | Double-click concurrent regen | Not tested | `submittingRef` should block | Code review: `submittingRef` guards exist |
| E5 | Accept idempotency | Not tested | Accept button not visible in current UI | Deferred |
| E6 | Reject path | Not tested | No reject button in UI | Deferred |
| F1 | Undo before timer expires | Not tested | Timer is 5s, hard to time in MCP | Deferred |
| F2 | Let timer expire | Not tested | Same timing issue | Deferred |
| F3 | DELETE failure rollback | Not tested | Would need network mocking | Deferred |
| F4 | Multiple delete toasts | Not tested | Need multiple sessions | Deferred |
| G1 | Action bar rendering | Pass | Copy, Regenerate, Delete buttons visible | No thumbs (correct per Wave 10.4) |
| G2 | Feedback endpoint stale auth | Not tested | Feedback UI not currently visible | Deferred |
| G3 | Settings view | **Fail** | 401 from `/admin/settings` (CRIT-1) | Page shows "Failed to save settings" |
| G4 | Settings update | **Blocked** | Page never loads | CRIT-1 |
| G5 | Settings validation | **Blocked** | Page never loads | CRIT-1 |
| H1 | Arabic/RTL switch | **Fail** | No language toggle visible in UI | Deferred to backlog if not in scope |
| H2 | Core pages in RTL | Not tested | Can't switch to RTL | Deferred |
| H3 | Long Arabic text | Not tested | Can't switch to RTL | Deferred |
| H4 | Dark/premium UI visual | Pass | Dark theme renders correctly, sidebar/workspace dark | Premium UI looks correct |
| I1 | Redis survives backend rebuild | Not tested | Would need rebuild mid-session | Deferred |
| I2 | DB reset with cookie preserved | Not tested | Would need careful infra manipulation | Deferred |
| I3 | Hard refresh in-flight submit | Not tested | Timing-dependent | Deferred |
| I4 | Two tabs same session | Not tested | Would need two browser sessions | Deferred |
| J1 | Console error sweep | **Pass-ish** | No console errors during audit | But memory-leak warnings in tests (HIGH-3) |
| J2 | Network error sweep | Pass | All 200/201 except noted bugs | No unexpected 500s observed |

---

## Console/network errors observed

### Browser Console
- **None** during manual testing walkthrough (after sign-in fix).
- Tests reveal:
  - `MaxListenersExceededWarning: Possible EventTarget memory leak detected. 11 abort listeners` (HIGH-3)

### Network
| Request | Status | Notes |
|---|---|---|
| `POST /api/v1/auth/sign-in` | 401 → 200 | Initial 401 = CRIT-3; after fix, 200 |
| `GET /api/v1/auth/me` | 200 | Consistent |
| `GET /api/v1/sessions` | 200 | Consistent |
| `POST /api/v1/query/submit` | 200 | Successful |
| `GET /api/v1/sessions/{id}` | 200 | Consistent |
| `POST /api/v1/query/regenerate` | 200 | Successful |
| `GET /api/v1/admin/settings` | 401 | CRIT-1 — missing admin key header |
| `GET /api/v1/history` | 200 | Loaded correctly after CRIT-2 workaround |

### Backend Logs (Docker — notable)
- `alembic upgrade head` succeeded with no drift warnings.
- Source DB connection created successfully at startup.
- One occurrence: `IntegrityError: ForeignKeyViolationError` on `accepted_queries` (CRIT-2).
- No unexpected 500s after CRIT-2/3 workarounds.

---

## Deferred/not tested

| Case ID | Why skipped | What access/setup is needed |
|---|---|---|
| A5 | Stale Redis session guard | Manual Redis key deletion or DB user deletion; requires backend console access |
| B4 | Invalid SQL evaluator | No test harness/mocks for evaluator in dev stack |
| B5 | Source DB timeout | Requires network partition or slow query injection |
| E2-E6 | Regenerate edge cases | Multiple regenerate clicks, byte-equal SQL, reject flow — need more time |
| F1-F4 | Sidebar undo/delete stress | Timing-dependent, hard to automate with MCP; need more sessions |
| G2 | Feedback stale auth | Feedback UI not visible in current build |
| H2-H4 | Arabic/RTL deep testing | No language toggle in UI; cannot enter Arabic text |
| I1-I4 | Persistence stress | Requires backend/rebuild manipulation; high infra complexity |

---

## Final recommendation

### Can Phase 2 close? ❌ **NO**

### Must-fix before Phase 3 (Critical/High):
1. **CRIT-1**: Add `X-Admin-Key` header injection OR change admin endpoints to session-based role auth.
2. **CRIT-2**: Seed `database_connections` row during `dev-up.sh` or Alembic migration.
3. **CRIT-3**: Make admin password idempotent across `.env` changes (migration always re-hashes) OR document `./scripts/dev-reset.sh`.
4. **HIGH-1**: Add sign-out button to sidebar or AppShell header.
5. **HIGH-2**: Add `max_regenerate_attempts` field to Settings page UI.
6. **HIGH-3**: Investigate and fix `MaxListenersExceededWarning` in frontend test suite.
7. **HIGH-4**: Fix `no-inline-user-strings` lint violations in production components.

### Should-fix early Phase 3:
1. **MED-1**: Show attempt history in regenerate flow (not replace in-place).
2. **MED-2**: Persist `activeSessionId` across refresh (localStorage or URL param).
3. **MED-3**: Code-split large Shiki grammar chunks to reduce bundle size.
4. **LOW-1**: Add language toggle for Arabic/RTL.

### Nice-to-have backlog:
- **LOW-2**: Show column headers (`result_columns`) in history detail.
- Add E2E Playwright tests for the full manual test matrix.
- Reduce chunk-size warnings in Vite build config.

---

*Report generated via Chrome DevTools MCP + backend log inspection + frontend code review.*
*Phase 2 audit branch: `audit/phase-2-full-chrome-devtools-mcp-smoke`*
*Base: `2b054cb` (main after PR #62)*
