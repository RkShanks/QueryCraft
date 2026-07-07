# Exhaustive Spec-Derived Regression Matrix

Prepared on 2026-07-07 from `main` base `38013c57545cddc7bca0e44e856d6575cfda8730`.

This folder is a planning artifact for a future full regression pass across Phases 1-6. It does not record a completed test run and must not be used to mark Phase 6 frozen or to start T-905.

## Source Set

- `AGENTS.md`
- `.agents/ORCHESTRATOR.md`
- `audit/full-regression/README.md`
- `audit/full-regression/runbook.md`
- `specs/001-core-text-to-sql/{spec.md,plan.md,tasks.md,contracts/openapi.yaml,plans/wave-7-snapshot.md}`
- `specs/002-phase2-premium-ui-rtl/{spec.md,plan.md,tasks.md,contracts/api-contracts.md,plans/wave-final-snapshot.md}`
- `specs/003-multi-dialect-source-dbs/{spec.md,plan.md,tasks.md,contracts/api-contracts.md,plans/wave-final-snapshot.md}`
- `specs/004-arabic-rtl-verification-polish/{spec.md,plan.md,tasks.md,plans/wave-final-snapshot.md}`
- `specs/005-sso-rbac-row-column-security/{spec.md,plan.md,tasks.md,contracts/api-contracts.md,plans/wave-final-snapshot.md,evidence/*}`
- `specs/006-quotas-hostile-input-audit-hardening/{tasks.md,plans/orchestration-log.md}`
- `audit/wave-18/{browser-smoke-wave18.md,gemini-findings.md,opus-findings.md,consolidation-report.md}`

## Files

| File | Purpose |
|---|---|
| `phase-1-matrix.md` | Phase 1 FR-001 through FR-030 regression rows. |
| `phase-2-matrix.md` | Phase 2 FR-031 through FR-058 regression rows. |
| `phase-3-matrix.md` | Phase 3 FR-059 through FR-094 regression rows. |
| `phase-4-matrix.md` | Phase 4 FR-095 through FR-114 regression rows. |
| `phase-5-matrix.md` | Phase 5 FR-115 through FR-146 regression rows. |
| `phase-6-matrix.md` | Phase 6 FR-147 through FR-180 regression rows. |
| `cross-phase-matrix.md` | Updated current contracts, deferrals, and end-to-end invariants spanning phases. |
| `execution-order.md` | Execution sequence for future Prompt 2 regression runners. |
| `missing-coverage.md` | Consolidated missing, setup-dependent, manual/live, and deferred items. |

## Status Semantics

| Status | Meaning |
|---|---|
| Covered by automated tests | Source tasks or runbook identify focused automated backend, frontend, contract, or e2e coverage. Execution still must be rerun before claiming pass. |
| Covered by browser/API full-regression evidence | Existing browser/API evidence artifacts cover the real-use path. Execution still must verify evidence against the target HEAD. |
| Needs manual/live test | The row needs a live provider, real IdP, human/browser inspection, or real LLM smoke beyond ordinary automated suites. |
| Deferred by prior decision | The source artifacts explicitly defer the scope or record it as non-blocking. |
| Missing coverage | A source requirement or audit finding lacks the required implementation, proof, or regression coverage. |
| Setup-dependent | The check is valid only when required external services, source databases, IdPs, Redis, or live LLM credentials are available. |

## Current Contract Notes

- Phase 1's "exactly one PostgreSQL source DB" and "single provisional administrator" are no longer the literal current contract. Phase 3 updates database access to centrally managed PostgreSQL, MySQL, and MSSQL connections. Phase 5 updates authentication to SSO for end users while preserving local login for built-in admins.
- Phase 5 deferred audit search/export to a later admin dashboard, but Phase 6 implements audit search, export, retention status, and purge-gap hardening. The current regression contract is Phase 6.
- Phase 6 has passed existing independent audits with 0 Critical and 0 High findings, but the consolidation report records 2 Mid and 2 Low non-blocking hardening items. This matrix preserves those as deferred or missing rows rather than claiming exhaustive closure.

