# Phase 3 Multi-Dialect Source DB Regression - 2026-07-22

Product head tested: `main` at `7cce728596716c556c486385e8942854444fea74`.

Scope was Phase 3 only. No Phase 4 work, T-905, or freeze work was started.

## Environment And Safety

- Docker services required for QueryCraft, PostgreSQL, MySQL, MSSQL, and Redis were healthy. The backend, frontend, and expected local service ports were available.
- The backend was configured for Gemini without exposing configuration values. A controlled live request returned an upstream `503`; QueryCraft returned a sanitized `502`/`llm_unavailable` response.
- Current Admin source connections were healthy and introspected with Admin policies: `source_analytics` (PostgreSQL, 30 tables / 172 columns), `MySQL Sakila` (MySQL, 23 / 132), and `MSSQL AdventureWorks` (MSSQL, 15 / 142).
- Browser/API responses and this evidence were checked for credential values, provider keys, cookies, hosts, driver text, stack traces, and untranslated keys. None were recorded. `password_value_exposed=false`; a source-schema column named `password`, where present, is metadata and not a credential value.
- Temporary local browser connections for all three dialects and one controlled unhealthy connection were deleted through the Admin UI. The final verification found `temporary_connections=0` and `temporary_schema_entries=0`; neither Admin nor the workspace selector retained a temporary entry.

## Gates And Live Checks

| Check | Result | Evidence |
|---|---|---|
| Phase 3 backend gates | Pass | 203 focused tests passed; one pre-existing async mock warning in schema-introspection coverage. |
| Backend style | Pass | `ruff check src tests` and `ruff format --check src tests`. |
| Frontend gates | Pass | 762 tests, lint, typecheck, logical-CSS audit, and build passed; build retained only its existing chunk advisory. |
| Current locale audit | Pass | 306 locale/logical-CSS checks passed; PR #206 added and covered the previously missing Admin connection action toasts. |
| Current icon audit | Pass | No inline SVG or extra icon-library findings; 27 Lucide imports. |
| Hosted CI for remediation | Pass | PRs #200 through #206 were merged with `backend-test` and `frontend-test` green. |
| Read-only/evaluator gate | Pass | PostgreSQL, MySQL, and MSSQL write/create/drop attempts were rejected before execution. |
| Live Gemini diagnostic | External availability observation | Configured backend returned upstream `503`; application output stayed sanitized. |
| Deterministic provider pipeline | Pass | Matrix-approved provider entered the real QueryCraft `/api/v1/query/submit` path, including evaluator, quota, session/attempt persistence, and real adapters. |

The deterministic pipeline browser run on the product head produced `SELECT COUNT(*) AS actor_count FROM actor` and result `200` for PostgreSQL and MySQL, and `SELECT COUNT(*) AS customer_count FROM SalesLT.Customer` and result `847` for MSSQL. Each response card used the connection display name and type badge without a raw UUID fallback. This is pipeline evidence, not a direct-adapter substitution.

## Matrix

| Matrix Row | Status | Evidence | Notes |
|---|---|---|---|
| P3-FR-059 | Pass | Current browser create/test/introspect/update/delete for PostgreSQL, MySQL, and MSSQL | Automatic healthy/introspected save, empty edit-password fields, and cleanup verified. |
| P3-FR-060 | Pass | Browser edit forms and API serialization checks | Stored credentials were not displayed or returned. |
| P3-FR-061 | Pass | Browser delete lifecycle; final temporary connection/schema counts zero | Historical delete `409` was remediated by PR #200; current allowed deletes returned `204`. |
| P3-FR-062 | Pass | API/browser response inspection and encryption tests | `password_value_exposed=false`. |
| P3-FR-063 | Pass | Browser health checks for all sources; controlled auth/network API retries | Healthy checks succeeded; failures were categorized and sanitized. |
| P3-FR-064 | Pass | Admin list and lifecycle API checks | Lifecycle, health, timestamp, and error-category fields persisted independently. |
| P3-FR-065 | Pass | Real PostgreSQL/MySQL/MSSQL schema introspection | Expected source summaries were available. |
| P3-FR-066 | Pass | Browser/API schema refresh | Refresh replaced metadata successfully for all healthy sources. |
| P3-FR-067 | Pass | Admin schema summaries | Table/column counts rendered without credential values. |
| P3-FR-068 | Pass | Controlled categorized introspection failures and current unhealthy browser record | Failed status, retry, and sanitized refresh error verified. |
| P3-FR-069 | Pass | Current-head deterministic `/query/submit` browser pipeline | PostgreSQL=200, MySQL=200, MSSQL=847; live Gemini availability is recorded separately. |
| P3-FR-070 | Pass | Prompt/dialect backend gate | Selected schema and target dialect coverage passed. |
| P3-FR-071 | Pass | Dialect evaluator/retry gate | Invalid dialect SQL was not executed. |
| P3-FR-072 | Pass | Cross-dialect evaluator/read-only gate | Unsafe write/create/drop statements were blocked before execution. |
| P3-FR-073 | Pass | Current browser selector | All three usable sources selectable near the prompt. |
| P3-FR-074 | Pass | Current browser/API selector inspection | Friendly names/types shown; no host or credential fields returned. |
| P3-FR-075 | Pass | Current browser submit-switch-submit | Attempts retained the selected connection and response metadata. |
| P3-FR-076 | Pass | Current browser response cards | Correct display name/type badge; no raw UUID fallback. |
| P3-FR-077 | Pass | Selector/prompt automated coverage | No/all-unhealthy prompt behavior covered. |
| P3-FR-078 | Pass | Current English/Arabic browser errors plus API failure paths | Connection, introspection, and query failures were localized/sanitized. |
| P3-FR-079 | Pass | Query error UI coverage and disabled-source browser submission | Inline error card rendered without driver details. |
| P3-FR-080 | Pass | Current Admin Connections browser smoke | Admin page loaded the three configured sources. |
| P3-FR-081 | Pass | Current Arabic RTL selector interaction | `lang=ar`, `dir=rtl`, selector options, and interactions verified. |
| P3-FR-082 | Pass | Current local-admin browser sign-in/sign-out | EN/AR auth surface remained usable; credential field was cleared. |
| P3-FR-083 | Pass | Current icon audit | No prohibited inline or non-Lucide icon usage found. |
| P3-FR-084 | Pass | Current locale parity audit | No missing Phase 3 locale keys; action-toast remediation included. |
| P3-FR-085 | Pass | Current logical-directional CSS audit | Phase 3 CSS passed physical-direction checks. |
| P3-FR-086 | Pass | Current Chrome DevTools smoke | Login, CRUD, health, schema, selector, lifecycle, and deterministic dialect queries completed. |
| P3-FR-087 | Pass | Migration gate | Connection/schema migration and backfill coverage passed. |
| P3-FR-088 | Pass | Current browser one-active-source check | With two sources disabled, MSSQL auto-selected; sources then re-enabled. |
| P3-FR-089 | Pass | Current browser disable/enable path | Disabled source left selector, rejected submission, then returned after enable. |
| P3-FR-090 | Pass | Admin lifecycle/health checks | Active-unhealthy and disabled state behavior remained distinct. |
| P3-FR-091 | Pass | Migration backfill gate | Legacy connection/backfill assertions passed. |
| P3-FR-092 | Pass | Dialect retry/refusal gate | Exhausted invalid-dialect retries returned a localized refusal without execution. |
| P3-FR-093 | Pass | Current browser healthy/unhealthy saves | Automatic health/introspection, failed status, retry, selector exclusion, and cleanup verified. |
| P3-FR-094 | Pass | Current browser session reload/selection check | Saved session cards and selected MSSQL connection restored correctly. |

## Closure

| Status | Count |
|---|---:|
| Pass | 36 |
| Fail | 0 |
| Partial | 0 |
| Setup-dependent incomplete | 0 |
| Not run | 0 |
| Deferred | 0 |

Product-path result: 36 matrix rows passed. Live Gemini availability: configured but upstream `503`, with a sanitized application response. Deterministic-provider pipeline: passed through the real QueryCraft route and all three real adapters. No genuine QueryCraft blocker remains.

Phase 3 is complete. Phase 4 is unblocked, but was not started by this run.
