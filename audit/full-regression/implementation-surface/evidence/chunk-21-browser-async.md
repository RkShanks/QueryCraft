# CHUNK-21 / IS-GAP-043 + IS-GAP-037 + IS-GAP-031 — browser async and runtime failures

Status: implementation and local verification passed on tested branch `phase-6/wave-19.21-browser-async`, starting from synchronized main `48f775834a9c2c1fa3f4c2ea95132c1ff287d119` (the squash merge of [#318](https://github.com/RkShanks/QueryCraft/pull/318)). The machine-readable peer is [chunk-21-browser-async.json](chunk-21-browser-async.json). No backend endpoint, response contract, or OpenAPI operation changed; runtime/canonical/generated parity remains 64 = 64 = 64.

Merge bookkeeping reconciliation carried in this branch: `CHUNK-20` / `IS-GAP-032`+`IS-GAP-038` was confirmed merged through [#318](https://github.com/RkShanks/QueryCraft/pull/318) at main `48f775834a9c2c1fa3f4c2ea95132c1ff287d119`; the JSON ledger's tested-branch rows became Resolved/merged without changing historical test evidence.

## Cancellation contract (IS-GAP-043)

One small request-scope utility (`src/api/requestScope.ts`) combines an owned `AbortController`, an optional parent signal, an optional client deadline, abort classification (`caller` / `parent` / `deadline`) and exactly-once listener/timer cleanup:

- `isAbortFailure` classifies every browser-side non-settlement (fetch abort or the typed errors); `isClientDeadlineError` isolates this client's own deadline expiry; `isRequestAbortedError` identifies intentional cancellation. Typed errors carry constant messages with no transport detail.
- Query submit/accept/reject/regenerate now run under one owned scope per operation: the scope's signal is passed into each generated SDK call; unmount aborts the in-flight request; a new deletion subscription aborts it when CHUNK-03 `beginSessionDeletion` fires for that session. Aborted responses are never consumed — no error kind, no toast, no stale result state; callers receive the typed silent-abort error and Workspace/Ask pages discard the pending turn silently.
- Browser abort suppresses frontend settlement only. Backend semantics are untouched: CHUNK-03 deletion precedence still wins (late responses during deletion keep rejecting with `session_deleted`), and query operations rely on CHUNK-04's authoritative backend deadline — **no client-side query deadline was added** (asserted by test).
- Ordinary read/admin clients may use one documented bounded network deadline (`ORDINARY_REQUEST_TIMEOUT_MS = 15_000`) through `withRequestDeadline`, wired into the four consumed queries that previously dropped the TanStack signal (fallback current-user, SSO provider discovery, admin settings, connection schema). Deadline expiry renders through the shared `ClientQueryState` as a localized recoverable timeout (`clientContract.requestTimeout`, EN/AR), distinct from intentional aborts and from sanitized backend 504s (`error.timeout`). Parent cancellations rethrow the native abort so TanStack treats them as silent cancellations.

## Route/runtime recovery (IS-GAP-037)

- A localized, sanitized `RouteErrorBoundary` wraps every protected route inside `PermissionGuard` + `AppShell`, keyed by the router location entry so deliberate retry or any navigation (including back/forward) replaces a failed boundary instance. Retry re-renders the route in place; a permission-aware "go to workspace home" action navigates to `firstPermittedRoute(user)` only when one exists. Raw stack/error text never reaches DOM, console channels owned by the app, or the accessibility tree.
- Unknown paths retain the current permission-aware redirect contract (first permitted route for authenticated users, sign-in for anonymous, access-denied when no permission resolves).
- Late work from previous routes/sessions cannot settle: owned scopes abort on unmount/deletion, TanStack signals cancel abandoned queries, and Workspace alerts plus AdminAudit toasts clear their timers on navigation/unmount exactly once.

## Lazy SQL highlighting and clipboard (IS-GAP-031)

- `SqlCodeBlock` loads the Shiki chunk lazily once per session and catches import failure locally: readable plain-text LTR SQL remains, a polite localized status announces unavailability without chunk/import details, and neither the route nor an unhandled rejection results. `ShikiHighlighter` contains its own highlighter-construction failure behind a shared caught promise, falling back to plain text.
- One `useCopyToClipboard` contract is shared by `CodeBlockActionBar` (workspace SQL) and `HistoryDetail`: unavailable API, denied and rejected writes map to distinct localized announced states (`aria-live` regions), retry works within the same bounded window, status timers are cleared on retry and unmount exactly once, focus stays on the control, and neither the copied value nor the raw error is ever logged or persisted.

## Audit export scope

`exportAuditEntries(request, signal?)` propagates the caller's signal. Each export runs under its own scope with the documented longer deadline (`AUDIT_EXPORT_TIMEOUT_MS = 60_000`): Cancel (localized action visible only while exporting), navigation/unmount and identity rotation abort the request; zero object URLs, anchors or downloads are produced before the complete Blob exists; anchor removal and `revokeObjectURL` run in a `finally` even when the click fails; canceled, client-timeout and server-failure toasts stay localized and distinct (existing quota/limit mapping unchanged). Filters, server filename handling and file-content contracts were not touched (CHUNK-22 owns them).

## TDD commits

| Stage | Commit |
| --- | --- |
| RED request lifetime | `0f065771eb4f0d2cc816c7bd2a2d4461f4bda2a5` |
| GREEN request-scope lifetime + signal propagation | `89eddf221a8c58be7b29801a9823da99b3a72fa6` |
| GREEN route boundaries + SQL fallback | `e796ff7b2ed476fd008948a21938d98e8d981060` |
| RED clipboard/export matrix | `69c855d9c972ac88e46305d63fcfde7f69534009` |
| GREEN clipboard contract + export cancellation | `8eb812d44200cc991c5f818d2976b8f926305e08` |
| Gate/lint/build corrections | `b749260cefd2faa812d1b6d61dacb5fbafa773f3` |
| Browser mocked + live proof | `b2d14e3e026b9c38971c358eb005c361f7ffbd79` |

RED evidence: the request-scope module did not exist; `useQuerySubmit` owned no signals (wire-level assertions failed on `signal.aborted`); fallback current-user/SSO/settings/schema queries never aborted on cancel; clipboard failures were console-logged silently; export had no Cancel/deadline/resource-failure path.

## Automated gates

- Full Vitest: 87 files / 1,283 tests passed (was 1,232 before this wave).
- ESLint clean; typecheck clean; production build clean (incl. test-inclusive `tsc -b`); stylelint clean.
- `gen:api:check` parity holds (64 = 64 = 64, generated tree untouched).
- Harness guard passed with 36 classified specs including both new entries.
- Backend compatibility subset: 37 unit tests across query endpoint/service/regenerate/reject-router/processing-lock passed; Ruff check/format clean; integration router subsets skip cleanly without live services (no backend change).
- `git diff --check` clean.

## Browser/live proof

Mocked Chromium matrix (`PLAYWRIGHT_OUTPUT_DIR=/tmp/opencode/chunk21-output npx playwright test chunk_21_browser_async.spec.ts`) — 6 passed in ~11 s:

1. Delayed submit aborted by navigating away mid-flight: zero stale loading/result UI on return, zero app console errors/page errors.
2. Export Cancel: request aborted, zero downloads, zero object URLs created, localized canceled toast, controls re-enabled.
3. Clipboard denial then granted retry: `copy failed` → `copied` announced states on the same control.
4. Rejected ShikiHighlighter chunk: readable plain-text SQL plus polite localized notice; no page errors.
5. Direct URL → reload → back/forward → unknown path → permission redirect all coherent for a two-permission user.
6. AR RTL at 375 px: rejected highlighter fallback keeps SQL readable with the Arabic unavailability notice inside RTL chrome.

Live spec against the real disposable FastAPI stack (`qc21` Compose project: platform PostgreSQL, Redis, backend :8000, frontend nginx :5183; migrations applied; one disposable user seeded directly into the platform database with two query permissions; no LLM call, no source database) — 2 passed:

- Unauthenticated deep link redirects to `/sign-in` via the real 401 path; authenticated direct URL + hard reload keeps shell/route; unknown path lands on the first permitted route.
- Four successive real-network route crossings settle with zero assistant-loading residue and zero app-level console/page errors.

The disposable Compose project, its volumes and the seeded user were destroyed after proof (`down -v`).

## Cleanup

Temporary Playwright output lived only under `/tmp/opencode/chunk21-*`; the debug spec file was removed immediately. The protected baseline (14 modified tracked PNGs, seven historical untracked screenshots, trace archives) was not staged, regenerated or deleted; `git add -A` was never used.

## Stop-condition review

None triggered: cancellation stayed frontend-only, route fallback required no product decision, no raw runtime detail reached DOM/console/storage, and generated-client determinism is unaffected (no generated file changed).

Ledger totals after CHUNK-21 merge will be 35 Resolved, 0 Resolved on tested branch, 9 Pending, 3 Needs Decision out of 47.
