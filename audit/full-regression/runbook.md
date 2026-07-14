# Full Regression Runbook

Prepared on 2026-07-03 from `main` at
`0ae7f526c65f257a09d0d3e53afcd98492083890`.

Do not run this book until explicitly approved. Run one chunk at a time and
report after each chunk.

## Recommended Execution Order

1. Pre-flight prerequisites.
2. Chunk 1 - Phase 1 core text-to-SQL.
3. Chunk 2 - Phase 2 premium UI / RTL.
4. Chunk 3 - Phase 3 multi-dialect source DBs.
5. Chunk 4 - Phase 4 Arabic RTL polish.
6. Chunk 5 - Phase 5 SSO / RBAC / row-column security.
7. Chunk 6 - Phase 6 quotas / hostile input / audit hardening.
8. Final consolidation report.

## Stop Conditions

Stop immediately and report if any of these occur:

- A backend/frontend foundation gate fails.
- Docker service required for the chunk is missing or unhealthy.
- Required real LLM env is missing for a required real-smoke chunk.
- Any Critical or High security, privacy, data isolation, SQL safety, audit
  integrity, or auth regression is found.
- A test mutates repo-tracked files outside expected evidence artifacts.
- Browser smoke finds visible secret leakage, raw internal error, or unusable
  primary workflow.

Do not continue to later chunks until the owner decides whether to fix, defer, or
rerun.

## What To Report After Each Chunk

Report:

- Branch and HEAD.
- Commands run with exit codes.
- Tests/smokes actually run. Do not claim unrun tests passed.
- Failures, skips, and environment limitations.
- Evidence files created or reviewed.
- Security/privacy observations.
- Whether the next chunk is unblocked.

## Pre-Flight Chunk

Read `pre-flight-prerequisites.md`, then run only setup checks:

```bash
rtk git status --short --branch
rtk git rev-parse HEAD
rtk docker ps
rtk docker compose -f docker-compose.dev.yml ps
rtk ss -ltnp
cd frontend && rtk npm run
cd frontend && rtk npm exec playwright -- --version
```

Check env presence without printing values using the commands in
`pre-flight-prerequisites.md`.

## Chunk 1 - Phase 1

Read `phase-1-core-text-to-sql.md`.

Backend:

```bash
cd backend && rtk uv run pytest tests/acceptance tests/integration/test_api_auth.py tests/integration/test_api_query.py tests/integration/test_api_history.py tests/integration/test_accept_only_persistence.py tests/integration/test_regenerate_then_accept.py tests/integration/test_evaluator_gate.py tests/integration/test_us5_provider_switch.py tests/integration/test_us5_reconfigured_provider.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/evaluator tests/unit/llm tests/unit/test_query_service_submit.py tests/unit/test_query_service_accept.py tests/unit/services/test_query_service_reject.py tests/unit/services/test_query_service_regenerate.py tests/unit/test_history_service.py tests/unit/test_schemas_query.py -x --tb=short
```

Frontend/browser:

```bash
cd frontend && rtk npm run test:e2e -- us1-sign-in-to-accept.spec.ts us2-reject-autoretry.spec.ts us2-double-reject-refine.spec.ts evaluator-blocks-unsafe-sql.spec.ts history-list-detail.spec.ts provider-switch.spec.ts query-timeout.spec.ts
```

LLM: run one approved live provider smoke if configured.

## Chunk 2 - Phase 2

Read `phase-2-premium-ui-rtl.md`.

Backend:

```bash
cd backend && rtk uv run pytest tests/acceptance/test_session_conversation.py tests/integration/test_sessions.py tests/integration/test_feedback.py tests/integration/test_admin_settings.py tests/integration/test_f011_lock_leak.py tests/contract/test_gemini_contract.py -x --tb=short
```

Frontend/browser:

```bash
cd frontend && rtk npm test -- --run
cd frontend && rtk npm run test:e2e -- rtl-snapshots.spec.ts i18n-audit.spec.ts
```

LLM: contract tests are required; live follow-up context smoke is optional unless
the owner requests it.

## Chunk 3 - Phase 3

Read `phase-3-multi-dialect-source-dbs.md`.

Backend:

```bash
cd backend && rtk uv run pytest tests/unit/db/test_migration_006_phase3.py tests/unit/source_db tests/unit/api/test_admin_connections.py tests/unit/api/test_connections.py tests/unit/api/test_session_connection.py tests/unit/api/test_query_connection_routing.py tests/unit/api/test_admin_refresh_schema.py tests/unit/evaluator/test_dialect_evaluator.py tests/unit/evaluator/test_dialect_validation.py -x --tb=short
```

Frontend/browser:

```bash
cd frontend && rtk npm run test:e2e -- wave_16_3_smoke.spec.ts
```

LLM: run approved PostgreSQL/MySQL/MSSQL dialect smoke if real provider and all
source DBs are ready.

## Chunk 4 - Phase 4

Read `phase-4-arabic-rtl-polish.md`.

Backend:

```bash
cd backend && rtk uv run pytest tests/unit/test_message_keys.py tests/unit/test_security_privacy_evidence.py tests/unit/test_audit_redaction.py tests/unit/test_audit_redaction_comprehensive.py tests/integration/test_api_query.py tests/integration/test_history_detail_validation.py -x --tb=short
```

Frontend/browser:

```bash
cd frontend && rtk npm test -- --run i18n
cd frontend && rtk npm test -- --run locales
cd frontend && rtk npm test -- --run no-physical
cd frontend && rtk npm run test:e2e -- i18n-audit.spec.ts rtl-snapshots.spec.ts wave_16_3_smoke.spec.ts
```

LLM: Arabic prompt smoke against PostgreSQL, MySQL, and MSSQL is required for a
Phase 4-style closure check.

## Chunk 5 - Phase 5

Read `phase-5-sso-rbac-row-column-security.md`.

Backend:

```bash
cd backend && rtk uv run pytest tests/unit/test_sso_oidc_flow.py tests/unit/test_sso_oidc_callback.py tests/unit/test_sso_saml_flow.py tests/unit/test_sso_saml_callback.py tests/unit/test_role_endpoints.py tests/unit/test_group_mapping_endpoints.py tests/unit/test_role_resolution.py tests/unit/test_permission_gates_all.py tests/unit/test_local_login_restriction.py tests/unit/test_admin_lockout_prevention.py tests/unit/test_unmapped_user_denial.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/test_row_filter_validation.py tests/unit/test_row_filter_injection.py tests/unit/test_schema_filtering.py tests/unit/test_column_masking.py tests/unit/test_query_flow_policy.py tests/unit/test_rerun_revalidation.py tests/unit/test_history_scoping.py tests/integration/test_cross_dialect_policy.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/test_audit_service.py tests/unit/test_audit_chain_verification.py tests/unit/test_audit_immutability.py tests/unit/test_audit_immutability_comprehensive.py tests/unit/test_rbac_audit_logging.py tests/unit/test_query_audit_logging.py tests/unit/test_audit_redaction_oidc.py -x --tb=short
```

Frontend/browser:

```bash
cd frontend && rtk npm test -- --run AdminSsoPage
cd frontend && rtk npm test -- --run SignInPage
cd frontend && rtk npm run test:e2e -- wave_17_3o_smoke.spec.ts wave_17_4e_audit_smoke.spec.ts
```

LLM: run one restricted-role real provider smoke if configured.

## Chunk 6 - Phase 6

Read `phase-6-quotas-hostile-input-audit-hardening.md`.

Backend:

```bash
cd backend && rtk uv run pytest tests/unit/test_quota_service.py tests/unit/test_quota_repository.py tests/unit/test_quota_enforcement.py tests/unit/test_quota_audit.py tests/unit/test_quota_error_sanitization.py tests/unit/test_quota_fail_closed.py tests/unit/test_quota_reset.py tests/integration/test_quota_admin.py tests/integration/test_execution_quota.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/test_detection_registry.py tests/unit/test_hostile_detector.py tests/unit/test_rule_prompt_injection.py tests/unit/test_rule_sql_injection.py tests/unit/test_rule_rbac_bypass.py tests/unit/test_rule_schema_exposure.py tests/unit/test_rule_destructive_sql.py tests/unit/test_hostile_audit_redaction.py tests/unit/test_detection_error_sanitization.py tests/unit/test_no_raw_hostile_payload.py tests/unit/test_detection_config_repo.py tests/integration/test_detection_passthrough.py tests/integration/test_detection_coverage.py tests/integration/test_detection_admin.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/test_audit_search_service.py tests/unit/test_audit_export_csv.py tests/unit/test_audit_export_json.py tests/unit/test_export_redaction_defense.py tests/unit/test_purge_gap_marker.py tests/unit/test_verify_chain_purge.py tests/unit/test_audit_retention_status.py tests/unit/test_audit_search_export_permissions.py tests/unit/test_audit_retention_window.py tests/integration/test_audit_search.py tests/integration/test_audit_export.py tests/integration/test_purge_verify_cycle.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/test_cross_dialect_quota_verification.py tests/integration/test_cross_dialect_quota.py tests/unit/test_phase6_sanitization_regression.py -x --tb=short
```

Frontend/browser:

```bash
cd frontend && rtk npm test -- --run AdminQuotasPage AdminDetectionPage AdminAuditPage QuotaExceededBanner HostileInputBlockedBanner
cd frontend && rtk npm run test:e2e -- wave_18_4b_smoke.spec.ts
```

LLM: run approved ordering smoke for benign, hostile, and over-quota prompts.

## Foundation Gates

After chunk-specific commands, run full foundation gates when approved for a
full pass:

```bash
cd backend && rtk uv run pytest tests/ -x --tb=short
cd backend && rtk uv run ruff check src tests
cd backend && rtk uv run ruff format --check src tests
cd frontend && rtk npm test -- --run
cd frontend && rtk npm run lint
cd frontend && rtk npm run typecheck
cd frontend && rtk npm run build
cd frontend && rtk npm run lint:css
rtk git diff --check
```

## Final Consolidation

Collect all chunk reports into one final full-regression report. Include:

- HEAD SHA tested.
- Docker/env/browser state.
- Per-phase pass/fail/skip table.
- Evidence paths.
- New findings by severity.
- Explicit recommendation on readiness for T-905.

Do not mark Phase 6 frozen. T-905 and freeze metadata remain separate
orchestrator tasks.
