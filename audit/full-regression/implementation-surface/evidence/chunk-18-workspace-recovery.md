# CHUNK-18 / IS-GAP-041 + IS-GAP-027 + IS-GAP-028 — workspace result and recovery behavior

Status: resolved on tested branch `phase-6/wave-19.18-workspace-recovery` in [#316](https://github.com/RkShanks/QueryCraft/pull/316). Product behavior is at `bbc9ef5bc6bb0b8bc2627fb36a8cbace636e6aff`; the final local verification head is `85145026c15c1e8fca47706d5fa4d31abc645f7f`. Responsive Chromium, a real-network FastAPI flow, focused/full gates and cleanup passed. PR CI and squash merge remain the only CHUNK-19 dispatch gates.

Starting synchronized main was `f29cec51cc673f2ae84ad0d60c3c62246b939c45`, the squash merge of [#315](https://github.com/RkShanks/QueryCraft/pull/315). No backend source, endpoint, canonical OpenAPI document, generated API contract or runtime validation rule changed.

The machine-readable [JSON evidence](chunk-18-workspace-recovery.json) records the same behavior, commits, browser/API results, cleanup and ledger counts.

## Behavior matrix

| Surface | Verified behavior |
| --- | --- |
| Zero-row result | A localized EN/AR “No results found” cell renders inside a labelled semantic table. The successful response card and its valid actions remain available. |
| Large result | Already-returned rows render in deterministic 50-row client pages. Across 101 synthetic rows, every value appears exactly once and no page renders more than 50 body rows. This bounds DOM rendering only; it does not claim to bound the response, network transfer or client memory. |
| Pagination state | Localized Lucide previous/next controls have accessible names and a polite status. A changed attempt/row set resets to page one; a shortened current set clamps to its final valid page. |
| Table preservation | Column headers retain `scope="col"`, masked-column badges remain visible on every page, data direction remains automatic with LTR column names, and horizontal scrolling remains available. |
| Definite delete failure | The exact turn/deletion snapshot is restored and a localized Retry is exposed; backend details are never rendered. |
| Lost/ambiguous delete response | Authoritative history lookup treats `not_found` as committed deletion, restores a present record, and restores with an explicit uncertain state if reconciliation fails. A direct structured `not_found` is also treated as committed. |
| Delete concurrency | Per-record in-flight identity suppresses duplicate requests. Active-session and session-deletion versions suppress late settlements after switch/delete. |
| Regenerate pending/failure | The previous result card remains visible while pending. Recoverable failure preserves the exact SQL, result, accepted-query ID and original active attempt ID, then offers localized Retry against that original attempt. |
| Regenerate terminal failure | `attempt_invalid` and `attempt_expired` refetch authoritative session state and render a terminal notice without an endless invalid Retry. |
| Regenerate concurrency | Per-attempt in-flight identity and disabled actions suppress duplicates; session/deletion continuity suppresses stale mutation. Existing regenerate service behavior continues to own CHUNK-05 quota and sanitized audit accounting. |
| Connection management errors | `noConnections`, `disabled`, `unhealthy` and `noSchema` navigate to `/admin/connections` only with `admin.connections.manage`; other users receive localized non-interactive guidance. No schema-refresh or test action was invented. |
| Query connection errors | `queryExecutionFailed` and `timeout` retry only when the original question, source session and immutable CHUNK-01 connection ID are present. Otherwise localized guidance renders without a button. Duplicate/stale retry responses are suppressed. |
| Accessibility/localization | Alerts are labelled/described, pending states use live regions, buttons expose localized accessible names and visible focus, and EN/AR/RTL component assertions pass. |

## TDD commits

| Stage | Commit |
| --- | --- |
| RED bounded/zero result behavior | `cfa58f726c4968a74b991b37ab303d27edd4d279` |
| GREEN bounded/zero result behavior | `5ddbb279230bd8a0f3149417ffdf5477bbcf13b0` |
| RED delete/regenerate recovery | `65d67bdfc4fcac9260a2ad31c732135b2d27cf44` |
| GREEN delete/regenerate recovery | `cc5523976c161eadb243d836809efcc23a91f7a3` |
| RED connection-card handler matrix | `b4fdec231edc0d6bcf01cf0fc8abda4c1f4c4f33` |
| RED workspace connection wiring | `5f27c205618955ac3c86f8ddf19b9e5f9367aa46` |
| GREEN safe connection actions | `b539d3257aaa6cfcabb2beebd410ec4540e5fd52` |
| REFACTOR recovery hardening and browser matrix | `bbc9ef5bc6bb0b8bc2627fb36a8cbace636e6aff` |
| RED shared Playwright connection contract | `73ab8f386020e3dbc068910b1da0b8b34cfb7e2b` |
| GREEN valid typed connection fixture | `8ed15ea719e3cd05344a77959213721ca115e12c` |
| Browser/live verification tests | `4372bc5c323507dfebea96ea3bb6be5ff345bcc7`, `f5bee151a75ddebf00fafa8d04dbb4b1920177a0`, `85145026c15c1e8fca47706d5fa4d31abc645f7f` |

The new RED command was `cd frontend && npx vitest run src/api/responseContracts.test.ts --reporter=verbose`: the new shared-fixture assertion failed while the other 21 tests passed because `conn-1` violated the generated UUID schema. The same command at GREEN passed all 22 tests after the typed fixture moved to deterministic UUID `550e8400-e29b-41d4-a716-446655440010`. Runtime validation and production fallback behavior were unchanged.

## Browser and live-network evidence

The exact requested command passed:

`cd frontend && PLAYWRIGHT_HTML_OUTPUT_DIR=/tmp/querycraft-chunk18-report PLAYWRIGHT_OUTPUT_DIR=/tmp/querycraft-chunk18-browser rtk npm run test:e2e -- chunk_18_workspace_recovery.spec.ts`

- 1440px EN: 101 unique values traversed across three pages, no more than 50 rendered body rows, masking/table semantics and viewport bounds — passed in 1.6s.
- 768px EN: prior result remained visible, regenerate failure/retry recovered, delete rollback/retry recovered, and the raw canary stayed out of the UI — passed in 2.2s.
- 375px AR/RTL: semantic zero-row success, no unnecessary pagination, localized timeout retry using immutable context and viewport bounds — passed in 1.5s.
- Result: 3 passed in 7.0s. The dev proxy logged connection refusal for an intentionally unmocked post-assertion session-detail refresh; it did not reach the UI or affect any CHUNK-18 assertion. No listener restriction remained.

Every spec importing `mockConnections` was rerun in one isolated Chromium worker. Result: 32 passed, 1 classified skip and 34 pre-existing failures in older specs that do not mock newly required query-limit/session/admin dependencies (plus one older ambiguous Retry locator). All three CHUNK-18 cases passed in that sweep. A diagnostic run while the real API was intentionally active was discarded because mocked identities received correct 401s from unrelated unmocked calls; it was not used as product evidence.

The final live command passed one test in 5.4s:

`cd frontend && CHUNK18_LIVE_USERNAME=<disposable> CHUNK18_LIVE_PASSWORD=<disposable> CHUNK18_LIVE_SOURCE_PASSWORD=<disposable> PLAYWRIGHT_HTML_OUTPUT_DIR=/tmp/querycraft-chunk18-live-report rtk npm run test:e2e -- chunk_18_live_workspace.spec.ts`

The isolated runtime used real FastAPI HTTP, PostgreSQL platform/source containers, Redis, migrations and the deterministic provider. Chromium signed in through the real API, tested and introspected the disposable healthy source, applied an Admin connection policy through the real API, submitted “Return one deterministic row”, received `SELECT 1 AS id`, and rendered header `id` plus cell `1` through `ResultTable`. No `page.route` mocking was used. The API response, rendered body, console and page-error streams were checked for the disposable credentials, traceback/stack text and password assignments; none appeared. No paid LLM call was made.

## Automated gates

- Focused frontend: 7 files, 456 tests passed in 3.38s, including response contracts, both ResultTables, ConnectionErrorCard, Workspace recovery and locale/a11y coverage.
- Full frontend: 78 files, 1,141 tests passed in 19.22s.
- Backend compatibility: 80 tests passed in 9.06s across history, regenerate, query, accept-only persistence, retry quota and query audit logging.
- `npm run typecheck`, `npm run lint`, `npm run lint:css`, `npm run build`, `npm run gen:api:check`, `npm run test:harness` and `git diff --check` passed. The harness classifies 30 Playwright specs.
- The first final build correctly caught a test-only browser/API response-type mismatch; `85145026c15c1e8fca47706d5fa4d31abc645f7f` narrowed the helper to the shared interface and the repeated build passed.

## Quality guards and cleanup

Test Guard retained public-contract validation, behavior-level recovery assertions, unique traversal, duplicate/stale settlement cases, an unmocked live flow and classified skip metadata. Clean Code Guard found no new production-code concern; the continuation changed only typed fixtures and verification code. Vercel React guidance required no production adjustment because the existing memoized pagination/recovery implementation was unchanged. Docs Guard reconciled commands, counts, commits, contract statements and the consumer-sweep limitation against source and output.

The disposable Compose project, containers, network and volumes were removed. `/tmp/querycraft-chunk18-browser`, `/tmp/querycraft-chunk18-report`, all additional CHUNK-18 reports/JSON, `frontend/test-results`, `frontend/playwright-report` and ignored `frontend/dist` were removed. The protected baseline remains exactly 14 modified tracked PNGs, seven historical untracked screenshots and existing trace archives; none was staged, regenerated, restored or deleted.

The three gaps are Resolved on tested branch in [#316](https://github.com/RkShanks/QueryCraft/pull/316). Ledger totals are now 23 Resolved, 4 Resolved on tested branch, 17 Pending and 3 Needs Decision out of 47. CHUNK-19 becomes unblocked only after the focused PR has passing `backend-test` and `frontend-test`, is squash-merged, its branch is deleted and local main is synchronized.
