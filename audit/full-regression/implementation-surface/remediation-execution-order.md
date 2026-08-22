# Remediation execution order

Status: `CHUNK-01` through `CHUNK-18` are resolved and merged; CHUNK-12 merged through [#310](https://github.com/RkShanks/QueryCraft/pull/310) at main `58098c05dfc92b7fd22b1096d38229e5c8a66f52`, and CHUNK-18 through [#316](https://github.com/RkShanks/QueryCraft/pull/316) at main `abd51680690714f9ae5b759271056c4873f6743f`. CHUNK-19 is resolved on tested branch `phase-6/wave-19.19-interaction-accessibility` starting from that synchronized main. Selector keyboard, dialog/toast/timer, and SignInForm contract behavior plus mocked/live Chromium proof and full local gates passed. This PR’s CI, squash merge, branch deletion and synchronized main remain before CHUNK-20 dispatch. See [evidence](evidence/chunk-19-interaction-a11y.md).

The order puts the Critical source-continuity defect first, then security/data integrity, API behavior, canonical contract work, dependent frontend behavior, evidence-only work, low cleanup, and decision-gated surfaces. Every dispatch contains at most three closely related consolidated gaps and is scoped below 200k context. Mixed backend/frontend chunks are sequential handoffs: backend behavior and tests first, frontend behavior/evidence second.

## Universal dispatch contract

- Read `AGENTS.md`, the applicable implementer role, Karpathy guidance, TDD skill, this file, the named consolidated JSON objects, and only the directly affected requirement/evidence rows.
- Use RED → GREEN → REFACTOR commits where implementation is authorized. Apply Test Guard to changed tests and Clean Code Guard to changed product code. Run docs guard if behavior documentation changes.
- Stage exact paths only. Never use `git add -A`; preserve the protected dirty baseline.
- Evidence goes under `audit/full-regression/implementation-surface/evidence/` in a new chunk-specific file/directory and contains categories/counts/status only—never credentials, cookies, tokens, full prompts, SQL, source rows, hostile payloads, raw errors or canary values.
- Stop on a new requirement ambiguity, any sensitive-data disclosure, mutation of a non-disposable source, inability to isolate Redis/PostgreSQL/browser state, a dependency regression, a context estimate approaching 180k, or a failing foundation gate outside the chunk's changes. Do not absorb unrelated fixes.

## CHUNK-01 — selected-source continuity (standalone Critical)

- **Progress:** Resolved. Three-dialect merged-main HTTP and focused browser proof passed; all isolated resources were removed and the protected baseline was preserved. `CHUNK-02` is unblocked.

- **IDs / role / branch / context:** `IS-GAP-001`; Backend Implementer (Kimi/GLM) then Frontend Implementer (Gemini); `phase-6/wave-19.01-source-continuity`; target 120–160k.
- **Likely source:** `backend/src/app/core/attempt_store.py`, `backend/src/app/api/v1/query.py`, `backend/src/app/services/query_service.py`, `frontend/src/hooks/useQuerySubmit.ts`; affected router/service/component tests only.
- **TDD:** First reproduce MySQL/MSSQL HTTP submit→reject/regenerate and fresh-accept fallback with connection/dialect/policy/adapter sentinels; then persist/validate immutable context and update frontend only if the stabilized contract requires it.
- **Focused gates:** attempt-store unit; accept/reject/regenerate service and router integration; query audit; Ruff check/format for touched paths; frontend hook/component tests, ESLint/typecheck if frontend changes; diff check.
- **Regression subset:** P3-FR-069/073, P5-FR-128/131/132, XP-002/005/007.
- **Browser/live:** Required three-source HTTP and focused browser decision flow; value-safe source/dialect labels only.
- **Isolation/cleanup/evidence:** Dedicated platform DB/Redis and disposable read-only PG/MySQL/MSSQL fixtures; remove attempts/sessions/audit rows and source fixtures; write `evidence/chunk-01-source-continuity.md` plus JSON summary.
- **Stop conditions:** Any fallback semantics requiring a product choice, policy/source mismatch outside the reproduced path, or inability to prove all three dialects without touching shared fixtures.

## CHUNK-02 — protected rows in attempt state

- **Progress:** Resolved. Submit and regenerate persist metadata-only attempts; three-dialect merged-main Redis/API/browser proof passed, all isolated resources were removed, and the protected baseline was preserved. `CHUNK-03` subsequently resolved the next dependency.

- **IDs / role / branch / context:** `IS-GAP-002`; Backend Implementer (Kimi/GLM); `phase-6/wave-19.02-masked-attempt-state`; 70–100k.
- **Likely source:** `backend/src/app/services/query_service.py`, `backend/src/app/core/attempt_store.py`, policy enforcement and their unit/security tests.
- **TDD:** RED Redis serialization assertion for a masked role; cover submit/regenerate and ensure retry data remains sufficient without raw values.
- **Focused gates:** attempt-store, query submit/regenerate, masking/privacy/audit-redaction suites; Ruff and diff check.
- **Regression subset:** P5-FR-132/143, XP-006/012.
- **Browser/live:** Real Redis/API comparison required; browser only a focused masked-result sentinel.
- **Isolation/cleanup/evidence:** Disposable Redis and restricted source rows; destroy cache/source fixtures; `evidence/chunk-02-masked-attempt-state.json` with boolean absence results.
- **Stop conditions:** Retry correctness would require retaining protected values, a canary appears in any retained artifact, or CHUNK-01 is not merged.

## CHUNK-03 — session delete/cancel lifecycle

- **Progress:** Resolved. DELETE establishes durable cancellation before database deletion; same-process work is interrupted where safe, late cross-worker completion is suppressed, owned attempt/lock state is cleaned without racing replacement owners, and frontend Undo/cache/workspace behavior remains coherent. Deterministic browser/API and real PostgreSQL source proof passed. `CHUNK-04` subsequently resolved the next dependency.

- **IDs / role / branch / context:** `IS-GAP-003`; Backend Implementer then Frontend Implementer; `phase-6/wave-19.03-session-delete-cancel`; 130–170k.
- **Likely source:** `backend/src/app/api/v1/sessions.py`, `backend/src/app/repositories/session_repository.py`, processing/attempt state, `frontend/src/hooks/useSessions.ts`, `frontend/src/components/sidebar/UndoToast.tsx`, `WorkspacePage.tsx`.
- **TDD:** RED controllable long-query delete race; define cancellation, late-result suppression, Undo-before-DELETE and delete-after-Undo transitions.
- **Focused gates:** session API/repository/concurrency, lock/attempt/audit tests; Undo/Sidebar/Workspace component tests; Ruff, ESLint, typecheck and diff check.
- **Regression subset:** P2-FR-044/058, XP-013.
- **Browser/live:** Required slow-query delete/undo/delete with DOM/network/Redis/DB observation.
- **Isolation/cleanup/evidence:** Disposable session, controlled adapter and Redis namespace; cancel all tasks and verify no late history/audit success; `evidence/chunk-03-session-cancel.md`.
- **Stop conditions:** Undo meaning cannot be preserved without a product decision, adapter cancellation is unsafe, or any task survives cleanup.

## CHUNK-04 — configured query deadline and lock lifetime

- **Progress:** Resolved. Submit, regenerate, and accepted-query rerun share one monotonic configured deadline; provider and source calls receive only the remaining budget while every other stage shares the same timer. Locks use `ceil(deadline) + 5 seconds`, timeout cleanup is ownership-safe, and CHUNK-03 deletion remains authoritative. Controlled HTTP and real PostgreSQL/MySQL/MSSQL proof passed. CHUNK-05 subsequently resolved the next dependency.

- **IDs / role / branch / context:** `IS-GAP-004`; Backend Implementer; `phase-6/wave-19.04-query-timeout-config`; 80–110k.
- **Likely source:** `backend/src/app/core/config.py`, `processing_lock.py`, `query_service.py`, source executor and focused tests.
- **TDD:** RED non-default deadline on submit/regenerate/rerun and lock TTL; cover timeout, cancellation, attempt and audit state.
- **Focused gates:** settings, processing-lock, query service, executor and lock-leak tests; Ruff and diff check.
- **Regression subset:** P1-FR-012, XP-013/014.
- **Browser/live:** Controlled slow-source API timing; one focused timeout UI check only if response contract changes.
- **Isolation/cleanup/evidence:** Disposable Redis/slow adapter, bounded fake/monotonic clocks; `evidence/chunk-04-timeout-config.json`.
- **Stop conditions:** Exact lock-margin policy is ambiguous, timing cannot be made deterministic, or cleanup leaves a live lock/task.

## CHUNK-05 — retry quotas and audit lifecycle

- **Progress:** Resolved on tested branch commit `d4cff9cbb1edb22b8a0bbb78bd4733151293b9c2` via [#303](https://github.com/RkShanks/QueryCraft/pull/303). Direct regenerate and explicit reject share one query/execution accounting boundary and one durable, sanitized retry lifecycle. Real HTTP counters/call spies, exact audit action/resource/outcome assertions, hash-chain verification, failure rollback, cancellation/deadline compatibility and PostgreSQL/MySQL/MSSQL execution-denial proof passed. Merge remains gated on backend/frontend CI; CHUNK-06 has not started.

- **IDs / role / branch / context:** `IS-GAP-005`, `IS-GAP-006`; Backend Implementer; `phase-6/wave-19.05-retry-quota-audit`; 120–160k.
- **Likely source:** `backend/src/app/services/query_service.py`, quota/audit services, query API and focused quota/audit tests.
- **TDD:** RED query/execution quota denial before retry work and RED exact audit lifecycle for regenerate success/reject/validation failure/timeout/cancellation/source failure.
- **Focused gates:** quota enforcement, query audit logging, regenerate/reject service/router, hostile ordering and audit-chain tests; Ruff and diff check.
- **Regression subset:** P5-FR-140/141, P6-FR-151/152/155, XP-005/010.
- **Browser/live:** API counter/call-order/chain evidence; focused UI quota banner only if contract changes.
- **Isolation/cleanup/evidence:** Disposable counters/audit DB and controlled provider/source; `evidence/chunk-05-retry-quota-audit.md`.
- **Stop conditions:** One action would double-charge contrary to locked quota dimensions, event taxonomy needs a new product decision, or audit persistence is not durable.

## CHUNK-06 — migration chain and revision-007 rollback

- **Progress:** Resolved on tested branch commit `2a48ec9b0da9c7abe408cb5248104525f5350604` via [#304](https://github.com/RkShanks/QueryCraft/pull/304). The 33-test isolated suite passed every fresh, stepwise, populated parent-cycle, historical-to-head, head-to-historical, revision-007 refusal/remediation and concurrent-execution case. All disposable databases, containers and volumes were removed; authoritative backend/frontend CI passed.
- **IDs / role / branch / context:** `IS-GAP-009`; Backend Implementer; `phase-6/wave-19.06-migration-chain`; 100–140k.
- **Likely source:** `backend/alembic/versions/001_*.py` through `backend/alembic/versions/009_*.py`, migration tests/fixtures.
- **TDD:** RED populated revision-007 downgrade with SSO NULL password plus fresh and stepwise 001↔009 cases; encode approved destructive expectations.
- **Focused gates:** isolated migration suite and model/repository smoke; Ruff/format only if Python changes; diff check.
- **Regression subset:** P5 auth/RBAC persistence rows and XP-018 migration gate.
- **Browser/live:** None.
- **Isolation/cleanup/evidence:** Brand-new disposable PostgreSQL per case; destroy databases; `evidence/chunk-06-migration-cycle.json` with revision/count/schema hashes.
- **Stop conditions:** A downgrade requires choosing data loss versus backfill, any shared DB is targeted, or a revision cannot be made reversible without owner approval.

## CHUNK-07 — browser identity and authorization boundary

- **Progress:** Resolved on tested product commit `3d2f05a6046ed1bd9f6b2a461fedd2c7f82b10db` in [#305](https://github.com/RkShanks/QueryCraft/pull/305); authoritative backend/frontend CI passed. Auth and feature caches are identity/permission generation-scoped, late settlement is suppressed, 401 removal remains distinct from 403 reconciliation, all eight permissions share one catalog, and exact route/nav/request plus role round-trip and EN/AR access-denied evidence passed. Disposable browser/backend resources were removed and the protected baseline was preserved.

- **IDs / role / branch / context:** `IS-GAP-023`, `IS-GAP-025`, `IS-GAP-022` in that internal order; Frontend Implementer; `phase-6/wave-19.07-ui-identity-permissions`; 140–175k.
- **Likely source:** `QueryProvider.tsx`, `useAuth.ts`, `uiStore.ts`, affected feature hooks, `AdminRolesPage.tsx`, `App.tsx`, `Sidebar.tsx`, PermissionGuard and tests.
- **TDD:** RED two-user/failed-signout/role-revocation cache tests; RED permission-catalog round trip; RED ordinary direct-route/nav/zero-background-request matrix.
- **Focused gates:** auth/cache/store, role page/hooks, App/PermissionGuard/Sidebar tests; ESLint, typecheck, focused Vitest and diff check.
- **Regression subset:** P5-FR-122/127/134, P6-FR-177, XP-001/003/011/012.
- **Browser/live:** Required same-browser users with disjoint history/connections/permissions and direct ordinary routes.
- **Isolation/cleanup/evidence:** Disposable roles/users/sessions and a fresh browser profile; clear all caches/profile; `evidence/chunk-07-ui-identity-permissions.md`.
- **Stop conditions:** No permitted landing route is a product decision, any old identity value renders, or role updates require active-session revocation contrary to Phase 5.

## CHUNK-08 — configured primary prompt length

- **Progress:** Resolved on tested product commit `1a11980ad3e395bf3b65131b1d5e6ce0209a19b5` in [#306](https://github.com/RkShanks/QueryCraft/pull/306). One positive configured setting now drives safe authenticated discovery, early API rejection and the primary Workspace counter/submission boundary. Exact Python/browser Unicode behavior, loading/error/retry, IME/newline, retained correction, double-submit, isolated 200/401/403/400 API and EN/AR desktop/375px Chromium proof passed. Disposable resources were removed and the protected baseline was preserved. Authoritative backend/frontend CI passed; squash merge remains required before CHUNK-09 dispatch.

- **IDs / role / branch / context:** `IS-GAP-020`; Backend Implementer then Frontend Implementer; `phase-6/wave-19.08-prompt-length-contract`; 80–115k.
- **Likely source:** backend settings/query schema/API; `PromptInput.tsx`, Workspace, locale keys and tests.
- **TDD:** RED non-default API boundaries and primary prompt paste/keyboard/counter/double-submit at limit−1/limit/limit+1.
- **Focused gates:** settings/schema/query API; PromptInput/Workspace/locale tests; Ruff, ESLint, typecheck and diff check.
- **Regression subset:** P1-FR-004/005/012, XP-006.
- **Browser/live:** Required focused boundary check; retain lengths only.
- **Isolation/cleanup/evidence:** Synthetic prompts and disposable attempt/session; `evidence/chunk-08-prompt-length.json`.
- **Stop conditions:** Limit discovery requires exposing unrelated settings or complete prompt text appears in evidence.

## CHUNK-09 — quota DB/cache partial success

- **Progress:** Resolved on tested product commit `dca6ed77ab6e16a762a0c0f5a2d4286b9f58ba51` in [#307](https://github.com/RkShanks/QueryCraft/pull/307). PostgreSQL is authoritative; a cross-worker Redis transition invalidates stale enforcement before DB mutation, pending checks fail closed without counter increments, and post-commit publication failure returns the documented applied/pending 503. PUT/DELETE retry, timestamp/audit idempotency, rollback republish, concurrent readers/workers, authoritative frontend reload, localized retry and desktop/375px/768px browser proof passed. Disposable resources were removed and the protected baseline was preserved. Authoritative CI passed on `42df59fe56e1dbebc6485b10c4ba96d936973454`; squash merge `453875adb54599dd1ba16baa10101af6427588fa` unblocked CHUNK-10.
- **IDs / role / branch / context:** `IS-GAP-014`; Backend Implementer then Frontend Implementer; `phase-6/wave-19.09-quota-partial-success`; 105–140k.
- **Likely source:** `admin_quotas.py`, quota service/repository, `useAdminQuotas.ts`, `AdminQuotasPage.tsx` and tests.
- **TDD:** RED cache-refresh failure after commit for PUT/DELETE, audit count and idempotent retry; RED UI authoritative refetch/recovery.
- **Focused gates:** quota admin/repository/cache/audit; quota page/hook tests; Ruff, ESLint, typecheck and diff check.
- **Regression subset:** P6-FR-148/155, XP-013.
- **Browser/live:** Required save/reset 503 then reload/retry.
- **Isolation/cleanup/evidence:** Disposable quota role, PostgreSQL and Redis fault seam; `evidence/chunk-09-quota-partial-success.md`.
- **Stop conditions:** Chosen response semantics would change API contract without documentation, or retry cannot be idempotent.

## CHUNK-10 — persisted security/resource invariants

- **Progress:** Resolved on tested product commit `3b6f90dd938d51bef9e04ba4f5a57afce3335b68` in [#308](https://github.com/RkShanks/QueryCraft/pull/308). Revision 010 enforces ten named checks and one singleton index after a value-safe atomic preflight, inserts one default only for an empty detection table, and downgrades without deleting rows. Real PostgreSQL direct-write, refusal, `009→010→009→010`, base/head and eight-worker singleton proof passed. Query/admin/quota/source/provider consumers fail closed without repair or sensitive responses; API-only explicit repair/retry passed. Disposable resources were removed and the protected baseline was preserved. Authoritative CI passed on `c0a74d891b3a28b8b35d405a85a1969a69ec561f`, and squash merge `09651c2c130025512d63fa4b36ef1ba51675bd73` unblocked CHUNK-11.
- **IDs / role / branch / context:** `IS-GAP-017`, `IS-GAP-013`; Backend Implementer; `phase-6/wave-19.10-data-invariants`; 120–155k.
- **Likely source:** role-quota/detection/connection models, detection repository, new Alembic revision and related tests.
- **TDD:** RED invalid direct rows and concurrent detection initialization; decide migration repair behavior before GREEN.
- **Focused gates:** migration, quota repository, detection repository/admin/runtime and connection-model tests; Ruff and diff check.
- **Regression subset:** P3 connection state, P6-FR-148/159/160, XP-005/018.
- **Browser/live:** API-only sanitized corruption/recovery check; no broad browser run.
- **Isolation/cleanup/evidence:** Disposable populated PostgreSQL; `evidence/chunk-10-data-invariants.json`.
- **Stop conditions:** Existing invalid production-row handling needs an owner choice, constraint migration would silently delete data, or revision-007 work is not merged.

## CHUNK-11 — atomic concurrent-session eviction

- **Progress:** Resolved on tested product commit `00b5ad8f266d7f6156a5c3ce6ed11b59c54f5652` via [#309](https://github.com/RkShanks/QueryCraft/pull/309). One Redis Lua operation creates the session key, inserts/prunes the per-user index, assigns deterministic sequence-based order, evicts overflow sessions, deletes victim keys, and refreshes index/sequence TTLs. Shared atomic lifecycle paths cover sign-out, idle expiry, stale-user cleanup, local and OIDC/SAML audit rollback, outage fail-closed behavior, rollout timestamp-score compatibility, CAS-safe refresh and no-resurrection races. Real Redis direct/local/SSO concurrency and API outage proof passed; disposable Redis cleanup ended with zero keys. Authoritative backend/frontend CI passed on `f17bf48ba7a829a1f77aea374de2fe7276491c6c`, and squash merge `fce00de777e400f38d53d0e20e90e38c2d7e8e5c` unblocked CHUNK-12.
- **IDs / role / branch / context:** `IS-GAP-012`; Backend Implementer; `phase-6/wave-19.11-session-limit-atomic`; 70–100k.
- **Likely source:** `session_repository.py`, auth/SSO callers and concurrent-session tests.
- **TDD:** RED real Redis simultaneous login with equal/ordered timestamps, exact max and key/index cleanup.
- **Focused gates:** concurrent-session, auth/SSO session, Redis dependency tests; Ruff and diff check.
- **Regression subset:** P5-FR-127, XP-001/013.
- **Browser/live:** API concurrent login only.
- **Isolation/cleanup/evidence:** Disposable Redis namespace/users/sessions; `evidence/chunk-11-session-limit.json`.
- **Stop conditions:** Ordering tie-break requires a product decision or an atomic implementation cannot clean both key/index consistently.

## CHUNK-12 — bounded collections and fan-out

- **Progress:** Resolved on tested product commit `80652b47b6a53687bbe67f849c070b8ffb9f82d0` in [#310](https://github.com/RkShanks/QueryCraft/pull/310). Session and attempt endpoints now return exact ownership-scoped keyset pages with default 50/range 1–100 and stable timestamp/UUID order; attempt metadata is one bounded query. Quota status returns stable configured-role pages, keyset-streams current-page users in batches of 500, reads counters only through MGET batches of at most 500, skips null-limit dimensions, and fails the whole request closed on malformed data or Redis failure. Cancellable infinite-query clients render explicit localized pagination with deduplication, deletion/session-switch safety, quota recovery and scroll-stable older attempts. Real 10,000-session/10,000-attempt and 120-role/3,000-user proof, complete gates, six-case EN/AR responsive Chromium, cleanup and authoritative CI passed. Squash merge `58098c05dfc92b7fd22b1096d38229e5c8a66f52` unblocked CHUNK-13.
- **IDs / role / branch / context:** `IS-GAP-019`; Backend Implementer then Frontend Implementer; `phase-6/wave-19.12-collection-bounds`; 135–175k.
- **Likely source:** sessions API/repository/schema, quota status/service, generated contract inputs, `useSessions.ts`, Sidebar/Workspace and tests.
- **TDD:** RED high-cardinality bounds/stable cursors/batched Redis failure and client pagination/cancellation/rendering.
- **Focused gates:** sessions/quota APIs/repositories plus affected hook/page tests; Ruff, ESLint, typecheck, diff check.
- **Regression subset:** P2 session/history rows, P6 quota status, XP-013.
- **Browser/live:** Required synthetic high-cardinality desktop/mobile responsiveness.
- **Isolation/cleanup/evidence:** Seeded disposable platform DB/Redis; delete all data; `evidence/chunk-12-collection-bounds.json`.
- **Stop conditions:** Pagination semantics require a product decision, response compatibility cannot be preserved, or load exceeds isolated resource limits.

## CHUNK-13 — liveness/readiness contract

- **Progress:** Resolved on tested product commit `1c56b6305329cbc82fff5cc4066c995f2717873b` in [#311](https://github.com/RkShanks/QueryCraft/pull/311). Public constant liveness/readiness routes bypass session cookies; readiness concurrently checks current platform PostgreSQL, Redis and Alembic revision under one two-second deadline with application-managed clients and no mutation. Lifecycle state, Compose `service_healthy` gating, migration-before-backend and health-before-frontend dev-up ordering are locked. Isolated dependency/revision loss and restoration, excluded source/provider availability, local foundations and cleanup passed with zero backend restarts. Authoritative backend/frontend CI passed on `270ce0577c29f201f583a40c0f51a36b25984478`; squash merge `e18d2335f44a93f055bb7d3c03f08012c91443f6` unblocked CHUNK-14.
- **IDs / role / branch / context:** `IS-GAP-007`; Backend Implementer; `phase-6/wave-19.13-readiness`; 90–120k.
- **Likely source:** `main.py`, settings/dependencies, `docker-compose.dev.yml`, `scripts/dev-up.sh`, operational tests/docs.
- **TDD:** RED liveness/readiness states for startup, Redis/DB/migration drift, shutdown and recovery with constant bodies.
- **Focused gates:** ASGI health tests, Compose config validation, shell checks, Ruff and diff check.
- **Regression subset:** XP-013/018.
- **Browser/live:** Production-like Compose probes required; browser not required.
- **Isolation/cleanup/evidence:** Disposable Compose project/network/volumes; `evidence/chunk-13-readiness.md`.
- **Stop conditions:** Readiness dependency policy is ambiguous, probes disclose internal detail, or normal shared services would be stopped.

## CHUNK-14 — canonical OpenAPI and generated client

- **Progress:** Resolved on tested product commit `9f82c73c0abe1ec07199583343e954e65fd6d358` in [#312](https://github.com/RkShanks/QueryCraft/pull/312), then squash-merged as `0cc010a59b128423169bd252aa63df2acfeb2130`. The historical snapshot's 60 operations grew to 63 through query limits plus liveness/readiness; runtime, canonical artifact and generated SDK matched exactly at 63. Stable IDs, typed bodies/responses, deterministic generation, 63-operation Schemathesis, focused API/Chromium proof, full gates, cleanup and authoritative CI passed. CHUNK-15 is now the only legitimate successor operation change.
- **IDs / role / branch / context:** `IS-GAP-008`; Backend Implementer then Frontend Implementer; `phase-6/wave-19.14-openapi-canonical`; 150–180k.
- **Likely source:** FastAPI response/request models/routes, canonical OpenAPI artifact, contract tests, `generate-api-client.sh`, generated frontend API tree; remove/retire stale updater only if covered by scope.
- **TDD:** RED runtime/canonical/client operation/status/schema/content-type parity; then type redirect/form/download/error bodies and regenerate deterministically.
- **Focused gates:** contract/Schemathesis parity, generated-diff check, focused backend API tests; frontend API/hook tests, ESLint, typecheck/build only for generated-client integration; diff check.
- **Regression subset:** Constitution XII, P1-FR-031, P5/P6 endpoint contracts, XP-018.
- **Browser/live:** Focused query/auth/admin/download checks after generation; no broad visual sweep.
- **Isolation/cleanup/evidence:** App factory with placeholder non-secret settings; temporary generated output comparison; `evidence/chunk-14-openapi-parity.json`, current source-derived target 63=63=63 (historical snapshot 60 plus three later routes).
- **Stop conditions:** Runtime behavior is still changing in an earlier chunk, generation produces nondeterministic diffs, or a status/body decision is undocumented.

## CHUNK-15 — role policy editor safety and preview

- **Progress:** Resolved on tested product commit `750c21fa4f70bf1f1b106396852b9be846b931dc` in [#313](https://github.com/RkShanks/QueryCraft/pull/313), then squash-merged as `c92255de4e0be0fde59b3f0bf3045b7115de7354`. Added `testDraftRolePolicy`, producing deterministic 64-operation runtime/canonical/generated parity; shared evaluation proves no persistence, LLM or source execution. Matching full role detail gates Save and resists failed/late/background responses. The frontend uses structural filter checks only and the backend owns a 21-case shared corpus. Focused/full foundations, real local ASGI, EN/AR 1440/768/375 Chromium verification, authoritative backend/frontend CI and cleanup passed; CHUNK-16 was unblocked. See [evidence](evidence/chunk-15-role-policy-editor.md).
- **IDs / role / branch / context:** `IS-GAP-035`, `IS-GAP-026`, `IS-GAP-024`; Frontend Implementer; `phase-6/wave-19.15-role-policy-editor`; 145–180k.
- **Likely source:** `PolicyEditor.tsx`, `AdminRolesPage.tsx`, `useAdminRoles.ts`, generated policy-test client/types, locale keys and focused tests.
- **TDD:** RED shared filter corpus; RED delayed/failed/stale detail immediate-save; RED allowed/blocked/invalid/sanitized policy preview states.
- **Focused gates:** PolicyEditor/AdminRoles/useAdminRoles/locale tests, relevant backend policy-test/row-filter contract tests, ESLint/typecheck and diff check.
- **Regression subset:** P5-FR-123/128/131/132/136/137/138.
- **Browser/live:** Required EN/AR preview and delayed/failed hydration using disposable non-empty policies; prove no LLM/source execution.
- **Isolation/cleanup/evidence:** Disposable role/connection/schema and controllable response delay; `evidence/chunk-15-role-policy-editor.md`.
- **Stop conditions:** “Before saving” cannot be reconciled with the existing role-ID endpoint without a product/API decision, or any save can serialize absent policies as deletion.

## CHUNK-16 — role/group-mapping composite recovery

- **Progress:** Resolved and squash-merged as `f41e8c721450adb8fd50201de6218381289f531f` in [#314](https://github.com/RkShanks/QueryCraft/pull/314). Existing typed POST/PUT role contracts atomically persist role fields, connection policies, mapping diffs and success audits in one PostgreSQL transaction. Duplicate/cross-role conflicts, audit/response/commit faults and concurrent same-group claims are sanitized and preserve all-or-nothing semantics. Composite Save emits one role write, emits zero standalone mapping writes, suppresses duplicate submission and distinguishes confirmed success/rejection from lost-response uncertainty by authoritative reconciliation. Complete local foundations, exact 64-operation parity, EN/AR 1440/768/375 Chromium proof and authoritative backend/frontend CI passed. See [evidence](evidence/chunk-16-role-mapping-recovery.md).
- **IDs / role / branch / context:** `IS-GAP-036`; Frontend Implementer, with Backend Implementer if an atomic API is selected; `phase-6/wave-19.16-role-mapping-transaction`; 90–135k.
- **Likely source:** role/group-mapping APIs and schemas if changed, `useAdminRoles.ts`, `AdminRolesPage.tsx`, hook/page tests.
- **TDD:** RED failure after role commit and during mapping add/delete; implement atomic or resumable/idempotent semantics without claiming total rollback falsely.
- **Focused gates:** role/mapping backend tests when applicable; useAdminRoles/AdminRolesPage tests; lint/typecheck and diff check.
- **Regression subset:** P5-FR-123/125/140.
- **Browser/live:** Required retry/cancel/refetch partial-failure flow.
- **Isolation/cleanup/evidence:** Disposable role/mappings/user; `evidence/chunk-16-role-mapping-recovery.md`.
- **Stop conditions:** Atomic-versus-resumable approach materially changes API and is not decided, or retry can duplicate mappings.

## CHUNK-17 — client shape states and harness fidelity

- **Progress:** Resolved and squash-merged as `f29cec51cc673f2ae84ad0d60c3c62246b939c45` in [#315](https://github.com/RkShanks/QueryCraft/pull/315); authoritative backend/frontend CI passed in run `31803892021`. The canonical generator emits a complete 64-operation response manifest and deterministic component schemas. All 41 consumed JSON operations validate and strip unknown fields before state; one payload-free contract error drives localized initial/background retry states without losing prior valid data. The static guard classifies 28 Playwright specs and rejects stale permissions, unclassified mocks/skips, assertion-light function checks and tracked evidence output. Full local frontend/canonical gates and focused mocked/live Chromium passed. See [evidence](evidence/chunk-17-client-harness.md).
- **IDs / role / branch / context:** `IS-GAP-042`, `IS-GAP-033`; Frontend Implementer; `phase-6/wave-19.17-client-contract-harness`; 145–180k.
- **Likely source:** generated/custom clients, affected hooks/pages, MSW fixtures, `src/test/setup.ts`, Playwright config/helpers and focused tests.
- **TDD:** RED static fixture/contract drift and malformed/partial/background-state cases; isolate outputs before any browser execution.
- **Focused gates:** new harness lint/parity, affected hook/page fault matrix, focused Playwright only, ESLint/typecheck and diff check.
- **Regression subset:** P3/P5/P6 admin async states, XP-008/017/018.
- **Browser/live:** Focused malformed/partial/stale recovery; mocked/live classification required.
- **Isolation/cleanup/evidence:** Schema-derived fixtures and temporary test-results/screenshots; `evidence/chunk-17-client-harness.json`.
- **Stop conditions:** Any test writes tracked evidence, a raw cast cannot be removed without an API decision, or the named state is not assertion-observable.

## CHUNK-18 — workspace result and recovery behavior

- **Progress:** Resolved on tested product commit `bbc9ef5bc6bb0b8bc2627fb36a8cbace636e6aff` in [#316](https://github.com/RkShanks/QueryCraft/pull/316), with verification through `85145026c15c1e8fca47706d5fa4d31abc645f7f`. Result rendering is bounded to 50 DOM rows with semantic zero-row success; delete/regenerate recovery preserves and reconciles exact state with duplicate/stale suppression; connection recovery is permission/context-aware and never renders a dead CTA. The generated-contract fixture RED/GREEN, 1,141-test frontend suite, 456-test focused suite, production/static gates, 80 FastAPI compatibility tests, three-case 1440/768/375 Chromium matrix, unmocked authenticated FastAPI/source flow, cleanup and authoritative CI passed. Squash merge `abd51680690714f9ae5b759271056c4873f6743f` completed and unblocked CHUNK-19. See [evidence](evidence/chunk-18-workspace-recovery.md).
- **IDs / role / branch / context:** `IS-GAP-041`, `IS-GAP-027`, `IS-GAP-028`; Frontend Implementer; `phase-6/wave-19.18-workspace-recovery`; 120–155k.
- **Likely source:** chat `ResultTable`, `WorkspacePage.tsx`, `ConnectionErrorCard.tsx`, result/action components and tests.
- **TDD:** RED zero/large results; RED failed optimistic delete/regenerate rollback; RED each visible recovery CTA.
- **Focused gates:** ResultTable/Workspace/ConnectionErrorCard component tests, focused API mocks, locale/a11y tests, ESLint/typecheck and diff check.
- **Regression subset:** P1-FR-014/029, P2-FR-057/058, P3-FR-068/093.
- **Browser/live:** Required large/zero result, mutation failure and CTA/focus at desktop/768/375.
- **Isolation/cleanup/evidence:** Synthetic bounded rows and disposable sessions; `evidence/chunk-18-workspace-recovery.md`.
- **Stop conditions:** Pagination requires a backend contract change not planned in CHUNK-12/14, or a CTA destination/action is ambiguous.

## CHUNK-19 — interaction and form accessibility

- **IDs / role / branch / context:** `IS-GAP-029`, `IS-GAP-030`, `IS-GAP-039`; Frontend Implementer; `phase-6/wave-19.19-interaction-accessibility`; 150–180k.
- **Likely source:** DatabaseSelector, SessionItem, UndoToast, connection/admin dialogs/toasts, common form controls and representative page tests.
- **Progress:** Resolved on tested branch starting from synchronized main `abd51680690714f9ae5b759271056c4873f6743f`. The selector exposes one trigger/listbox keyboard model (open-focus, arrows/Home/End, Enter/Space, Escape/Tab restoration, locale-aware typeahead, active-versus-selected distinction, list-change coherence, duplicate-free auto-selection); the connection-delete overlay is a modal dialog with focus trap, Escape-hold destructive pending state and trigger-focus restore; session activation/delete became sibling buttons; toasts announce via status/alert roles with localized dismissal names; UndoToast pauses on hover/focus, resumes from the remainder, expires exactly once and cleans up on unmount; SignInForm implements the boundary/first-invalid-focus/aria-association/double-suppression/rejection-retry/success-status contract with secret hygiene. Component coverage: 471 focused tests within the 1,181-test full suite. Browser proof: four-case mocked EN/AR 1440/768/375 Chromium matrix plus one unmocked live sign-in round trip on disposable FastAPI credentials. Merge bookkeeping for CHUNK-12 (#310) and CHUNK-18 (#316) was reconciled without changing historical test evidence.
- **TDD:** RED full selector keyboard model; RED dialog/focus/live-region/timer cases; RED parameterized form boundary/error association/double-submit cases.
- **Focused gates:** affected component/page accessibility and locale tests, focused Playwright keyboard tree, ESLint/typecheck and diff check.
- **Regression subset:** P3 forms, P4-FR-107/109, P5/P6 admin forms, XP-008/009.
- **Browser/live:** Required keyboard/focus/accessibility-tree at desktop/768/375 EN/AR for representative states.
- **Isolation/cleanup/evidence:** Synthetic admin/session data, fake timers, temporary browser output; `evidence/chunk-19-interaction-a11y.md`.
- **Stop conditions:** One generic form abstraction would exceed scope, any destructive behavior changes without a requirement, or accessibility semantics conflict with actual control behavior.

## CHUNK-20 — history dataset and locale runtime

- **IDs / role / branch / context:** `IS-GAP-032`, `IS-GAP-038`; Frontend Implementer; `phase-6/wave-19.20-history-locale`; 100–140k.
- **Likely source:** history API/hook/page/list/detail, `i18n.ts`, App/AppShell direction, date/number formatters and tests.
- **TDD:** RED multi-page search/error placement/selection semantics; RED locale precedence, persistence, ar-EG direction and fixed-time formatting.
- **Focused gates:** history hook/components, locale parity/direction tests, focused browser spec, ESLint/typecheck and diff check.
- **Regression subset:** P1-FR-021/022, P4-FR-094/095/098/107, XP-008.
- **Browser/live:** Required multi-page search and EN/ar/ar-EG reload/formatting.
- **Isolation/cleanup/evidence:** Disposable history pages, fixed clocks/browser locale; `evidence/chunk-20-history-locale.md`.
- **Stop conditions:** Locale precedence requires product choice or search requires an unplanned API contract.

## CHUNK-21 — browser async and runtime failures

- **IDs / role / branch / context:** `IS-GAP-043`, `IS-GAP-037`, `IS-GAP-031`; Frontend Implementer; `phase-6/wave-19.21-browser-async`; 135–170k.
- **Likely source:** generated/custom clients, query/audit hooks/pages, App route/error boundaries, Shiki/clipboard/history actions and tests.
- **TDD:** RED abort/deadline/unmount; RED direct/reload/back-forward/unknown route and rejected lazy work; RED clipboard/console recovery.
- **Focused gates:** client/hook/router/runtime-failure tests, focused Playwright network/console checks, ESLint/typecheck/build and diff check.
- **Regression subset:** P1-FR-012, P2-FR-052/058, P4-FR-105/114, XP-008/012/013/014.
- **Browser/live:** Required navigation/unmount/download abort, clipboard denial and zero-unhandled-rejection checks.
- **Isolation/cleanup/evidence:** Delayed HTTP controls, temporary downloads and fresh browser profile; `evidence/chunk-21-browser-async.json`.
- **Stop conditions:** Cancellation would alter server semantics outside CHUNK-03/04, raw runtime detail reaches console/DOM, or lazy error behavior needs a product design decision.

## CHUNK-22 — audit download contract

- **IDs / role / branch / context:** `IS-GAP-034`; Frontend Implementer; `phase-6/wave-19.22-audit-download`; 75–105k.
- **Likely source:** `AdminAuditPage.tsx`, `api/audit.ts`, generated client metadata handling and tests.
- **TDD:** RED applied-versus-unsent filters, safe Content-Disposition, cancellation/retry and no partial file.
- **Focused gates:** audit API/client/page tests, focused backend export contracts, ESLint/typecheck and diff check.
- **Regression subset:** P6-FR-168/169/170, XP-004/012.
- **Browser/live:** Required real CSV/JSON download/file/filename inspection.
- **Isolation/cleanup/evidence:** Disposable sanitized audit entries and temporary downloads removed afterward; `evidence/chunk-22-audit-download.json`.
- **Stop conditions:** Server filename contract is absent after CHUNK-14 or a sensitive/formula-shaped value reaches filename/file unexpectedly.

## CHUNK-23 — authentication UX and enterprise IdP evidence

- **IDs / role / branch / context:** `IS-GAP-044`, `IS-GAP-016`; Frontend Implementer then Backend Implementer/evidence runner; `phase-6/wave-19.23-auth-recovery-idp`; 120–160k.
- **Likely source:** SignInPage/Form, useAuth, SSO service/adapters and focused tests/harness.
- **TDD:** RED provider loading/empty/failure, double-submit and rejected-signout recovery; keep protocol negatives deterministic before real IdP smoke.
- **Focused gates:** auth frontend tests, OIDC/SAML service suites, lint/typecheck/Ruff and diff check.
- **Regression subset:** P5-FR-117/118/119/121/139, XP-001.
- **Browser/live:** Required focused accessible auth recovery; real/standards-complete IdP rotation/outage only in approved isolated environment.
- **Isolation/cleanup/evidence:** Disposable HTTPS IdP/users/sessions/DB/Redis/browser; retain no tokens/assertions/URLs; `evidence/chunk-23-auth-idp.json`.
- **Stop conditions:** Live IdP/credentials are unavailable (record setup-dependent, do not fake closure), any auth material enters evidence, or signout semantics conflict with CHUNK-07.

## CHUNK-24 — non-Gemini provider evidence

- **IDs / role / branch / context:** `IS-GAP-015`; Backend Implementer/evidence runner; `phase-6/wave-19.24-provider-matrix`; 60–90k.
- **Likely source:** Anthropic/OpenAI/Ollama adapters and contract tests; product code only if a real defect is separately reproduced and authorized.
- **TDD:** Extend deterministic adapter boundaries first; one approved bounded smoke per available provider.
- **Focused gates:** provider adapter/factory/lifecycle tests and focused query composition; Ruff/diff check.
- **Regression subset:** P1-FR-009/026, P2-FR-047, XP-014.
- **Browser/live:** API only unless a provider-specific user-visible failure is found.
- **Isolation/cleanup/evidence:** In-memory credentials, one benign bounded invocation, no prompt/response retention; `evidence/chunk-24-provider-matrix.json`.
- **Stop conditions:** Credentials/approval unavailable, cost/invocation cap cannot be guaranteed, or a product defect is found (stop and draft a separate scoped fix).

## CHUNK-25 — bootstrap and source-fixture operations

- **IDs / role / branch / context:** `IS-GAP-018`; Backend Implementer; `phase-6/wave-19.25-bootstrap-hardening`; 90–125k.
- **Likely source:** `setup-source-dbs.sh`, `restore-mssql.sh`, `dev-up.sh`, seed scripts and operational tests/docs.
- **TDD:** RED failed/corrupt download, checksum mismatch, hostile env characters, partial restore, rerun and cleanup in disposable infrastructure.
- **Focused gates:** shell/static checks, script-specific tests, seed unit tests, Compose config validation and diff check.
- **Regression subset:** P3-FR-059/065, XP-015/018.
- **Browser/live:** None.
- **Isolation/cleanup/evidence:** Temporary directories and disposable source containers/volumes; `evidence/chunk-25-bootstrap.json`.
- **Stop conditions:** A shared fixture/database would be reset, upstream checksum/source is not authoritative, or secrets would enter command output.

## CHUNK-26 — detection form boundary

- **IDs / role / branch / context:** `IS-GAP-040`; Frontend Implementer; `phase-6/wave-19.26-detection-form`; 55–80k.
- **Likely source:** `AdminDetectionPage.tsx`, `useAdminDetection.ts`, generated schemas and tests.
- **TDD:** RED NaN/infinity/out-of-range/order/native-bypass/server rejection plus reset/dirty recovery.
- **Focused gates:** detection page/hook and backend schema/admin tests; locale/a11y, ESLint/typecheck and diff check.
- **Regression subset:** P6-FR-159/160.
- **Browser/live:** Focused numeric keyboard/range/error announcement.
- **Isolation/cleanup/evidence:** Disposable detection config and synthetic values; `evidence/chunk-26-detection-form.md`.
- **Stop conditions:** Persisted invariant work in CHUNK-10 is not merged or malformed response behavior is still undefined after CHUNK-17.

## CHUNK-27 — responsive assertion coverage

- **IDs / role / branch / context:** `IS-GAP-046`; Frontend Implementer; `phase-6/wave-19.27-responsive-evidence`; 70–110k.
- **Likely source:** focused Playwright specs/config/helpers; product code only if a separate defect is reproduced and authorized.
- **TDD:** Add failing machine-observable overflow/reachability/accessibility assertions before any product fix.
- **Focused gates:** selected component tests and responsive Playwright at 1440/768/375 EN/AR; no screenshot baseline update; ESLint/diff check.
- **Regression subset:** P4-FR-111, XP-008/009/017.
- **Browser/live:** Required dynamic/error/dialog/table/download/security states.
- **Isolation/cleanup/evidence:** Temporary output only, removed after summarized evidence; `evidence/chunk-27-responsive.json`.
- **Stop conditions:** Any tracked screenshot/trace would change, a product defect is reproduced (stop and split a fix), or prerequisite UI chunks are unmerged.

## CHUNK-28 — joint cross-channel privacy evidence

- **IDs / role / branch / context:** `IS-GAP-047`; Frontend Implementer with security review; `phase-6/wave-19.28-browser-privacy-evidence`; 90–130k.
- **Likely source:** security browser harness only unless a new defect is separately reproduced; query/audit/auth callers as observation points.
- **TDD:** Build negative-canary assertions for DOM, accessibility text, console, storage, in-memory cache, rendered response summary and downloads across hostile/error/download/user-switch flows.
- **Focused gates:** focused privacy/unit tests, new browser security integration and evidence schema/secret scan; lint/typecheck and diff check.
- **Regression subset:** P4-FR-114, P5-FR-143, P6-FR-164/170, XP-006/012.
- **Browser/live:** Mandatory real API/browser joint flow.
- **Isolation/cleanup/evidence:** Disposable users/sessions/audit/downloads/browser profile; boolean/count-only `evidence/chunk-28-browser-privacy.json`; destroy all canary-bearing state.
- **Stop conditions:** Any canary is observed, evidence tooling would retain a sensitive value, or IS-GAP-002/008/023/034/042 remains open.

## CHUNK-29 — cleanup and corrupted-cache recovery

- **IDs / role / branch / context:** `IS-GAP-021`; Backend Implementer; `phase-6/wave-19.29-cleanup-cache-recovery`; 55–80k.
- **Likely source:** `backend/src/app/main.py::lifespan`, attempt/session cache parsing, exception mapping and focused tests.
- **TDD:** RED one failing closer while later closers still run; RED semantically malformed valid JSON records with constant outcomes.
- **Focused gates:** lifespan, adapter lifecycle, attempt/session cache and error sanitization tests; Ruff/diff check.
- **Regression subset:** XP-013/018.
- **Browser/live:** None.
- **Isolation/cleanup/evidence:** Disposable Redis and mocked closers; `evidence/chunk-29-cleanup-cache.json`.
- **Stop conditions:** Cleanup aggregation would hide a security failure or typed corruption semantics require a broader API change.

## CHUNK-30 — deployed headers and documentation exposure [NEEDS DECISION]

- **IDs / role / branch / context:** `IS-GAP-010`, `IS-GAP-011`; Orchestrator decision, then Backend/Frontend Implementers; provisional `phase-6/wave-19.30-deployment-policy`; 80–115k after decisions.
- **Likely source:** `backend/src/app/main.py`, `backend/src/app/core/config.py`, `frontend/Dockerfile`, `frontend/vite.config.ts`, `frontend/index.html`, `docker-compose.dev.yml`, and deployment tests/docs.
- **TDD:** After decisions, RED direct/proxied header matrix, docs access policy and EN/AR title/history behavior.
- **Focused gates:** ASGI/deployment config, production-like HTTP checks, focused browser title; lint/typecheck/Ruff/diff check as applicable.
- **Regression subset:** XP-008/011/012/018.
- **Browser/live:** Required proxied production-like response/title checks.
- **Isolation/cleanup/evidence:** Disposable proxy/backend; `evidence/chunk-30-deployment-policy.md`.
- **Stop conditions:** Do not dispatch before both ownership/exposure decisions are recorded; stop on conflicting duplicate headers or exposed internals.

## CHUNK-31 — legacy `/ask` disposition [NEEDS DECISION]

- **IDs / role / branch / context:** `IS-GAP-045`; Product owner/Orchestrator then Frontend Implementer; provisional `phase-6/wave-19.31-ask-route-disposition`; 45–75k.
- **Likely source:** `App.tsx`, `AskQuestionPage.tsx`, legacy route/tests and bookmark/redirect evidence.
- **TDD:** After decision, RED redirect/bookmark/history behavior or RED parity obligations.
- **Focused gates:** App/router and affected legacy/Workspace tests; focused Playwright direct URL/back-forward; ESLint/typecheck/diff check.
- **Regression subset:** P1-FR-004, P2-FR-052.
- **Browser/live:** Required direct URL/bookmark/back-forward.
- **Isolation/cleanup/evidence:** Disposable session only; `evidence/chunk-31-ask-route.md`.
- **Stop conditions:** Do not dispatch before support status is decided; do not silently delete compatibility or expand parity scope.

## First recommended implementation dispatch

`CHUNK-01` through `CHUNK-17` are resolved and merged. CHUNK-18 implementation, responsive Chromium, live valid FastAPI flow, cleanup and authoritative CI are complete on the tested branch. Continue only its squash merge, branch deletion and synchronized-main gates. Do not dispatch CHUNK-19 before those gates complete.
