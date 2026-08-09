# CHUNK-08 configured primary prompt-length evidence

Status: local backend, frontend, isolated API and real-browser proof passed on tested product commit `1a11980ad3e395bf3b65131b1d5e6ce0209a19b5`; authoritative `backend-test` and `frontend-test` passed on `48ad094d8b95480aa87110c4a477b63533217bd0` in [#306](https://github.com/RkShanks/QueryCraft/pull/306). Squash merge is the remaining CHUNK-09 dispatch gate.

Starting main: `8581ac25ad38b006488b80a92c7f2b27916c2416`.

## Outcome

`IS-GAP-020` is resolved on the tested branch. `Settings.MAX_QUESTION_LENGTH` is validated as a positive integer and is the only runtime limit authority. Authenticated callers with `query.submit` can discover only `max_question_length` through `GET /api/v1/query/limits`; unrelated settings, environment values and provider configuration are absent.

`POST /api/v1/query/submit` receives a canonically trimmed question, measures Unicode code points against the current setting, and rejects over-limit input before constructing the query service. The rejection keeps the existing sanitized `error.validation.questionTooLong` contract and contains no submitted text.

Workspace loads the authenticated contract through one permission-gated TanStack query. PromptInput fails closed while the limit is loading or unavailable, exposes localized retry, counter and error states, preserves invalid text for correction, and never truncates. Button and Enter submission are blocked above the limit; Shift+Enter remains a newline, composition Enter remains inert, and an immediate in-flight lock deduplicates rapid submission.

## Cross-runtime canonicalization

- Python schema canonicalization remains authoritative for edge trimming.
- Browser canonicalization mirrors the Python 3.12 edge-whitespace code-point set rather than relying on JavaScript `trim()`, whose edge set differs.
- Python `len()` and browser `Array.from(...).length` agree for the asserted ASCII, Arabic and non-BMP cases.
- The focused matrix covered limit−1, limit, limit+1, surrounding whitespace, Python-only edge whitespace, browser-only whitespace and Arabic/non-BMP boundaries.
- Accepted boundary inputs reached the deterministic service boundary with canonical length only. Rejected boundary inputs constructed no service and made no database or Redis calls.

## API contract

The response model has one positive-integer field:

```json
{"max_question_length":37}
```

Isolated live status and safe-shape observations:

| Case | Status | Safe result |
| --- | ---: | --- |
| No session | 401 | `error.unauthorized` |
| Authenticated without `query.submit` | 403 | `error.forbidden` |
| Authenticated with `query.submit` | 200 | one key; configured value 37 |
| Canonical length 38 with configured value 37 | 400 | `error.validation.questionTooLong` |

The live over-limit request was observed after authentication and before any query pipeline state changed. Database counts before/after were `accepted_queries=0`, `sessions=0`, `audit_entries=3`; the audit count includes the preceding authentication/authorization proof and remained unchanged by the length rejection. Redis counts before/after were zero for attempt, active-attempt, processing-lock, session-operation and quota key families. Focused router tests additionally assert zero query-service construction, which keeps detection, provider and source boundaries unreachable.

## Frontend behavior

- The client strictly accepts one positive integer and treats missing, zero, negative, fractional or string values as a failed contract.
- Query-limit discovery is enabled only for `query.submit` and participates in the exact permission-request matrix.
- The counter and localized over-limit alert are connected to the textarea with `aria-describedby`; `aria-invalid` tracks correction and recovery.
- Loading and failed discovery disable prompt submission. Failure renders a sanitized localized retry action and never falls back to 2000.
- Over-limit paste, button activation and Enter produced zero submit requests while retaining the same code-point length in the textarea.
- Correction to the configured boundary submitted once. Rapid/double activation at the boundary produced exactly one request.
- Logical CSS, localized EN/AR text and the 375px layout kept the prompt container inside the viewport.

## TDD history

- RED `92da38c909f3f8f61e36e6c8a42a71e44c8773c3` → GREEN `eb3652ba36aecd105fb954c35e874e1da6d52834`: positive setting and authenticated limit discovery.
- RED `44840926337a334f6d8db071495a91542fddb9f5` → GREEN `0d71707c8af5f6b1059647a426bdf81476169076`: configured submit boundaries before downstream work.
- RED `8e08a7653cf38cca43cf917348dc5d3e04295dde` → GREEN `13d39edac5ad4127d66a74abc89e9e8b32c90c9b`: strict permission-gated browser contract loading.
- RED `2959d366344720b1ec27160dba083b44606f4ce3` → GREEN `7d69d8578c8c1bfc9e5a128bdc2addce0d0c8eca`: primary prompt interaction, recovery, accessibility and deduplication.
- RED `176b66abd2d47d3287a69f531806cff7d4922948` → GREEN `a93bbaad1e735a582db1c972304d05c01fa9a60e`: exact Python/browser edge trimming.
- REFACTOR `1a11980ad3e395bf3b65131b1d5e6ce0209a19b5`: explicit no-service assertion and clear prompt-boundary names.
- `e88825d727772b723f849b40f60d90ec16e51384` keeps the pre-existing accessibility fixture on the new required contract; `7aa5914fe6baf9e68160107177cf39818e06ead9` adds retained Chromium regression coverage.

Test Guard accepted the observable API, service-boundary, MSW and browser assertions. Clean Code Guard accepted the narrow response model, early router guard, strict client parser and interaction lock. Vercel React Best Practices accepted permission-gated TanStack caching, stable retry callback dependencies and the absence of unnecessary memoization.

## Browser proof

The focused real Chromium run used a non-default value of 37 and a deterministic intercepted submit boundary, with screenshots, traces and video disabled:

| Locale/layout | Direction | Over-limit blocked and retained | Exact-limit request count | Viewport fit |
| --- | --- | --- | ---: | --- |
| EN desktop 1280×800 | LTR | true | 1 | true |
| AR desktop 1280×800 | RTL | true | 1 | true |
| EN mobile 375×812 | LTR | true | 1 | true |
| AR mobile 375×812 | RTL | true | 1 | true |

A fifth Chromium case held submission closed through loading and two sanitized discovery failures, then verified explicit retry recovery on request 3 with zero submit requests. Result: 5 passed.

The Chrome DevTools connector was unavailable in this session, so the repository's Playwright-driven Chromium/CDP path supplied equivalent real-browser execution. No browser media or profile was retained.

## Gates

- Focused backend settings/schema/query contract: 30 passed.
- Backend unit foundation against isolated PostgreSQL/Redis: 2,478 passed, 14 integration-marked tests deselected; four warnings from unchanged AsyncMock-based tests remained non-failing.
- Focused PromptInput/Workspace/hook/locale/permission slice: 10 files, 413 passed.
- Full frontend Vitest: 71 files, 955 passed.
- Focused Playwright Chromium: 5 passed.
- Ruff check: passed.
- Ruff format check: 431 files already formatted.
- ESLint: passed.
- Typecheck: passed.
- CSS lint: passed.
- Production build: passed; the existing bundle-size advisory remained non-failing.
- `git diff --check`: passed after evidence and ledger updates.
- Test Guard, Clean Code Guard and Vercel React Best Practices: passed.
- Docs Guard: applied to this evidence and the linked ledgers.
- Authoritative PR `backend-test` and `frontend-test`: passed on `48ad094d8b95480aa87110c4a477b63533217bd0`.

## Contract remediation note

No broad OpenAPI or generated-client regeneration was performed. The narrow client is intentionally hand-written and strictly parsed for this chunk. Focused canonical representation and full regeneration remain recorded for `CHUNK-14` / `IS-GAP-008`, as locked by the remediation order.

## Cleanup and baseline

- Disposable API users, roles and sessions remaining: 0; isolated database and Redis volumes were destroyed.
- Disposable containers, volumes and networks remaining: 0.
- Browser output, profiles, cookies, request files, response files, test caches and scripts remaining under `/tmp`: 0.
- CHUNK-08 local service ports remaining: 0.
- Complete prompt text retained in evidence, logs, screenshots, traces or temporary files: false.
- The 14 protected modified PNGs, seven untracked historical screenshots and untracked traces directory are unchanged from the starting dirty baseline and were never staged.

CHUNK-09 becomes unblocked only after CI-passed [#306](https://github.com/RkShanks/QueryCraft/pull/306) is squash-merged. Do not start CHUNK-09 from this evidence alone. The machine-readable peer is [chunk-08-prompt-length.json](chunk-08-prompt-length.json).
