# Implementation-surface coverage summary

Snapshot: `0713c14a3e4dc44d4c330347d17aa86f52280d17`, with local `main` and `origin/main` synchronized before branching.

## Surface accounting

| Inventory | Exact | Partial | Missing | Intentional N/A | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Backend | 206 | 47 | 5 | 6 | 264 |
| Frontend | 32 | 142 | 10 | 8 | 192 |
| **Combined** | **238** | **189** | **15** | **14** | **456** |

Checks:

- Backend: 206 + 47 + 5 + 6 = 264.
- Frontend: 32 + 142 + 10 + 8 = 192.
- Combined: 238 + 189 + 15 + 14 = 456.
- Partial + Missing is 204 surfaces. Gap candidates group those rows by root cause; candidate and surface counts are intentionally not one-to-one.

## Candidate accounting

| Candidate inventory | Critical | High | Mid | Low | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Backend | 1 | 8 | 10 | 2 | 21 |
| Frontend | 0 | 10 | 20 | 3 | 33 |
| **Raw** | **1** | **18** | **30** | **5** | **54** |

Seven raw candidates share a root cause already represented by another candidate:

| Duplicate candidate | Canonical candidate | Consolidated gap |
| --- | --- | --- |
| FE-GAP-005 | BE-GAP-001 | IS-GAP-001 selected-source continuity |
| FE-GAP-004 | BE-GAP-003 | IS-GAP-003 session delete/cancel lifecycle |
| FE-GAP-009 | BE-GAP-008 | IS-GAP-008 canonical OpenAPI/client drift |
| BE-GAP-020 | FE-GAP-003 | IS-GAP-020 configured primary prompt length |
| FE-GAP-029 | BE-GAP-010 | IS-GAP-010 deployed header/document metadata boundary |
| FE-GAP-032 | BE-GAP-014 | IS-GAP-014 quota DB/cache partial success |
| FE-GAP-031 | BE-GAP-019 | IS-GAP-019 bounded collections/fan-out |

Therefore 54 − 7 = **47 unique consolidated gaps**. The candidate appendix in the matrix contains 47 canonical Source rows and seven Duplicate/Merged rows, exactly 54 entries.

## Consolidated severity

| Severity | Unique gaps |
| --- | ---: |
| Critical | 1 |
| High | 15 |
| Mid | 28 |
| Low | 3 |
| **Total** | **47** |

The severity reduction from raw counts is explained entirely by deduplication:

- Three High duplicates merge into an existing Critical/High root (`FE-GAP-005`, `FE-GAP-004`, `FE-GAP-009`).
- Two Mid duplicates merge into Mid roots (`FE-GAP-031`, `FE-GAP-032`).
- Two Low duplicates merge upward into a High and a Mid root (`BE-GAP-020`, `FE-GAP-029`).

## Disposition and category

### Unique consolidated gaps

| Disposition/category | Count |
| --- | ---: |
| Confirmed Product Gap | 36 |
| Confirmed Coverage Gap | 4 |
| Confirmed Contract/Documentation Drift | 1 |
| Confirmed Test-Harness Gap | 1 |
| Confirmed Operational Gap | 4 |
| Dead/Legacy Surface | 0 |
| Duplicate/Merged | 0 |
| Already Covered | 0 |
| Not a Current Requirement | 0 |
| Needs Decision | 1 |
| **Total** | **47** |

The category counts requested for execution planning are therefore: **product 36, coverage 4, contract 1, harness 1, operational 4, dead-code 0**, plus one product-scope decision (`IS-GAP-045`). `IS-GAP-010` and `IS-GAP-011` are operational gaps whose implementation status is also Needs Decision because ownership/exposure policy cannot be inferred from source.

The stale, uncalled `backend/scripts/update_openapi_phase5.py` was a dead maintenance surface inside the broader contract gap `IS-GAP-008`; CHUNK-14 removed it after caller verification and replacement parity gates, so it is not counted again as a separate dead-code gap. The reachable legacy `/ask` route is not declared dead until `IS-GAP-045` is decided.

### Raw candidate dispositions after deduplication

| Candidate disposition | Count |
| --- | ---: |
| Confirmed Product Gap | 36 |
| Confirmed Coverage Gap | 4 |
| Confirmed Contract/Documentation Drift | 1 |
| Confirmed Test-Harness Gap | 1 |
| Confirmed Operational Gap | 4 |
| Dead/Legacy Surface | 0 |
| Duplicate/Merged | 7 |
| Already Covered | 0 |
| Not a Current Requirement | 0 |
| Needs Decision | 1 |
| **Total** | **54** |

## Status

| Status | Count |
| --- | ---: |
| Pending | 5 |
| Resolved | 38 |
| Resolved on tested branch | 0 |
| Closed by Existing Evidence | 0 |
| Needs Decision | 3 |
| Partial | 1 |
| **Total** | **47** |

`IS-GAP-001` is resolved on tested main `3522440f0bbf3c837aafe62edaf2e9d89d4717fb` via [#297](https://github.com/RkShanks/QueryCraft/pull/297). Its [CHUNK-01 evidence](evidence/chunk-01-source-continuity.md) records the three-dialect HTTP matrix, focused browser decision flow, fail-closed cases, gates, cleanup, and protected-baseline confirmation.

`IS-GAP-002` is resolved on tested main `76f317b6894ffb4300133d51ad4e201ecb022d96` via [#299](https://github.com/RkShanks/QueryCraft/pull/299). Its [CHUNK-02 evidence](evidence/chunk-02-masked-attempt-state.md) records the metadata-only storage design, direct/alias/nested/row-filter matrix across three dialects, Redis/API/history/audit/browser absence checks, failure behavior, gates, and cleanup.

`IS-GAP-003` is resolved on tested product commit `4580925594c872ae0283485155bbdf4bd7e225f4` via [#301](https://github.com/RkShanks/QueryCraft/pull/301). Its [CHUNK-03 evidence](evidence/chunk-03-session-cancel.md) records durable cancellation, ownership-safe cleanup, failure/rollback races, frontend Undo/cache behavior, deterministic provider/second-worker proof, and real PostgreSQL source cancellation with DB/Redis/audit/browser inspection.

`IS-GAP-004` is resolved on tested product commit `61723e46dc267e74c7aa3539a40990b1482e9edc` via [#302](https://github.com/RkShanks/QueryCraft/pull/302). Its [CHUNK-04 evidence](evidence/chunk-04-timeout-config.md) records the shared monotonic deadline, remaining provider/source budgets, derived five-second lock grace, sanitized exactly-once timeout state, deletion precedence, real HTTP timing, three-dialect slow-query behavior, gates, and cleanup.

`IS-GAP-005` and `IS-GAP-006` are resolved on tested branch commit `d4cff9cbb1edb22b8a0bbb78bd4733151293b9c2` via [#303](https://github.com/RkShanks/QueryCraft/pull/303). Their [CHUNK-05 evidence](evidence/chunk-05-retry-quota-audit.md) records shared reject/regenerate quota boundaries, exact provider/source call and Redis counter deltas, ordered durable audit lifecycles, hash-chain verification, rollback, session-deletion/deadline compatibility, three-dialect denial behavior, sanitization and cleanup.

`IS-GAP-009` is resolved on tested branch commit `2a48ec9b0da9c7abe408cb5248104525f5350604` via [#304](https://github.com/RkShanks/QueryCraft/pull/304). Its [CHUNK-06 evidence](evidence/chunk-06-migration-cycle.md) records the complete disposable PostgreSQL 001-009 transition matrix, exact schema fingerprints/counts, revision-007 atomic refusal and explicit fixture remediation, revision-006 parent-contract restoration, model/repository smoke, concurrency behavior and zero-resource cleanup. Authoritative backend/frontend CI passed.

`IS-GAP-023`, `IS-GAP-025` and `IS-GAP-022` are resolved on tested product commit `3d2f05a6046ed1bd9f6b2a461fedd2c7f82b10db` in [#305](https://github.com/RkShanks/QueryCraft/pull/305); authoritative backend/frontend CI passed. Their [CHUNK-07 evidence](evidence/chunk-07-ui-identity-permissions.md) records generation-safe outer/feature cache isolation, late-settlement suppression, distinct 401/403 behavior, the typed eight-permission catalog, exact route/navigation/request gating, role round trips, localized access denial, same-browser switching and zero-resource cleanup.

`IS-GAP-020` is resolved on tested product commit `1a11980ad3e395bf3b65131b1d5e6ce0209a19b5` in [#306](https://github.com/RkShanks/QueryCraft/pull/306); authoritative backend/frontend CI passed on `48ad094d8b95480aa87110c4a477b63533217bd0`. Its [CHUNK-08 evidence](evidence/chunk-08-prompt-length.md) records positive configured authority, safe authenticated discovery, exact Python/browser Unicode boundaries, early no-downstream rejection, fail-closed localized prompt behavior, request deduplication, EN/AR desktop/375px Chromium proof and zero-resource cleanup.

`IS-GAP-014` is resolved on tested branch product commit `dca6ed77ab6e16a762a0c0f5a2d4286b9f58ba51` in [#307](https://github.com/RkShanks/QueryCraft/pull/307); authoritative backend/frontend CI passed on `42df59fe56e1dbebc6485b10c4ba96d936973454` and squash merge `453875adb54599dd1ba16baa10101af6427588fa` unblocked CHUNK-10. Its [CHUNK-09 evidence](evidence/chunk-09-quota-partial-success.md) records the pre-commit cross-worker fail-closed transition, sanitized post-commit partial-success response, idempotent PUT/DELETE reconciliation without timestamp/audit duplication, rollback republish, real PostgreSQL/Redis fault seams, authoritative frontend reload/retry, EN/AR desktop/375px/768px Chromium proof and zero-resource cleanup.

`IS-GAP-017` and `IS-GAP-013` are resolved on tested product commit `3b6f90dd938d51bef9e04ba4f5a57afce3335b68` in [#308](https://github.com/RkShanks/QueryCraft/pull/308); authoritative backend/frontend CI passed on `c0a74d891b3a28b8b35d405a85a1969a69ec561f`, and squash merge `09651c2c130025512d63fa4b36ef1ba51675bd73` unblocked CHUNK-11. Their [CHUNK-10 evidence](evidence/chunk-10-data-invariants.md) records revision-010 named constraints, value-safe atomic preflight/refusal, explicit repair, reversible migration cycles, direct invalid-write rejection, real concurrent singleton initialization, fail-closed quota/detection/source/provider consumers, API-only corruption/recovery, gates and cleanup.

`IS-GAP-012` is resolved on tested product commit `00b5ad8f266d7f6156a5c3ce6ed11b59c54f5652` via [#309](https://github.com/RkShanks/QueryCraft/pull/309); authoritative backend/frontend CI passed on `f17bf48ba7a829a1f77aea374de2fe7276491c6c`, and squash merge `fce00de777e400f38d53d0e20e90e38c2d7e8e5c` unblocked CHUNK-12. Its [CHUNK-11 evidence](evidence/chunk-11-session-limit.md) records real Redis atomic create/delete/refresh, deterministic sequence ordering for equal timestamps, ordered-timestamp and two-user isolation bursts, rollout score compatibility, stale-member pruning, CAS/no-resurrection refresh, local/SSO concurrency, rollback/outage behavior, gates and cleanup.

`IS-GAP-019` is resolved on tested product commit `80652b47b6a53687bbe67f849c070b8ffb9f82d0` in [#310](https://github.com/RkShanks/QueryCraft/pull/310); authoritative backend/frontend CI passed and squash merge `58098c05dfc92b7fd22b1096d38229e5c8a66f52` unblocked CHUNK-13. Its [CHUNK-12 evidence](evidence/chunk-12-collection-bounds.md) records opaque value-safe keysets, exact ownership-scoped totals, 10,000-session and 10,000-attempt traversal, one-query attempt metadata, bounded 120-role/3,000-user PostgreSQL/Redis aggregation, fail-closed counter faults, cancellable infinite queries, localized responsive browser proof and cleanup.

`IS-GAP-007` is resolved on tested product commit `1c56b6305329cbc82fff5cc4066c995f2717873b` in [#311](https://github.com/RkShanks/QueryCraft/pull/311); authoritative backend/frontend CI passed on `270ce0577c29f201f583a40c0f51a36b25984478`, and squash merge `e18d2335f44a93f055bb7d3c03f08012c91443f6` unblocked CHUNK-14. Its [CHUNK-13 evidence](evidence/chunk-13-readiness.md) records exact public probe bodies, cookie independence, bounded concurrent platform PostgreSQL/Redis/revision checks, startup/shutdown transitions, runtime outage/recovery with zero backend restarts, Compose health gating, disposable dev-up ordering and cleanup.

`IS-GAP-008` is resolved on tested product commit `9f82c73c0abe1ec07199583343e954e65fd6d358` in [#312](https://github.com/RkShanks/QueryCraft/pull/312). Its [CHUNK-14 evidence](evidence/chunk-14-openapi-parity.md) records the historical 60-operation snapshot and three later routes, exact then-current 63-operation runtime/canonical/generated parity, typed request/success/error/redirect/download/204 contracts, deterministic generation hashes, generated-derived wrapper types, all-operation Schemathesis, focused real-ASGI and Chromium checks, complete frontend gates, and cleanup. Authoritative backend/frontend CI passed on `257fbdeaa2fbba7aef2d31e8dc30ed219777b8e7`; squash merge `0cc010a59b128423169bd252aa63df2acfeb2130` unblocked CHUNK-15.

`IS-GAP-024`, `IS-GAP-026`, and `IS-GAP-035` are resolved on tested product commit `750c21fa4f70bf1f1b106396852b9be846b931dc` in [#313](https://github.com/RkShanks/QueryCraft/pull/313). Their [CHUNK-15 evidence](evidence/chunk-15-role-policy-editor.md) records the complete unsaved draft-policy endpoint and generated client, authoritative full-detail hydration, stale/refetch/save race suppression, the shared 21-case cross-dialect row-filter corpus, localized accessible preview states, exact 64-operation runtime/canonical/generated parity, real-ASGI zero-persistence/zero-execution proof, responsive EN/AR Chromium, gates and cleanup. Authoritative backend/frontend CI passed on `6cbe326b8462c8924b1a3aadd4b14c04c655b00b`; squash merge `c92255de4e0be0fde59b3f0bf3045b7115de7354` unblocked CHUNK-16.

`IS-GAP-036` is resolved and merged as `f41e8c721450adb8fd50201de6218381289f531f` in [#314](https://github.com/RkShanks/QueryCraft/pull/314); authoritative backend/frontend CI passed on `d14831e1016441d07d6736a3132e9309f78716d2`. Its [CHUNK-16 evidence](evidence/chunk-16-role-mapping-recovery.md) records one-transaction role/policy/mapping/audit persistence, duplicate/conflict/audit/commit rollback, exactly one winner under same-group concurrency, omitted/empty/no-op mapping semantics, exact audit counts, one composite role write and zero standalone mapping writes per Save, authoritative lost-response reconciliation, preserved drafts, 64-operation parity, complete local gates, and responsive EN/AR Chromium proof.

`IS-GAP-042` and `IS-GAP-033` are resolved and merged as `f29cec51cc673f2ae84ad0d60c3c62246b939c45` in [#315](https://github.com/RkShanks/QueryCraft/pull/315); authoritative backend/frontend CI passed in run `31803892021` on `1b6e53d2f18594f93822bcbd36445c94ff38b163`. Their [CHUNK-17 evidence](evidence/chunk-17-client-harness.md) records the complete 64-operation classification, generated-schema runtime validation for all 41 production-consumed JSON responses, constant payload-free contract errors, explicit EN/AR initial/background/empty/partial/retry/stale states, 28 classified Playwright specs, static harness failures for stale fixtures/tracked output, full frontend gates, and focused mocked plus real-API Chromium proof.

`IS-GAP-041`, `IS-GAP-027`, and `IS-GAP-028` are resolved on tested product commit `bbc9ef5bc6bb0b8bc2627fb36a8cbace636e6aff` in [#316](https://github.com/RkShanks/QueryCraft/pull/316), with final local verification through `85145026c15c1e8fca47706d5fa4d31abc645f7f`. Their [CHUNK-18 evidence](evidence/chunk-18-workspace-recovery.md) records semantic zero-row and 50-row client rendering, complete unique pagination, authoritative delete reconciliation, exact regenerate restoration, permission/context-aware connection recovery, the generated-contract fixture RED/GREEN, 1,141 frontend tests, 80 FastAPI compatibility tests, responsive Chromium, an unmocked authenticated FastAPI/source flow and cleanup. Authoritative backend/frontend CI passed on `6ff6ee5c2721437814963d3cce3527d3a8bcb44c` in run `32582534493`; squash merge `abd51680690714f9ae5b759271056c4873f6743f` completed and unblocked CHUNK-19.

`IS-GAP-029`, `IS-GAP-030`, and `IS-GAP-039` are resolved at product commit `21a2fcacc92edd3d37104e406068bb3b1cbf1b40` in [#317](https://github.com/RkShanks/QueryCraft/pull/317), merged as `841905cd182140b60ee1594a07baa9bbdc7012b6`. Their [CHUNK-19 evidence](evidence/chunk-19-interaction-a11y.md) records the single trigger/listbox selector keyboard model with locale-aware typeahead, active-versus-selected distinction, list-change coherence and duplicate-free auto-selection; modal connection-delete dialog semantics with focus trap, Escape-hold destructive pending state and trigger-focus restore; sibling-button session controls; status/alert toast roles with localized dismissal names; UndoToast hover/focus pause with resume-from-remainder, single-shot expiry and unmount-safe timers; and the SignInForm boundary/focus/error-association/double-submit/retry/success matrix with secret hygiene. Component coverage is 471 focused tests inside an 1,181-test full suite; Chromium proof is a four-case mocked EN/AR 1440/768/375 matrix plus one unmocked live sign-in round trip against disposable FastAPI credentials. Merge bookkeeping for [#310](https://github.com/RkShanks/QueryCraft/pull/310) at `58098c05dfc92b7fd22b1096d38229e5c8a66f52` and [#316](https://github.com/RkShanks/QueryCraft/pull/316) at `abd51680690714f9ae5b759271056c4873f6743f` was reconciled without altering historical test evidence. Authoritative backend/frontend CI passed on `21a2fcacc92edd3d37104e406068bb3b1cbf1b40`; squash merge `841905cd182140b60ee1594a07baa9bbdc7012b6` via [#317](https://github.com/RkShanks/QueryCraft/pull/317) completed and unblocked CHUNK-20.

`IS-GAP-032` and `IS-GAP-038` are resolved and merged at main `48f775834a9c2c1fa3f4c2ea95132c1ff287d119` via [#318](https://github.com/RkShanks/QueryCraft/pull/318). Their [CHUNK-20 evidence](evidence/chunk-20-history-locale.md) records the bounded trimmed literal-substring history search with escaped wildcards and bound parameters, hash-bound opaque cursors that reject cross-filter replay while accepting legacy unfiltered cursors, filtered first-page totals and audit privacy; server-side frontend search with filter-bound query keys and stale-response isolation, derived selection reconciliation, panel-scoped errors, localized no-match/loading-more states and a semantic list of independent aria-pressed buttons replacing focusable divs and fake columnheaders; plus locked locale precedence (?lng= → persisted → navigator → html lang → en), ar-EG/en-US variant normalization, authoritative manual switching with stale-parameter rewrite, storage-unavailable fallbacks, an accessible EN/Arabic toggle in both shells and active-locale date/number formatting with preserved LTR SQL/code isolation. Coverage is 28 new backend tests inside the 2,561-test unit suite, 13 integration tests on a disposable PostgreSQL stack, 64 Schemathesis subtests, 52+36 focused frontend suites inside a 1,232-test full run, a six-case mocked EN/ar/ar-EG 1440/768/375 Chromium matrix and two live real-FastAPI paginated-search cases against disposable seeded records.
`IS-GAP-043`, `IS-GAP-037` and `IS-GAP-031` are resolved and merged at main `74aa30481377321c6178d0523ab593c697525725` via [#319](https://github.com/RkShanks/QueryCraft/pull/319). Their [CHUNK-21 evidence](evidence/chunk-21-browser-async.md) records one request-scope utility giving query submit/accept/reject/regenerate owned controllers with wire-level aborts on unmount, route/session/user replacement and CHUNK-03 deletion, late-settlement suppression without error/toast/stale state, the preserved `session_deleted` precedence, CHUNK-04's authoritative backend deadline with no client query deadline, one documented bounded ordinary deadline across the previously signal-dropping queries with a localized recoverable timeout, a longer documented export deadline with explicit Cancel and exactly-once resource cleanup, a location-keyed sanitized route boundary inside the authenticated shell with retry and permission-aware navigation, navigation-scoped timer cleanup for Workspace alerts and audit toasts, one shared bounded clipboard contract across CodeBlockActionBar and HistoryDetail and contained lazy-Shiki fallbacks keeping readable plain-text LTR SQL. Coverage is seven RED/GREEN/gate commits inside a 1,283-test full Vitest run (up from 1,232), ESLint/typecheck/build/CSS-lint/gen-parity/harness guards with 36 classified specs, 37 backend compatibility unit tests plus Ruff, a six-case mocked Chromium matrix and two live cases against a disposable FastAPI stack destroyed afterward.
`IS-GAP-034` is resolved and merged at main `e4c3ca5aac856b6c73c41c931331bf3a482a57a5` via [#320](https://github.com/RkShanks/QueryCraft/pull/320). Its [CHUNK-22 evidence](evidence/chunk-22-audit-download.md) records applied-filter authority, safe server filename/media handling, cancellation/retry/no-partial-file behavior, 1,327 frontend tests, backend export/search/OpenAPI groups, complete local frontend gates, 4/4 mocked Chromium cases, two real CSV/JSON browser downloads with checksum/redaction inspection and disposable-stack cleanup. Authoritative CI run `32738202877` passed backend-test and frontend-test; merge and cleanup completed.
These decisions block only `CHUNK-30` and `CHUNK-31`. All product chunks through `CHUNK-23` are now merged; `CHUNK-20` merged as `48f775834a9c2c1fa3f4c2ea95132c1ff287d119` via [#318](https://github.com/RkShanks/QueryCraft/pull/318), and CHUNK-23 merged as `2114f8a8ef2f20141c0a43d87cb81b1a3ff1c758` via [#322](https://github.com/RkShanks/QueryCraft/pull/322) with authoritative backend/frontend CI passing in run `32773267333`.

`IS-GAP-044` and `IS-GAP-016` are resolved and merged at main `2114f8a8ef2f20141c0a43d87cb81b1a3ff1c758` via [#322](https://github.com/RkShanks/QueryCraft/pull/322). Their [CHUNK-23 evidence](evidence/chunk-23-auth-idp.md) records the distinct accessible provider loading/configured/empty/failure+retry states, sanitized invalid-callback mapping, double-submit suppression, rejected sign-out retry and confirmed sign-out boundaries, a reproduced-and-fixed rejected-sign-in visibility defect, and the disposable isolated HTTPS OIDC/SAML IdP proof: real-browser redirect/callback flows, signing-key and certificate rotation without restart, retired-material rejection, claim/assertion negatives, replay, outage and recovery under strict TLS with zero auth material in any channel. Authoritative CI run `32773267333` passed backend-test and frontend-test; branch deletion and synchronized main completed.

`IS-GAP-015` is **Partial** via CHUNK-24 from synchronized main `1bfc245448e2ff4dd7b2111065ee7ce04bdff7e9` (RED `542bd34`, GREEN `81fc501`). Its [CHUNK-24 evidence](evidence/chunk-24-provider-matrix.md) records a 44-case deterministic matrix covering selection/normalization, factory routing, missing/malformed configuration, unsupported providers, invalid base URLs/models, timeout/cancellation propagation, HTTP/API failures, sanitized error mapping, no-unintended-fallback, no-secret-retention and cross-adapter query-composition compatibility (P1-FR-009, P1-FR-026, P2-FR-047, XP-014); one confirmed in-gap defect where the Anthropic/OpenAI/Ollama adapters leaked raw framework exceptions on malformed 200 bodies and 4xx responses was fixed by mirroring GeminiAdapter's typed sanitized constant-message mapping with no signature changes and Gemini untouched. Gates: focused suites 143 passed, full backend unit foundation 2240 passed/365 skipped, Ruff/format/diff-check clean. The required one-benign-live-request-per-provider evidence is Setup-dependent for all three providers — Anthropic has no credentials, Ollama is not installed locally, and the OpenAI credential's cost/invocation approval was declined by the owner — so the gap is Partial, not Resolved, with zero external spend and zero invocations.

Existing evidence narrows the remaining work but does not close another unique consolidated root cause:

- CHUNK-07 closes the identity/cache/permission slice with joint same-browser cache, DOM, accessibility, storage, network and console inspection. IS-GAP-047 remains open because its broader hostile/error/download privacy flow still depends on other unresolved gaps.
- CHUNK-08 closes the primary Workspace prompt-length contract. The reachable legacy `/ask` disposition remains open under IS-GAP-045/CHUNK-31. CHUNK-14 now closes canonical OpenAPI/client regeneration under IS-GAP-008.

## Decision ledger

- `IS-GAP-010`: assign security/cache-header ownership between backend and reverse proxy. Title work remains required under either choice.
- `IS-GAP-011`: choose production access policy for `/docs`, `/redoc`, `/openapi.json`, and `/docs/oauth2-redirect`.
- `IS-GAP-045`: decide whether `/ask` redirects/retires or remains a fully supported compatibility UI.

These decisions block only `CHUNK-30` and `CHUNK-31`. All product chunks through `CHUNK-23` are now merged; `CHUNK-20` merged as `48f775834a9c2c1fa3f4c2ea95132c1ff287d119` via [#318](https://github.com/RkShanks/QueryCraft/pull/318), and CHUNK-23 merged as `2114f8a8ef2f20141c0a43d87cb81b1a3ff1c758` via [#322](https://github.com/RkShanks/QueryCraft/pull/322) with authoritative backend/frontend CI passing in run `32773267333`.

## Validation scope

The original consolidation used only source/caller/assertion inspection, read-only app-factory OpenAPI generation, JSON/accounting/path/parity/cycle/size/secret checks and diff validation. CHUNK-06 separately ran the migration, persistence and cleanup gates recorded in its linked evidence. CHUNK-07 separately ran the frontend unit/build gates and mocked plus isolated live Chromium evidence recorded in its linked evidence. CHUNK-08 separately ran configured backend boundaries, the backend unit foundation, full frontend gates, isolated HTTP 200/401/403/400 proof and EN/AR desktop/375px Chromium evidence recorded in its linked evidence. CHUNK-09 separately ran real PostgreSQL/Redis transition/publication fault seams, cross-worker enforcement and retry races, quota/audit regressions, full frontend gates and EN/AR desktop/375px/768px Chromium recovery evidence recorded in its linked evidence. CHUNK-10 separately ran the complete disposable migration matrix, named direct-write constraints, atomic refusal/repair, real singleton concurrency, fail-closed consumers, API-only corruption/repair/retry and backend foundation gates recorded in its linked evidence. CHUNK-11 separately ran real Redis atomic session-lifecycle concurrency and cleanup. CHUNK-12 separately ran 10,000-row session/attempt traversal, bounded PostgreSQL/Redis aggregation, counter/cancellation/permission faults, complete frontend gates and EN/AR desktop/768px/375px isolated Chromium proof. CHUNK-13 separately ran exact ASGI/lifecycle tests, isolated Compose platform-dependency and revision transitions, excluded-dependency availability, disposable script ordering, complete local backend/frontend gates and cleanup. CHUNK-14 separately ran exact current-source/canonical/generated parity, deterministic two-run generation, 63-operation Schemathesis, focused real-ASGI and Chromium checks, complete frontend gates and cleanup. CHUNK-15 separately ran shared draft/persisted evaluator tests, a 21-case backend/frontend row-filter corpus, hydration races, 64-operation generation parity, real-ASGI zero-persistence/execution proof, complete frontend/backend gates, and EN/AR desktop/768px/375px isolated Chromium checks. CHUNK-16 separately ran real PostgreSQL composite transaction, fault/concurrency and exact-audit-count tests, one-write client recovery tests, unchanged 64-operation parity, complete backend/frontend gates, and EN/AR 1440/768/375 Chromium checks. CHUNK-17 separately ran generated-schema response fault matrices, named response-state and leakage assertions, a classified static harness guard, complete frontend gates and focused mocked plus real-API Chromium checks. CHUNK-18 separately ran its full frontend and focused recovery gates, FastAPI compatibility tests, 1440/768/375 EN/AR Chromium recovery matrix, unmocked authenticated FastAPI/source query flow and disposable-runtime cleanup.
