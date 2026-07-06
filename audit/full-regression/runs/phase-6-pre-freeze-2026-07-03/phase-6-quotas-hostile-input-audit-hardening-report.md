# Phase 6 Quotas Hostile Input Audit Hardening Regression Report

Run date: 2026-07-05
Scope: Chunk 6 only - Phase 6 quotas, hostile input detection, audit search/export/retention hardening

Branch tested: `main`; backend blocker fixes validated on `fix/phase6-backend-regression-blockers`
HEAD SHA tested: `e059a40f8ee75b68cfe1d1a4dd43da14c6c3d7de`

## Summary

Focused Phase 6 backend gates passed for quotas, hostile input detection, audit search/export/retention, cross-dialect quotas, and sanitization regressions. The run stopped at the first required backend blocker during the full backend foundation gate: `tests/acceptance/test_query_timeout.py::test_query_timeout_cancellation_and_cleanup` expected the legacy timeout path (`504 error.timeout`) but received Phase 6 quota exceeded (`429 error.quota_exceeded`) before the timeout path.

Per the runbook stop condition, frontend gates, browser flows, manual API/security checks, and real LLM smoke were not run after this backend blocker.

Backend finisher update on 2026-07-07: the full backend blocker chain was resolved on `fix/phase6-backend-regression-blockers` without weakening Phase 6 ordering. Root causes were test/setup drift: acceptance timeout tests inherited persistent quota configuration, the source Postgres seed allowed `CREATE` on schema `public` through PUBLIC, and the secure-cookie endpoint regression test inherited the global non-HTTPS test cookie setting. The full backend gate and backend ruff gates now pass. Frontend/browser Phase 6 gates remain not started by this backend-only pass.

## Preflight

| Task | Status | Evidence |
|---|---|---|
| `rtk git status --short --branch` | Pass | `main...origin/main`; existing modified Phase 5 evidence PNGs plus prior untracked regression screenshots/traces were already present before Chunk 6. |
| `rtk git rev-parse HEAD` | Pass | `e059a40f8ee75b68cfe1d1a4dd43da14c6c3d7de`. |
| Docker compose services | Pass | Backend `8000`, frontend `5173`, platform Postgres `5433`, source Postgres `5434`, Redis `6379`, MySQL `3306`, and MSSQL `1433` running; DB/Redis/source services healthy. |
| Required ports listening | Pass | `5173`, `8000`, `5433`, `5434`, `6379`, `3306`, and `1433` listening. |
| Signed-in admin sees usable connections | Pass | Sanitized API probe signed in with configured local admin and listed `source_analytics`, `MySQL Sakila`, and `MSSQL AdventureWorks` as active, healthy, and schema-success. |

## Backend Gates

| Task | Status | Evidence |
|---|---|---|
| Quota service/repository/enforcement/audit/error sanitization/fail-closed/reset/admin/execution tests | Pass | `59 passed`. |
| Hostile detector, built-in rules, audit redaction, config repo, passthrough, coverage, admin tests | Pass | `205 passed`. |
| Audit search/export/retention/purge marker/verify-chain tests | Pass | `149 passed, 1 skipped`. |
| Cross-dialect quota and Phase 6 sanitization regression tests | Pass | `52 passed`. |
| Full backend foundation gate: `cd backend && rtk uv run pytest tests/ -x --tb=short` | Pass | Backend finisher rerun passed: `2478 passed, 4 skipped, 16 warnings, 35 subtests passed in 684.32s`. |
| `cd backend && rtk uv run ruff check src tests` | Pass | `All checks passed!` after Ruff sorted four import blocks in changed files. |
| `cd backend && rtk uv run ruff format --check src tests` | Pass | `384 files already formatted`. |

## Frontend Gates

| Task | Status | Evidence |
|---|---|---|
| AdminQuotasPage/AdminDetectionPage/AdminAuditPage/banner unit tests | Blocked | Not run because the required backend foundation gate failed first. |
| Full frontend unit tests, lint, typecheck, build, CSS lint | Blocked | Not run because the required backend foundation gate failed first. |
| `wave_18_4b_smoke.spec.ts` | Blocked | Not run because the required backend foundation gate failed first. |

## Regression Task Matrix

| Task | Status | Evidence |
|---|---|---|
| Role quota config CRUD and status cover query, execution, and export dimensions. | Pass | Focused quota backend gate passed; manual API CRUD/status not run after foundation blocker. |
| Redis-backed daily UTC counters fail closed when unavailable. | Pass | Focused quota fail-closed tests passed; manual Redis outage smoke not run after foundation blocker. |
| Query flow order is hostile detection, query quota, then LLM generation. | Pass | Focused detection/order and sanitization tests passed; real LLM ordering smoke not run after foundation blocker. |
| Blocked hostile input does not increment quota and returns only the sanitized hostile-input message key. | Pass | Focused detection error/no-raw-payload tests passed; manual API smoke not run after foundation blocker. |
| Built-in detection rules cover prompt injection, SQL injection, RBAC bypass, schema/secret exposure, and destructive SQL in English and Arabic patterns. | Pass | `205 passed` hostile detection gate included rule and coverage suites. |
| Detection threshold config validates `block_confidence > flag_confidence`. | Pass | Detection admin/config tests passed. |
| Hostile blocked/flagged audit entries never persist raw hostile payloads. | Pass | Hostile audit redaction and no-raw-payload tests passed. |
| Audit search supports filters, pagination, retention window, and self-audit. | Pass | Audit search/retention tests passed with one existing skip. |
| Audit export supports CSV/JSON, 50k limit, checksum metadata, formula-injection prevention, export quota, and defense-in-depth redaction. | Pass | Audit export and redaction-defense tests passed; manual export smoke not run after foundation blocker. |
| Retention purge inserts `audit.purge` marker and verify-chain treats valid purge gaps as intentional while detecting unmarked gaps. | Pass | Purge marker, verify-chain purge, and purge verify cycle tests passed. |
| Phase 6 admin quota/detection/audit surfaces are localized and RTL-safe. | Blocked | Browser and frontend checks not run because the required backend foundation gate failed first. |

## API And Security Checks

| Task | Status | Evidence |
|---|---|---|
| `/api/v1/admin/quotas` CRUD/status/delete and permission gates. | Pass / Partial | Required focused backend tests passed. Manual live API check blocked by full backend gate failure. |
| Query quota 429 path and Redis fail-closed 503 path. | Pass / Partial | Required focused backend tests passed. Manual live API check blocked by full backend gate failure. |
| Execution quota 429 path and Redis fail-closed 503 path. | Pass / Partial | Required focused backend tests passed. Manual live API check blocked by full backend gate failure. |
| Query ordering: hostile detection first, query quota second, LLM generation third. | Pass / Partial | Required focused backend tests passed. Real LLM ordering smoke blocked by full backend gate failure. |
| Hostile blocked path does not increment quota and returns only sanitized hostile-input message key. | Pass / Partial | Required focused backend tests passed. Manual live API check blocked by full backend gate failure. |
| Detection config read/update validation and permission gates. | Pass / Partial | Required focused backend tests passed. Manual live API check blocked by full backend gate failure. |
| Built-in hostile detection categories in English and Arabic. | Pass | Required focused backend tests passed. |
| Hostile blocked/flagged audit entries never persist raw hostile payloads. | Pass | Required focused backend tests passed. |
| Audit search filters, pagination, retention window, and self-audit. | Pass / Partial | Required focused backend tests passed. Manual UI/API smoke blocked by full backend gate failure. |
| Audit export CSV/JSON 50k limit, checksum metadata, formula prevention, export quota, redaction. | Pass / Partial | Required focused backend tests passed. Manual UI/API smoke blocked by full backend gate failure. |
| Audit retention endpoint and purge marker. | Pass / Partial | Required focused backend tests passed. Manual UI/API smoke blocked by full backend gate failure. |
| Verify-chain treats valid purge gaps as intentional and detects unmarked gaps. | Pass | Required focused backend tests passed. |
| Phase 6 error bodies omit counters, policy IDs, role internals, rule names/patterns/confidence, raw hostile text, DB host/port, provider names, stack traces, and OIDC/SAML tokens. | Pass / Partial | Required focused sanitization tests passed. Manual live API response sampling blocked by full backend gate failure. |

## Browser And Real LLM

| Task | Status | Evidence |
|---|---|---|
| `/admin/quotas` English and Arabic flows | Blocked | Not run because the required backend foundation gate failed first. |
| Arabic quota exceeded flow | Blocked | Not run because the required backend foundation gate failed first. |
| Arabic hostile input blocked flow | Blocked | Not run because the required backend foundation gate failed first. |
| `/admin/detection` Arabic flow | Blocked | Not run because the required backend foundation gate failed first. |
| `/admin/audit` Arabic flow | Blocked | Not run because the required backend foundation gate failed first. |
| Mobile 375px and 768px quota/detection/audit checks | Blocked | Not run because the required backend foundation gate failed first. |
| Real LLM benign-under-quota, hostile-before-quota/LLM, benign-over-quota ordering smoke | Blocked | Not run because the required backend foundation gate failed first. |

## Blocker

| Task | Status | Evidence |
|---|---|---|
| Backend full regression compatibility with Phase 6 quota enforcement | Pass | Resolved by isolating acceptance quota state so timeout coverage reaches the timeout path while preserving Phase 6 order: hostile detection, query quota, then LLM/provider/timeout path. Follow-on backend gate blockers were resolved as setup/test drift: source Postgres PUBLIC schema `CREATE` was revoked for read-only invariant coverage, and secure-cookie regression test now opts into production secure-cookie settings. |

## Evidence Files

- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-6-quotas-hostile-input-audit-hardening-report.md`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-6-browser-smoke-evidence.json`

## Security And Privacy Notes

No secrets, cookies, API keys, DB credentials, full auth payloads, raw sensitive request bodies, JWTs, SAML payloads, certificates, raw hostile payloads, provider payloads, or Playwright trace zips were added as Phase 6 evidence.

Task summary after backend finisher: Pass 13, Fail 0, Skipped 0, Blocked 10.

Chunk 6 backend blocker chain is resolved. Chunk 6 can resume from frontend/browser Phase 6 gates and real LLM/manual API smoke. Full pre-freeze regression is not complete.
