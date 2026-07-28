# Phase 6A Quotas Current-Head Regression

Run date: 2026-07-28

Scope: quotas only; detection, audit hardening beyond quota-event verification, Phase 6 final closure, T-905, freeze work, and the implementation-surface gap audit were not started.

Starting synchronized main HEAD: `3ff9afad8511dac5070cd43f3873409eb65630f3`

Tested product HEAD: `4aff12b76686bd2788a7d1c6f12852e112e2c794`

Runtime: isolated platform database, disposable Redis instances/databases, deterministic provider/adapter spies, real backend APIs, headless Chromium, and Chrome DevTools MCP.

## Result

| Status | Count |
|---|---:|
| Pass | 9 |
| Fail | 0 |
| Partial | 0 |
| Setup-dependent | 0 |
| Not run | 0 |
| Deferred | 0 |

## Requirement Matrix

| ID | Status | Automated Evidence | Browser/API Evidence | Notes |
|---|---|---|---|---|
| P6-FR-147 | Pass | Quota repository, admin API, validation, permission, cache-refresh, and audit suites passed within the full backend gate. | A real administrator listed and updated quotas, received 422 for malformed JSON, 400 for invalid values and malformed identifiers, 404 for a missing role, and 204 when resetting to uncapped. A quota-only administrator loaded the quota API successfully. | Nullable limits remained uncapped. Configuration audit context contained action/change metadata only; limit and counter values were absent. |
| P6-FR-148 | Pass | The isolated real-Redis suite passed 10/10, including concurrent saturation, per-dimension behavior, uncapped behavior, malformed results, and recovery. Unit and cross-dialect suites also passed. | Real quota status responses exposed only the public role-level status contract. No internal cache identifier or stored counter value was retained in evidence. | Atomic denials did not advance usage beyond the configured ceiling; user, dimension, and UTC-day isolation passed. |
| P6-FR-149 | Pass | Admin Quotas regression, component, and locale suites passed 316/316; full Vitest passed 65 files and 785 tests. ESLint, typecheck, build, and CSS lint passed. | Real administrator edit/reset flows succeeded. The quota-only page made zero role-management and zero SSO-mapping requests. Chrome DevTools verified EN/LTR and AR/RTL desktop pages. Chromium checks at 375px EN and 768px AR found no page overflow, clipped cards/actions, physical-direction classes, or forbidden requests. | Loading, empty, success, 403, unavailable, validation, and uncapped states are localized. No fresh screenshot was required or staged. |
| P6-FR-150 | Pass | The focused cache suite and isolated real-Redis suite verified a real 60-second cache, hit-without-repository-read, expiry refresh, immediate upsert/delete refresh, minimal serialization, stale-write protection, and concurrent read/invalidation boundaries. | Real administrator upsert and reset took effect immediately in the quota list/status flow. | Cache/Redis failures remained fail closed. No unrelated role or security data was serialized. |
| P6-FR-151 | Pass | Deterministic query, execution, export, fail-closed, Phase 6 sanitization, and cross-dialect tests verified ordering, exactly-once under-limit calls, and no relevant downstream call after 429/503. The focused post-fix selection passed 49/49. | A real benign query with a zero query quota returned 429 before chat, attempt, or LLM work. The temporary source connection was deleted and the quota was restored immediately after the check. | Query denial precedes LLM/chat/attempt creation; execution denial precedes the adapter; export denial precedes export generation/download. |
| P6-FR-152 | Pass | Quota error sanitization, Phase 6 sanitization, cross-dialect response, and localized banner suites passed. | The real 429 body contained only `error`, `message_key`, and contract-allowed `reset_at`; the message key was `error.quota_exceeded`. EN and AR localized UI coverage passed. | No usage value, configured limit, policy reference, role internals, SQL, provider detail, host, or stack trace appeared. |
| P6-FR-153 | Pass | The disposable-container outage/timeout/recovery test passed 1/1 without application restart. Isolated real-Redis tests covered malformed cache data, malformed script state, and recovery; service and endpoint suites covered sanitized fail-closed 503 behavior and downstream spies. | Recovery was exercised against disposable state only; normal development Redis and platform data were not disrupted. | Redis unavailable, timeout, malformed response, and script-error paths fail closed without LLM, source execution, export, chat, history, or attempt work. |
| P6-FR-154 | Pass | Real-Redis coverage passed for the final fractional microsecond before UTC midnight, bounded positive TTL, atomic missing-expiry repair, preservation of valid expiry, new-day isolation, and concurrent rollover. Unit reset tests also passed. | No browser check was required. | The earlier zero-floor and missing-expiry deferrals are closed; no valid expiry was extended incorrectly. |
| P6-FR-155 | Pass | Quota audit tests verify durable query/execution denial events and sanitized contexts. The focused audit/enforcement selection passed 49/49 and the full backend gate passed. | Current-head audit API searches returned configuration-change entries and two representative quota-denial entries. Denial context contained only `dimension` and `reset_at`; configuration context omitted limit/counter data. | A reproduced rollback defect was fixed so denial events persist before 429. Searches and evidence contain no sensitive values. |

## Regression Fixes

- [PR #239](https://github.com/RkShanks/QueryCraft/pull/239) — implemented the required 60-second Redis configuration cache; prevented atomic counter overshoot; repaired missing expiry atomically; preserved valid expiry; used positive ceiling precision at UTC midnight; validated script responses; retained fail-closed behavior.
- [PR #240](https://github.com/RkShanks/QueryCraft/pull/240) — added localized Admin Quotas loading/empty/403/unavailable/validation states, strict safe-integer input, quota-only request isolation, and responsive EN/AR cards for narrow layouts.
- [PR #241](https://github.com/RkShanks/QueryCraft/pull/241) — made sanitized query/execution quota-denial audit events durable without committing pending request side effects.

Each fix PR passed both required CI jobs and was squash-merged with its branch deleted.

## Automated Validation

| Gate | Result |
|---|---|
| Focused backend quota service/repository/admin/enforcement/reset/audit/fail-closed/cross-dialect/execution/export/sanitization selection for the cache and TTL fix | 145 passed |
| Focused audit durability/enforcement/fail-closed/sanitization/cross-dialect/admin/execution selection | 49 passed |
| Isolated real-Redis cache/concurrency/TTL/boundary/error suite | 10 passed |
| Disposable Redis outage/timeout/recovery suite | 1 passed |
| Full backend pytest after the final production fix | 2,554 passed; 15 skipped; 6 pre-existing warnings; 35 subtests passed |
| Ruff check | Pass |
| Ruff format check | Pass; 395 files already formatted |
| Focused Admin Quotas and locale suites | 316 passed |
| Full Vitest | 65 files passed; 785 tests passed |
| ESLint | Pass |
| TypeScript typecheck | Pass |
| Production build | Pass; existing chunk-size warning only |
| CSS lint | Pass |
| `rtk git diff --check` | Pass |
| Fix PR CI | `backend-test` and `frontend-test` passed for PRs #239, #240, and #241 |

The full affected gate commands included:

| Command | Result |
|---|---|
| `cd backend && rtk uv run pytest -q` | 2,554 passed; 15 skipped; 6 pre-existing warnings; 35 subtests passed |
| `cd backend && rtk uv run ruff check src tests` | Pass |
| `cd backend && rtk uv run ruff format --check src tests` | Pass; 395 files already formatted |
| `cd frontend && rtk npm test -- --run` | 65 files passed; 785 tests passed |
| `cd frontend && rtk npm run lint` | Pass |
| `cd frontend && rtk npm run typecheck` | Pass |
| `cd frontend && rtk npm run build` | Pass; existing chunk-size warning only |
| `cd frontend && rtk npm run lint:css` | Pass |

## Browser and API Verification

- Chrome DevTools MCP verified the real quota-only page on tested product HEAD in English/LTR and Arabic/RTL at desktop width. Both quota configuration and status tables were visible, no raw translation key appeared, and no physical-direction utility class was present.
- Headless Chromium verified 375px English and 768px Arabic layouts. Both viewports had complete configuration/status cards, visible actions, no document overflow, and zero role-management or SSO-mapping requests.
- A real administrator performed quota list, upsert, validation, missing-role, malformed-identifier, and reset/delete flows. Mutations occurred exactly once and temporary state was restored.
- A real zero-quota query returned a localized, sanitized 429. Representative configuration-change and denial entries were then found through the current audit search API.
- Deterministic spies, not provider availability, controlled quota correctness. No live LLM was required.

## Isolation, Leakage, and Cleanup

- Outage, timeout, cache, concurrency, and boundary-time checks used disposable Redis state separate from normal development Redis.
- Browser/API checks used an isolated platform database. The source connection used to reach the quota boundary was temporary and deleted immediately.
- Evidence contains no credentials, cookies, session material, internal cache identifiers, stored counter values, sensitive payloads, or raw audit records.
- Pre-existing dirty Phase 5 PNGs and historical Phase 1/2 screenshots/traces were not staged, edited, deleted, or reverted.
- Temporary screenshots were kept outside the repository and are not part of the evidence PR.

Phase 6A is complete at 9/9 Pass. Phase 6B is unblocked but was not started.
