# CHUNK-17 / IS-GAP-042 + IS-GAP-033 — client response contracts and harness fidelity

Status: implementation and local verification passed on product commit `30621830633e5131960d41e0e6e46c05b1f8e1e4`; authoritative `backend-test` and `frontend-test` passed in run `31803892021` on PR head `1b6e53d2f18594f93822bcbd36445c94ff38b163`; squash merge is pending in [#315](https://github.com/RkShanks/QueryCraft/pull/315).

Starting main was `f41e8c721450adb8fd50201de6218381289f531f`, the squash merge of [#314](https://github.com/RkShanks/QueryCraft/pull/314). No product endpoint or backend behavior changed.

The machine-readable [JSON evidence](chunk-17-client-harness.json) records the exact operation classifications, response families, fault/state matrix, browser classifications, TDD commits, gates and protected-baseline counts.

## Authoritative response boundary

Canonical `backend/openapi.json` remains authoritative. The pinned generator emits the SDK, generated component schemas and a machine-checked response-operation manifest. Runtime, canonical and generated operation parity remains **64 = 64 = 64** across 48 application paths.

| Classification | Operations |
| --- | ---: |
| Consumed JSON requiring runtime validation | 41 |
| 204 / no body | 8 |
| Redirect / browser navigation | 4 |
| Blob / download | 1 |
| Generated but intentionally unused | 10 |
| **Total** | **64** |

Every one of the 41 production-consumed JSON operations passes through the generated fetch boundary before reaching TanStack Query, component state, Zustand, browser storage or a success callback. AJV 2020 validation uses generated component schemas derived from canonical OpenAPI. Generated schema sanitization strips unknown properties before returning the value; response-only schemas continue to omit connection passwords and unmasked SSO secrets.

Schema validation and small generated-type-based semantic refinements cover:

- query submit/reject/regenerate unions, result row/column dimensions and counters;
- session list/detail/connection responses, timestamps, totals and cursors;
- history list/detail timestamps, totals and cursors;
- user connections and admin connection/detail/schema lifecycle values;
- authentication profiles, settings and query limits;
- SSO provider and group-mapping responses;
- roles, policies and draft/persisted policy-test responses;
- audit status/search/retention pagination and timestamps;
- quota lists/status dimensions, counters, reset times and cursors;
- detection configuration thresholds, ordering and timestamps.

Missing, wrong-type, enum-invalid, nested malformed and semantic-invalid responses throw only `ClientContractError` with constant code `client_contract_invalid_response`. The error carries no payload. The malformed value is not returned, cached, stored, rendered, logged or attached. Ordinary API errors still pass through the canonical sanitized error schema.

## State and fault matrix

| State or fault | Assertion-bearing result |
| --- | --- |
| Initial loading, no prior data | Existing page loading surfaces remain visible until a validated result or sanitized error settles. |
| Valid empty | Explicit localized empty copy renders; it is not treated as an error or partial result. |
| Valid partial/paginated | Accessible polite status announces that more results are available. |
| Background refresh | Prior validated data remains visible with an accessible refreshing announcement. |
| Malformed initial response | Localized EN/AR contract alert renders with one explicit Retry; automatic retry is disabled for contract errors. |
| Malformed background response | Prior validated data remains visible with a localized contract-refresh alert and Retry. |
| Ordinary sanitized API error | Existing localized ordinary error path remains distinct from contract failure. |
| Explicit retry | The Retry action issues one new request and can transition to valid empty or valid data. |
| Late/stale response | AbortSignal propagation and TanStack query-key ownership prevent the older response from replacing newer valid state. |
| Invalid timestamp/enum/counter/dimension/cursor/union/nullability | Validation fails before render; no render exception occurs. |
| Unknown canary fields | Stripped before state/cache; absent from DOM, accessibility text, storage and console. |

The shared `ClientQueryState` is applied to current connections, SSO, roles/policies, audit, quotas and detection admin surfaces, plus session/history/user-connection consumers identified by FE-GAP-016. Workspace query limits retain their existing safe localized retry surface while using the same validated response boundary.

## Harness fidelity

`npm run test:harness` runs a RED/GREEN-tested static guard and fails on:

- a Playwright spec without a mocked/live/deterministic-provider/setup-dependent/deferred-placeholder classification and reason;
- a browser mock or shared mock helper without classification;
- an intentional skip without both a reason and superseding evidence;
- tracked audit/spec screenshot, trace or video destinations;
- stale `history.read` permissions;
- function-existence assertions that do not observe behavior or a named state.

MSW fixtures touched by this chunk use generated response types with `satisfies` or generated-type builders. The i18n error helper inspects the intended current error/empty state before any navigation. Historical screenshot writers now use `testInfo.outputPath`; no test writes to protected audit/spec evidence.

All 28 Playwright specs are classified: 24 mocked, one live, one deterministic-provider and two setup-dependent. There are no deferred-placeholder specs. One shared mock helper is classified. Both intentional skips have a recorded reason and superseding evidence.

## TDD commits

| Stage | Commit |
| --- | --- |
| RED generated response boundary | `d7f84ad25d68016ea4a317f4bf2e8fcbd37b65a7` |
| GREEN canonical response validation | `fce50ef1a7ac89e510b692c71866d84f38b8ef3c` |
| RED malformed UI states | `bde094ce5000337545c9a23a8e6c52e74ef4a8de` |
| RED session states | `de5dc54a907a533241ff557bd91d4584b781043a` |
| RED constant client-contract error | `6102791bc39f7f65360fdab7b97ae0d3e6abb600` |
| RED harness guard | `bce7dc567472ba334229b4310f94e27d9f877546` |
| GREEN validated client response states | `858c01049197e1786e9d78c84faafb569c3e4e56` |
| RED audit partial state | `93b2debfdf5a1e6b951e751bcb2462734d75330a` |
| GREEN audit partial state | `d931083e61b847d71e52bf7915fbd7bca62e15e4` |
| RED explicit contract retry | `b8ed08833123920891a827556740624c79d086e8` |
| GREEN immediate malformed surface | `69cc253fe5bb35ac6c75f3ec1b9428320b72a5a8` |
| RED Chromium contract states | `d98870bcfd44a0ee65a1f74e5c85a03056221fa1` |
| GREEN valid-data preservation | `241ce9568912954e057312ed9c6b4fb526310626` |
| GREEN harness fidelity | `2bade7e1ea3916389840aa5c8ccb39a7b741d4b8` |
| Full-suite stale-fixture correction | `1a3415a09277a40d5c3b335ab79839d0b71c1a92` |
| Production-build contract correction | `30621830633e5131960d41e0e6e46c05b1f8e1e4` |

A separate REFACTOR commit was not warranted; required production and harness behavior remained clearer as GREEN/gate corrections.

## Browser proof

Classification: focused Playwright Chromium only; no broad visual sweep, source query or paid LLM call.

The mocked contract spec passed three tests in 4.5 seconds:

- EN malformed initial response, payload isolation, accessible alert and successful explicit retry;
- AR/RTL malformed initial response, payload isolation, localized alert and successful explicit retry;
- valid partial audit data, background refresh, malformed-background preservation, valid empty, and late-response suppression.

The canary was absent from DOM text, the accessibility snapshot, local/session storage and captured console messages. Unit integration additionally inspected the TanStack Query cache and confirmed the malformed canary was absent while prior validated data remained.

The live spec passed one test in 2.3 seconds against the real FastAPI `GET /api/v1/auth/sso/providers` response with the development PostgreSQL/Redis services. The documented Compose image rebuild was blocked by a transient external package-repository response, so the migrated API was started locally with only service-host overrides and stopped immediately after proof.

## Local gates

| Gate | Result |
| --- | --- |
| Runtime/canonical/generated OpenAPI parity | 64 = 64 = 64 |
| Canonical OpenAPI tests | 21 passed in 2.78s |
| Canonical and generated-client deterministic checks | Passed |
| Static harness guard | Passed; 28 specs classified |
| Focused contract/page tests after build corrections | 52 passed |
| Full Vitest | 1,086 passed across 76 files in 12.75s |
| ESLint | Passed |
| TypeScript no-emit typecheck | Passed |
| Production build | Passed; existing large-chunk advisory only |
| CSS lint | Passed |
| Mocked Chromium | 3 passed in 4.5s |
| Live Chromium | 1 passed in 2.3s |
| Test Guard / Clean Code Guard / Vercel React guidance | Passed |
| Docs Guard | Passed; source, artifact, count, commit and command claims reconciled |
| `git diff --check` | Passed |
| Authoritative GitHub CI | `backend-test` and `frontend-test` passed in run `31803892021` on `1b6e53d2f18594f93822bcbd36445c94ff38b163` |

## Cleanup and next gate

The temporary local API process was stopped. Ignored browser reports, screenshots, videos and production-build output were removed. The protected baseline remains exactly 14 modified tracked PNGs, seven historical untracked screenshots and two trace archives; none has been staged, regenerated, reverted or deleted.

CHUNK-18 remains blocked until this focused PR is squash-merged, its branch is deleted and local main is synchronized.
