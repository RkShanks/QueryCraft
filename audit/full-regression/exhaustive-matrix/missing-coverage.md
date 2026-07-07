# Missing Coverage and Setup-Dependent Index

This file consolidates rows whose status is not ordinary automated or existing browser/API evidence. It is the handoff list for the next regression-execution prompt.

## By Phase

| Phase | Missing Coverage | Setup-Dependent | Needs Manual/Live Test | Deferred by Prior Decision |
|---|---:|---:|---:|---:|
| Phase 1 | 0 | 2 | 1 | 0 |
| Phase 2 | 0 | 1 | 0 | 0 |
| Phase 3 | 0 | 6 | 1 | 0 |
| Phase 4 | 0 | 3 | 1 | 0 |
| Phase 5 | 0 | 3 | 0 | 0 |
| Phase 6 | 1 | 1 | 0 | 1 |
| Cross-phase | 0 | 5 | 3 | 2 |

## Missing Coverage

| Row | What is missing | What is needed |
|---|---|---|
| P6-FR-150 | Phase 6 task/audit sources planned a 60-second Redis quota config cache, but both Gemini and Opus audits found current behavior reads quota config directly from the repository. | Either implement the Redis config cache with focused tests for 60-second TTL and immediate admin-change semantics, or explicitly update the Phase 6 current contract/closeout to say direct DB reads are intentional. |

## Setup-Dependent Rows

| Row | Dependency | What is needed |
|---|---|---|
| P1-FR-009 | Live or fully mocked configured LLM providers. | Run provider-switch smoke with configured provider credentials or approved provider mocks; verify no provider secrets leak. |
| P1-FR-026 | Provider config and history fixture. | Switch provider by configuration, restart if required, submit a query, and verify old accepted history remains readable. |
| P2-FR-047 | Optional live Gemini or equivalent provider contract check. | Run simulated contract tests always; run live provider smoke only when credentials and owner approval exist. |
| P3-FR-059 | Real PG/MySQL/MSSQL services for end-to-end add/test flows. | Bring up local source DB services, add each connection, verify credentials are not returned. |
| P3-FR-063 | Real DB health checks. | Exercise success and categorized failures for each supported DB. |
| P3-FR-065 | Real schemas for PG/MySQL/MSSQL. | Introspect Pagila/Sakila/AdventureWorksLT or equivalent approved fixtures. |
| P3-FR-068 | Controlled DB/introspection failure cases. | Force auth/network/timeout/permission failures and verify localized sanitized status. |
| P3-FR-069 | Real LLM or approved SQL-generation mock plus all three DBs. | Generate dialect-specific SQL with at least one dialect marker per DB and execute safely. |
| P3-FR-093 | Real connection create path with health and schema services. | Save good and bad connections; verify auto health/schema behavior and retry action. |
| P4-FR-101 | Real DBs plus Arabic prompt SQL generation. | Re-run Arabic prompt execution and dialect marker inspection for PG, MySQL, MSSQL. |
| P4-FR-102 | Arabic prompt evaluator path. | Verify Arabic prompts do not cause false evaluator rejection and valid SQL executes. |
| P4-FR-112 | All three Phase 4 source DB fixtures. | Treat missing PG/MySQL/MSSQL as a setup blocker for closure-style Phase 4 check. |
| P5-FR-117 | OIDC IdP, mocked or live. | Run OIDC authorization code flow with callback validation and role assignment. |
| P5-FR-118 | SAML IdP, mocked or live. | Run SAML login/ACS flow with assertion validation and replay/expiry negatives. |
| P5-FR-131 | Real DBs for row-filter execution differences across dialects. | Execute restricted-role queries on PG/MySQL/MSSQL and prove filtered results differ. |
| P6-FR-174 | External purge scheduler environment. | Review or execute external scheduler invocation outside the app; verify purge marker behavior through automated service tests. |
| XP-001 | End-to-end auth with local admin and SSO. | Run local admin login plus mapped/unmapped SSO scenarios. |
| XP-002 | Multi-DB services. | Add/select/query PG/MySQL/MSSQL; verify current single-connection degenerate behavior. |
| XP-013 | Redis degraded-service simulation. | Stop or mock Redis for session/lock/quota paths and verify fail-closed behavior per path. |
| XP-014 | Live LLM credentials if owner requests live smoke. | Run one approved real-provider query with redacted transcript. |
| XP-015 | PG/MySQL/MSSQL source services. | Health, schema, dialect SQL marker, execution result for each DB. |

## Needs Manual or Live Test Rows

| Row | Why automated coverage is not enough | What is needed |
|---|---|---|
| P1-FR-008 | Need to inspect actual provider prompt context for schema inclusion and Phase 5 role filtering. | Capture redacted provider/mock prompt transcript. |
| P3-FR-086 | Source requires Chrome DevTools MCP/browser smoke for user-facing flows. | Re-run browser smoke for admin connection CRUD, health, schema, selector, dialect query, and login. |
| P4-FR-109 | Keyboard tab order is best validated by browser role/tab traversal. | Run Playwright or manual keyboard traversal in Arabic RTL. |
| XP-017 | Existing screenshots may be stale for the target full-regression HEAD. | Refresh evidence in a new approved run folder; do not stage old screenshots/traces. |
| XP-018 | Matrix-only task did not run foundation gates. | Run backend/frontend gates only during the approved execution prompt. |

## Deferred Rows

| Row | Prior decision | Follow-up |
|---|---|---|
| P6-FR-154 | Consolidated Wave 18 audit recorded TTL edge cases C6-L01 and C6-L02 as Low, non-blocking quota hardening. | Keep as backlog unless owner pulls it into a hardening wave. |
| XP-009 | Phase 5 final snapshot deferred two Low mobile clipping issues: admin roles table actions at 375px and SSO group mapping add button at 375px. | Re-check in mobile sweep; fix if owner promotes mobile polish. |
| XP-016 | User explicitly prohibited T-905/freeze in this task. | Do not start freeze from this PR. |
