# Phase 2 Premium UI / RTL Regression Report

Run date: 2026-07-04
Scope: Chunk 2 only - Phase 2 premium UI / RTL / sessions

Branch tested: `fix/phase2-playwright-e2e-config`
Base HEAD SHA tested: `2ee4bb51c1ff7309b167e0322feda46488a02464`

## Summary

PR #187 is merged and the Phase 2 backend preconditions are clean:
acceptance/integration/contract `35 passed`; backend unit `40 passed`.

The Phase 2 targeted frontend e2e gate blocker is fixed in the Playwright test
harness. The original command was reproduced before the fix:

`cd frontend && rtk npm run test:e2e -- rtl-snapshots.spec.ts i18n-audit.spec.ts`

It failed before tests ran with:

`Error: Process from config.webServer was not able to start. Exit code: 1`

Root cause: `frontend/playwright.config.ts` waited for
`http://localhost:3000`, but the `webServer.command` did not force Vite to
serve port 3000. The full-regression real-app mode also needs to target the
already-running Docker frontend at `http://localhost:5173` without starting a
second Vite server. After the config fix, browser execution exposed stale
i18n-audit auth mocks: the tests submitted sign-in credentials but did not mock
the current `/api/v1/auth/sign-in` and `/api/v1/auth/me` cookie-session flow, so
AuthGuard stayed on `/sign-in`.

Fixes made:

- Playwright now derives one `baseURL` from `E2E_BASE_URL` or
  `http://localhost:3000`.
- Default local Playwright mode starts Vite with `--port 3000` and waits on the
  same URL.
- External real-app mode skips `webServer` when `E2E_BASE_URL` is set.
- The i18n audit e2e helper uses sanitized network-boundary auth mocks for the
  current local-login endpoints.

Both required e2e modes now pass. The Phase 2 browser/LLM real-use smoke was
not run by request. Phases 3-6 and T-905 were not started.

## Regression Task Matrix

| Task | Status | Evidence |
|---|---|---|
| New Chat creates a session, focuses prompt input, and stores preview text. | Blocked | Browser smoke was intentionally not run in this harness-fix scope. |
| Sidebar switches sessions, groups by Today / Previous 7 Days / Older, and supports delete with a 5-second undo window. | Blocked | Browser smoke was intentionally not run in this harness-fix scope. |
| Follow-up questions include the last N completed attempts according to admin context cap. | Blocked | Live follow-up/browser smoke was intentionally not run in this harness-fix scope. |
| Response card renders highlighted SQL, result table, copy/regenerate actions, thumbs feedback, implicit feedback, and saved state. | Blocked | Browser smoke was intentionally not run in this harness-fix scope. |
| Admin settings can read/update LLM context cap in range 0-10. | Blocked | Browser settings smoke was intentionally not run in this harness-fix scope. |
| Arabic locale sets `dir="rtl"` and mirrors sidebar, bubbles, prompt input, forms, icons, and response chrome while SQL code remains LTR. | Pass | Targeted e2e gate passed in default local mode and external `E2E_BASE_URL=http://localhost:5173` mode. See `logs/phase2-frontend-e2e-rtl-i18n-local.log` and `logs/phase2-frontend-e2e-rtl-i18n-external.log`. |
| LLM wire-format contract tests cover happy path, 429, 5xx, malformed response, and oversized schema context. | Pass | Backend precondition from PR #187: contract coverage included in `35 passed`. |
| Lifecycle invariant framework detects lock, feedback, and session-touch leaks. | Pass | Backend precondition from PR #187: lifecycle/session/feedback coverage included in backend gates. |

Task counts after e2e harness fix: Pass 3, Fail 0, Skipped 0, Blocked 5.

## Commands Run

| Command | Exit | Notes |
|---|---:|---|
| `rtk git checkout -b fix/phase2-playwright-e2e-config` | 0 | Created fix branch before harness edits. |
| `rtk git rev-parse HEAD` | 0 | Base: `2ee4bb51c1ff7309b167e0322feda46488a02464`. |
| `cd frontend && rtk npm run test:e2e -- rtl-snapshots.spec.ts i18n-audit.spec.ts` | 1 | Reproduced original pre-fix startup failure. See `logs/phase2-frontend-e2e-rtl-i18n-repro.log`. |
| `cd frontend && rtk npm run test:e2e -- rtl-snapshots.spec.ts i18n-audit.spec.ts` | 0 | Default local Playwright mode passed: 11 passed. See `logs/phase2-frontend-e2e-rtl-i18n-local.log`. |
| `cd frontend && E2E_BASE_URL=http://localhost:5173 rtk npm run test:e2e -- rtl-snapshots.spec.ts i18n-audit.spec.ts` | 0 | External real-app frontend mode passed: 11 passed. See `logs/phase2-frontend-e2e-rtl-i18n-external.log`. |
| `cd frontend && rtk npm test -- --run` | 0 | 63 test files passed; 755 tests passed. See `logs/phase2-frontend-vitest-after-e2e-fix.log`. |
| `cd frontend && rtk npm run lint` | 0 | ESLint passed. See `logs/phase2-frontend-lint-after-e2e-fix.log`. |
| `cd frontend && rtk npm run typecheck` | 0 | TypeScript no-emit check passed. See `logs/phase2-frontend-typecheck-after-e2e-fix.log`. |
| `cd frontend && rtk npm run build` | 0 | Production build passed; Vite emitted the existing large chunk warning. See `logs/phase2-frontend-build-after-e2e-fix.log`. |
| `cd frontend && rtk npm run lint:css` | 0 | Stylelint passed. See `logs/phase2-frontend-lint-css-after-e2e-fix.log`. |

## Browser Flows

| Flow | Status | Evidence |
|---|---|---|
| Open frontend and sign in through UI. | Blocked | Not run by request during this harness-fix task. |
| Create a new chat/session and submit a benign question. | Blocked | Not run by request during this harness-fix task. |
| Verify response card renders generated SQL, result table, copy/regenerate/reject/accept controls. | Blocked | Not run by request during this harness-fix task. |
| Create a second session and verify sidebar/session switching keeps conversation state isolated. | Blocked | Not run by request during this harness-fix task. |
| Verify sidebar grouping is visible enough to identify current/recent sessions. | Blocked | Not run by request during this harness-fix task. |
| Delete a session and use undo within the toast window. | Blocked | Not run by request during this harness-fix task. |
| Submit a follow-up question and verify prior context behavior is functional. | Blocked | Not run by request during this harness-fix task. |
| Use feedback controls if present. | Blocked | Not run by request during this harness-fix task. |
| Visit admin settings and verify LLM context cap read/update behavior if exposed. | Blocked | Not run by request during this harness-fix task. |
| Switch to Arabic locale and verify RTL mirroring while SQL remains LTR. | Blocked | Not run by request during this harness-fix task. |

## Real LLM Result

Not run by request. The live Gemini follow-up conversation smoke can resume
after this harness fix merges. Real provider secrets were not printed or stored.

## Evidence Files

- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-2-premium-ui-rtl-report.md`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-2-browser-smoke-evidence.json`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/phase2-frontend-e2e-rtl-i18n-repro.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/phase2-frontend-e2e-rtl-i18n-local.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/phase2-frontend-e2e-rtl-i18n-external.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/phase2-frontend-vitest-after-e2e-fix.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/phase2-frontend-lint-after-e2e-fix.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/phase2-frontend-typecheck-after-e2e-fix.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/phase2-frontend-build-after-e2e-fix.log`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/logs/phase2-frontend-lint-css-after-e2e-fix.log`

No Phase 2 browser-smoke screenshots were captured because real-use browser
validation did not run. No Playwright trace zip was committed or added as
evidence.

## Security and Privacy Notes

No secrets, cookies, passwords, full auth payloads, raw hostile prompts, or raw
sensitive request bodies were stored in evidence. E2E auth uses sanitized mock
user data and route-level HTTP mocks.

Chunk 2 browser/LLM validation can resume after this harness fix merges. Chunk
3 remains blocked until the remaining Phase 2 browser/LLM validation completes.
