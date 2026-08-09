# CHUNK-09 quota partial-success recovery evidence

Status: local backend, frontend, disposable PostgreSQL/Redis and isolated Chromium proof passed on tested product commit `dca6ed77ab6e16a762a0c0f5a2d4286b9f58ba51` in [#307](https://github.com/RkShanks/QueryCraft/pull/307). Authoritative PR CI and squash merge remain the CHUNK-10 dispatch gate.

Starting main: `7924a0da2839eb51c2fbb463433213a4fcd6e90b`.

## Outcome

`IS-GAP-014` is resolved on the tested branch. PostgreSQL is authoritative for quota configuration. Every PUT or DELETE first establishes an atomic, cross-worker Redis transition that advances the configuration revision and removes the previously publishable cache entry. Quota readers fail closed while that transition exists, including inside the atomic counter script, so no counter increment can occur after transition creation and before authoritative publication.

Redis failure before transition creation returns the existing sanitized ordinary 503 and leaves the database and audit log unchanged. Database failure after transition creation rolls back both mutation and audit, then republishes the prior PostgreSQL state; if that publication is also unavailable, enforcement remains fail closed.

After a successful database commit, publication failure retains the one truthful mutation and success audit and returns the focused response extension:

```json
{"error":"quota_sync_pending","message_key":"error.quota_sync_pending","mutation_applied":true}
```

The body contains no cache implementation details, configuration revisions, key material, role values, quota values, counter values or stack traces. An identical PUT retry publishes the authoritative row and returns 200 without another timestamp change or audit. A retry of a committed deletion publishes the authoritative tombstone and returns 204 without another audit; a later genuinely non-pending deletion preserves 404.

## Database, cache and audit proof

The focused integration suite used disposable PostgreSQL and Redis. Fault injection wrapped the real Redis client only at the post-commit publication command, leaving transition creation, PostgreSQL transactions, public API routing and subsequent quota enforcement real.

| Case | API result | Database result | Quota-change audit result | Enforcement/counter result |
| --- | ---: | --- | --- | --- |
| Redis unavailable before transition | 503 ordinary unavailable | delta 0 | delta 0 | no mutation attempted |
| PUT publication failure after commit | 503 applied/pending | authoritative mutation retained | exactly +1 | pending check unavailable; counter delta 0 |
| Identical PUT while publication still fails | same 503 applied/pending | row and timestamps unchanged | additional delta 0 | remains fail closed |
| Identical PUT after Redis recovery | 200 | row and timestamps unchanged | additional delta 0 | new authoritative config published |
| DELETE publication failure after commit | 503 applied/pending | deletion retained | exactly +1 | pending check unavailable; counter delta 0 |
| DELETE after Redis recovery | 204 | deletion unchanged | additional delta 0 | authoritative tombstone published |
| Later non-pending DELETE | 404 | unchanged | additional delta 0 | unchanged |
| Deferred PostgreSQL commit failure | 500 sanitized | mutation rolled back | delta 0 | prior authoritative config republished |
| Separate-worker reader during blocked publication | 503 internally | committed state not exposed through stale cache | unchanged | counter delta 0 |
| Two workers retry identical PUT | 200 and 200 | one unchanged authoritative row | additional delta 0 | one coherent publication sequence |

The separate-worker case used an independent Redis client connection. Publication was held after PostgreSQL commit, the other worker failed closed without incrementing, and the same worker consumed the new configuration after publication. The concurrent retry case forced both workers to observe the same abandoned transition before either acquired the database row lock; both completed safely without a duplicate mutation or audit.

The original 60-second configuration-cache TTL, monotonic revision validation, atomic daily counter ceiling, query-before-execution quota ordering and durable audit-chain behavior remain covered by the regression gate.

## Frontend recovery

- Every failed save or reset awaits an active authoritative quota-list refetch.
- Only the exact three-field applied/pending response enters recovery; ordinary failures retain the localized generic error path.
- Pending recovery never emits a success toast. It closes a stale editor, renders the refetched PostgreSQL-backed list, and exposes one accessible Retry action.
- The retry operation is versioned, schema-validated, scoped to the authenticated user and retained only in session storage. Reload never overlays quota configuration; it reloads the authoritative list and restores only the retry intent.
- An immediate event-bound lock suppresses duplicate save/reset activation before React mutation state settles.
- Recovery success clears retained intent and emits the normal success notification. A continuing failure keeps recovery available.
- The quota-only permission path made no role-discovery or SSO-discovery requests. A status-request failure continued to render the independent authoritative configuration list.
- New styling uses logical alignment and wrap-safe flex behavior. EN/LTR and AR/RTL recovery remained inside desktop, 375px and 768px viewports.

## TDD history

- RED `1b69721fe7a30081a0667227ad5911713a510ae1` → GREEN `aa82dc098f9f330a4ae3f400200285ae8867c5ee`: fail-closed transition and atomic counter boundary.
- RED `367b38abbb4eb554fa7ed7bdbee3b6405110d2ee` → GREEN `83369bd8573f8df49ae5e1420b4d0850b9b8de31`: PUT commit/publication partial success and idempotent repair.
- RED `973f102317ed6bfd932c1803b9d5f6a36da6d51a` → GREEN `7327e502ff8c215bb0c38b7b35ca804940d76a77`: DELETE commit/publication partial success, tombstone repair and preserved 404.
- RED `39b5bd218ba574c808e0a900493e5adb17a5802b` → GREEN `bdf36000fd12b58b440ba79badfbffe2fe3a4f79`: stable applied/pending response across continuing publication failure.
- RED `8708bbf19c1bedda250c52908c4c057e796f8339` → GREEN `b8f1198a05eda7ce6406e42d4fd45b5ca8ea12e5`: cross-worker reader and concurrent identical retry recovery.
- RED `d1a30f86d82c37848996f2e47bcd2a7e5e95837c` → GREEN `a0aa0633b57f404d5d96a63f93ab423b106e3a73`: authoritative frontend refetch, reload, localized recovery, retry and duplicate-click suppression.
- REFACTOR `66ecd41d454da9902e6b10dcfcc3b1287218488c`: fixed audit dimension ordering, centralized truthful audit construction, awaited refetch boundaries and focused endpoint documentation.
- Browser proof `dca6ed77ab6e16a762a0c0f5a2d4286b9f58ba51` retains the three isolated Chromium recovery cases.

Test Guard accepted the real-boundary fault seam, state/audit/timestamp/counter assertions and behavior-level MSW/browser cases. Clean Code Guard accepted the explicit transition lifecycle and shared audit/reconciliation helpers. Vercel React Best Practices shaped the user-scoped versioned storage, event-bound duplicate lock and absence of effect-driven derived state. Docs Guard verified the focused response and retry semantics here and in the endpoint docstrings.

## Browser proof

The Chrome DevTools connector was unavailable, so the repository Playwright Chromium fallback was used with all output directed to `/tmp`.

| Locale/layout | Mutation | Pending 503 | Authoritative reload | Identical retry | Viewport fit |
| --- | --- | --- | --- | --- | --- |
| EN desktop 1280×900 | save | visible; no success toast | applied database state shown | 200; same body | true |
| EN mobile 375×812 | save | visible; no success toast | applied database state shown | 200; same body | true |
| AR tablet 768×1024 | reset/delete | visible; no success toast | configuration absent | 204 | true |

All three cases preserved quota-only permission isolation and made zero role/SSO discovery requests. Result: 3 passed. Screenshots, video, traces and browser output retained: 0.

## Gates

- Focused quota admin/repository/cache/audit after refactor: 35 passed.
- Quota ordering, atomic counters, real Redis outage/recovery, permission revocation and audit-chain regressions: 178 passed.
- Focused AdminQuotas page/hook/locale/permission slice: 4 files, 339 passed.
- Full frontend Vitest: 71 files, 958 passed.
- Focused Playwright Chromium: 3 passed.
- Ruff check: passed.
- Ruff format check: 432 files already formatted.
- ESLint: passed.
- Typecheck: passed.
- CSS lint: passed.
- Production build: passed; the existing bundle-size advisory remained non-failing.
- `git diff --check`: passed before evidence; rerun after evidence and ledger updates.
- Test Guard, Clean Code Guard and Vercel React Best Practices: passed.
- Docs Guard: applied to endpoint documentation, this evidence and the five progress ledgers.
- Authoritative PR `backend-test` and `frontend-test`: pending before merge.

## Contract remediation note

This chunk documents only the focused mutation-failure extension above. Ordinary 503 behavior and all success/404 contracts remain unchanged. The frontend parser accepts the exact applied/pending shape and otherwise uses ordinary failure handling. No broad OpenAPI or generated-client regeneration was performed; canonical regeneration remains `CHUNK-14` / `IS-GAP-008` scope.

## Cleanup and baseline

- Disposable CHUNK-09 containers, volumes and networks remaining: 0.
- Disposable PostgreSQL and Redis service ports remaining: 0.
- Browser output, screenshots, video and traces remaining under `/tmp`: 0.
- Temporary CHUNK-09 test cache remaining under `/tmp`: 0.
- Role-sensitive quota values or Redis key material retained in evidence: false.
- The 14 protected modified PNGs, seven untracked historical screenshots and untracked traces directory remain unstaged and unchanged from the starting dirty baseline.

CHUNK-10 becomes unblocked only after authoritative backend/frontend CI passes and this branch is squash-merged. Do not start CHUNK-10 from this evidence alone. The machine-readable peer is [chunk-09-quota-partial-success.json](chunk-09-quota-partial-success.json).
