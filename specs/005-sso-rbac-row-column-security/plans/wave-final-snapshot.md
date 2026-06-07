# Wave Final Snapshot — Phase 5: SSO, RBAC, Row/Column Security

**Date**: 2026-06-07
**Phase**: 5
**Status**: Ready to Freeze
**Task Range**: T-600 – T-777 complete, T-778 pending until post-merge freeze.

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

## PR Summary (#101..#149)

46 Pull Requests were merged to deliver Phase 5:
- **#101–#104**: Foundation models, migrations, permission middleware, schemas.
- **#105–#115**: SsoService, SSO endpoints, admin SSO config, sign-in page, concurrent session limit.
- **#116–#123**: Role CRUD, group mapping, permission gates, unmapped user denial.
- **#124–#140**: Schema filtering, row filters, column masking, evaluator rule, history scoping, policy editor.
- **#141–#146**: Audit coverage, immutability, redaction, verification endpoint, verification UI, retention config.
- **#147–#149**: Arabic/RTL polish, cross-dialect verification, audit findings hardening (F-001 HIGH, F-002 MID fixes).

## Audit Result Summary

The independent Phase 5 security audit is fully resolved for high/mid findings:
- **0 Critical findings**
- **0 High findings** (F-001 fixed by PR #149)
- **0 Mid findings** (F-002 fixed by PR #149)
- **1 Low finding** deferred (F-003)

## Known Residual Risk

1. **F-003 LOW Deferred**: `LLMUnavailable` exception carries the provider name in structured logs. This is intentionally not fixed as there is zero user-facing leak (the HTTP layer sanitizes it to a constant i18n key).
2. **Operational Requirement**: The audit retention mechanism (F-001 fix) requires an external scheduler (cron, k8s CronJob, systemd timer) to invoke `AuditService.purge_expired_entries()` at a suggested monthly cadence.

## Freeze Instructions

To complete the transition of Phase 5 to `FROZEN`:
1. Wait for the Wave 17.5d closeout PR to merge to `main`.
2. Update `AGENTS.md` Phase 5 status from `IN PROGRESS` to `FROZEN`.
3. Mark task **T-778** complete.
(This must be done in a final docs PR or direct commit post-merge).
