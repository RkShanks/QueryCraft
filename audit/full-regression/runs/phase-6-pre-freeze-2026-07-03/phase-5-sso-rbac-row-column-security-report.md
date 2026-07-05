# Phase 5 SSO RBAC Row/Column Security Regression Report

Run date: 2026-07-05
Scope: Chunk 5 only - Phase 5 SSO, RBAC, row/column security, user-scoped history, audit log

Branch tested: `main`
HEAD SHA tested: `6392497110f10e731d63029a31e62341ba70ead1`

## Summary

Backend gates and frontend non-e2e gates passed. Focused API smoke passed after repairing shared dev seed drift caused by the required backend tests. Restricted-role real Gemini smoke passed: the allowed actor query returned 5 rows with a masked `last_name` column, and a disallowed `film` query was blocked before execution with `error.queryBlockedPolicy`.

Follow-up blocker fix completed: the sign-in SSO button key `auth.signIn.sso.button` was added to English and Arabic locale resources, SignInPage regression coverage now reproduces missing-key behavior, and the focused browser smoke shows OIDC and SAML buttons by provider name with no raw i18n key visible. Chunk 5 can resume/close from the Phase 5 evidence; Chunk 6 is unblocked after normal orchestration acceptance.

## Preflight

| Task | Status | Evidence |
|---|---|---|
| `rtk git status --short --branch` | Pass | `main...origin/main`; prior chunk untracked screenshots/traces already present. |
| `rtk git rev-parse HEAD` | Pass | `6392497110f10e731d63029a31e62341ba70ead1`. |
| Docker compose services | Pass | Backend `8000`, frontend `5173`, platform Postgres `5433`, source Postgres `5434`, Redis `6379`, MySQL `3306`, MSSQL `1433` running. |
| Required ports listening | Pass | `5173`, `8000`, `5433`, `5434`, `6379`, `3306`, and `1433` listening. |
| Signed-in admin sees usable connections | Pass | Initial preflight returned `source_analytics`, `MySQL Sakila`, and `MSSQL AdventureWorks`. After backend tests mutated shared seed state, `seed_e2e_connection.py` restored all three healthy/introspected. |

## Backend Gates

| Task | Status | Evidence |
|---|---|---|
| OIDC/SAML flow, callback, errors, JWKS, signed assertion, replay tests | Pass | `84 passed`. |
| Role endpoints, group mappings, role resolution, permission gates, local-login restriction, admin lockout, unmapped denial tests | Pass | `169 passed`. |
| Row filter validation/injection, schema filtering, column masking, query policy, rerun, history, cross-dialect policy tests | Pass | `189 passed, 1 warning` (`AsyncMock` warning in existing test). |
| Audit service, chain verification, immutability, RBAC/query audit logging, OIDC redaction tests | Pass | `170 passed`. |
| `rtk uv run ruff check src tests` | Pass | `All checks passed!` |
| `rtk uv run ruff format --check src tests` | Pass | `384 files already formatted`. |

## Frontend Gates

| Task | Status | Evidence |
|---|---|---|
| `rtk npm test -- --run AdminSsoPage` | Pass | 1 file passed, 15 tests passed. |
| `rtk npm test -- --run SignInPage` | Pass | Initial full-regression gate: 1 file passed, 6 tests passed. Blocker follow-up: 1 file passed, 7 tests passed. |
| `rtk npm test -- --run localeCoverage` | Pass | Blocker follow-up: 1 file passed, 297 tests passed. |
| `rtk npm test -- --run` | Pass | 63 files passed, 756 tests passed. |
| `rtk npm run lint` | Pass | ESLint completed. |
| `rtk npm run typecheck` | Pass | `tsc --noEmit` completed. |
| `rtk npm run build` | Pass | Production build completed; existing large-chunk warning only. |
| `rtk npm run lint:css` | Pass | Stylelint completed. |
| Required e2e wrapper: `wave_17_4e_audit_smoke.spec.ts` | Pass / Harness | 2 mocked audit wrapper tests passed with escalation. |
| Required e2e wrapper: `wave_17_3o_smoke.spec.ts` | Harness Drift | Spec mocks connections/roles/schema/query and now fails before assertions because `/sign\s*in/i` matches local sign-in plus configured SSO buttons. Failure artifacts were removed. Direct browser validation used for real app coverage. |

## Regression Task Matrix

| Task | Status | Evidence |
|---|---|---|
| OIDC and SAML provider configuration masks secrets and validates sanitized input. | Pass | Admin SSO API returned mask placeholders for client secret, SAML metadata, and certificate; invalid callback paths redirected with safe error codes. |
| End-user OIDC/SAML sign-in validates protocol controls and maps groups to roles. | Pass | Protocol behavior covered by 84 backend tests. Follow-up browser smoke shows active OIDC and SAML buttons as `Sign in with Phase5 OIDC` and `Sign in with Phase5 SAML`; raw key `auth.signIn.sso.button` is no longer visible. |
| Users with no mapped role are denied access. | Pass | Backend unmapped-user denial tests passed. |
| Local password login is restricted to built-in admin; built-in admin cannot be deleted or locked out. | Pass | Backend tests passed; API smoke returned `401 error.unauthorized` for local non-admin and `403 error.builtinRoleProtected` for built-in admin role delete. |
| Role CRUD supports priority, fixed permissions, allowed tables/columns, row filters, placeholders, and column masks. | Pass | Backend tests passed; API created regression role with three connection policies; direct browser rendered priority, permissions, group mapping, policy editor, row-filter controls, and column-mask controls. |
| Duplicate group mappings are prevented; multi-group resolution uses lowest numeric priority. | Pass | Backend tests passed; API duplicate mapping returned 409. |
| UI routes and API endpoints enforce permissions. | Pass | Backend permission tests passed; restricted SSO-style session got 403 on admin roles API. |
| LLM schema context is role-filtered; evaluator blocks disallowed schema. | Pass | Real Gemini restricted-role smoke allowed `actor` query and blocked `film` query before execution with `error.queryBlockedPolicy`. |
| Row filters apply across PostgreSQL, MySQL, and MSSQL; masked columns show localized indicator. | Pass | Backend cross-dialect tests passed; API policy dry-run passed for all three dialects with row filters and mask metadata; frontend/component masked indicator tests passed. |
| History is scoped per user and rerun re-validates current role policy. | Pass | Backend history/rerun tests passed; restricted user history API returned only own visible rows. |
| Audit log records required security events, is immutable through app paths, and verifies chained hashes. | Pass | Audit tests passed; API verify-chain returned `verified=true`; real admin audit page displayed status/verify action. |
| Phase 5 Arabic/RTL surfaces are localized and mirrored. | Pass | Direct browser smoke confirmed Arabic roles and audit pages had `dir=rtl` and localized Arabic labels. |

## Real LLM Restricted Role

| Task | Status | Evidence |
|---|---|---|
| Allowed restricted query | Pass | Gemini-backed query against `source_analytics` returned `kind=result`, `row_count=5`, with `last_name` marked masked. |
| Disallowed schema query | Pass | Restricted `film` query returned HTTP 422 with `error.queryBlockedPolicy`; no source execution evidence was stored. |
| Provider schema exposure | Pass | Inferred from role policy outcome: allowed table succeeded, disallowed table blocked before execution. Raw prompts/provider payloads were not stored. |

## Cross-Dialect Row/Mask Results

| Dialect | Status | Evidence |
|---|---|---|
| PostgreSQL `source_analytics` | Pass | Policy dry-run allowed `actor`, reported one row filter and masked `actor.last_name`; blocked `film` with `error.queryBlockedPolicy`. |
| MySQL `MySQL Sakila` | Pass | Policy dry-run allowed `actor`, reported one row filter and masked `actor.last_name`; blocked `film` with `error.queryBlockedPolicy`. |
| MSSQL `MSSQL AdventureWorks` | Pass | Policy dry-run allowed `Customer`, reported one row filter and masked `Customer.EmailAddress`; blocked `Product` with `error.queryBlockedPolicy`. |

## Setup Limitations / Spec Drift

| Task | Status | Evidence |
|---|---|---|
| Required backend tests mutate shared dev seed state. | Repaired | After gates, platform DB had only `source_analytics` in `untested/none` state and admin hash matched test default. Backend restart restored configured admin password; `python src/seed_e2e_connection.py` restored all three source connections. |
| `wave_17_3o_smoke.spec.ts` wrapper | Harness Drift | Stale selector and mocked data paths; failed before product assertions when configured SSO providers added extra sign-in buttons. |
| Non-escalated Playwright | Harness Limitation | Chromium launch fails in sandbox; escalated Playwright works. |
| SSO sign-in missing-key blocker | Fixed | Root cause: missing `auth.signIn.sso.button` in `frontend/src/locales/en.json` and `frontend/src/locales/ar.json`, combined with the app's missing-key handler returning the raw key. Fixed with locale entries, locale coverage, and SignInPage EN/AR regression assertions. |

## Browser Evidence

| Task | Status | Evidence |
|---|---|---|
| SSO sign-in providers and sanitized error | Pass | Historical failing screenshot `phase5-sso-signin-providers.png` showed OIDC raw key. Follow-up screenshot `phase5-sso-signin-buttons-fixed.png` shows `Sign in with Phase5 OIDC`, `Sign in with Phase5 SAML`, sanitized `SSO validation failed.`, and no raw `auth.signIn.sso.button`. |
| Local admin sign-in | Pass | Screenshot `phase5-admin-signed-in.png`. |
| Admin SSO masks | Pass | Screenshot `phase5-admin-sso-masked.png`. |
| Role editor and policy controls | Pass | Screenshots `phase5-admin-roles-policy-editor.png`, `phase5-admin-roles-row-mask-controls.png`. |
| Audit verify page | Pass | Screenshot `phase5-admin-audit-verify-real.png`. |
| Arabic/RTL roles and audit | Pass | Screenshots `phase5-ar-admin-roles.png`, `phase5-ar-admin-audit.png`. |

## Evidence Files

- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-5-sso-rbac-row-column-security-report.md`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-5-browser-smoke-evidence.json`

## Security and Privacy Notes

No secrets, cookies, API keys, DB credentials, full auth payloads, raw sensitive request bodies, JWTs, SAML payloads, certificates, or Playwright trace zips were stored as evidence. Generated Playwright failure artifacts were removed after stale wrapper failures.

Task summary: Pass 12, Fail 0, Skipped 0, Blocked 0.

Chunk 5 blocker is fixed. Chunk 5 can resume/close, and Chunk 6 is unblocked after orchestration acceptance of this focused rerun.
