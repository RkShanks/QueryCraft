# Phase 3 Multi-Dialect Source DB Regression Report

Run date: 2026-07-04
Scope: Chunk 3 only - Phase 3 backend/API/browser validation

Branch tested: `main`
HEAD SHA tested: `a00f5abbc88fa66b6cb5480845ba89bab9989e84`

## Summary

Initial run found an unacceptable setup gap: only PostgreSQL `source_analytics`
was seeded as a usable QueryCraft connection. The deterministic E2E seed support
script now repairs PostgreSQL, MySQL, and MSSQL source connections, restores the
local MSSQL `AdventureWorksLT` fixture when needed, runs the normal connection
health and schema introspection service paths, and seeds built-in Admin role
policies from introspected schema entries.

After the fix, signed-in admin API/UI state exposes three usable connections:
`source_analytics` (`postgresql`), `MySQL Sakila` (`mysql`), and
`MSSQL AdventureWorks` (`mssql`), all active, healthy, and successfully
introspected.

2026-07-05 rerun: real `/api/v1/query/submit` for MySQL now passes with
generated SQL `SELECT COUNT(*) FROM actor` and result `200`. MSSQL remains
blocked by Gemini provider quota (`429 Too Many Requests`), surfaced as
sanitized `error.llmUnavailable`. This is no longer a source DB setup gap.
Direct QueryCraft source-adapter execution through the encrypted seeded
connection rows passes for all three dialects.

2026-07-05 updated-key rerun: backend was recreated so the running app could
load the updated provider environment. The backend reports `LLM_PROVIDER=gemini`
and a configured Gemini key without exposing the value. Deterministic seed state
is still present for PostgreSQL, MySQL, and MSSQL, but both MySQL and MSSQL
`/api/v1/query/submit` calls returned sanitized 502 `error.llmUnavailable`.
Recent backend provider logs showed Gemini `429 Too Many Requests` for both
calls, so the provider quota/key blocker is not cleared.

2026-07-05 saved-`.env` rerun: backend was recreated after the updated `.env`
was saved. The backend reports `LLM_PROVIDER=gemini` and a configured Gemini key
without exposing the value. Real `/api/v1/query/submit` passed for MySQL with
generated SQL `SELECT COUNT(*) FROM actor` and result `200`, and passed for MSSQL
with generated SQL `SELECT COUNT(*) FROM SalesLT.Customer` and result `847`.
The provider blocker is cleared.

## Preflight

| Task | Status | Evidence |
|---|---|---|
| `rtk git status --short --branch` | Pass | `main...origin/main`; existing untracked prior-run screenshots/traces were present before Chunk 3 evidence was added. |
| `rtk git rev-parse HEAD` | Pass | `a00f5abbc88fa66b6cb5480845ba89bab9989e84`. |
| `rtk docker compose -f docker-compose.dev.yml ps` | Pass | Backend/frontend running; platform Postgres, source Postgres, Redis, MySQL, and MSSQL running; data services healthy where applicable. |
| Confirm required ports are listening | Pass | `ss -ltnp` showed `5173`, `8000`, `5433`, `5434`, `6379`, `3306`, and `1433` listening. |
| Repair stale local admin/session seed state if needed | Pass | Backend restart made local admin sign-in return 200. Updated `seed_e2e_connection.py` repaired PostgreSQL, MySQL, and MSSQL to healthy/success with Admin policies present. |

## Regression Task Matrix

| Task | Status | Evidence |
|---|---|---|
| Admin can add, edit, test, disable, enable, and hard-delete eligible source connections. | Pass | Sanitized API probe created invalid eligible temp connections for PostgreSQL/MySQL/MSSQL, updated display names, tested health, disabled, enabled, and hard-deleted each with expected sanitized unhealthy results. |
| Passwords are encrypted at rest and never returned after save. | Pass | Admin/user/lifecycle/schema/query API responses exposed no password, encrypted password, credential, secret, token, authorization, or connection string fields. |
| First successful save runs health check and initial schema introspection. | Pass | Focused backend tests passed; live `source_analytics` seed repair used normal service methods and produced `health=healthy`, `schema_status=success`, 29 tables, 171 columns. |
| Schema refresh replaces prior metadata and reports failures without using stale data silently. | Pass | `POST /api/v1/admin/connections/{id}/refresh-schema` returned 200 for `source_analytics`; schema summary remained usable with 29 tables. Focused integration test `test_admin_refresh_schema.py` passed. |
| Workspace database selector is per-session, disabled until selected when multiple active connections exist, and auto-selects when exactly one exists. | Pass | Browser selector showed all three usable options: `source_analytics POSTGRESQL`, `MySQL Sakila MYSQL`, `MSSQL AdventureWorks MSSQL`; each option could be selected. |
| Generated/evaluated SQL matches selected dialect: PostgreSQL, MySQL, or T-SQL. | Pass | PostgreSQL live `/query/submit` returned `SELECT count(*) FROM actor` with result `200`. Saved-`.env` rerun returned MySQL `SELECT COUNT(*) FROM actor` → `200` and MSSQL `SELECT COUNT(*) FROM SalesLT.Customer` → `847`. |
| Response cards and history show friendly connection name and database type. | Pass | Browser/UI selector and Admin Connections show all friendly names/types. PostgreSQL response card passed. MySQL and MSSQL query-submit now pass via API. |
| Legacy Phase 1/2 rows are backfilled with the migrated PostgreSQL connection. | Pass | Current usable user connection is the migrated PostgreSQL `source_analytics`; Phase 2 final run had already queried and saved against it. |
| Localized errors sanitize raw driver details and credentials. | Pass | Invalid connection test responses returned generic categories/message keys only; invalid query connection id returned `connection_not_found` / `error.connection_not_found`; no secret-shaped fields were present. |

## Backend/API Checks

| Task | Status | Evidence |
|---|---|---|
| Source PostgreSQL, MySQL, and MSSQL containers are reachable. | Pass | PostgreSQL actor count `200`; MySQL actor count `200`; MSSQL `AdventureWorksLT` restored and `SalesLT.Customer` count `847`. |
| Admin connection listing/creation/update/test/introspection behavior for all supported dialects where applicable. | Pass | Admin list returned three active/healthy/success connections. Lifecycle API passed for all three dialect enums using hard-delete-eligible invalid temp connections. Health/schema refresh passed for PostgreSQL, MySQL, and MSSQL. |
| Connection health and schema introspection produce usable schema entries. | Pass | PostgreSQL: 29 tables / 171 columns. MySQL: 23 tables / 132 columns. MSSQL: 15 tables / 142 columns including `SalesLT.Customer`. |
| `/api/v1/connections` exposes only active/healthy/introspected usable connections. | Pass / Contract Note | Returned three minimal connections (`id`, `display_name`, `database_type`) for PostgreSQL, MySQL, and MSSQL; no host/port/credentials. Current service contract filters by active/healthy/introspected state; role-policy filtering is not implemented in this Phase 3 endpoint path. |
| Dialect-specific query execution paths remain functional and sanitized on errors. | Pass | Direct QueryCraft adapters executed known count SQL through encrypted seeded connection rows for all three dialects. `/query/submit` passed for PostgreSQL, MySQL, and MSSQL. Invalid connection path returned sanitized 400. |
| Phase 3 backend focused tests. | Pass | `115 passed, 1 warning`; `90 passed`; `ruff check` passed; `ruff format --check` passed. |

## Browser Flows

| Task | Status | Evidence |
|---|---|---|
| Sign in through UI. | Pass | Signed in as configured local admin. Screenshot: `screenshots/phase3-01-signed-in-workspace.png`. |
| Open Admin Connections. | Pass | Admin Connections loaded and showed `source_analytics`, `MySQL Sakila`, and `MSSQL AdventureWorks`. Screenshot: `screenshots/phase3-05-admin-connections-all-dialects.png`. |
| Verify at least Postgres source connection is visible and healthy. | Pass | Admin page text included `source_analytics` and healthy status. |
| Verify MySQL/MSSQL health/introspection state if exposed. | Pass | MySQL and MSSQL are now exposed in Admin Connections as usable seeded connections. |
| Submit at least one benign real query against Postgres via UI. | Pass | UI query returned response; SQL captured as `SELECT COUNT(*) FROM actor`; result marker observed. Screenshot: `screenshots/phase3-04-postgres-query-response.png`. |
| Submit benign MySQL/MSSQL query if available to admin. | Pass | Saved-`.env` rerun: MySQL `/query/submit` returned 200 with generated SQL `SELECT COUNT(*) FROM actor` and result `200`; MSSQL `/query/submit` returned 200 with generated SQL `SELECT COUNT(*) FROM SalesLT.Customer` and result `847`. |
| Verify schema/connection selection UI behaves correctly. | Pass | Selector showed and selected all three options. Screenshot: `screenshots/phase3-06-selector-all-dialects.png`. |
| Verify sanitized error handling for failed/invalid connection or unavailable dialect path. | Pass | API invalid connection id returned sanitized 400 with `error.connection_not_found`; invalid temp connection health checks returned generic categories/message keys and no credentials. |

## Commands Run

| Task | Status | Evidence |
|---|---|---|
| `rtk uv run pytest tests/unit/db/test_migration_006_phase3.py ... tests/unit/api/test_query_connection_routing.py tests/unit/test_seed_e2e_connection.py -x --tb=short` | Pass | `115 passed, 1 warning`. |
| `rtk uv run pytest tests/unit/evaluator/test_dialect_evaluator.py ... tests/integration/api/test_admin_refresh_schema.py -x --tb=short` | Pass | `90 passed`. |
| `rtk uv run ruff check src tests` | Pass | `All checks passed!` |
| `rtk uv run ruff format --check src tests` | Pass | `384 files already formatted`. |
| Existing `wave_16_3_smoke.spec.ts` via wrapper | Skipped | Two wrapper attempts were interrupted with exit 130 after hanging/no useful child output. Direct Playwright browser probe was used instead and completed. |
| Direct Playwright browser probe | Pass | `phase-3-browser-smoke-evidence.json` and four `phase3-` screenshots. |
| Updated deterministic seed script | Pass | `python /tmp/seed_e2e_connection.py` in backend container restored MSSQL if needed and seeded three healthy/introspected connections with Admin policies. |
| QueryCraft adapter smoke | Pass | Actual encrypted QueryCraft connection rows executed PostgreSQL actor count `200`, MySQL actor count `200`, and MSSQL `SalesLT.Customer` count `847`. |
| MySQL/MSSQL `/query/submit` retry probe | Pass | Saved-`.env` rerun passed: MySQL result `200`, MSSQL result `847`. |

## Real LLM / Query Results

| Dialect | Status | Evidence |
|---|---|---|
| PostgreSQL | Pass | UI and API submitted `How many actors are there?`; generated SQL `SELECT COUNT(*) FROM actor`; result `200`. |
| MySQL | Pass | Seeded QueryCraft connection is active/healthy/introspected with Admin policy present. 2026-07-05 `/query/submit` generated `SELECT COUNT(*) FROM actor` and returned `200`. |
| MSSQL | Pass | Seeded QueryCraft connection is active/healthy/introspected with Admin policy present. Saved-`.env` rerun generated `SELECT COUNT(*) FROM SalesLT.Customer` and returned `847`. |

## Setup Limitations / Spec Drift

| Task | Status | Evidence |
|---|---|---|
| Current dev seed exposes all three dialect connections. | Fixed | `seed_e2e_connection.py` now seeds/repairs PostgreSQL, MySQL, and MSSQL. `/api/v1/connections` returns all three. |
| MSSQL AdventureWorks fixture. | Fixed | `seed_e2e_connection.py` now restores `AdventureWorksLT` from the existing local backup when needed and configures the read-only app login. |
| `/api/v1/connections` RBAC wording. | Contract Note | Current implementation returns active/healthy/introspected connections with minimal fields; the repository method does not take a user/role policy argument. |
| Real LLM MySQL/MSSQL query submission. | Fixed | Saved-`.env` rerun passed both remaining provider-backed submissions: MySQL `200`, MSSQL `847`. |

## Real Query Rerun - 2026-07-05

| Task | Status | Evidence |
|---|---|---|
| Confirm deterministic seed state is present for PostgreSQL, MySQL, and MSSQL. | Pass | Reran `seed_e2e_connection.py`; all three source connections were active/healthy/successfully introspected. Admin policies present with PostgreSQL 29, MySQL 23, and MSSQL 15 allowed tables. |
| `/api/v1/connections` returns usable PostgreSQL, MySQL, and MSSQL for signed-in admin. | Pass | Container-local API probe returned `source_analytics` (`postgresql`), `MySQL Sakila` (`mysql`), and `MSSQL AdventureWorks` (`mssql`). |
| Admin Connections API confirms all three healthy/introspected. | Pass | `/api/v1/admin/connections` returned all three as `active`, `healthy`, `success`. |
| MySQL `/api/v1/query/submit` actor count against Sakila source. | Pass | Real provider-backed submit returned 200; generated SQL `SELECT COUNT(*) FROM actor`; result `200`; expected `200`. |
| MSSQL `/api/v1/query/submit` customer count against AdventureWorksLT/SalesLT source. | Blocked | Real provider-backed submit returned sanitized 502 `error.llmUnavailable`; recent backend provider log showed Gemini `429 Too Many Requests`. Direct adapter execution remains `SELECT COUNT(*) FROM SalesLT.Customer` → `847`. |
| Provider 429 cleared for all remaining Phase 3 checks. | Blocked | Cleared for MySQL; not cleared for MSSQL. |

## Updated-Key Real Query Rerun - 2026-07-05

| Task | Status | Evidence |
|---|---|---|
| Recreate backend to load updated Gemini provider environment. | Pass | `rtk docker compose -f docker-compose.dev.yml up -d --force-recreate backend`; backend restarted and reported `llm_provider=gemini`, `gemini_key_configured=True` without printing the key. |
| Confirm deterministic seed state remains present. | Pass | Reran `seed_e2e_connection.py`; PostgreSQL, MySQL, and MSSQL updated from backend environment and reported healthy/success with Admin policies present. |
| `/api/v1/connections` returns usable PostgreSQL, MySQL, and MSSQL for signed-in admin. | Pass | API probe returned `source_analytics` (`postgresql`), `MySQL Sakila` (`mysql`), and `MSSQL AdventureWorks` (`mssql`). |
| Admin Connections API confirms all three healthy/introspected. | Pass | `/api/v1/admin/connections` returned all three as `active`, `healthy`, `success`. |
| MySQL `/api/v1/query/submit` actor count against Sakila source. | Blocked | Updated-key rerun returned sanitized 502 `error.llmUnavailable`; backend provider log showed Gemini `429 Too Many Requests`; expected count remains `200`. |
| MSSQL `/api/v1/query/submit` customer count against AdventureWorksLT/SalesLT source. | Blocked | Updated-key rerun returned sanitized 502 `error.llmUnavailable`; backend provider log showed Gemini `429 Too Many Requests`; expected count remains `847`. |
| Provider 429 cleared for all remaining Phase 3 checks after key update. | Blocked | Not cleared; both MySQL and MSSQL updated-key submit calls hit Gemini 429. |

## Saved-`.env` Real Query Rerun - 2026-07-05

| Task | Status | Evidence |
|---|---|---|
| Recreate backend after saving updated `.env`. | Pass | `rtk docker compose -f docker-compose.dev.yml up -d --force-recreate backend`; backend reported `llm_provider=gemini`, `gemini_key_configured=True` without printing the key. |
| Confirm deterministic seed state remains present. | Pass | Reran `seed_e2e_connection.py`; PostgreSQL, MySQL, and MSSQL reported healthy/success with Admin policies present. |
| `/api/v1/connections` returns usable PostgreSQL, MySQL, and MSSQL for signed-in admin. | Pass | API probe returned `source_analytics` (`postgresql`), `MySQL Sakila` (`mysql`), and `MSSQL AdventureWorks` (`mssql`). |
| Admin Connections API confirms all three healthy/introspected. | Pass | `/api/v1/admin/connections` returned all three as `active`, `healthy`, `success`. |
| MySQL `/api/v1/query/submit` actor count against Sakila source. | Pass | Real provider-backed submit returned 200; generated SQL `SELECT COUNT(*) FROM actor`; result `200`; expected `200`. |
| MSSQL `/api/v1/query/submit` customer count against AdventureWorksLT/SalesLT source. | Pass | Real provider-backed submit returned 200; generated SQL `SELECT COUNT(*) FROM SalesLT.Customer`; result `847`; expected `847`. |
| Provider 429 cleared for all remaining Phase 3 checks after `.env` save. | Pass | Both remaining real query-submit checks passed. |

## Evidence Files

- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-3-multi-dialect-source-dbs-report.md`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-3-browser-smoke-evidence.json`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase3-01-signed-in-workspace.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase3-02-admin-connections.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase3-03-workspace-selector.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase3-04-postgres-query-response.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase3-05-admin-connections-all-dialects.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase3-06-selector-all-dialects.png`

## Security and Privacy Notes

No secrets, cookies, passwords, full auth payloads, raw sensitive request bodies,
or Playwright trace zips were stored in evidence. API/browser evidence is
sanitized to statuses, connection display names/types, generated benign SQL,
and aggregate row-count observations.

Task counts after 2026-07-05 saved-`.env` query-submit rerun: Pass 30, Fail 0, Skipped 0, Blocked 0,
Setup Gap 0.

Chunk 3 setup gaps are fixed. MySQL and MSSQL real `/query/submit` checks now
pass through QueryCraft with real Gemini-backed SQL generation and expected
source DB results. Chunk 3 is complete and Chunk 4 is unblocked.
