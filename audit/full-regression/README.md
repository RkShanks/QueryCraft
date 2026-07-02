# Full Regression Matrix

Prepared on 2026-07-03 from `main` at
`0ae7f526c65f257a09d0d3e53afcd98492083890`.

This directory is a reusable planning artifact for full regression before Phase
6 freeze and for later phase closeouts. It does not record a completed test
run. Do not mark tests passed from these files alone.

## When To Run

Run this matrix before a phase freeze, after a full wave audit, or before
dispatching a later phase that depends on all prior shipped surfaces. For Phase
6, run it only after explicit approval for full regression execution. Do not
start T-905 or mark Phase 6 frozen from this matrix.

Stop the run at the first Critical or High regression, failed foundation gate,
security/privacy leak, missing required service, or real-LLM setup failure.

## Files By Phase

| Phase | File |
|---|---|
| 1 - Core text-to-SQL | `phase-1-core-text-to-sql.md` |
| 2 - Premium UI and Arabic/RTL activation | `phase-2-premium-ui-rtl.md` |
| 3 - Multi-dialect source DBs | `phase-3-multi-dialect-source-dbs.md` |
| 4 - Arabic/RTL polish | `phase-4-arabic-rtl-polish.md` |
| 5 - SSO, RBAC, row/column security | `phase-5-sso-rbac-row-column-security.md` |
| 6 - Quotas, hostile input, audit hardening | `phase-6-quotas-hostile-input-audit-hardening.md` |
| Pre-flight setup | `pre-flight-prerequisites.md` |
| Execution sequence | `runbook.md` |

## Future Phase 7+ Updates

Future subwaves should update the smallest relevant phase file when they add or
change a shipped surface. Add the new feature to the checklist, add focused
backend/frontend commands, update smoke checks, and record expected evidence.
Keep old phase behavior intact unless the frozen phase snapshot says it was
replaced.

For new phases, add one new phase file and one chunk in `runbook.md`. Do not
rewrite earlier phase files into broad summaries; preserve concrete commands and
known limitations so a cheap runner can execute one phase at a time.

## Keeping Context Small

Use `runbook.md` as the dispatcher entrypoint. Give each runner only:

- `pre-flight-prerequisites.md`
- `runbook.md`
- the one phase file for that chunk
- the relevant phase spec or snapshot when needed

Do not send every phase file to a single model unless it is doing final
consolidation. After each chunk, report commands run, pass/fail, skipped items,
evidence paths, and blockers.
