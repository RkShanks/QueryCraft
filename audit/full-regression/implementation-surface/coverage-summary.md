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
| Pending | 44 |
| Closed by Existing Evidence | 0 |
| Needs Decision | 3 |
| **Total** | **47** |

Existing evidence is substantial and narrows the required work, but it does not close a unique consolidated root cause:

- Current cross-phase source-selection evidence covers initial submit and accepted/rerun paths, not the public reject/regenerate reconstruction defect.
- Masking evidence covers response/history, not raw pre-mask Redis attempt state.
- Phase 2 session evidence proves CRUD/cascade and frontend timer Undo, not in-flight cancellation.
- Timeout evidence proves default failure shape, not configured non-default behavior.
- Phase 6 quota and audit evidence covers initial submit/export and sanitized retry failure, not retry accounting and successful regenerate lifecycle.
- Final browser privacy evidence genuinely covers API/UI/audit/export/log/storage/accessibility slices, but not a single joint same-browser cache/console/network/download flow after failed or implicit identity change.

## Decision ledger

- `IS-GAP-010`: assign security/cache-header ownership between backend and reverse proxy. Title work remains required under either choice.
- `IS-GAP-011`: choose production access policy for `/docs`, `/redoc`, `/openapi.json`, and `/docs/oauth2-redirect`.
- `IS-GAP-045`: decide whether `/ask` redirects/retires or remains a fully supported compatibility UI.

These decisions block only `CHUNK-30` and `CHUNK-31`. `CHUNK-01` through the confirmed security/data-integrity sequence are unblocked for a future authorized remediation phase.

## Validation scope

This consolidation used only source/caller/assertion inspection, read-only app-factory OpenAPI generation, JSON/accounting/path/parity/cycle/size/secret checks and diff validation. It did not run product tests, builds, Playwright, browsers, live services, migrations or remediation.
