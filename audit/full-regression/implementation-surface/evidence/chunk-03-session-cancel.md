# CHUNK-03 session cancellation evidence

Status: **Resolved**  
Gap: `IS-GAP-003`  
Starting main: `9eda3c71128d2840aad469f8b182b5f6c9185ec7`  
Tested product commit: `4580925594c872ae0283485155bbdf4bd7e225f4`  
Fix PR: [#301](https://github.com/RkShanks/QueryCraft/pull/301)

## Outcome

Deleting an owned chat session now establishes a durable Redis cancellation tombstone before destructive database work. The running query checks that shared state before and after provider work, after evaluator work, before and after source execution, before masking/persistence, and before success audit/response. Same-process provider, evaluator, and source child tasks are also canceled promptly.

The marker carries an opaque ownership token. DELETE rolls back and clears only its own marker if database deletion fails; a cancellation-state dependency failure returns the existing sanitized dependency response before database deletion. Wrong-user, missing, malformed, and duplicate deletion retain the private not-found contract and cannot cancel another user's work.

Each query operation records the owning user, HTTP session, attempt IDs, and processing-lock owner in Redis. Cancellation cleanup removes attempt, active-attempt, and lock state only when those ownership values still match. A late worker therefore cannot remove replacement state acquired after a race. Deleted sessions are never recreated: invalidated work rolls back and returns the existing sanitized 404 instead of persisting, auditing success, or returning a result.

The frontend keeps Undo as a true pre-DELETE operation. Hiding a sidebar item does not cancel its query; Undo before the five-second timer prevents DELETE and lets the query settle normally. Once DELETE begins, the active workspace moves to a safe empty state, session/detail/history caches are removed or refetched coherently, and any pre-existing query settlement is ignored. A failed DELETE restores/refetches session state while retaining the generation that suppresses the obsolete request.

CHUNK-03 does not change general timeout configuration, retry quotas, regenerate audit taxonomy, health endpoints, or the broader AbortSignal contract assigned to later chunks.

## TDD and automated gates

| Check | Result |
| --- | --- |
| Backend RED commit | `393bc030341f61c0f0cb45647e7375d71d8a5a64` |
| Frontend RED commit | `36c9bf06f671c1c31f5c0db8ced8aef3f4d9fec1` |
| GREEN commit | `0f886134a355150880e0819dbb138ff71f9794fc` |
| REFACTOR commit | `4580925594c872ae0283485155bbdf4bd7e225f4`; made attempt-set membership and TTL one atomic Redis operation and aligned legacy unit fixtures with required session binding |
| Focused backend session/query/concurrency/attempt/lock/audit | 102 passed |
| Focused frontend Workspace/Sidebar/Undo/session/query lifecycle | 107 passed |
| MySQL/MSSQL source-policy regression | 2 passed |
| Exact local backend CI unit command | 2,397 passed; 14 deselected |
| Ruff check and format check for touched backend scope | Passed |
| Frontend Vitest, ESLint, typecheck, build, and CSS lint | Passed |
| Diff validation | Passed |
| PR merge gates | Full GitHub `backend-test` and `frontend-test` required before merge |

The RED backend test reproduced a late successful submit after session deletion. The frontend RED test reproduced a delayed result surviving the deferred-delete lifecycle. Test Guard was applied to changed tests, Clean Code Guard to production changes, and Docs Guard to this evidence and the implementation-surface status updates.

Automated regressions cover deletion during provider, evaluator, mocked source, and real PostgreSQL source work; a deterministic barrier immediately before persistence; same-process task cancellation; simulated second-worker provider and adapter completion; duplicate DELETE; wrong-user, missing-session, malformed-ID, Redis-outage, database-rollback, and lock/active-attempt ownership races. Frontend tests cover Undo before expiry, DELETE after expiry, duplicate timer settlement, DELETE failure recovery/refetch, active-session navigation, exact cache removal, and suppression of late cards, alerts, and hook state.

## Real browser and service proof

The browser exercised the production React application and FastAPI routes with deterministic provider and source barriers. Chrome network timing, DOM, accessibility state, console/unhandled-error capture, TanStack cache state, PostgreSQL, Redis, and audit search were inspected. No screenshot or trace was retained.

| Scenario | Observed result |
| --- | --- |
| Undo before timer expiry | No DELETE request; the session returned to the sidebar and the provider-stage query completed normally. |
| Provider-stage expiry | DELETE returned 204; the invalidated submit returned the sanitized 404; the workspace became empty with no result card, alert, or console error. |
| Real PostgreSQL source execution | The source statement was observed active and waiting on a controlled table lock before DELETE; it was absent from source activity after DELETE while the blocker remained held. |
| Late source settlement | Platform session/history counts were zero and successful execute-audit count did not increase. Direct session/history APIs and audit search agreed. |
| Redis lifecycle | Operation, processing-lock, active-attempt, attempt-set, and attempt-record counts were zero after both successful deletions; only short-lived cancellation tombstones remained until proof cleanup. |
| Accessibility and UI | Loading used a polite status; destructive controls remained named; the deleted active session navigated to the safe empty workspace with no stale card, toast, sidebar row, or alert. |

The PostgreSQL proof used a real source adapter and a transaction-held table lock, not provider quota or wall-clock guessing. The final canceled run left the pre-run success-audit count unchanged. Browser requests are recorded here only as sanitized route classes (`POST /api/v1/query`, `DELETE /api/v1/sessions/{session}`), without identifiers or bodies.

## Multi-dialect cancellation result

Correctness does not depend on driver-level interruption. A native-driver probe showed the MySQL operation stopped promptly when its stage task was canceled. The MSSQL driver call remained blocked until the controlled five-second operation completed, confirming that physical adapter cancellation is not portable. The second-worker late-adapter regression therefore proves the required fallback: a durable tombstone suppresses persistence, history, success audit, attempt state, and client success even when adapter work finishes late.

PostgreSQL received the full real HTTP/browser/source-execution proof. MySQL and MSSQL retained their existing real-adapter policy regression, and both native drivers were inspected for cancellation behavior; no dialect-specific persistence path was found that bypasses the shared post-source cancellation boundary.

## Failure, race, and privacy results

- Cancellation-state failure during DELETE failed closed with a sanitized 503 and preserved the database session.
- Forced database deletion rollback cleared only the marker owned by that DELETE and left the session usable.
- Concurrent duplicate deletion produced one 204 winner and one private 404 loser.
- Wrong-user deletion returned the private 404 without creating a marker or disturbing the owner's query.
- Missing and malformed identifiers retained the existing sanitized missing/validation contracts.
- Cancellation cleanup removed every attempt registered to the session, but preserved a raced replacement lock and active attempt with different ownership.
- Provider, evaluator, source, pre-persistence, audit, and response boundaries emitted no late history row or success response after invalidation.
- No prompt, generated statement, source row, credential, cookie, token, internal identifier, or raw dependency error is retained in this evidence.

## Cleanup and handoff

- Stopped the disposable browser backend/frontend and the controlled source blocker.
- Restored the normal local-admin bootstrap configuration.
- Flushed the isolated Redis database; its final key count was zero.
- Removed the temporary browser harness and retained no browser artifact.
- Confirmed ports used by the disposable frontend/backend were closed.
- Confirmed the protected dirty baseline remains limited to the original 14 tracked images, seven historical screenshots, and historical traces.

`IS-GAP-003` is resolved by PR #301 on the tested product commit. `CHUNK-04` is unblocked after this PR merges; no CHUNK-04 work was started.
