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

The stale, uncalled `backend/scripts/update_openapi_phase5.py` is a dead maintenance surface inside the broader confirmed contract gap `IS-GAP-008`; it is not counted again as a separate dead-code gap. The reachable legacy `/ask` route is not declared dead until `IS-GAP-045` is decided.

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
| Pending | 34 |
| Resolved | 10 |
| Closed by Existing Evidence | 0 |
| Needs Decision | 3 |
| **Total** | **47** |

`IS-GAP-001` is resolved on tested main `3522440f0bbf3c837aafe62edaf2e9d89d4717fb` via [#297](https://github.com/RkShanks/QueryCraft/pull/297). Its [CHUNK-01 evidence](evidence/chunk-01-source-continuity.md) records the three-dialect HTTP matrix, focused browser decision flow, fail-closed cases, gates, cleanup, and protected-baseline confirmation.

`IS-GAP-002` is resolved on tested main `76f317b6894ffb4300133d51ad4e201ecb022d96` via [#299](https://github.com/RkShanks/QueryCraft/pull/299). Its [CHUNK-02 evidence](evidence/chunk-02-masked-attempt-state.md) records the metadata-only storage design, direct/alias/nested/row-filter matrix across three dialects, Redis/API/history/audit/browser absence checks, failure behavior, gates, and cleanup.

`IS-GAP-003` is resolved on tested product commit `4580925594c872ae0283485155bbdf4bd7e225f4` via [#301](https://github.com/RkShanks/QueryCraft/pull/301). Its [CHUNK-03 evidence](evidence/chunk-03-session-cancel.md) records durable cancellation, ownership-safe cleanup, failure/rollback races, frontend Undo/cache behavior, deterministic provider/second-worker proof, and real PostgreSQL source cancellation with DB/Redis/audit/browser inspection.

`IS-GAP-004` is resolved on tested product commit `61723e46dc267e74c7aa3539a40990b1482e9edc` via [#302](https://github.com/RkShanks/QueryCraft/pull/302). Its [CHUNK-04 evidence](evidence/chunk-04-timeout-config.md) records the shared monotonic deadline, remaining provider/source budgets, derived five-second lock grace, sanitized exactly-once timeout state, deletion precedence, real HTTP timing, three-dialect slow-query behavior, gates, and cleanup.

`IS-GAP-005` and `IS-GAP-006` are resolved on tested branch commit `d4cff9cbb1edb22b8a0bbb78bd4733151293b9c2` via [#303](https://github.com/RkShanks/QueryCraft/pull/303). Their [CHUNK-05 evidence](evidence/chunk-05-retry-quota-audit.md) records shared reject/regenerate quota boundaries, exact provider/source call and Redis counter deltas, ordered durable audit lifecycles, hash-chain verification, rollback, session-deletion/deadline compatibility, three-dialect denial behavior, sanitization and cleanup.

`IS-GAP-009` is resolved on tested branch commit `2a48ec9b0da9c7abe408cb5248104525f5350604` via [#304](https://github.com/RkShanks/QueryCraft/pull/304). Its [CHUNK-06 evidence](evidence/chunk-06-migration-cycle.md) records the complete disposable PostgreSQL 001-009 transition matrix, exact schema fingerprints/counts, revision-007 atomic refusal and explicit fixture remediation, revision-006 parent-contract restoration, model/repository smoke, concurrency behavior and zero-resource cleanup. Authoritative backend/frontend CI passed.

`IS-GAP-023`, `IS-GAP-025` and `IS-GAP-022` are resolved on tested product commit `3d2f05a6046ed1bd9f6b2a461fedd2c7f82b10db`; PR/CI pending. Their [CHUNK-07 evidence](evidence/chunk-07-ui-identity-permissions.md) records generation-safe outer/feature cache isolation, late-settlement suppression, distinct 401/403 behavior, the typed eight-permission catalog, exact route/navigation/request gating, role round trips, localized access denial, same-browser switching and zero-resource cleanup.

Existing evidence narrows the remaining work but does not close another unique consolidated root cause:

- CHUNK-07 closes the identity/cache/permission slice with joint same-browser cache, DOM, accessibility, storage, network and console inspection. IS-GAP-047 remains open because its broader hostile/error/download privacy flow still depends on other unresolved gaps.

## Decision ledger

- `IS-GAP-010`: assign security/cache-header ownership between backend and reverse proxy. Title work remains required under either choice.
- `IS-GAP-011`: choose production access policy for `/docs`, `/redoc`, `/openapi.json`, and `/docs/oauth2-redirect`.
- `IS-GAP-045`: decide whether `/ask` redirects/retires or remains a fully supported compatibility UI.

These decisions block only `CHUNK-30` and `CHUNK-31`. `CHUNK-08` is next after the CHUNK-07 PR passes authoritative CI and merges; no CHUNK-08 work has started.

## Validation scope

The original consolidation used only source/caller/assertion inspection, read-only app-factory OpenAPI generation, JSON/accounting/path/parity/cycle/size/secret checks and diff validation. CHUNK-06 separately ran the migration, persistence and cleanup gates recorded in its linked evidence. CHUNK-07 separately ran the frontend unit/build gates and mocked plus isolated live Chromium evidence recorded in its linked evidence.
