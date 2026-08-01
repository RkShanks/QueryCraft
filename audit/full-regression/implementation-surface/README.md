# Implementation-surface audit

This directory contains separate backend and frontend static inventories. The backend snapshot is `93bd5191e0b851df8b872ecd4e4f1dc04d2397e7` (2026-08-01). The frontend snapshot is synchronized `main` at `5c05c5b1b91c581becc9601510bb5a8f4f46eeaf` (2026-08-02). Neither inventory changes product code or tests, runs a long regression/browser/build suite, starts remediation or consolidation, or performs Phase 6 T-905/freeze work.

## Outcome

The backend inventory enumerates 264 surfaces. Runtime reconciliation found 60 application operations plus eight GET/HEAD method registrations on four FastAPI documentation routes (64 registered route objects total). No application route differed between router source and generated runtime OpenAPI. A separate missing surface records the absence of liveness/readiness endpoints.

Backend coverage is behavior-specific: Exact 206, Partial 47, Missing 5, Intentional N/A 6. Every Partial/Missing row maps to at least one of 21 gap candidates: Critical 1, High 8, Mid 10, Low 2.

The frontend inventory enumerates 192 independently observable surfaces across 12 routes, 11 pages, 45 grouped actions, 55 application API functions/inline operations, 28 hooks, 13 state boundaries, 10 accessibility boundaries, seven localization boundaries, and 11 browser/test/operational boundaries. Coverage is Exact 32, Partial 142, Missing 10, Intentional N/A 8. Every Partial/Missing row maps to at least one of 33 frontend gap candidates: Critical 0, High 10, Mid 20, Low 3.

## Artifacts

- `backend-inventory.md` — human-readable inventory, counts, drift ledger, and all required row fields.
- `backend-inventory.json` — machine-readable source of truth for the same rows and reconciliation metadata.
- `backend-gap-candidates.md` — one candidate for every Partial/Missing surface, grouped by meaningful security/state boundary.
- `frontend-inventory.md` — human-readable route/page/action/API/hook/state/accessibility/i18n/browser inventory with all required row fields.
- `frontend-inventory.json` — machine-readable source of truth, counts, API parity, dead/reachable-legacy ledgers, rows, and embedded gap references.
- `frontend-gap-candidates.md` — one grouped candidate for every Partial/Missing frontend surface.

## Method

1. Each audit captured its protected dirty baseline and synchronized local `main`/`origin/main` at the expected SHA before branching.
2. Both audits read AGENTS/orchestrator guidance, all seven exhaustive matrices, the missing-coverage ledger, and final Phase 1–6/cross-phase reports. Later-phase behavior supersedes frozen earlier wording where source/reports establish current-contract evolution.
3. The backend pass generated runtime OpenAPI from `create_app()` with placeholder non-secret environment values; reconciled router/runtime/static operations; and structurally enumerated services, repositories, ORM/enums, nine Alembic revisions, lifecycle/middleware, adapters, scripts, tests, and operational entrypoints.
4. The frontend pass structurally enumerated App routes, pages, exported components, visible controls, API clients/inline operations, hooks, query keys/invalidation, browser/session/local state, locale keys, logical-direction CSS, responsive/accessibility boundaries, MSW/Playwright harnesses, and development/production configuration.
5. Both passes used `rg` caller/test searches and read assertions before assigning evidence. The frontend pass cross-checked every application client operation against the backend runtime inventory and recorded dead/unreachable surfaces separately.

## Interpretation

- Exact means assertions/current-head evidence exercise the same entrypoint and boundary, including real-use proof where the contract needs it.
- Partial means useful evidence exists but misses a required API, dependency, migration, concurrency, configuration, or operational boundary.
- Missing means the behavior/surface has no implementation or no assertion-bearing evidence at that boundary.
- Intentional N/A records test-only, extension, or explicitly deferred code. It is not treated as covered.

The 198-row matrix remains a requirements ledger; it is not an implementation inventory. Its broad Pass rows cannot close narrower current-source boundaries such as selected-connection continuity, masked Redis persistence, in-flight cancellation, or non-default timeout wiring.

For frontend surfaces, a mocked browser test is Partial whenever the real backend/browser contract is material. A screenshot proves only the captured visual state. Backend-only operations intentionally lacking UI are not frontend gaps unless a requirement expects a UI; `POST /admin/roles/{id}/test-policy` is the one identified requirement-backed missing frontend operation.

## Lightweight validation contract

The artifacts are intended to pass JSON parsing/schema checks, unique surface/gap IDs, coverage/gap consistency, route/API/OpenAPI count reconciliation, referenced-path checks, locale-key structural comparison, and `rtk git diff --check`. No runtime service, frontend build, Vitest, Playwright, browser, or regression suite is required.
