# Phase 5 - SSO RBAC Row/Column Security Regression

Source scope: `specs/005-sso-rbac-row-column-security/`.

## Scope Summary

Phase 5 replaces provisional single-admin-only access with enterprise SSO for
end users, local admin safety-net login, role management, group mapping, fixed
platform permissions, row filters, column masking, user-scoped history, policy
testing, Arabic/RTL support, and a tamper-evident audit log.

## Feature Checklist

- OIDC and SAML provider configuration, masked secrets, and sanitized validation.
- End-user OIDC/SAML sign-in validates issuer, audience, signature, expiry,
  nonce/state or replay controls, and maps groups to roles.
- Users with no mapped role are denied access.
- Local password login is restricted to built-in admin; built-in admin cannot be
  deleted or locked out.
- Role CRUD supports priority, fixed permissions, allowed tables/columns, row
  filters with `{user.email}`, `{user.subject_id}`, `{user.role}`, and column
  masks.
- Duplicate group mappings are prevented; multi-group resolution uses lowest
  numeric priority.
- UI routes and API endpoints enforce permissions.
- LLM schema context is role-filtered; evaluator blocks disallowed schema.
- Row filters apply across PostgreSQL, MySQL, and MSSQL; masked columns show a
  localized indicator.
- History is scoped per user and rerun re-validates current role policy.
- Audit log records required security events, is immutable through app paths, and
  verifies chained hashes.
- Phase 5 Arabic/RTL surfaces are localized and mirrored.

## Backend Commands

```bash
cd backend && rtk uv run pytest tests/unit/test_sso_oidc_flow.py tests/unit/test_sso_oidc_callback.py tests/unit/test_sso_oidc_errors.py tests/unit/test_sso_oidc_jwks.py tests/unit/test_sso_saml_flow.py tests/unit/test_sso_saml_callback.py tests/unit/test_sso_saml_errors.py tests/unit/test_sso_saml_signed_assertions.py tests/unit/test_replay_protection.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/test_role_endpoints.py tests/unit/test_group_mapping_endpoints.py tests/unit/test_role_resolution.py tests/unit/test_permission_gates_all.py tests/unit/test_local_login_restriction.py tests/unit/test_admin_lockout_prevention.py tests/unit/test_unmapped_user_denial.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/test_row_filter_validation.py tests/unit/test_row_filter_injection.py tests/unit/test_schema_filtering.py tests/unit/test_column_masking.py tests/unit/test_query_flow_policy.py tests/unit/test_rerun_revalidation.py tests/unit/test_history_scoping.py tests/integration/test_cross_dialect_policy.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/test_audit_service.py tests/unit/test_audit_chain_verification.py tests/unit/test_audit_immutability.py tests/unit/test_audit_immutability_comprehensive.py tests/unit/test_rbac_audit_logging.py tests/unit/test_query_audit_logging.py tests/unit/test_audit_redaction_oidc.py -x --tb=short
cd backend && rtk uv run ruff check src tests
cd backend && rtk uv run ruff format --check src tests
```

## Frontend Commands

```bash
cd frontend && rtk npm test -- --run AdminSsoPage
cd frontend && rtk npm test -- --run SignInPage
cd frontend && rtk npm test -- --run
cd frontend && rtk npm run lint
cd frontend && rtk npm run typecheck
cd frontend && rtk npm run build
cd frontend && rtk npm run lint:css
cd frontend && rtk npm run test:e2e -- wave_17_3o_smoke.spec.ts wave_17_4e_audit_smoke.spec.ts
```

## Browser / Manual Smoke Checks

- Local admin sign-in still works and admin-only routes are visible.
- SSO sign-in page shows configured OIDC/SAML providers and sanitized errors.
- Admin SSO config masks client secret, SAML metadata, and certificate content.
- Role CRUD, priority reorder, group mapping, row filter, column mask, and policy
  test screens work in English and Arabic.
- Non-admin cannot access admin routes or admin API endpoints.
- Submit a query as a restricted role and verify allowed schema only, row filter
  enforcement, masked output indicator, and blocked disallowed table/column.
- Verify audit page status/verify success/failure states.

## API Checks

- OIDC/SAML configure, initiate, callback, error, and no-role denial responses.
- Role CRUD, group mappings, policy test endpoint, and permission middleware.
- Query submit/execute role policy integration and accepted-query rerun.
- History list/detail user scoping.
- Audit write path, immutability guards, verify-chain, and redaction.

## Real LLM Smoke

Applicable. With real provider configured, submit one allowed query and one
disallowed-schema query as a restricted role. Verify the provider receives only
role-allowed schema and that disallowed SQL is blocked before execution.

## Expected Pass Criteria

- Listed gates pass.
- No non-admin can access admin endpoints or admin UI routes.
- Unauthorized schema never reaches LLM prompt context.
- Row filters and masks enforce consistently across all three dialects.
- Audit entries contain no secrets, full tokens, credentials, or raw provider
  details.

## Known Local Skips / Limitations

- Mock IdP tests cover OIDC/SAML protocol behavior; live enterprise IdP testing
  requires user-provided provider setup.
- Role policy changes apply on next query, not retroactively to in-flight query.
- Full audit search/export UI is Phase 6/7 scope; Phase 5 owns storage/write and
  verify path.

## Evidence To Capture

- Command logs.
- Screenshots for SSO sign-in, SSO config, role editor, group mapping, masked
  result, Arabic role screen, and audit verify.
- Redacted API examples for unauthorized admin access, no-role denial, row-filter
  policy block, and masked result.
- Audit chain verification result.

## Update Notes For Future Waves

Any future admin feature must state its required fixed permission and add both UI
route and API permission checks here or in the new phase file.
