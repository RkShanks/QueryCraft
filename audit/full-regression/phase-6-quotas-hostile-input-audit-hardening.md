# Phase 6 - Quotas, Hostile Input, Audit Hardening Regression

Source scope: `specs/006-quotas-hostile-input-audit-hardening/`.

Prepared after T-903 consolidation. T-904 is skipped by condition because the
consolidated audit reported 0 Critical and 0 High findings. This file does not
start T-905 and does not mark Phase 6 frozen.

## Scope Summary

Phase 6 adds role-level daily quotas for queries, executions, and audit exports;
hostile input detection before quota and LLM generation; detection threshold
configuration; hostile input audit redaction; audit search/export/retention
hardening; purge-gap markers; export redaction and formula-injection prevention;
and Arabic/RTL admin UI for the new surfaces.

## Feature Checklist

- Role quota config CRUD and status for query, execution, and export dimensions.
- Redis-backed daily UTC counters fail closed when unavailable.
- Query flow order is hostile detection, query quota, then LLM generation.
- Blocked hostile input does not increment quota and returns only the sanitized
  hostile-input message key.
- Built-in detection rules cover prompt injection, SQL injection, RBAC bypass,
  schema/secret exposure, and destructive SQL in English and Arabic patterns.
- Detection threshold config validates `block_confidence > flag_confidence`.
- Hostile blocked/flagged audit entries never persist raw hostile payloads.
- Audit search supports filters, pagination, retention window, and self-audit.
- Audit export supports CSV/JSON, 50k limit, checksum metadata, formula-injection
  prevention, export quota, and defense-in-depth redaction.
- Retention purge inserts `audit.purge` marker and verify-chain treats valid
  purge gaps as intentional while detecting unmarked gaps.
- Phase 6 admin quota/detection/audit surfaces are localized and RTL-safe.

## Backend Commands

```bash
cd backend && rtk uv run pytest tests/unit/test_quota_service.py tests/unit/test_quota_repository.py tests/unit/test_quota_enforcement.py tests/unit/test_quota_audit.py tests/unit/test_quota_error_sanitization.py tests/unit/test_quota_fail_closed.py tests/unit/test_quota_reset.py tests/integration/test_quota_admin.py tests/integration/test_execution_quota.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/test_detection_registry.py tests/unit/test_hostile_detector.py tests/unit/test_rule_prompt_injection.py tests/unit/test_rule_sql_injection.py tests/unit/test_rule_rbac_bypass.py tests/unit/test_rule_schema_exposure.py tests/unit/test_rule_destructive_sql.py tests/unit/test_hostile_audit_redaction.py tests/unit/test_detection_error_sanitization.py tests/unit/test_no_raw_hostile_payload.py tests/unit/test_detection_config_repo.py tests/integration/test_detection_passthrough.py tests/integration/test_detection_coverage.py tests/integration/test_detection_admin.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/test_audit_search_service.py tests/unit/test_audit_export_csv.py tests/unit/test_audit_export_json.py tests/unit/test_export_redaction_defense.py tests/unit/test_purge_gap_marker.py tests/unit/test_verify_chain_purge.py tests/unit/test_audit_retention_status.py tests/unit/test_audit_search_export_permissions.py tests/unit/test_audit_retention_window.py tests/integration/test_audit_search.py tests/integration/test_audit_export.py tests/integration/test_purge_verify_cycle.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/test_cross_dialect_quota_verification.py tests/integration/test_cross_dialect_quota.py tests/unit/test_phase6_sanitization_regression.py -x --tb=short
cd backend && rtk uv run pytest tests/ -x --tb=short
cd backend && rtk uv run ruff check src tests
cd backend && rtk uv run ruff format --check src tests
```

## Frontend Commands

```bash
cd frontend && rtk npm test -- --run AdminQuotasPage AdminDetectionPage AdminAuditPage QuotaExceededBanner HostileInputBlockedBanner
cd frontend && rtk npm test -- --run
cd frontend && rtk npm run lint
cd frontend && rtk npm run typecheck
cd frontend && rtk npm run build
cd frontend && rtk npm run lint:css
cd frontend && rtk npm run test:e2e -- wave_18_4b_smoke.spec.ts
```

## Browser / Manual Smoke Checks

- `/admin/quotas` in English and Arabic: edit limits, view status, verify no
  quota-only admin calls role or SSO group-mapping endpoints.
- Query flow in Arabic: quota exceeded shows localized sanitized banner with
  reset time and no counters/limits/policy IDs.
- Query flow in Arabic: hostile input blocked shows localized sanitized banner
  and does not echo raw input.
- `/admin/detection` in Arabic: thresholds render, validate, and save.
- `/admin/audit` in Arabic: search filters, paginated table, retention panel,
  CSV/JSON export controls, and export quota errors.
- Mobile 375px and 768px: quotas, detection, audit search, retention, and quota
  status have no clipping or overlap.

## API Checks

- `/api/v1/admin/quotas`, `/status`, quota upsert/delete and permission gates.
- Query submit/execute quota 429 and Redis fail-closed 503 paths.
- `/api/v1/admin/detection/config` read/update validation and permission gates.
- Query submit hostile blocked/flagged/passthrough behavior.
- `/api/v1/admin/audit/entries`, `/export`, `/retention`, `/verify` permission
  gates, search filters, export format behavior, retention status, and purge
  verify handling.
- All Phase 6 error bodies must omit counter values, policy IDs, role internals,
  rule names, patterns, confidence scores, raw hostile text, DB host/port,
  provider names, stack traces, and OIDC/SAML tokens.

## Real LLM Smoke

Applicable only for passthrough and ordering confirmation. With a real provider
configured, submit:

- A benign prompt under quota and verify it reaches LLM generation.
- A hostile prompt and verify it is blocked before quota/LLM.
- A benign prompt over quota and verify it is blocked before LLM.

Capture audit event categories and sanitized API/UI responses. Do not store raw
hostile payloads in evidence.

## Expected Pass Criteria

- Listed gates pass or any known local limitation is explicitly isolated.
- Quotas fail closed and do not leak internal counter/policy details.
- Hostile input detection runs before quota and never persists raw hostile text.
- Audit export/search/retention self-audits are sanitized.
- Purge marker verify-chain behavior passes.
- Independent audit gate remains 0 Critical / 0 High.

## Known Local Skips / Limitations

- Full backend regression may still expose local non-HTTPS secure-cookie behavior
  if run outside the configured CI/container context; report this separately.
- Consolidated Mid/Low backlog from T-903 remains non-blocking: quota config
  Redis cache absence, verify-chain memory usage, quota TTL precision, and
  missing-TTL repair.
- No Chrome DevTools MCP tool is exposed in the current Codex session; use
  Playwright unless a runner starts/attaches a CDP-capable browser.

## Evidence To Capture

- Full backend/frontend gate logs.
- Wave 18.4b browser smoke report and screenshots.
- Redacted API examples for quota exceeded, hostile blocked, detection config
  validation, audit export limit, export quota exceeded, retention status, and
  purge verify.
- Audit event samples proving sanitized context and no raw hostile payload.
- T-903 consolidation report reference and any new regression findings.

## Update Notes For Future Waves

If a future phase changes query ordering, quota dimensions, detection rules, or
audit export format, update this file first. Preserve the invariant that blocked
hostile input is not counted against quota and never reaches the LLM.
