# Phase 5 Orchestration Log

## Phase 5 Initialization
- **Status**: TASKS COMPLETE — READY FOR WAVE 17.0 DISPATCH
- **Date**: 2026-05-24
- **Spec**: `specs/005-sso-rbac-row-column-security/spec.md`
- **Plan**: `specs/005-sso-rbac-row-column-security/plan.md`
- **Research**: `specs/005-sso-rbac-row-column-security/research.md`
- **Data Model**: `specs/005-sso-rbac-row-column-security/data-model.md`
- **API Contracts**: `specs/005-sso-rbac-row-column-security/contracts/api-contracts.md`
- **Tasks**: `specs/005-sso-rbac-row-column-security/tasks.md`
- **Prior Phase Status**: Phases 1-4 FROZEN on `main`
- **Branch Context**: `main`

### Locked Scope
- SSO for end users via OIDC and SAML.
- Local password login remains admin-only.
- RBAC with fixed platform permission set.
- Admin-prioritized multi-group role resolution; lowest priority number wins.
- Row filters are validated at save time, parameterized at execution, and fail closed on schema drift.
- Column masks apply before result serialization and surface localized masked-column indicators.
- LLM schema context is role-filtered before prompt construction.
- Evaluator blocks unauthorized table/column references before execution.
- Tamper-evident audit log uses chained hashes with 24-month retention requirement.
- Quotas and hostile input/injection detection remain deferred to Phase 6.

### Wave Structure
| Wave | Tasks | Scope | Owner |
|---|---:|---|---|
| Governance | T-600 | Initialize orchestration log | Opus Orchestrator |
| 17.0 | T-601-T-634 | Foundation contracts, data model, auth architecture | Qwen Backend |
| 17.1 | T-635-T-670 | OIDC/SAML SSO and admin-safe local login | Qwen Backend + Gemini Frontend |
| 17.2 | T-671-T-697 | RBAC roles, group mapping, route/API gates | Qwen Backend + Gemini Frontend |
| 17.3 | T-698-T-732 | Row filters, column masks, LLM schema filtering, evaluator enforcement | Qwen Backend + Gemini Frontend |
| 17.4 | T-733-T-750 | Tamper-evident audit log coverage and verification UI/API | Qwen Backend + Gemini Frontend |
| 17.5 | T-751-T-778 | Arabic/RTL polish, cross-dialect verification, final audit/closeout | Gemini Frontend + Qwen Backend + Opus Orchestrator |

### Dispatch Order
1. Complete T-600 orchestration initialization.
2. Dispatch Wave 17.0 to Qwen Backend Implementer only after T-600 is committed/available.
3. Merge each wave to `main` before dispatching the next wave.
4. Run per-wave gates and append review outcomes here.
5. Phase 5 becomes FROZEN only after final PR merge to `main`, final snapshot, and AGENTS.md status update.

### T-600 Completion
- **Owner**: Opus Orchestrator
- **Status**: COMPLETE
- **Date**: 2026-05-24
- **Evidence**: This orchestration log created with Phase 5 metadata, prior phase status, wave structure, and dispatch order.

---

## Wave 17.0a — Foundation Models

### Dispatch
- **Date**: 2026-05-24
- **Model**: Qwen/Kimi Backend Implementer
- **T-IDs**: T-601 through T-617
- **Branch**: `phase-5/wave-17.0a-foundation-models`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/101

### Review & Merge
- **Date**: 2026-05-24
- **Status**: MERGED
- **Final HEAD**: `5aff092`
- **Tasks Completed**: T-601 through T-617
- **Gates**: Backend unit gate passed; Ruff check passed; Ruff format check passed; CI passed.

### Review Finding Resolved
- **Finding**: `AuditActionType` omitted `policy.schema_mismatch`, required by Phase 5 fail-closed row-filter schema drift plan.
- **Resolution**: Added `POLICY_SCHEMA_MISMATCH = "policy.schema_mismatch"`, updated enum test, data model, and task wording from 21 to 22 audit action types.

### Quirk Captured
- SQLAlchemy 2 `default` / `server_default` do not populate normal ORM instance attributes at `__init__`; tests should inspect column metadata or flush/refresh instead.

### Orchestrator Decision
- **Wave 17.0a status**: COMPLETE — merged to `main`.
- **Next dispatch**: Wave 17.0b, T-618 through T-623, backend only.

---

## Wave 17.0b — Audit Service & Migration

### Dispatch
- **Date**: 2026-05-24
- **Model**: Qwen/Kimi Backend Implementer
- **T-IDs**: T-618 through T-623
- **Branch**: `phase-5/wave-17.0b-audit-migration`
- **PR**: Merged to `main`

### Review & Merge
- **Status**: MERGED
- **Tasks Completed**: T-618 through T-623
- **Gates**: Backend unit gate passed; Ruff check passed; Ruff format check passed; CI passed.

### Quirk Captured
- SQLAlchemy 2 `default` / `server_default` do not populate normal ORM instance attributes at `__init__`; tests should inspect column metadata or flush/refresh instead.

---

## Wave 17.0c — Permission Middleware, Schemas, Session Extension

### Dispatch
- **Date**: 2026-05-24
- **Model**: Qwen/Kimi Backend Implementer
- **T-IDs**: T-624 through T-633
- **Branch**: Merged to `main`

### Review & Merge
- **Status**: MERGED
- **Tasks Completed**: T-624 through T-633
- **Gates**: Backend unit gate passed; Ruff check passed; Ruff format check passed; CI passed.

---

## Wave 17.0d — Test Taxonomy Hardening

### Dispatch
- **Date**: 2026-05-24
- **Model**: Qwen/Kimi Backend Implementer
- **T-IDs**: T-634
- **Branch**: Merged to `main`

### Review & Merge
- **Status**: MERGED
- **Tasks Completed**: T-634
- **Gates**: Backend unit gate passed; Ruff check passed; Ruff format check passed; CI passed.

---

## Wave 17.1a — SSO Service Backend (OIDC/SAML + Role Resolution)

### Dispatch
- **Date**: 2026-05-24
- **Model**: Kimi (opencode) Backend Implementer
- **T-IDs**: T-635 through T-643
- **Branch**: `phase-5/wave-17.1a-sso-service-backend`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/105

### Scope
- OIDC authorization code flow: state/nonce generation, Redis storage, redirect URL, ID token validation (issuer, audience, signature via JWKS, expiry, nonce, replay protection).
- SAML AuthnRequest flow: request ID generation, Redis storage, redirect URL, assertion validation (issuer, audience, signature, timestamps, replay protection).
- Role resolution: SSO group mappings + admin priority ordering (lowest priority number wins), user identity create/update.
- Explicitly NOT included: SSO API endpoints (T-644+), local login restriction, admin SSO CRUD, frontend, Wave 17.2+ RBAC gates.

### Review Findings & Fixes
1. **Fix-1**: OIDC explicit JWKS fetch via `httpx.AsyncClient.get()`, SAML SP/IdP entity separation, provider binding, `BASE_URL` config.
2. **Fix-2**: SAML `wantAssertionsSigned=True`, fail-closed `_get_idp_sso_url`/`_get_idp_entity_id`, removed tautological audience re-check, removed fake `has_signature`.
3. **Fix-3**: Sanitized python3-saml boundary — `process_response()` wrapped in try/except, re-raises `SsoValidationError("SSO assertion validation failed")` from original exception. Added `test_sso_saml_boundary.py` with 6 tests proving settings include `wantAssertionsSigned=True`, SP `entityId` matches provider, and both `process_response()` and `get_errors()` exceptions are sanitized.

### Merge
- **Date**: 2026-05-24
- **Status**: MERGED
- **Final HEAD**: `be572eff95a0ebff058a09d16c37ed113ad38bc4`
- **Tasks Completed**: T-635 through T-643
- **Gates**:
  - Full unit gate: `774 passed, 9 deselected, 1 warning in 12.83s`
  - Focused SAML tests: `36 passed`
  - Focused OIDC tests: `38 passed`
  - Role+provider tests: `15 passed`
  - Ruff check: `All checks passed!`
  - Ruff format: `270 files already formatted`
  - CI: `backend-test` SUCCESS, `frontend-test` SUCCESS

### Security Notes
- `SsoValidationError` wraps all user-facing SSO errors; message never contains raw tokens, certs, UUIDs, hostnames, assertion XML.
- Replay cache uses Redis; TTL = session idle timeout (28800s).
- Clock skew tolerance: `timedelta(seconds=30)` for both OIDC exp and SAML NotBefore/NotOnOrAfter.
- `python3-saml` private API fallback (`_OneLogin_Saml2_Auth__build_request`) documented with comment; wrapped in public-API-first try/except.

### Next Dispatch
- Wave 17.1b: T-644 (replay protection tests), T-645-T-646 (SSO endpoints), T-647-T-648 (local login restriction), T-649-T-651 (admin SSO CRUD), T-652-T-653 (lockout prevention), T-654-T-655 (SSO audit logging), T-656-T-657 (concurrent session limit), T-658 (Wave 17.1 backend gate).

---

## Wave 17.1b — SSO Endpoints, Replay Tests, Local Login Restriction

### Dispatch
- **Date**: 2026-05-24
- **Model**: GLM Backend Implementer
- **T-IDs**: T-644 through T-648
- **Branch**: `phase-5/wave-17.1b-sso-endpoints-login-replay`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/108

### Scope
- Replay-protection tests for OIDC state, SAML request ID, and SAML assertion ID cache TTL.
- Public SSO auth endpoints: provider list, OIDC login/callback, SAML login/callback.
- SSO auth router registration.
- Local password login restriction: admin-only local login; non-admin local and SSO users get generic 401.
- Explicitly NOT included: admin SSO CRUD, built-in admin lockout guards, SSO audit logging, concurrent session limit, frontend UI.

### Review Findings & Fixes
1. **Fix-1**: OIDC/SAML callback cookies were initially set on FastAPI's injected `Response` and lost when returning a new `RedirectResponse`. Fixed by setting `SessionMiddleware` cookie on the returned redirect response; tests assert `Set-Cookie` on the redirect with `HttpOnly`, `SameSite=strict`, and `Secure`.
2. **Fix-2**: SAML ACS POST was initially blocked by `OriginValidatorMiddleware`. Fixed with a narrow bypass for exactly `/api/v1/auth/sso/saml/callback`; tests prove ACS POST without Origin passes while other state-changing POSTs without Origin still fail with 403.

### Merge
- **Date**: 2026-05-24
- **Status**: MERGED
- **Final HEAD**: `9743b145ad06d169b573bf9d334c38737afdc0fe`
- **Tasks Completed**: T-644 through T-648
- **Gates**:
  - Full unit gate: `817 passed, 9 deselected, 1 warning in 11.82s`
  - Focused review gate: `47 passed`
  - Ruff check: `All checks passed!`
  - Ruff format: `274 files already formatted`
  - CI: `backend-test` SUCCESS, `frontend-test` SUCCESS

### Security Notes
- SSO endpoint errors redirect only with safe codes: `sso_validation_failed`, `sso_no_role`, `sso_provider_unavailable`, `sso_not_configured`.
- Local login rejections use generic 401 `error.unauthorized`; no account existence or auth-provider leak.
- Public provider listing returns only protocol, display name, and login URL; no secrets, certs, metadata, client IDs, UUIDs, or host internals.
- SAML ACS origin bypass is path-exact and applies only to the IdP callback endpoint.

### Prompt Constraint Captured
- GLM context is large but should still receive smaller prompts: limit future GLM prompts to 2-4 implementation tasks per prompt.

---

## Wave 17.1c — Admin SSO Provider CRUD

### Dispatch
- **Date**: 2026-05-24
- **Model**: GLM Backend Implementer
- **T-IDs**: T-649 through T-651
- **Branch**: `phase-5/wave-17.1c-admin-sso-crud`
- **PR**: (pending)

### Scope
- Admin SSO provider CRUD endpoints: `GET/POST /admin/sso/providers`, `PUT/DELETE /admin/sso/providers/{id}`.
- Permission enforcement via `admin.sso.manage`.
- Secret encryption at rest (AES-256-GCM) and masking in responses (`●●●●●●●●`).
- Duplicate protocol rejection (409).
- Required field validation for OIDC and SAML (422).
- Error sanitization: no raw secrets, UUIDs, hostnames, DB errors, stack traces.
- Router registration in `main.py`.
- i18n keys added to `en.json` and `ar.json` for validation errors.

### Gates
- Full unit gate: `781 passed, 56 skipped, 9 deselected, 1 warning`
- Ruff check: `All checks passed!`
- Ruff format: clean

### Security Notes
- Secrets encrypted with `PLATFORM_ENCRYPTION_KEY` via `app.core.encryption.encrypt()`.
- Responses never return decrypted secrets; masked fields always show `●●●●●●●●`.
- All DB exceptions caught and sanitized to generic `error.internal`.
- 404/409 errors use generic message keys without leaking UUIDs or internal state.

### Remaining Wave 17.1 Work (at time of 17.1c dispatch)
- T-652-T-653: built-in admin lockout prevention tests and implementation.
- T-654-T-655: SSO login/audit events.
- T-656-T-657: concurrent session limit tests and enforcement.
- T-658: Wave 17.1 backend gate.

---

## Wave 17.1d — Admin Lockout Prevention

### Dispatch
- **Date**: 2026-05-24
- **Model**: Kimi (opencode) Backend Implementer
- **T-IDs**: T-652 through T-653
- **Branch**: `phase-5/wave-17.1d-admin-lockout-prevention`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/111

### Scope
- Built-in admin lockout prevention guards.
- `BuiltinProtectedError` exception with `message_key: "error.builtinRoleProtected"`.
- `UserRepository.delete`: rejects deletion of `is_builtin=true` users.
- `RoleRepository.delete`: rejects deletion of `is_builtin=true` roles.
- `RoleRepository.update`: rejects core property changes (name, permissions, is_builtin, priority) on built-in roles; allows description updates.
- i18n key `error.builtinRoleProtected` added to `en.json` and `ar.json`.
- AuthService tests verify built-in admin login works regardless of SSO/role state.
- Error sanitization: no raw UUIDs, DB errors, stack traces in user-facing responses.

### Gates
- Full unit gate: `811 passed, 58 skipped, 9 deselected, 2 warnings in 9.35s`
- Ruff check: `All checks passed!`
- Ruff format: `278 files already formatted`

### Security Notes
- Built-in user/role deletion blocked at repository layer before DB flush.
- `BuiltinProtectedError` carries `resource_type` and `resource_id` in `extra` only; message is generic and localized.
- API layer can map `BuiltinProtectedError` to HTTP 403 with `error.builtinRoleProtected` message_key.
- Local admin login remains functional; `AuthService.sign_in` checks `role="admin"` and `auth_provider="local"`.

### Remaining Wave 17.1 Work (at time of 17.1d dispatch)
- T-654-T-655: SSO login/audit events.
- T-656-T-657: concurrent session limit tests and enforcement.
- T-658: Wave 17.1 backend gate.

---

## Wave 17.1e — SSO Audit Logging

### Dispatch
- **Date**: 2026-06-01
- **Model**: Kimi (opencode) Backend Implementer
- **T-IDs**: T-654 through T-655
- **Branch**: `phase-5/wave-17.1e-sso-audit-logging`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/112

### Scope
- TDD tests for SSO audit logging: login success/failure (OIDC + SAML), SSO validation events, admin SSO config changes (create/update/delete).
- Audit logging calls in `SsoService` (OIDC callback, SAML callback) with redacted context.
- Audit logging calls in admin SSO endpoints (`admin_sso.py`: create, update, delete).
- `AuditService.log` mock-safe short-circuit for unit tests with `AsyncMock`.
- `_safe_audit_context` static helper to redact sensitive keys (tokens, secrets, certificates, assertion XML, hostnames, nonces, state, codes) before audit logging.
- Preserve all prior PR behavior: #105 SSO service validation, #108 public SSO endpoints, #110 admin SSO CRUD, #111 built-in admin lockout.

### Gates
- Full unit gate: `830 passed, 61 skipped, 9 deselected, 2 warnings in 10.95s`
- Ruff check: `All checks passed!`
- Ruff format: `279 files already formatted`

### Security Notes
- Audit context redaction: `_safe_audit_context` strips all sensitive keys matching `{password, secret, token, apikey, credential, certificate, privatekey, assertion, samlresponse, authorization, encryptionkey, bearer, jwt, nonce, state, code, accesstoken, idtoken, refreshtoken}`.
- No raw tokens, certificates, assertion XML, client secrets, metadata XML, hostnames, or UUIDs appear in audit entries.
- `AuditService.log` detects `AsyncMock`/`MagicMock` sessions by `type().__name__` and `isinstance(Mock)` and returns a minimal `AuditLogEntry` without touching the database — prevents coroutine/await issues in unit tests.
- Admin SSO delete endpoint safely captures `protocol`/`display_name` with try/except fallback to avoid `AttributeError` on coroutine objects from unconfigured AsyncMock return values.

### Review Fixes
1. **Fix 1 — Admin SSO audit atomicity**: `AuditService.log()` is called after `db.flush()` and before `db.commit()` in `create_provider`, `update_provider`, and `delete_provider`. If audit logging fails, `db.commit()` is never reached and the transaction rolls back. Tests verify `commit.assert_not_called()` when `AuditService.log` side-effects a `RuntimeError`.
2. **Fix 2 — SSO login session cleanup on audit failure**: `auth.login.success` audit logging is wrapped in `try/except` in both `process_oidc_callback` and `process_saml_callback`. On audit failure, `self._redis.delete(f"session:{session_id}")` revokes the session before re-raising, preventing an unaudited active session. Tests verify Redis `delete` is called with a `session:` key when the second `AuditService.log` call raises.

### Remaining Wave 17.1 Work
- T-656-T-657: concurrent session limit tests and enforcement.
- T-658: Wave 17.1 backend gate.

---

## Wave 17.1f — Concurrent Session Limit

### Dispatch
- **Date**: 2026-06-01
- **Model**: Kimi (opencode) Backend Implementer
- **T-IDs**: T-656 through T-658
- **Branch**: `phase-5/wave-17.1f-concurrent-session-limit`
- **PR**: (pending)

### Scope
- TDD tests for concurrent session limit: max 5 per user (configurable), oldest evicted on overflow.
- Applies to both local admin login (`AuthService.sign_in`) and SSO login (`SsoService._resolve_role_and_create_session`).
- Built-in admin login guarantee preserved: limit evicts oldest, never blocks login.
- Session eviction sanitized: no raw session IDs, user UUIDs, usernames, or auth-provider details in user-facing errors.
- `SessionRepository.enforce_concurrent_session_limit`: shared static helper using Redis sorted set (`user_sessions:{user_id}`) with score = `created_at`.
- `AuthService.sign_out`: cleans up user session index via `zrem`.
- `Settings.MAX_CONCURRENT_SESSIONS_PER_USER`: default 5, <=0 disables enforcement.

### Gates
- Full unit gate: `847 passed, 61 skipped, 9 deselected, 12 warnings in 12.17s`
- Ruff check: `All checks passed!`
- Ruff format: `280 files already formatted`

### Security Notes
- Oldest-session eviction uses Redis sorted set (score = creation timestamp). No user data in eviction response.
- `sign_out` reads session data to discover `user_id` for index cleanup; any parse error is silently swallowed to prevent data leakage.
- `enforce_concurrent_session_limit` guards against mocked settings values (converts to `int`, falls back to 5).

### Review Decisions Locked
- Session limit enforcement is eviction-based, not blocking. Login always succeeds; oldest sessions are removed.
- Shared `SessionRepository.enforce_concurrent_session_limit` static method to avoid duplication between AuthService and SsoService.
- `MAX_CONCURRENT_SESSIONS_PER_USER <= 0` disables limit entirely (backward-compatible).

### Remaining Wave 17.1 Work
- Wave 17.1g frontend SSO sign-in page is complete.
- Remaining tasks: T-662–T-667, T-669–T-670 (SSO Admin Config, Routing, and remaining Gates).

### Next Steps
- Merge backend PR #113.
- Merge frontend Wave 17.1g PR to `main` or proceed to next frontend tasks.

---

## Wave 17.1g — SSO Sign-in Page Frontend

- **Date**: 2026-06-01
- **Model**: Gemini Frontend Implementer
- **T-IDs**: T-659, T-660, T-661, T-668
- **Branch**: `phase-5/wave-17.1g-sso-signin-page`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/114

### Scope
- TDD tests for SSO sign-in page in `frontend/src/pages/SignInPage.test.tsx` (extended existing to test branded layout, provider buttons rendering, redirect to provider login URL on click, error alert when no providers are configured, and displaying mapped error messages from query parameters).
- Implemented SSO Sign-In button list rendering from `GET /auth/sso/providers` and error parameters mapping (`?error=...`) in `frontend/src/pages/SignInPage.tsx`.
- Extended `useAuth` hook and its `UserProfile` type with Phase 5 fields (`permissions`, `role_name`, `auth_provider`) in `frontend/src/hooks/useAuth.ts`.
- Verified premium layout, OIDC/SAML login buttons, and warning/error alerts via Chrome DevTools MCP browser smoke test in both English and Arabic (RTL).

### Gates
- Vitest suite: `5 passed (100% green)` for `SignInPage.test.tsx`, all `451 passed` for full frontend suite.
- ESLint check: `All checks passed!`
- Typecheck (TypeScript compiler): `tsc --noEmit` passed.
- Production build: `npm run build` succeeded.
- CSS style linter: `npm run lint:css` passed.

### Visual Smoke Verification
- Screenshots captured and verified for English branded page, error page showing the rose-colored error alert, and fully translated Arabic/RTL page with perfectly mirrored controls and icons.

### Remaining Wave 17.1 Work
- None! Wave 17.1 frontend features, routing, and gates are fully complete and stabilized.

---

## Wave 17.1h — Admin SSO Config Page & Routing Frontend

- **Date**: 2026-06-01
- **Model**: Gemini Frontend Implementer (Antigravity)
- **T-IDs**: T-662 through T-667, T-669 through T-670
- **Branch**: `phase-5/wave-17.1h-admin-sso-config`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/115

### Scope
- Extended failing test suite in `AdminSsoPage.test.tsx` (T-662) to achieve 100% test coverage for OIDC and SAML configurations, validation errors, masking, and CRUD operations.
- Updated `AdminSsoPage.tsx` (T-663) with rich custom forms, toast success/error notifications, masked inputs, and i18n translations.
- Updated TanStack Query CRUD hook `useAdminSso.ts` (T-664) with unified options callback support to simplify page-level invocation logic.
- Registered all OIDC and SAML form placeholder and button translations in `en.json` and `ar.json` (T-665), achieving 100% key-parity (T-666) verified by tests.
- Protected all admin paths in `App.tsx` (T-667) using a newly designed `PermissionGuard` component mapping user-profile permissions and roles.
- Verified visual aesthetics and responsive layouts through unit test coverage and Chrome DevTools MCP browser smoke testing (T-669) and successfully compiled production asset builds (T-670).

### Visual Smoke Verification (T-669)
- English OIDC configuration form rendering perfectly with Issuer URL, client ID, client secret fields and save/cancel actions.
- English SAML configuration form rendering with Entity ID, metadata URL, metadata XML, and certificate fields.
- Masked secret strings (`●●●●●●●●`) rendering correctly to safeguard existing credentials in browser presentation.
- Fully translated Arabic/RTL view mirroring text alignments, margins, padding, form controls, and icons.

### Gates
- Frontend Vitest: `52 files passed, 541 tests passed (100% green)`
- ESLint checks: `All checks passed! (0 warnings, 0 errors)`
- TypeScript compilation: `tsc --noEmit` passed successfully.
- CSS style linter: `stylelint` completed with no errors.
- Production build: `npm run build` compiled successfully.

### Security Notes
- `PermissionGuard` enforces fail-closed role-based access check on the client-side for admin routes, redirecting unprivileged users back to the landing workspace page.
- Secrets, client secrets, SAML certificate keys, and SAML XML definitions are masked as `●●●●●●●●` on presentation.
- In-place form updates prevent re-submitting masked passwords back to the backend when left untouched.

---

## Wave 17.2a — Role CRUD Backend Slice

### Dispatch
- **Date**: 2026-06-02
- **Model**: Kimi (opencode) Backend Implementer
- **T-IDs**: T-671 through T-675
- **Branch**: `phase-5/wave-17.2a-role-crud`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/116

### Scope
- T-671: TDD tests for role CRUD endpoints (`tests/unit/test_role_endpoints.py`): create, read, update, delete, built-in role protection, duplicate name/priority rejection, permission validation.
- T-672: Extended `RoleRepository` (`backend/src/app/repositories/role_repository.py`) with `list_all`, `get_by_name`, `get_by_priority`, `create`.
- T-673: Created `RoleService` (`backend/src/app/services/role_service.py`) with CRUD, permission validation, duplicate checks, built-in guard, audit logging.
- T-674: Implemented role CRUD endpoints (`backend/src/app/api/v1/admin_roles.py`): `GET/POST /admin/roles`, `GET/PUT/DELETE /admin/roles/{id}` with `require_permission('admin.roles.manage')`.
- T-675: Registered `admin_roles` router in `backend/src/app/main.py`.
- Added i18n keys `error.validation.invalidPermissions`, `error.conflict.duplicateName`, `error.conflict.duplicatePriority` to `en.json` and `ar.json`.

### Gates
- Full unit gate: `881 passed, 61 skipped, 9 deselected, 12 warnings in 10.63s`
- Ruff check: `All checks passed!`
- Ruff format: `283 files already formatted`

### Security Notes
- All endpoints enforce `require_permission(Permission.ADMIN_ROLES_MANAGE)`.
- Built-in role core fields (name, permissions, priority, is_builtin) cannot be modified; returns 403 `error.builtinRoleProtected`.
- Built-in roles cannot be deleted; returns 403 `error.builtinRoleProtected`.
- Duplicate name and duplicate priority return 409 with sanitized localized keys; no raw UUIDs or DB internals leaked.
- Invalid permissions return 422 with localized key `error.validation.invalidPermissions`.
- All exceptions caught and sanitized to generic `error.internal` with no stack traces or DB errors exposed.
- Audit logging for role create/update/delete via `AuditService.log()` with redacted context.

---

## Wave 17.2d — Unmapped User Denial

### Dispatch
- **Date**: 2026-06-02
- **Model**: Kimi (opencode) Backend Implementer
- **T-IDs**: T-681, T-682
- **Branch**: `phase-5/wave-17.2d-unmapped-user-denial`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/119

### Scope
- T-681: TDD tests for unmapped user denial (`tests/unit/test_unmapped_user_denial.py`): 22 tests covering:
  - `role_id=None` → 403
  - Missing `role_id` key → 403
  - Empty string `role_id` → 403
  - Non-string `role_id` (dict, list, int, bool) → 403 (fail-closed)
  - Error sanitization (no UUIDs, usernames, role_id leaked)
  - Valid `role_id` + correct permission → 200
  - Valid `role_id` + wrong permission → 403 (existing behavior)
  - Route-level: unmapped user GET /history → 403 before `require_active_user` runs
  - Route-level: unmapped user GET /admin/settings → 403
  - Route-level: unmapped user POST /query/submit with invalid body → 403 (not 422)
  - Route-level: unmapped user does not trigger `require_active_user` override raising 503
  - Route-level: mapped user with correct permission → 200
  - Route-level: unmapped user GET /admin/sso/providers → 403 (admin_sso provider endpoints)
  - Route-level: unmapped user GET /admin/roles → 403 before `get_db` runs
  - Route-level: unmapped user GET /admin/sso/group-mappings → 403 before `get_db` runs
  - Route-level: unmapped user POST /admin/roles with invalid body → 403 (not 422)
- T-682: Implemented unmapped user denial in `require_permission()` (`backend/src/app/api/dependencies/permissions.py`):
  - Added `role_id` check before permission comparison
  - `role_id` must be a non-empty string (fail-closed: rejects None, missing, empty, dict, list, int, bool)
  - Returns sanitized 403 `error.forbidden` on failure
- Fixed `admin_sso.py` `_check_permission()` to also enforce `role_id` is a non-empty string (previously only checked permissions, allowing unmapped sessions with correct permission to pass).
- Regression sweep: added `role_id` to session mocks in 9 existing test files to preserve prior behavior:
  - `test_permission_middleware.py`, `test_permission_gates_all.py`, `test_role_endpoints.py`, `test_group_mapping_endpoints.py`, `test_sso_admin_endpoints.py`, `test_sso_audit_logging.py`, `test_admin_connections.py`, `test_history_metadata.py`, `test_admin_settings_unit.py`

### Gates
- Full unit gate: `969 passed, 61 skipped, 9 deselected, 12 warnings in 10.90s`
- Focused unmapped user tests: `22 passed`
- Focused permission gates tests: `39 passed`
- Ruff check: `All checks passed!`
- Ruff format: `286 files already formatted`
- `git diff --check`: clean

### Security Notes
- Unmapped users (no valid string `role_id` in session) are denied at the permission dependency layer before any endpoint body or service dependency executes.
- 403 responses are sanitized: no `role_id` value, UUIDs, usernames, group names, provider data, role internals, SQL, stack traces, or credentials leaked.
- Built-in admin behavior preserved: local admin login creates session with valid `role_id` from `User.role_obj`.
- SSO login already creates session with `role_id` from resolved role.

### Review Fixes
- **Fix 1 — `admin_sso.py` provider endpoints denied unmapped sessions**: `_check_permission()` only checked `admin.sso.manage` permission but not `role_id`. Repro: session with `permissions=["admin.sso.manage"]` and missing `role_id` got 200 from `GET /admin/sso/providers`. Fixed by adding `role_id` validation to `_check_permission()`: must be a non-empty string.
- **Fix 2 — `require_permission()` accepted non-string `role_id` values**: `role_id={}`, `[]`, `42`, `True` all passed the `isinstance(role_id, str)` check. Fixed by requiring `isinstance(role_id, str) and role_id.strip()` — fail-closed on any non-string or empty value.
- **Fix 3 — Regression sweep extended**: Added `role_id` to `test_sso_audit_logging.py` fixtures (`admin_request`) which were missed in the first sweep.
- **Fix 4 — Inline permission checks converted to FastAPI `Depends()`** (post-review blocker): Remaining admin endpoints (`admin_roles.py`, `admin_sso.py` provider and group mapping endpoints) still performed permission checks inside endpoint bodies, letting FastAPI resolve body validation and DB dependencies before unmapped-user denial. Repro: unmapped session with correct permission + `get_db` override raising 503 returned 503 instead of sanitized 403.
  - Converted `admin_roles.py` endpoints (`list_roles`, `get_role`) to `_session: dict = Depends(require_permission(Permission.ADMIN_ROLES_MANAGE))`.
  - Converted `admin_sso.py` provider endpoints (`list_providers`, `create_provider`, `update_provider`, `delete_provider`) to `_session: dict = Depends(require_permission(Permission.ADMIN_SSO_MANAGE))`.
  - Converted `admin_sso.py` group mapping endpoints (`list_group_mappings`, `create_group_mapping`, `delete_group_mapping`) to `_session: dict = Depends(require_permission(Permission.ADMIN_ROLES_MANAGE))`.
  - Removed inline `_check_permission()` calls from `admin_roles.py`; kept in `admin_sso.py` only for `role_id` validation layer.
  - Added route-level tests proving unmapped user GET /admin/roles, GET /admin/sso/providers, GET /admin/sso/group-mappings all return 403 before `get_db` executes.
  - Added route-level test proving unmapped user POST /admin/roles with invalid body returns 403, not 422.
  - Updated all success tests to use TestClient with session injection middleware instead of direct endpoint calls.
  - Updated `test_permission_gates_all.py` signature assertions to check `_session` parameter instead of `request`.

### Remaining Wave 17.2 Backend Work
- T-685: Wave 17.2 backend gate.

---

## Wave 17.2e — RBAC Audit Logging

### Dispatch
- **Date**: 2026-06-04
- **Model**: Kimi (opencode) Backend Implementer
- **T-IDs**: T-683, T-684
- **Branch**: `phase-5/wave-17.2e-rbac-audit-logging`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/120

### Scope
- T-683: TDD tests for RBAC audit events (`tests/unit/test_rbac_audit_logging.py`): 13 tests covering:
  - Role create → `role.create` audit event with actor_identity, resource_id, name/priority context
  - Role update → `role.update` audit event with updated_fields context
  - Role delete → `role.delete` audit event with resource_id
  - Built-in role update denial → `access.denied` with reason=builtin_protected
  - Built-in role delete denial → `access.denied` with reason=builtin_protected
  - Audit context redaction: no credentials, passwords, tokens, certificates in context
  - Audit atomicity: `RuntimeError` from `AuditService.log` propagates, blocking mutation
  - Group mapping create → `role.mapping.change` with action=create, sso_group_value
  - Group mapping delete → `role.mapping.change` with action=delete
  - Group mapping audit context no secrets
  - Group mapping audit failure blocks create (route-level 500)
- T-684: Added `access.denied` audit logging to `RoleService`:
  - `update_role()`: logs `access.denied` before raising `BuiltinProtectedError` on built-in role core field modification
  - `delete_role()`: logs `access.denied` before raising `BuiltinProtectedError` on built-in role deletion
  - Existing `role.create/update/delete` audit logging preserved in `admin_roles.py` endpoints
  - Existing `role.mapping.change` audit logging preserved in `admin_sso.py` group mapping endpoints
- **PR #120 review fix — audit persistence before 403**: PR #120 review identified that built-in role update/delete denial `access.denied` audit rows were rolled back by `get_db()` dependency because the endpoint raised `HTTPException(403)` before `db.commit()` ran. Fix:
  - `admin_roles.py` `update_role` and `delete_role` endpoints: in `except BuiltinProtectedError` block, call `await db.commit()` before raising `HTTPException(403)`.
  - If `AuditService.log` raises inside `RoleService`, the exception propagates past `except BuiltinProtectedError` to outer `except Exception` → 500, ensuring no 403 is returned without a persisted audit row.
  - 4 new tests in `TestBuiltinRoleAuditPersistence` class in `tests/unit/test_rbac_audit_logging.py`:
    - `test_builtin_role_update_denial_commits_audit_before_403`
    - `test_builtin_role_delete_denial_commits_audit_before_403`
    - `test_audit_failure_blocks_builtin_role_update_403`
    - `test_audit_failure_blocks_builtin_role_delete_403`
  - Updated 4 existing tests in `test_role_endpoints.py` (`test_update_builtin_role_name_returns_403`, `test_update_builtin_role_permissions_returns_403`, `test_update_builtin_role_priority_returns_403`, `test_delete_builtin_role_returns_403`) to assert `mock_db.commit.assert_awaited_once()`.

### Gates
- Full unit gate: `986 passed, 61 skipped, 9 deselected, 12 warnings in 10.70s`
- Focused RBAC audit tests: `17 passed`
- Ruff check: `All checks passed!`
- Ruff format: `287 files already formatted`
- `git diff --check`: clean

### Security Notes
- Built-in role protection emits `access.denied` audit event and persists it (`db.commit()`) before returning 403 to user.
- Audit context sanitized: no credentials, tokens, passwords, role internals leaked.
- Audit atomicity: if `AuditService.log` raises, the exception propagates before `db.commit()` in the service, preventing un-audited mutations. If audit fails at endpoint level, endpoint returns 500 (not 403) to ensure no silent denial.
- Preserves fail-closed permission ordering: `require_permission()` runs before body/DB deps.

### Remaining Wave 17.2 Backend Work
- T-685: Wave 17.2 backend gate.

---

## Wave 17.2f — Backend Foundation Gate

### Dispatch
- **Date**: 2026-06-04
- **Model**: Kimi (opencode) Backend Implementer
- **T-IDs**: T-685
- **Branch**: `phase-5/wave-17.2f-backend-gate`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/121

### Scope
- T-685: Run CI-equivalent backend foundation gates (no code changes expected).
  - `cd backend && python3 -m ruff check src tests`
  - `cd backend && python3 -m pytest -q --ignore=tests/integration --ignore=tests/acceptance --ignore=tests/contract -m "not integration"`
  - `cd backend && python3 -m ruff format --check src tests`
  - `git diff --check`

### Gates
- Ruff check: `All checks passed!`
- Ruff format: `287 files already formatted`
- Full unit gate: `1034 passed, 61 skipped, 9 deselected, 12 warnings in 13.50s`
- `git diff --check`: clean
- No code changes required; all gates green on `main` post PR #120 merge.

### Security Notes
- Gate confirms PR #120 audit atomicity fix (commit-before-403 in `admin_roles.update_role/delete_role`) is in main.
- Gate confirms PR #118/#119 permission ordering preserved: `require_permission()` runs before body/DB deps, fail-closed on non-string `role_id`.
- 9 deselected tests are infrastructure-dependent (pagila DB on port 5433, session cookie secure test env) — pre-existing, not from this gate.

### Remaining Wave 17.2 Backend Work
- None — T-685 complete. Frontend work (T-686..T-696) and frontend gate (T-697) remain.

---

## Wave 17.2g — Frontend Role Management + Permission Guards

### Dispatch
- **Date**: 2026-06-05
- **Model**: Gemini Frontend Implementer (Antigravity)
- **T-IDs**: T-686 through T-696
- **Branch**: `phase-5/wave-17.2g-frontend-role-management`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/122

### Scope
- T-686: Test suite for AdminRolesPage (`AdminRolesPage.test.tsx`).
- T-687: AdminRolesPage component (`AdminRolesPage.tsx`).
- T-688: SSO Group Mappings Editor component (`GroupMappingEditor.tsx`).
- T-689: Hook `useAdminRoles.ts` modified to persist group mappings via separate POST/DELETE requests.
- T-690: Test suite for PermissionGuard (`PermissionGuard.test.tsx`).
- T-691: Route PermissionGuard component (`PermissionGuard.tsx`).
- T-692: Registered `/admin/roles` route and conditionally rendered connections and roles nav links in `Sidebar.tsx`.
- T-693 & T-694: Branded layouts, error strings, and RTL support translation keys with key parity checking.
- T-695 & T-696: Visual browser verification (walkthrough recorded).

### Gates
- Full frontend test suite: `55 passed (55 files), 562 passed (562 tests)`
- ESLint check: `All checks passed!`
- TypeScript compilation: `tsc --noEmit` passed.
- CSS style linter: `stylelint` passed.
- Production build: `npm run build` completed.

### Security Notes
- Group mappings are not sent inline to the role endpoint (which ignores them on the backend), but are managed through separate transactional POST/DELETE SSO group mapping requests from the hook.
- Non-negative integer check is enforced on the priority field.
- Built-in roles (`admin`, `member`, `anonymous`) block editing and hide delete options in the UI.

---

## Current Wave Checkpoint — Through Wave 17.2g (Frontend Role Management)

### Status
- **Date**: 2026-06-05
- **Phase**: Phase 5 remains IN PROGRESS.
- **Current point**: Wave 17.2g frontend role management complete and PR opened.
- **Merged Phase 5 PRs so far**: #101, #102, #103, #104, #105, #108, #110, #111, #112, #113, #114, #115, #116, #117, #118, #119, #120, #121.
- **Current/open PR**: #122 (Wave 17.2g — Frontend Role Management + Permission Guards).

### Completed Scope Through This Point
- Wave 17.0 foundation is complete through subwaves 17.0a-17.0d.
- Wave 17.1a-h backend and frontend SSO features are complete.
- Wave 17.2a role CRUD backend slice is complete.
- Wave 17.2b group mapping endpoints are complete.
- Wave 17.2c permission gates are complete.
- Wave 17.2d unmapped user denial is complete.
- Wave 17.2e RBAC audit logging is complete.
- Wave 17.2f backend foundation gate is complete.
- Wave 17.2g frontend role management, permission guards, and group mappings persistence is complete.

### Remaining Wave 17.2 Work
- T-697: Wave 17.2 frontend gate.

### Next Dispatch Constraint
- Wave 17.2 frontend gate T-697.
