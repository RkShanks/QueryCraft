# CHUNK-12 / IS-GAP-019 — bounded collections and quota-status fan-out

Status: implementation proof and authoritative GitHub backend/frontend CI passed on branch `phase-6/wave-19.12-collection-bounds` in [#310](https://github.com/RkShanks/QueryCraft/pull/310); squash merge is pending.

Tested product commit: `80652b47b6a53687bbe67f849c070b8ffb9f82d0`.

## Additive API contracts

| Endpoint | Inputs | Existing collection field | Added metadata | Stable order |
| --- | --- | --- | --- | --- |
| `GET /api/v1/sessions` | `cursor`; `limit` default 50, range 1–100 | `items` | exact owned `total`; `next_cursor` | `last_activity_at DESC`, `id DESC` |
| `GET /api/v1/sessions/{id}` | `attempt_cursor`; `attempt_limit` default 50, range 1–100 | `attempts` | exact owned `attempts_total`; `attempts_next_cursor` | `accepted_at DESC`, `id DESC` |
| `GET /api/v1/admin/quotas/status` | `cursor`; `limit` default 50, range 1–100 | `status` | exact configured-role `total`; `next_cursor` | role name ASC, role ID ASC |

Existing callers without pagination parameters now receive the first bounded page. All three endpoints use keyset pagination. Cursor payloads contain only a version, collection namespace, sort position, and UUID. Malformed, empty, oversized, wrong-namespace, wrong-version, naive-datetime, and invalid-UUID cursors use the existing sanitized invalid-cursor response; cursors retain no question, SQL, result, role-policy, credential, or Redis-key data.

Session pages remain owned by the authenticated user. Attempt connection metadata is loaded once for the bounded page. The frontend fetches no later page until the localized action is invoked, flattens pages with ID deduplication, passes `AbortSignal` through the touched clients, and suppresses a deleted or superseded session's late settlement.

Keyset traversal does not claim snapshot isolation. On an unchanged dataset it has no duplicates or gaps, including equal timestamps. Concurrent create/update/delete can move rows before or across a saved cursor; a continuation reflects the current rows after that position, while an explicit first-page refresh reconciles the current ordering and exact total.

## High-cardinality PostgreSQL/Redis proof

The focused live suite used separately named PostgreSQL 15 and Redis 7 containers with tmpfs data stores, a migrated disposable platform database, transaction-scoped PostgreSQL fixtures, and isolated Redis DB 1.

| Scenario | Cardinality | Page bound | Traversal/result | Database calls | Redis calls |
| --- | ---: | ---: | --- | ---: | ---: |
| Equal-timestamp owned sessions | 10,000 | 100 | 100 complete pages; exact total; unique stable traversal | bounded page + exact-count queries | 0 |
| Equal-timestamp owned attempts | 10,000 | 100 | 100 complete pages; exact total; unique stable traversal | bounded page + exact-count queries | 0 |
| Attempt connection metadata | 3 metadata IDs | 50 default | 3 attempts | 1 metadata SELECT | 0 |
| Quota status | 120 roles; 3,000 users | 50 roles; 500 users/keys | 3 complete pages; exact total | 8 user-batch SELECTs; 6 quota page/count SELECTs | 12 MGET; every batch 500 keys; 0 GET |

Only the query and export dimensions in the high-cardinality fixture had limits, so the null-limit execution dimension produced zero counter reads. Missing counters returned zero. Malformed, negative, noncanonical, expected Redis failure, and unexpected Redis failure cases returned one sanitized 503 with no partial status. Permission denial read zero counters, and cancellation propagated without partial settlement.

Focused high-cardinality result: **17 passed in 4.29s**. The two 10,000-row traversals completed in 0.78s and 1.24s respectively; the 120-role/3,000-user aggregation completed in 0.20s.

## Frontend and browser proof

- Session and quota hooks are cancellable infinite queries with page size 50 and stable ID deduplication.
- Sidebar and Admin Quotas render the first page only and expose accessible localized Load More actions.
- Workspace reverses the descending API pages into chronological conversation order and exposes localized Load Older.
- Loading older attempts preserves the visible scroll position after the prepended page commits.
- Deletion, Undo, creation/invalidation, grouping, totals, quota recovery, session switching, and late-response suppression operate across loaded pages.
- A quota-only administrator generated zero admin-role discovery requests and zero admin-SSO discovery requests.

Chrome DevTools MCP was unavailable, so the required fallback used isolated Playwright Chromium with all output under `/tmp`. Six cases passed in **29.4s**: desktop, 768px, and 375px, each in EN/LTR and AR/RTL. Each case asserted 50 initial session DOM items, an explicit transition to 60 loaded items, 50 initial quota-status items, an explicit transition to 60 loaded items, reachable localized controls, correct document direction, no document-width overflow, and no late old-session content. Desktop also asserted older-page scroll preservation; EN desktop and AR 375px asserted the sanitized quota failure/retry path. No screenshots, video, traces, or browser payloads were retained.

## TDD commits

| Stage | Commits |
| --- | --- |
| RED session list and metadata fan-out | `6853a98`, `be7b9ab` |
| GREEN bounded session list and metadata batch | `20ac6c6`, `362d371` |
| RED/GREEN attempt pagination | `72e40a2`, `cb59d74` |
| RED/GREEN quota fan-out and fail-closed counters | `f911dc6`, `d35f61d`, `32905a7`, `71618c8` |
| RED/GREEN frontend infinite queries | `17cb1fc`, `0cd3396` |
| RED/GREEN session and quota UI | `c4ff568`, `12e68f4`, `61d91f7`, `d33124b` |
| RED/GREEN keyset indexes | `9cfa1fc`, `09b7652` |
| RED/GREEN malformed-boundary hardening | `9e68b66`, `3abac87` |
| REFACTOR guards and production gates | `28e6732`, `c98c2e1`, `b54c605`, `ca2d7d1` |
| RED/GREEN older-page scroll preservation | `3fdf79a`, `e2c0f1c`, `80652b4` |

## Gates

| Gate | Result |
| --- | --- |
| Live session/attempt/quota high-cardinality integration | 17 passed in 4.29s on dedicated tmpfs PostgreSQL/Redis |
| Session API/repository/schema, accepted-query, quota repository/cache/permission, CHUNK-03 cancellation, CHUNK-07 identity/cache focused regressions | 139 passed, 11 skipped in 28.26s |
| Backend unit foundation | 2,469 passed, 44 deselected, 3 pre-existing warnings in 63.24s |
| Complete Alembic transition matrix through revision 011 | 35 passed in 45.51s |
| Ruff check | `src tests` passed |
| Ruff format check | 442 files already formatted |
| Full Vitest | 71 files, 970 tests passed in 9.71s |
| ESLint | passed |
| TypeScript no-emit typecheck | passed |
| Production build | passed; existing chunk-size advisory only |
| CSS lint | passed |
| Isolated Playwright Chromium | 6 passed in 29.4s |
| JSON validation | evidence and consolidated matrix passed |
| `git diff --check` | passed |
| GitHub backend-test | passed on `80652b47b6a53687bbe67f849c070b8ffb9f82d0` |
| GitHub frontend-test | passed on `80652b47b6a53687bbe67f849c070b8ffb9f82d0` |

## Cleanup and protected baseline

- Redis test DB size before container removal: 0.
- Retained synthetic PostgreSQL session, attempt, role, and user row counts before container removal: 0, 0, 0, and 0.
- Disposable CHUNK-12 PostgreSQL/Redis container count after cleanup: 0; both tmpfs containers auto-removed.
- Running repository proof service count after cleanup: 0; the three repository services used by the earlier verification pass were stopped.
- Temporary browser spec and `/tmp` output count after cleanup: 0.
- The protected baseline remains exactly 14 modified tracked PNGs, seven untracked historical screenshots, and two untracked trace archives; none was edited, staged, regenerated, deleted, or reverted by CHUNK-12.
- Evidence contains only counts, page/batch/query sizes, booleans, timings, statuses, and commit IDs. It retains no synthetic question, SQL, result row, session payload, role policy, credential, Redis key, screenshot, video, or trace.
- CHUNK-13 remains gated only on squash merge of #310. No CHUNK-13 work was started.
