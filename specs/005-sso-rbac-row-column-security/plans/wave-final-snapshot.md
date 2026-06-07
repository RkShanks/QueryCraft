# Wave Final Snapshot — Phase 5: SSO, RBAC, Row/Column Security

**Date**: 2026-06-07
**Phase**: 5
**Status**: FROZEN
**Task Range**: T-600 – T-778 complete.

## Scope Delivered

Phase 5 replaces the provisional single-admin auth model with enterprise SSO, RBAC, and fine-grained security:
- **SSO Authentication**: OIDC and SAML identity provider integration.
- **Role-Based Access Control**: Prioritized multi-group role resolution mapping SSO claims to platform permissions.
- **Row-Level Security**: Injectable, parameterized SQL WHERE filters validated at save time and applied at execution (PostgreSQL, MySQL, MSSQL).
- **Column-Level Masking**: Post-execution masking of sensitive column data with localized UI indicators.
- **LLM Context Filtering**: Schema context passed to the LLM is restricted to role-allowed tables and columns.
- **Evaluator Authorization**: Pipeline blocks unauthorized SQL statements before database execution.
- **Tamper-Evident Audit Log**: Chained SHA-256 event log covering all security-relevant actions with strict secret redaction and 24-month retention.
- **i18n & RTL**: 100% Arabic/RTL parity across all new surfaces.

## Wave Summary (17.0 – 17.5d)

- **17.0 Foundation**: Contracts, Data Model, Auth Architecture
- **17.1 SSO Auth**: OIDC/SAML integration, admin-safe local login fallback, SSO config UI, SSO sign-in page
- **17.2 RBAC Gates**: Role CRUD, group mapping, permission-gated routes and APIs, unmapped user denial
- **17.3 Policy Enforcement**: Row filters, column masks, LLM schema filtering, evaluator enforcement, policy test endpoint, query flow integration
- **17.4 Audit Verification**: Tamper-evident audit log coverage, verification API, verification UI, retention config
- **17.5 Polish & Closeout**: Arabic/RTL polish, browser smoke, cross-dialect security verification, privacy evidence, audit findings hardening

## FR / SC Completion Summary

- **Functional Requirements (FR-115..FR-146)**: 32/32 COMPLETE. All functionality shipped and verified via passing automated integration tests and browser smoke.
- **Success Criteria (SC-046..SC-062)**: 17/17 MET. All criteria achieved with documented evidence, passing foundation gates, and zero critical/high audit findings remaining.

## PR Summary (#101..#152)

50 Pull Requests were merged to deliver Phase 5:
- **#101–#104**: Foundation models, migrations, permission middleware, schemas.
- **#105–#115**: SsoService, SSO endpoints, admin SSO config, sign-in page, concurrent session limit.
- **#116–#123**: Role CRUD, group mapping, permission gates, unmapped user denial.
- **#124–#140**: Schema filtering, row filters, column masking, evaluator rule, history scoping, policy editor.
- **#141–#146**: Audit coverage, immutability, redaction, verification endpoint, verification UI, retention config.
- **#147–#152**: Arabic/RTL polish, cross-dialect verification, audit findings hardening (F-001 HIGH, F-002 MID fixes), closeout artifacts, SMOKE-001 admin audit permission fix, final freeze.

## Audit Result Summary

The independent Phase 5 security audit is fully resolved for high/mid findings:
- **0 Critical findings**
- **0 High findings** (F-001 fixed by PR #149; SMOKE-001 fixed by PR #151 and verified by Gemini rerun)
- **0 Mid findings** (F-002 fixed by PR #149)
- **3 Low findings** deferred (F-003, SMOKE-002, SMOKE-003)

## Known Residual Risk

1. **F-003 LOW Deferred**: `LLMUnavailable` exception carries the provider name in structured logs. This is intentionally not fixed as there is zero user-facing leak (the HTTP layer sanitizes it to a constant i18n key).
2. **SMOKE-002 LOW Deferred**: Admin roles table clips the actions column on a 375px mobile viewport. Mobile polish only; desktop/admin workflow remains functional.
3. **SMOKE-003 LOW Deferred**: SSO group mapping add button clips on a 375px mobile viewport. Mobile polish only; desktop/admin workflow remains functional.
4. **Operational Requirement**: The audit retention mechanism (F-001 fix) requires an external scheduler (cron, k8s CronJob, systemd timer) to invoke `AuditService.purge_expired_entries()` at a suggested monthly cadence.

## Freeze Status

Phase 5 is `FROZEN` after PR #152 merged to `main`, `AGENTS.md` was updated, T-778 was marked complete, and Gemini reran UC-10 with zero Critical/High smoke findings.
