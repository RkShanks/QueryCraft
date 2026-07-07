# Phase 6 Quotas Hostile Input Audit Hardening Regression Report

Run date: 2026-07-05 through 2026-07-07
Scope: Chunk 6 only - Phase 6 quotas, hostile input detection, audit search/export/retention hardening

Branch tested: `main`
HEAD SHA tested: `287e75ed30446327efb2f7acd7c1ed5e80f0c81c`

## Summary

Chunk 6 is complete. Backend full regression was already completed and merged via PR #193, and this continuation completed frontend gates, Wave 18.4b Playwright smoke, live browser/API Phase 6 flows, and real LLM ordering checks.

No product blocker remains. Local setup required repair during live validation: the stale backend container failed restart, was rebuilt/recreated, `source_analytics` was pointed at the Docker-network source host, schema was refreshed, and the Admin source policy was restored from the refreshed schema. These were regression-environment repairs only; no product code was changed.

## Preflight / Setup

| Task | Status | Evidence |
|---|---|---|
| Branch / HEAD | Pass | `main` at `287e75ed30446327efb2f7acd7c1ed5e80f0c81c`. |
| Existing worktree noise | Not touched | Pre-existing Phase 5 evidence PNGs, old Phase 1/2 screenshots, and traces remain outside this chunk's evidence updates. |
| Docker services | Pass | Backend rebuilt/recreated; frontend, backend, Postgres platform/source, Redis, MySQL, MSSQL running. |
| Source connection | Pass after setup repair | `source_analytics` healthy, schema refresh 200, user `/connections` count 1. |

## Backend Gates

| Task | Status | Evidence |
|---|---|---|
| Quota service/repository/enforcement/audit/error sanitization/fail-closed/reset/admin/execution tests | Pass | `59 passed`. |
| Hostile detector, built-in rules, audit redaction, config repo, passthrough, coverage, admin tests | Pass | `205 passed`. |
| Audit search/export/retention/purge marker/verify-chain tests | Pass | `149 passed, 1 skipped`. |
| Cross-dialect quota and Phase 6 sanitization regression tests | Pass | `52 passed`. |
| Full backend foundation gate | Pass | `2478 passed, 4 skipped, 16 warnings, 35 subtests passed in 684.32s` from PR #193. |
| Backend ruff / format | Pass | `ruff check` passed; `384 files already formatted`. |

## Frontend Gates

| Command | Status | Evidence |
|---|---|---|
| `cd frontend && rtk npm test -- --run` | Pass | 63 files, 759 tests passed. |
| `cd frontend && rtk npm run lint` | Pass | ESLint completed with exit 0. |
| `cd frontend && rtk npm run typecheck` | Pass | `tsc --noEmit` completed with exit 0. |
| `cd frontend && rtk npm run build` | Pass | Build completed; Vite large chunk warnings only. |
| `cd frontend && rtk npm run lint:css` | Pass | Stylelint completed with exit 0. |
| `cd frontend && rtk npm run test:e2e -- wave_18_4b_smoke.spec.ts` | Pass | 4 Playwright tests passed. Initial sandbox bind failure on port 3000 was rerun outside sandbox. |

## Browser / API / Real LLM Flow Table

| Task | Status | Evidence |
|---|---|---|
| Admin quotas page sign-in, view role quotas, update thresholds, success UI | Pass | Live browser: signed in, `/admin/quotas?lng=ar`, update PUT 200, success toast visible. |
| Quota-only admin avoids roles/SSO group-mapping calls | Pass | Live browser auth/me override with only `admin.quotas.manage`; roles/SSO group-mapping calls: 0. |
| Quota exceeded flow | Pass | Live API: low query quota then benign submit returned 429 `error.quota_exceeded`; no `generated_sql`, no `attempt_id`, no leaks. |
| Hostile input blocked flow | Pass | Live API: hostile submit returned 400 with only `message_key=error.hostile_input_blocked`; query quota used count unchanged; no leaks. |
| Benign under quota reaches LLM/DB | Pass | Live API: benign submit returned 200 `kind=result`, `generated_sql` present, numeric `row_count`. |
| Admin detection page | Pass | Live browser/API: thresholds rendered, invalid client validation visible, valid update PUT 200, restored original thresholds. |
| Detection permission gate | Pass | Backend focused tests plus live signed-in admin permission count; route requires `admin.security.manage`. |
| Audit search filters and pagination | Pass | Live API page 1/page 2 returned 200 with pagination; filters by action/date/actor/outcome/resource exercised. |
| Audit table redaction | Pass | Hostile audit filter returned sanitized data; no raw hostile payload, rule names, patterns, stack, DB host, token, password, or secret in sampled visible/API data. |
| Audit export CSV/JSON | Pass | Live browser downloaded CSV and JSON; filenames captured; export request used current unsent form filters, not stale submitted filters. |
| Audit export metadata redaction | Pass | Live API CSV/JSON export metadata scan found no sensitive leaks. |
| Audit retention | Pass | Live API/UI rendered `retention_months`, `last_purge_at`/Never, `purged_count`; permission covered by backend tests. |
| Arabic RTL/admin surfaces | Pass | Live browser `dir=rtl` on quotas/detection/audit; screenshots captured. |
| Mobile 375px / 768px | Pass | Live browser Arabic audit smoke at 375 and 768 had `dir=rtl` and no horizontal overflow; Wave 18.4b also covered quota/detection/audit mobile surfaces. |

## Regression Task Matrix

| Task | Status | Evidence |
|---|---|---|
| Role quota config CRUD and status cover query, execution, and export dimensions. | Pass | Backend tests; live quota list/status/update/restore. |
| Redis-backed daily UTC counters fail closed when unavailable. | Pass | Backend focused fail-closed coverage. |
| Query flow order is hostile detection, query quota, then LLM generation. | Pass | Live hostile blocked before quota increment; live over-quota blocked before LLM; live benign under quota reached LLM. |
| Blocked hostile input does not increment quota and returns only sanitized hostile-input message key. | Pass | Live API quota used count unchanged; 400 `message_key` only. |
| Built-in detection rules cover prompt injection, SQL injection, RBAC bypass, schema/secret exposure, and destructive SQL in English and Arabic patterns. | Pass | `205 passed` hostile detection suite. |
| Detection threshold config validates `block_confidence > flag_confidence`. | Pass | Live invalid threshold validation plus backend tests. |
| Hostile blocked/flagged audit entries never persist raw hostile payloads. | Pass | Backend tests and live audit/export leak scans. |
| Audit search supports filters, pagination, retention window, and self-audit. | Pass | Backend tests; live filtered API pagination. |
| Audit export supports CSV/JSON, 50k limit, checksum metadata, formula-injection prevention, export quota, and defense-in-depth redaction. | Pass | Backend tests; live CSV/JSON downloads and metadata scans. |
| Retention purge inserts `audit.purge` marker and verify-chain treats valid purge gaps as intentional while detecting unmarked gaps. | Pass | Backend focused purge/verify-chain coverage. |
| Phase 6 admin quota/detection/audit surfaces are localized and RTL-safe. | Pass | Wave 18.4b smoke plus live Arabic screenshots. |

## Setup Gaps / Spec Drift

| Item | Classification | Evidence |
|---|---|---|
| Stale Docker backend container failed restart with missing `uvicorn`. | Harness/setup drift | Rebuilt/recreated backend container; no product code changes. |
| Failed in-container `uv run` damaged that container venv. | Harness/setup drift caused during recovery | Recreated backend from rebuilt image; dependency path restored. |
| Local `.env` source DB host values are host-oriented while Docker backend needs Docker-network names. | Local setup drift | Repaired platform `source_analytics` row to `postgres-source:5432`; refreshed schema and Admin policy. |
| Audit UI pagination not visible under narrowed hostile-input filter. | Non-blocking coverage note | Live API pagination passed; Wave 18.4b mocked UI smoke covers pagination controls. |

## Evidence Files

- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-6-quotas-hostile-input-audit-hardening-report.md`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-6-browser-smoke-evidence.json`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase6-admin-quotas-live-ar.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase6-admin-detection-live-ar.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase6-admin-audit-live-ar.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase6-mobile-375-audit-live-ar.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase6-mobile-768-audit-live-ar.png`

## Security And Privacy Notes

No secrets, cookies, API keys, DB credentials, full auth payloads, JWTs, SAML payloads, certificates, raw hostile payloads, provider payloads, or Playwright trace zips were added as Phase 6 evidence. Sampled UI/API responses and export metadata did not expose raw hostile payloads, rule names, patterns, confidence scores, stack traces, DB host, tokens, passwords, or secrets.

Chunk 6 status: COMPLETE.
Next step: T-905 final snapshot/freeze prep.
