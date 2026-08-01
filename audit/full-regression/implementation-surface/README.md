# Backend implementation-surface audit

Snapshot: `main` at `93bd5191e0b851df8b872ecd4e4f1dc04d2397e7` on 2026-08-01. Scope is backend inventory and gap analysis only; no product code, tests, browser execution, long regression suite, Phase 6 freeze work, or frontend inventory was performed.

## Outcome

This audit enumerates 264 backend surfaces. Runtime reconciliation found 60 application operations plus eight GET/HEAD method registrations on four FastAPI documentation routes (64 registered route objects total). No application route differed between router source and generated runtime OpenAPI. A separate missing surface records the absence of liveness/readiness endpoints.

Coverage is behavior-specific: Exact 206, Partial 47, Missing 5, Intentional N/A 6. Every Partial/Missing row maps to at least one of 21 gap candidates: Critical 1, High 8, Mid 10, Low 2.

## Artifacts

- `backend-inventory.md` — human-readable inventory, counts, drift ledger, and all required row fields.
- `backend-inventory.json` — machine-readable source of truth for the same rows and reconciliation metadata.
- `backend-gap-candidates.md` — one candidate for every Partial/Missing surface, grouped by meaningful security/state boundary.

## Method

1. Captured the protected dirty baseline and synchronized local `main`/`origin/main` at the expected SHA before branching.
2. Read AGENTS/orchestrator guidance, all seven exhaustive matrices, missing-coverage ledger, final Phase 1–6/cross-phase reports, Phase 1–6 design/task/snapshot/log material, backend source, migrations, tests, scripts, and static OpenAPI contract.
3. Generated runtime OpenAPI from `create_app()` with placeholder non-secret environment values and enumerated `app.routes` independently.
4. Structurally enumerated every public service/repository method; searched production callers and tests with `rg`; inspected assertions before assigning evidence.
5. Enumerated ORM models/enums, all nine Alembic revisions, lifecycle/middleware, dependency adapters, and operational entrypoints.
6. Mapped surfaces to the 198-row matrix and final current-head evidence. Later-phase behavior supersedes frozen earlier wording where source/reports establish current-contract evolution.

## Interpretation

- Exact means assertions/current-head evidence exercise the same entrypoint and boundary, including real-use proof where the contract needs it.
- Partial means useful evidence exists but misses a required API, dependency, migration, concurrency, configuration, or operational boundary.
- Missing means the behavior/surface has no implementation or no assertion-bearing evidence at that boundary.
- Intentional N/A records test-only, extension, or explicitly deferred code. It is not treated as covered.

The 198-row matrix remains a requirements ledger; it is not an implementation inventory. Its broad Pass rows cannot close narrower current-source boundaries such as selected-connection continuity, masked Redis persistence, in-flight cancellation, or non-default timeout wiring.

## Lightweight validation contract

The artifacts are intended to pass JSON parsing/schema checks, unique surface/gap IDs, coverage/gap consistency, route/OpenAPI count reconciliation, Markdown relative-path checks, and `rtk git diff --check`. No runtime service or regression suite is required.
