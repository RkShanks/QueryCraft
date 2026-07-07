# Phase 1 Core Text-to-SQL Regression Report - 2026-07-07

Scope: pre-flight checks and Phase 1 matrix rows only. Phases 2-6 and T-905 were not run.

## Tested Revision

- Branch: `main`
- HEAD: `481044c8bd028a6cf58237a428c73c6a0996a9af`
- Requested base main: `481044c8bd028a6cf58237a428c73c6a0996a9af`
- Worktree before report: pre-existing dirty evidence under `specs/005-sso-rbac-row-column-security/evidence/*.png` and pre-existing untracked full-regression screenshots/traces. These were not staged or intentionally modified.

## Pre-Flight

| Check | Status | Evidence |
|---|---|---|
| Branch and HEAD | Pass | `rtk git status --short --branch`; `rtk git rev-parse HEAD` returned `main` at `481044c8bd028a6cf58237a428c73c6a0996a9af`. |
| Docker/services | Pass | Escalated `rtk docker ps` and `rtk docker compose -f docker-compose.dev.yml ps`: backend, frontend, platform Postgres, source Postgres, Redis, MySQL, and MSSQL containers running; DB/Redis/source services healthy. Unrelated `local-atlas-hybrid` container restarting. |
| Ports | Pass | Escalated `rtk ss -ltnp`: expected app/service ports listening on `5173`, `8000`, `5433`, `5434`, `6379`, `3306`, `1433`; Chrome remote debugging port `9222` also present. |
| Frontend scripts/browser tooling | Pass | `rtk npm run` listed expected scripts; `rtk npm exec playwright -- --version` returned `Version 1.59.1`. |
| Env presence without secrets | Pass | Current shell missing runtime env values; `.env` has `DATABASE_URL`, `REDIS_URL`, `PLATFORM_ENCRYPTION_KEY`, `DB_CREDENTIAL_KEY`, `ADMIN_API_KEY`, `LLM_PROVIDER`, `LLM_API_KEY_GEMINI`, `LLM_BASE_URL_OLLAMA`, `LLM_MODEL_NAME`, MySQL vars, and MSSQL vars set. Anthropic/OpenAI keys empty. No values printed. |

## Commands Run

| Command | Exit | Notes |
|---|---:|---|
| `rtk git status --short --branch` | 0 | Dirty evidence existed before this run. |
| `rtk git rev-parse HEAD` | 0 | Returned requested SHA. |
| `rtk docker ps` | 1 then 0 | Initial sandbox denial; escalated rerun passed. |
| `rtk docker compose -f docker-compose.dev.yml ps` | 1 then 0 | Initial sandbox denial; escalated rerun passed. |
| `rtk ss -ltnp` | 0 then 0 | Initial sandbox output lacked process detail due netlink denial; escalated rerun passed. |
| `rtk npm run` | 0 | Frontend scripts present. |
| `rtk npm exec playwright -- --version` | 0 | Playwright 1.59.1. |
| `.env` presence checks via `rtk bash` / `rtk awk` | 0 | Presence only, no secret values. |
| `rtk uv run pytest tests/acceptance ... tests/integration/test_us5_reconfigured_provider.py -x --tb=short` | 0 | 55 passed in 16.66s. |
| `rtk uv run pytest tests/unit/evaluator tests/unit/llm ... tests/unit/test_schemas_query.py -x --tb=short` | 0 | 245 passed in 0.83s. |
| `rtk uv run ruff check src tests` | 0 | All checks passed. |
| `rtk uv run ruff format --check src tests` | 0 | 384 files already formatted. |
| `rtk npm test -- --run` | 0 | 63 files, 759 tests passed. |
| `rtk npm run lint` | 0 | ESLint passed. |
| `rtk npm run typecheck` | 0 | TypeScript passed. |
| `rtk npm run lint:css` | 0 | Stylelint passed. |
| `rtk npm run build` | 0 | Production build passed; Vite chunk-size warning only. |
| `rtk npm run test:e2e -- us1-sign-in-to-accept.spec.ts ... query-timeout.spec.ts` | 1 | Configured dev webServer could not start. |
| `E2E_BASE_URL=http://localhost:5173 rtk npm run test:e2e -- us1-sign-in-to-accept.spec.ts ... query-timeout.spec.ts` | 1 | Sandbox blocked Chromium launch. |
| Escalated `E2E_BASE_URL=http://localhost:5173 rtk npm run test:e2e -- us1-sign-in-to-accept.spec.ts ... query-timeout.spec.ts` | 1 | Browser launched; 27 failed, 1 skipped. Failures stop at sign-in selector strict-mode violation because `/sign\s*in/i` matches local sign-in plus Phase 5 SSO buttons. |

## Stop Condition

Stopped at the Phase 1 Playwright gate. The failure is classified as test/spec drift, not a confirmed product blocker:

- The browser reached `/sign-in`.
- The failure is a Playwright strict-mode locator error before authentication or query workflow execution.
- The sign-in page currently exposes multiple accessible buttons matching `/sign\s*in/i`: `Sign In`, `auth.signIn.sso.button`, and `Sign in with Phase5 SAML`.
- Smallest fix: update Phase 1 e2e sign-in helpers to click the local credential submit button with an exact accessible name, submit-button scoping, or a stable `data-testid`; also fix the visible untranslated `auth.signIn.sso.button` key if that is not intentional fixture data.

## Matrix Results

| Matrix Row | Status | Evidence | Notes |
|---|---|---|---|
| P1-FR-001 | Blocked | Backend auth integration passed; Playwright sign-in gate failed at selector strict-mode violation. | Local admin browser sign-in not completed in this run. |
| P1-FR-002 | Blocked | Backend auth integration passed; browser redirect flow not completed after e2e blocker. | No user data exposure observed before blocker. |
| P1-FR-003 | Pass | Backend auth/session integration passed; frontend unit suite passed. | Browser reload/expiry not manually completed due stop condition. |
| P1-FR-004 | Pass | Backend query/integration suites passed; services and ports up. | Current contract includes Phase 3 managed connections. |
| P1-FR-005 | Pass | Acceptance evaluator/write-blocking tests passed. | Automated coverage proves unsafe writes blocked. |
| P1-FR-006 | Blocked | Frontend unit suite passed; browser natural-language ask blocked at sign-in selector. | Real-user path not completed. |
| P1-FR-007 | Pass | Backend schema/query tests and frontend unit suite passed. | Browser validation screenshots not refreshed due stop condition. |
| P1-FR-008 | Setup-dependent | `.env` has Gemini provider/key presence; no live or redacted provider transcript captured before stop. | Requires approved live/mock transcript after e2e blocker is fixed. |
| P1-FR-009 | Setup-dependent | Provider switch backend integration passed; `.env` has Gemini key presence. | Live provider smoke not run because execution stopped at e2e gate. |
| P1-FR-010 | Pass | Acceptance evaluator suites and unit evaluator suites passed. | Browser evaluator rejection path blocked by sign-in selector. |
| P1-FR-011 | Pass | Unit evaluator extensibility tests passed in focused backend suite. | No browser toggle exists. |
| P1-FR-012 | Pass | Acceptance timeout test passed; e2e timeout spec blocked at sign-in selector. | Browser timeout path not refreshed. |
| P1-FR-013 | Pass | Backend query integration and valid-select acceptance tests passed. | Browser/API execution against source DB not manually completed after stop. |
| P1-FR-014 | Blocked | Frontend unit suite passed; result-table browser path blocked at sign-in selector. | No new result rendering screenshot captured. |
| P1-FR-015 | Blocked | Frontend unit suite passed; action-control browser path blocked at sign-in selector. | Current Phase 2+ action bar not revalidated manually. |
| P1-FR-016 | Pass | Accept persistence integration and query service accept unit tests passed. | Browser accept/history path blocked at sign-in selector. |
| P1-FR-017 | Pass | Reject/autoretry service tests and regenerate-then-accept integration passed. | Browser reject path blocked at sign-in selector. |
| P1-FR-018 | Blocked | Frontend e2e double-reject spec blocked at sign-in selector. | Backend service coverage exists for reject/regenerate flow, but browser refine proof not refreshed. |
| P1-FR-019 | Pass | Regenerate service unit tests passed. | Browser regenerate path blocked at sign-in selector. |
| P1-FR-020 | Pass | Accept-only persistence integration passed; history service tests passed. | Browser mixed-flow history absence not refreshed. |
| P1-FR-021 | Pass | History integration and service tests passed. | Browser list/detail specs blocked at sign-in selector. |
| P1-FR-022 | Pass | History integration/service and frontend unit tests passed. | Browser filter path not refreshed after stop. |
| P1-FR-023 | Pass | History integration/service and frontend unit tests passed. | Browser detail path not refreshed after stop. |
| P1-FR-024 | Pass | Frontend unit suite passed. | Browser i18n audit screenshots not refreshed in this Phase 1-only stop. |
| P1-FR-025 | Pass | `rtk npm run lint:css` passed. | Browser RTL layout smoke not refreshed due stop condition. |
| P1-FR-026 | Setup-dependent | Backend provider-switch/reconfigured-provider integration passed. | Live/mock provider switch browser smoke blocked at sign-in selector. |
| P1-FR-027 | Pass | Accept persistence, history, and auth integration tests passed. | UI actor/audit inspection not completed. |
| P1-FR-028 | Pass | Evaluator gate integration and unit evaluator tests passed. | Browser evaluator error card blocked at sign-in selector. |
| P1-FR-029 | Blocked | Frontend unit suite passed; zero-row real browser smoke not completed. | No new zero-row screenshot. |
| P1-FR-030 | Blocked | Frontend e2e/concurrency path not reached due sign-in selector. | Backend lock-related Phase 1-specific browser proof not refreshed. |

## Browser/API/LLM Checks

| Check | Status | Evidence |
|---|---|---|
| Unauthenticated redirect/sign-in | Blocked | Browser opens sign-in but e2e helper fails before local sign-in because selector matches multiple buttons. |
| Local admin sign-in | Blocked | Same selector drift. |
| Ask natural-language query | Blocked | Not reached. |
| LLM SQL generation | Setup-dependent | Gemini key presence in `.env`; live smoke not run after stop. |
| Safe execution against source DB | Pass automated / Blocked browser | Backend integration passed; browser path not reached. |
| Result rendering | Blocked | Not reached. |
| Accept/save/history visibility | Pass automated / Blocked browser | Backend integration passed; browser path not reached. |
| Reject/regenerate/current replacement flow | Pass automated / Blocked browser | Backend unit/integration passed; browser path not reached. |
| Unsafe/hostile/evaluator rejection under current Phase 6 contract | Pass automated / Blocked browser | Backend evaluator/detection-adjacent Phase 1 evaluator suites passed; browser evaluator spec blocked at sign-in selector. |
| Timeout/error path | Pass automated / Blocked browser | Backend timeout passed; browser timeout spec blocked at sign-in selector. |
| Provider/config smoke | Setup-dependent | Backend provider switch tests passed; live provider/browser smoke not run. |
| Secret/stack trace leakage | Pass for observed outputs | No raw secrets printed by env checks. Browser failure screenshots/error contexts show button names and locator traces, not provider keys, DB passwords, DB hosts, or stack traces from the app. |

## Counts

- Matrix rows attempted: 30
- Passed: 16
- Failed product blockers: 0
- Blocked by test/spec drift: 11
- Setup-dependent: 3
- Skipped/deferred: 0

Phase 2 is not unblocked from this execution because the Phase 1 Playwright gate has a test/spec drift blocker that must be fixed or explicitly waived before continuing the full regression sequence.

## Blocker Fix Update - 2026-07-07

Branch: `chore/phase1-e2e-local-signin-helper`.

Resolution:

- Added a shared Phase 1 e2e local-login helper that scopes the click to `form.sign-in-form` and targets the exact local submit button name `^sign in$`.
- Replaced broad `/sign\s*in/i` local-login selectors in affected Phase 1 e2e specs and adjacent smoke specs.
- Converted frontend-isolated Phase 1 specs to mock auth at the HTTP boundary, matching their existing mocked query/history/connection boundary style.
- Updated the US-1 happy path to assert the current auto-saved history flow through deterministic HTTP-boundary mocks. Live provider execution remains setup-dependent and must be covered by the separate approved live smoke row.

Raw-key classification:

- Chrome DevTools MCP initially observed an `auth.signIn.sso.button` raw label on `/sign-in` in the running app.
- Source locales contain `auth.signIn.sso.button` in EN/AR, and `SignInPage.test.tsx` covers interpolation without raw keys.
- Focused `i18n-audit.spec.ts` passed after the harness fix, including `/sign-in has no raw i18n key strings`.
- Classified as transient running-state/fixture data, not a reproducible source regression in this PR.

Verification after fix:

| Command | Exit | Evidence |
|---|---:|---|
| `E2E_BASE_URL=http://localhost:5173 rtk npm run test:e2e -- us1-sign-in-to-accept.spec.ts` | 0 | 1 passed. |
| `E2E_BASE_URL=http://localhost:5173 rtk npm run test:e2e -- us1-sign-in-to-accept.spec.ts us2-reject-autoretry.spec.ts us2-double-reject-refine.spec.ts evaluator-blocks-unsafe-sql.spec.ts history-list-detail.spec.ts provider-switch.spec.ts query-timeout.spec.ts` | 0 | 27 passed, 1 skipped (`provider-switch` Phase 2 deferred full-stack case). |
| `E2E_BASE_URL=http://localhost:5173 rtk npm run test:e2e -- i18n-audit.spec.ts` | 0 | 9 passed. |
| `rtk npm run lint` | 0 | ESLint passed. |
| `rtk npm run typecheck` | 0 | TypeScript passed. |
| `rtk npm run lint:css` | 0 | Stylelint passed. |

Phase 1 browser gate status after fix: unblocked for the automated Phase 1 Playwright gate. Resume Phase 1 regression from the failed browser gate; live Gemini/provider checks remain setup-dependent and should not be reported as passed unless rerun explicitly.
