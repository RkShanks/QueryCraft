# CHUNK-18 / IS-GAP-041 + IS-GAP-027 + IS-GAP-028 — workspace result and recovery behavior

Status: implementation and non-browser verification passed on product commit `bbc9ef5bc6bb0b8bc2627fb36a8cbace636e6aff`; required Chromium and live-network FastAPI proof are blocked because the managed sandbox rejects localhost listeners with `listen EPERM`. The focused branch is pushed, but pull-request creation was rejected by the external-action reviewer after the account approval quota was exhausted. The three gaps remain Pending and merge is prohibited until those gates pass.

Starting synchronized main was `f29cec51cc673f2ae84ad0d60c3c62246b939c45`, the squash merge of [#315](https://github.com/RkShanks/QueryCraft/pull/315). No backend source, endpoint, canonical OpenAPI document or generated API contract changed.

The machine-readable [JSON evidence](chunk-18-workspace-recovery.json) records the behavior matrix, TDD commits, unit/API gates, blocked browser/live proof, protected baseline and remaining dispatch gate.

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
| REFACTOR recovery hardening, build correction and classified browser matrix | `bbc9ef5bc6bb0b8bc2627fb36a8cbace636e6aff` |

## Automated test evidence

The final focused run passed 415 tests across ResultTable pagination, the full ConnectionErrorCard kind/handler matrix, Workspace recovery, and locale coverage. Earlier focused runs explicitly covered the 101-row traversal/reset/clamp/table semantics, delete rollback/commit/uncertain/retry/duplicate/stale cases, regenerate restoration/retry/terminal/duplicate/stale cases, connection permission/context combinations, and EN/AR behavior.

The complete frontend suite passed 1,140 tests across 78 files. The production build, TypeScript no-emit check, ESLint, CSS lint, generated-client parity check and static browser-harness guard passed. The harness classifies 29 Playwright specs and discovers all three CHUNK-18 Chromium cases.

Relevant compatibility tests exercised the real FastAPI application through its ASGI integration boundary: 80 backend tests passed in 7.72 seconds across history, regenerate, query, accept-only persistence, retry quota and audit logging. This does not substitute for the requested live network flow.

## Browser and live-network hold

The classified Chromium matrix is ready to assert:

- 1440px EN: 101 unique values over three pages, at most 50 rendered rows, masking and viewport bounds;
- 768px EN: result preservation, regenerate failure/retry, delete rollback/retry, raw-canary absence and viewport bounds;
- 375px AR/RTL: semantic zero-row success, no unnecessary pagination, immutable-context timeout retry, localization and viewport bounds.

`playwright test` could not start Vite, and a direct Vite start failed with `listen EPERM`; the managed sandbox denied permission to bind localhost. No Chromium test executed, no screenshot is presented as proof, and no live network FastAPI flow was claimed. The Playwright list gate did pass with three discovered tests.

## Quality guards

Test Guard review retained behavior-level assertions, deterministic route-boundary fault injection, unique traversal checks, duplicate/stale settlement cases and temporary Playwright output paths. Clean Code Guard review kept recovery state typed, isolated snapshot/reconciliation helpers, sanitized error classification and required sequential reconciliation. Vercel React guidance led to memoized derived history/turn collections and stable callbacks without adding client fetch waterfalls beyond the required ambiguous-delete lookup. Docs Guard reconciled the behavior, commands, counts, commits and blocked claims here against source and test output.

## Cleanup and next gate

The protected baseline remains exactly 14 modified tracked PNGs, seven historical untracked screenshots and the pre-existing trace archives; none was staged, regenerated, reverted or deleted. The rejected browser start left `/tmp/querycraft-chunk18-browser` (8 KiB), `/tmp/querycraft-chunk18-report` (516 KiB) and ignored `frontend/dist` (12 MiB). Their explicit cleanup was also rejected by the managed approval service, so this evidence does not claim cleanup completion.

CHUNK-19 is blocked. To unblock it: run the three Chromium tests and one live valid FastAPI flow, remove the temporary outputs, create the focused PR, obtain passing `backend-test` and `frontend-test`, squash-merge, delete the branch and synchronize main.
