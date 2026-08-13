# CHUNK-15 / IS-GAP-024, IS-GAP-026, IS-GAP-035 — role policy editor safety and preview

Status: implementation, local verification, and authoritative GitHub backend/frontend CI passed on `phase-6/wave-19.15-role-policy-editor` in [PR #313](https://github.com/RkShanks/QueryCraft/pull/313); squash merge is pending. Tested product commit: `750c21fa4f70bf1f1b106396852b9be846b931dc`. Starting main: `0cc010a59b128423169bd252aa63df2acfeb2130`, the squash merge of [PR #312](https://github.com/RkShanks/QueryCraft/pull/312).

## Outcome

CHUNK-15 closes the three assigned implementation gaps on the tested branch:

| Gap | Result | Proof |
| --- | --- | --- |
| `IS-GAP-024` | Resolved on tested branch | The role editor tests the current unsaved draft through the generated client and renders localized, accessible empty/loading/allowed/blocked/invalid/retry/permission-denied/stale states. |
| `IS-GAP-026` | Resolved on tested branch | Existing-role Save remains disabled until matching full detail loads; failure, retry, role switch, late settlement and background refetch cannot serialize absent policies or overwrite dirty edits. |
| `IS-GAP-035` | Resolved on tested branch | The frontend raw-string security parser was removed. A shared 21-case corpus makes the backend parser authoritative while the UI retains structural validation only. |

No work from CHUNK-16, T-905, freeze, or unrelated remediation was started.

## API contract

The bounded `POST /api/v1/admin/roles/test-policy` operation has stable operation ID `testDraftRolePolicy`. Its generated `DraftPolicyTestRequest` carries the question, optional sample SQL and one complete connection policy. It returns the existing `PolicyTestResponse`, requires exactly `admin.roles.manage`, and declares `200/400/401/403/422/500`.

Current source inspection independently derives **64 runtime operations across 48 paths**. Canonical OpenAPI and the generated SDK also contain 64 operations. This is the expected `63 → 64` change from CHUNK-14. The existing persisted-role diagnostic endpoint remains available.

Both endpoints call the same schema/policy/evaluator helpers. The draft path reads the supplied policy, performs no role/policy persistence, calls no LLM and executes no source query. Invalid filters return only the localized constant contract; parser, schema, identifier, driver and stack details are not returned or rendered.

## TDD history

| Stage | Commit |
| --- | --- |
| RED backend draft contract, corpus, permission, sanitization and zero-execution proof | `3b613645355a958802cddcc6a33dd67a99de60ad` |
| GREEN shared backend evaluation, draft route, canonical OpenAPI and generated client | `0c4d3a67bf755da44a40868e73b7c346e1098198` |
| RED delayed/failed/stale role-detail hydration races | `31568725137ea415c6622ea1f383d7eca8fef4a3` |
| GREEN authoritative hydration and safe Save gating | `e8d68043ee79b1fd5c614ef9fa0727341f58027a` |
| RED unsaved preview states, deduplication and frontend corpus behavior | `cfee37e367cb819f68ddaf11d287e6871e4da92a` |
| GREEN accessible preview UI and backend-authoritative grammar | `b354b89a15b5dae74f4e68f22a57d5fdc064c231` |
| Passing isolated Chromium regression | `750c21fa4f70bf1f1b106396852b9be846b931dc` |

A separate REFACTOR commit was not warranted; the shared evaluator and isolated preview component were introduced directly in their GREEN commits.

## Hydration and preview matrices

| Hydration case | Observed result |
| --- | --- |
| Delayed detail plus mouse, keyboard or repeated submission | Save disabled; zero update requests. |
| Failed detail | Localized retry/cancel state; Save stays disabled; zero update requests. |
| Late role-A detail after role-B selection | Role B remains authoritative. |
| Background refetch after a dirty edit | Dirty fields and loaded connection policies remain unchanged. |
| Non-policy edit | Loaded connection policies remain in the eventual update payload. |
| Cancel or role switch | Form draft and preview state are cleared. |

| Preview state | Trigger/result |
| --- | --- |
| Empty | No sample question has been entered. |
| Loading | One draft request is in flight; duplicate clicks are ignored. |
| Allowed | Current unsaved policy and optional sample SQL are allowed. |
| Blocked | Current sample SQL is rejected by the policy evaluator. |
| Invalid | Authoritative backend validation returns localized, sanitized feedback. |
| Retry | Dependency/internal failure exposes a localized retry action only. |
| Permission denied | `401/403` or the constant permission key exposes localized feedback only. |
| Stale | Any relevant question, sample SQL or policy change invalidates the completed result. |

The result lists accessible/blocked tables, accessible columns, applicable filters and masks in left-to-right technical spans. The UI explicitly says no AI model or source query is run and does not claim generated SQL or source execution.

## Shared row-filter corpus

`contracts/row-filter-validation-corpus.json` contains 21 cases: 8 valid and 13 invalid across PostgreSQL, MySQL and MSSQL grammar. It covers quoted literals containing keyword/comment text, identity placeholders, boolean expressions, comments, separators, subqueries, UNION, DML, functions, unknown schema members and malformed syntax/placeholders.

The backend runs all 21 cases. Frontend UI tests run all 8 valid cases and the 12 invalid cases whose table is structurally selectable; the unknown-table case remains a backend authority case because the UI table control permits only loaded schema tables. Backend-valid quoted literals are sent unchanged. Backend-invalid filters reach the server and render only localized constant feedback.

## Browser and real API proof

Chrome DevTools MCP was unavailable. Classification is therefore **isolated Playwright Chromium with disposable mocked HTTP state**. Four tests passed in 15.1 seconds:

| Viewport | Locale/direction | Result |
| ---: | --- | --- |
| 1440px | English/LTR | Hydration, new/edit preview, allowed/blocked/invalid/stale/empty, cancellation and no-mutation checks passed. |
| 768px | Arabic/RTL | Localized preview, logical layout, LTR SQL field and no document overflow passed. |
| 375px | English/LTR | Responsive preview and no document overflow passed. |

The browser observed zero create/update role requests before outer Save and zero query, LLM, generation or execution API requests. Canceling a policy cleared preview input/result state; canceling an edited role restored the original persisted description and non-empty policy on the next edit. There were no unexpected API requests or request failures. Browser console errors were limited to the expected resource messages for injected `422` and `500` responses and were classified explicitly.

A separate **real FastAPI ASGI check with local PostgreSQL and Redis** created a disposable connection schema and a disposable role with one persisted policy. Allowed preview returned `200`; blocked preview returned `200`; invalid filter returned the exact sanitized `422` contract. Patches that would fail on any LLM factory or source-executor call observed zero calls. Full role detail before and after the unsaved previews was identical. The disposable role and connection were deleted in `finally`.

## Gates

| Gate | Result |
| --- | --- |
| Focused backend policy/row-filter/OpenAPI/role tests | 122 passed in 3.06s |
| Backend unit foundation | 2,539 passed, 44 deselected in 68.84s; three pre-existing warnings |
| Ruff check / format check | Passed; 452 files formatted |
| Canonical OpenAPI deterministic check | Passed |
| Generated client deterministic check | Passed |
| Focused frontend | 435 passed across 7 files in 2.72s |
| Full Vitest | 1,062 passed across 74 files in 11.46s |
| ESLint / typecheck / production build / CSS lint | Passed |
| Isolated Chromium | 4 passed in 15.1s |
| `rtk git diff --check` | Passed |
| Test Guard / Clean Code Guard / Vercel React guidance / Docs Guard | Passed |
| Authoritative `backend-test` / `frontend-test` | Passed on `6cbe326b8462c8924b1a3aadd4b14c04c655b00b`, run `31738776892` |

The production build emitted only the repository's existing large-chunk warning. The full frontend suite emitted existing MSW/React `act(...)` warnings; no test failed.

## Cleanup and status accounting

Temporary Playwright reports, screenshots, videos, traces and the temporary API-smoke script were removed from `/tmp`. The real API disposable rows were deleted. The protected baseline remains exactly 14 modified tracked PNGs, seven historical untracked screenshots and two untracked trace archives; none was edited, staged, regenerated, reverted or deleted by CHUNK-15.

After marking the three assigned gaps resolved, the 47-gap ledger totals are: 20 Resolved, 23 Pending, three Needs Decision and one Resolved on tested branch. CHUNK-16 remains blocked until this PR passes authoritative backend/frontend CI and is squash-merged.
