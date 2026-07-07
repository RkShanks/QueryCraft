# Execution Order

This is an execution plan for a future full-regression prompt. It preserves the existing `audit/full-regression/runbook.md` stop conditions and adds matrix-driven evidence requirements.

## Pre-Flight

1. Confirm branch and HEAD.
2. Confirm dirty worktree policy with the owner before creating new evidence.
3. Confirm Docker services, Redis, platform Postgres, source DBs, browser tooling, and optional live LLM credentials without printing secret values.
4. Do not start T-905 or freeze tasks from Phase 6.

## Phase Chunks

| Order | Chunk | Matrix Files | Primary Evidence |
|---|---|---|---|
| 1 | Pre-flight only | `README.md`, `cross-phase-matrix.md`, `missing-coverage.md` | Service/env readiness report, no feature pass claims. |
| 2 | Phase 1 core text-to-SQL | `phase-1-matrix.md` | Auth, ask/evaluate/execute/accept, reject/regenerate, timeout, history, provider smoke if configured. |
| 3 | Phase 2 sessions/UI/RTL | `phase-2-matrix.md` | Sessions, feedback, settings, premium UI, i18n/RTL, contract tests. |
| 4 | Phase 3 multi-DB | `phase-3-matrix.md` | Admin connections, health, schema, selector, dialect query, single-connection degenerate flow. |
| 5 | Phase 4 Arabic/RTL polish | `phase-4-matrix.md` | Arabic all-surface smoke, mobile RTL, real PG/MySQL/MSSQL Arabic prompts if services are available. |
| 6 | Phase 5 SSO/RBAC/security | `phase-5-matrix.md` | OIDC/SAML mocked or live flows, role/group/policy enforcement, audit verify, row filters, column masks, history scoping. |
| 7 | Phase 6 quotas/detection/audit hardening | `phase-6-matrix.md` | Quotas, hostile detection, audit search/export/retention, browser UC-11..UC-18, audit hardening gaps. |
| 8 | Cross-phase consolidation | `cross-phase-matrix.md`, `missing-coverage.md` | Updated current contract validation, final missing/deferred/setup-dependent summary. |

## Stop Conditions

Stop and report before continuing to the next chunk if any of these occur:

- Any Critical or High security/privacy/data-isolation/audit/auth/query-validation regression.
- Any foundation gate failure when gates are authorized for execution.
- Required source DB, Redis, browser, or IdP service is unavailable for a row that is not explicitly optional.
- A live LLM setup is required for a requested row but credentials are missing.
- Browser smoke shows visible secret leakage, raw internal error, untranslated key, or unusable primary flow.
- A command mutates tracked product files or unapproved evidence artifacts.

## Reporting Template

For each chunk, report:

- Branch and HEAD.
- Rows attempted by ID.
- Commands run with exit code.
- Browser/API checks run.
- Evidence paths.
- Rows passed, failed, skipped, setup-dependent, missing, or deferred.
- Security/privacy observations.
- Whether the next chunk is unblocked.

Do not report any unrun row as passed.

