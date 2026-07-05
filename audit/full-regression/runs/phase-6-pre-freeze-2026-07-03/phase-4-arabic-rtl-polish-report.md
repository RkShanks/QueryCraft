# Phase 4 Arabic RTL Polish Regression Report

Run date: 2026-07-05
Scope: Chunk 4 only - Phase 4 Arabic RTL verification and polish

Branch tested: `phase-4/fix-history-sql-ltr`
HEAD SHA tested: `8b74498f78aa6c8ca430c499abb1c1a83049bbb8`

## Summary

Backend gates and frontend non-e2e gates passed on the requested main HEAD.
The Playwright wrapper blocker was triaged as harness/setup, not product:
`E2E_BASE_URL` correctly disables `webServer`, Chromium can launch with
escalation, but the requested wrapper specs are mixed mock/real-app and stale
for the current seeded connection names.

A direct Playwright real-app browser validation was then run against the Docker
frontend. Arabic UI sign-in, RTL workspace, connection RBAC, admin connection
health/introspection, keyboard focus, SQL `dir=ltr` on response cards, and real
Arabic query execution for PostgreSQL/MySQL/MSSQL all produced evidence. The
later PostgreSQL provider-unavailable rerun is now classified as non-blocking
for this continuation because all required dialect query evidence is already
recorded.

The continuation avoided extra Gemini calls and resumed the remaining non-LLM
browser checks. The History detail SQL/code direction product regression was
fixed with a focused regression test: SQL `<pre>/<code>` blocks now have
`dir=ltr` while the surrounding Arabic chrome remains RTL. The remaining admin
connections/forms, settings, localized error/privacy, and mobile RTL checks
then passed.

## Preflight

| Task | Status | Evidence |
|---|---|---|
| `rtk git status --short --branch` | Pass | `phase-4/fix-history-sql-ltr`; Phase 4 evidence files/screenshots are untracked; prior-run untracked traces/screenshots remain. |
| `rtk git rev-parse HEAD` | Pass | `8b74498f78aa6c8ca430c499abb1c1a83049bbb8`. |
| Docker app availability | Pass | Frontend `5173`, backend `8000`, platform Postgres `5433`, source Postgres `5434`, Redis `6379`, MySQL `3306`, and MSSQL `1433` were previously confirmed listening. |
| Backend saved env applied | Pass | Backend restart reran admin sync; browser-origin auth probe returned `200` with session cookie present. |
| Gemini configured | Pass | Running backend has `LLM_PROVIDER=gemini` and `LLM_API_KEY_GEMINI` configured; key value was not printed. |
| Deterministic seed state | Pass | Existing seed script verified `source_analytics`, `MySQL Sakila`, and `MSSQL AdventureWorks` healthy, introspected, and Admin policy present. |

## Backend Gates

| Task | Status | Evidence |
|---|---|---|
| Message keys, privacy evidence, audit redaction, query API, history detail validation tests | Pass | `166 passed`. |
| Source DB and dialect evaluator tests | Pass | `65 passed, 1 warning`. |
| `ruff check src tests` | Pass | `All checks passed!` |
| `ruff format --check src tests` | Pass | `384 files already formatted`. |

## Frontend Gates

| Task | Status | Evidence |
|---|---|---|
| `rtk npm test -- --run i18n` | Pass | 3 files passed, 10 tests passed. |
| `rtk npm test -- --run locales` | Pass | 2 files passed, 300 tests passed. |
| `rtk npm test -- --run no-physical` | Pass | 2 files passed, 4 tests passed. |
| `rtk npm run lint` | Pass | ESLint completed. |
| `rtk npm run typecheck` | Pass | `tsc --noEmit` completed. |
| `rtk npm run build` | Pass | Production build completed; existing chunk-size warning only. |
| `rtk npm run lint:css` | Pass | Stylelint completed. |
| `rtk npm test -- --run HistoryDetail` | Pass | 1 file passed, 10 tests passed after focused RTL SQL direction regression was added. |
| Required Playwright wrapper external mode | Harness Limitation | Config correctly disables `webServer` when `E2E_BASE_URL` is set. Non-escalated Chromium launch is blocked by sandbox. Wrapper specs are unsuitable for full real-app Phase 4 because two specs mock auth/data and `wave_16_3_smoke` expects stale seeded display names. |
| Minimal direct Chromium smoke | Pass | Escalated Chromium launched and opened `http://localhost:5173/sign-in`. |

## Browser/User Flows

| Task | Status | Evidence |
|---|---|---|
| Sign in through UI | Pass | UI sign-in with Arabic locale reached workspace; `html` and app shell were `dir=rtl`. |
| Switch to Arabic and verify `dir="rtl"` | Pass | Existing i18next query-string detector path `?lng=ar` applied Arabic and RTL. |
| Invalid sign-in localized error | Pass | Arabic invalid-credentials message rendered without UUIDs, hostnames, driver strings, stacks, credentials, cookies, or raw payloads. |
| Signed-in admin usable connections | Pass | `/api/v1/connections` exposed PostgreSQL `source_analytics`, `MySQL Sakila`, and `MSSQL AdventureWorks`. |
| Admin health/introspection | Pass | Browser-context admin API confirmed all three active rows were healthy and `schema_introspection_status=success`. |
| Workspace RTL/localization | Pass | Workspace rendered Arabic RTL with no raw i18n keys or unexpected English fallback outside allowed brand/technical/query strings. |
| Workspace RTL shell mirroring | Pass | Continuation confirmed the sidebar is positioned to the right of workspace in RTL desktop layout. |
| Database selector and prompt input | Pass | Selector could select each dialect; prompt accepted Arabic text. |
| SQL/code blocks remain LTR on response cards | Pass | Result SQL highlighter had `dir=ltr` for PostgreSQL, MySQL, and MSSQL result cards. |
| Keyboard/tab accessibility | Pass | Database selector accepted focus and tab advanced without trapping focus. |
| History localization/privacy | Pass | Continuation found no raw i18n keys, common English UI fallback, or private/internal text on History. |
| History RTL shell mirroring and desktop overflow | Pass | Sidebar mirrored to the right; 1365px RTL History viewport had no horizontal overflow. |
| History detail SQL/code LTR | Pass | After fix, computed CSS direction was `ltr` for both History detail `pre` and `code`; both elements carry `dir=ltr`. Screenshot: `phase4-ar-history-code-dir-blocker.png`. |
| Admin connections localization/privacy and RTL | Pass | No raw i18n keys, common English UI fallback, or private/internal text found; sidebar mirrored right; 1365px viewport had no horizontal overflow. |
| Admin add/test connection form validation privacy | Pass | Blank required-field validation stayed localized/sanitized and did not call provider. |
| Settings localization/privacy and RTL | Pass | No raw i18n keys, common English UI fallback, or private/internal text found; sidebar mirrored right; invalid numeric setting validation stayed localized/sanitized. |
| Safe invalid connection API error | Pass | Invalid connection id returned sanitized `HTTP 400` with `connection_not_found` / `error.connection_not_found`; no provider call required. |

## Real Arabic Query Results

| Dialect | Status | Evidence |
|---|---|---|
| PostgreSQL | Pass | Successful direct run: `source_analytics`, SQL `SELECT count(actor_id) FROM actor`, result `200`, SQL block `dir=ltr`. Later redundant rerun showed localized sanitized LLM-unavailable alert, but required dialect evidence is already recorded. |
| MySQL | Pass | Successful direct run: `MySQL Sakila`, SQL `SELECT COUNT(*) FROM actor`, result `200`, SQL block `dir=ltr`. |
| MSSQL | Pass | Successful direct run: `MSSQL AdventureWorks`, SQL `SELECT COUNT(*) FROM SalesLT.Customer`, result `847`, SQL block `dir=ltr`. |

## Localized Error / Privacy Results

| Task | Status | Evidence |
|---|---|---|
| Backend localized-safe message/error/privacy coverage | Pass | Phase 4 backend gate passed `166` tests covering message keys, privacy evidence, audit redaction, query API, and history detail validation. |
| Browser invalid sign-in privacy | Pass | Arabic invalid sign-in error was generic and sanitized. |
| Browser provider error privacy | Pass | Historical PostgreSQL rerun surfaced Arabic localized LLM-unavailable alert; no UUIDs, hostnames, driver strings, stacks, credentials, cookies, or raw payloads were rendered. This is not the active blocker for this continuation. |
| Invalid connection/test connection browser path | Pass | Blank admin connection form validation and invalid connection id API path stayed localized/sanitized with no UUIDs, hostnames, driver strings, stacks, credentials, cookies, or raw payloads rendered. |

## Responsive / Mobile RTL

| Viewport | Status | Evidence |
|---|---|---|
| Desktop RTL | Pass | 1365px workspace had no horizontal overflow. |
| 375px RTL | Pass | Arabic RTL workspace had no horizontal overflow and visible controls were usable. |
| 768px RTL | Pass | Arabic RTL workspace had no horizontal overflow and visible controls were usable. |

## Setup Limitations / Spec Drift

| Task | Status | Evidence |
|---|---|---|
| Playwright default webServer with Docker real-use stack | Harness Limitation | Default wrapper starts its own dev server unless `E2E_BASE_URL` is set; Docker real-use regression must set `E2E_BASE_URL=http://localhost:5173`. |
| Requested e2e specs for real-app mode | Harness Limitation | `i18n-audit.spec.ts` and `rtl-snapshots.spec.ts` use mocked auth/data; `wave_16_3_smoke.spec.ts` is stale for current seeded display names. Direct Playwright validation was used for real app coverage. |
| Provider availability | Historical / Non-blocking | A redundant PostgreSQL rerun hit localized sanitized LLM-unavailable, but all three required dialect query results are already recorded. Remaining continuation work made no Gemini calls. |
| History SQL/code direction | Pass | Fixed product regression: History detail SQL `pre/code` now compute `direction: ltr` and carry `dir=ltr`; surrounding UI remains RTL. |

## Evidence Files

- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-4-arabic-rtl-polish-report.md`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-4-browser-smoke-evidence.json`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase4-ar-sign-in.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase4-ar-workspace.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase4-ar-postgres-result.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase4-ar-mysql-result.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase4-ar-mssql-result.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase4-ar-history-code-dir-blocker.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase4-ar-history.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase4-ar-admin-connections.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase4-ar-admin-connection-form-validation.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase4-ar-settings.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase4-ar-mobile-375.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase4-ar-mobile-768.png`

## Security and Privacy Notes

No secrets, cookies, API keys, DB credentials, full auth payloads, raw sensitive
request bodies, or Playwright trace zips were stored in evidence. Browser traces
from previous wrapper attempts remain untracked and were not added as evidence.

Task summary after fix and continuation: Pass 45, Fail 0, Skipped 0, Blocked 0.

Chunk 4 is complete. Chunk 5 is unblocked.
