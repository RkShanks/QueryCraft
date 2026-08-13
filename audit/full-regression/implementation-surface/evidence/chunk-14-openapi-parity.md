# CHUNK-14 / IS-GAP-008 — canonical OpenAPI and generated client

Status: implementation and local verification passed on branch `phase-6/wave-19.14-openapi-canonical`; PR creation and authoritative GitHub CI are pending.

Starting main: `e18d2335f44a93f055bb7d3c03f08012c91443f6`. Tested product commit: `9f82c73c0abe1ec07199583343e954e65fd6d358`.

The machine-readable [JSON evidence](chunk-14-openapi-parity.json) records every method/path and generated operation ID, generation hashes, contract checks, gates, browser/API classification, and cleanup.

## Inventory correction and exact parity

The August 2 implementation-surface snapshot correctly observed 60 application operations across 44 paths at that commit. Current main added three operations afterward: `GET /api/v1/query/limits`, `GET /health`, and `GET /ready`. CHUNK-14 therefore derives its target from current source and proves **63 runtime = 63 canonical = 63 generated operations** across 47 application paths. Nothing was deleted, hidden, or excluded to satisfy the historical 60-operation statement.

Four framework documentation helpers—`/docs`, `/docs/oauth2-redirect`, `/openapi.json`, and `/redoc`—are not application operations and remain outside the count. The exact sorted 63-row source/canonical/generated mapping is in `operation_sets.operations` in the JSON evidence. Its normalized method/path set hash is `ad09220c9cbc795a39c6d132a285c4f6dbd98bfb33c25e018c1db349279be5de`; the operation-ID set hash is `a9a9479e78d887263c80c16c154ded08e10ded9dcbdef1b30d68f1fa73ef8500`.

| Method | Operations |
| --- | ---: |
| DELETE | 7 |
| GET | 28 |
| PATCH | 3 |
| POST | 20 |
| PUT | 5 |
| **Total** | **63** |

## Authoritative contract

`create_app()` now rejects startup-time OpenAPI metadata when its current application route set differs from the stable operation-ID registry. The same runtime schema builder serves FastAPI OpenAPI and feeds deterministic `backend/openapi.json` generation. Contract tests and the locked frontend generator consume that artifact; the Phase 1 static contract is no longer the active Schemathesis or client-generation input.

Parity assertions compare every request-body schema/content map and every response status/schema/content map between runtime and the checked-in artifact. Focused assertions additionally lock:

- typed JSON bodies for query submit/accept/reject/regenerate, quota upsert, and audit export;
- typed success responses, query success unions, evaluator rejection, pagination, query limits, quota synchronization, and public health/readiness;
- sanitized validation, ordinary error, quota, and readiness schemas for implemented statuses;
- OIDC/SAML 302 responses with `Location` and no body, plus the SAML callback form fields and media type;
- audit CSV/JSON download media types, binary schemas, and `Content-Disposition`;
- eight empty 204 responses without declared response content.

The full canonical Schemathesis gate exercised all 63 operations and passed 63 subtests. It uses public or unauthenticated behavior to avoid mutation while validating each operation against the authoritative artifact.

## Deterministic generation and client impact

Two backend generator runs were byte-identical to each other and the checked-in canonical artifact. Two frontend generator runs were byte-identical to each other and the checked-in generated tree. The canonical SHA-256 is `def61239a3dd37d07b5ec0a8efe0e16da6d1b138957ddda4dae4137647fb2e01`; the deterministic 16-file generated manifest hash is `4df1ae13e74ee458b06d15da10addf3332a390cd1abfd46eab389fada917f8f3`. Per-file hashes are recorded in the JSON evidence.

Frontend generation uses the installed, locked `@hey-api/openapi-ts@0.95.0` package programmatically and performs no `npx` download. CI fails if either `backend/openapi.json` or `frontend/src/api/generated/` drifts.

The generated SDK exports exactly the 63 canonical operation IDs. Existing names were preserved where practical. Callers now use canonical path-parameter names and generated request/response types. Custom wrappers remain only for Blob parsing, cancellation, query normalization, quota synchronization, and runtime defensive parsing; their public types derive from generated contract types. Cookie credentials remain enabled. OIDC/SAML provider buttons still assign `window.location.href`; generated redirect functions did not replace browser navigation.

Caller search found no required non-audit/spec caller of `backend/scripts/update_openapi_phase5.py`, so the uncalled historical mutator was removed after the runtime generator and parity gates were green.

## Browser and API checks

Browser classification: real Chromium with mocked HTTP boundaries. Six focused cases passed in 8.9 seconds. The CHUNK-14 probe observed canonical `/api/v1/auth/me` and SSO-provider requests, then proved an OIDC provider click navigated the browser through the declared 302 path. Existing focused EN/AR desktop and 375px browser contracts proved query-limit discovery, submit gating/deduplication, sanitized limit failure, and explicit retry. No visual sweep, screenshot evidence, or paid LLM call was used.

API classification: real ASGI with local PostgreSQL and Redis for authentication, current-user, admin settings JSON, and audit CSV/JSON downloads; isolated endpoint seams for query submit and redirect behavior. Eleven database-backed integration checks passed, and the focused backend batch covered query limits/submit plus OIDC/SAML redirects. CSV returned `text/csv` with an attachment filename; JSON returned `application/json` with an attachment filename.

## TDD commits

| Stage | Commit |
| --- | --- |
| RED backend canonical parity | `4c6c0eb18f4dbee1c5b8e9039a146b39c00f6ac6` |
| RED query validation correction | `6ce7248587021f96bcd03a580a9ece1a91b5dc3d` |
| RED readiness degradation classification | `ef43fd6fce4562e6c28b0df798b1d97e93323604` |
| GREEN runtime canonical artifact | `892ac48200fa9a216c630b548270e873a24f48e6` |
| RED generated client parity | `a25945716ea77c96010cffca9c3cd118a5d6b1af` |
| GREEN generated client and callers | `9f82c73c0abe1ec07199583343e954e65fd6d358` |
| REFACTOR complete schema/content parity | `fe25c3bd185ba83dc79107da1f04bd27680e90c4` |

## Gates

| Gate | Result |
| --- | --- |
| Canonical parity unit tests | 19 passed |
| Focused OpenAPI, query, redirect, sanitization, and audit tests | 90 passed in 21.23s |
| Role/group typed-response regression | 78 passed in 0.65s |
| Focused database-backed API integration | 11 passed in 3.38s |
| Full canonical Schemathesis | 1 test and 63 operation subtests passed in 8.08s |
| Focused generated-client/API/hook tests | 6 files, 48 tests passed in 2.53s |
| Full frontend Vitest | 73 files, 984 tests passed in 10.75s |
| Deterministic canonical generation | passed |
| Deterministic frontend generation | passed |
| ESLint | passed |
| TypeScript no-emit typecheck | passed |
| Production build | passed; existing chunk-size advisory only |
| CSS lint | passed |
| Ruff check | passed for configured `src tests` scope plus the new generator |
| Ruff format check | 452 files formatted |
| Focused Chromium | 6 passed in 8.9s |
| Test Guard | passed with no unresolved findings |
| Clean Code Guard | passed with no unresolved findings |
| Docs Guard | passed with source/artifact/command assertions verified; PR/CI fields remain explicitly pending |
| JSON validation | passed for evidence and consolidated matrix |
| `git diff --check` | passed |
| GitHub backend-test | pending |
| GitHub frontend-test | pending |

## Cleanup and protected baseline

- Temporary generated comparisons and Playwright output under `/tmp` were removed; the temporary browser probe source was also removed.
- No real provider or paid LLM call ran. The local platform PostgreSQL/Redis services were reused. CHUNK-14 created no containers, networks, or volumes; all temporary screenshots, video, traces, and comparison outputs from the focused browser/generation checks were removed.
- The protected baseline remains exactly 14 modified tracked PNGs, seven historical untracked screenshots, and two untracked trace archives. None was edited, staged, regenerated, deleted, or reverted by CHUNK-14.
- Evidence contains only paths, schemas, statuses, counts, hashes, booleans, durations, and commit IDs; it retains no credentials, cookies, request values, database rows, raw errors, logs, screenshots, videos, or traces.

CHUNK-15 becomes unblocked only when the focused CHUNK-14 PR passes authoritative backend/frontend CI and is squash-merged.
