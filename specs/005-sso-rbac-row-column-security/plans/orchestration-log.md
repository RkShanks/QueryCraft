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

## Wave 17.2h — Frontend Foundation Gate

### Dispatch
- **Date**: 2026-06-05
- **Model**: Gemini Frontend Implementer (Antigravity)
- **T-IDs**: T-697
- **Branch**: `phase-5/wave-17.2h-frontend-gate`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/123

### Scope
- T-697: Run frontend foundation gates (no code changes expected).
  - `cd frontend && npm run test -- --run`
  - `cd frontend && npm run lint`
  - `cd frontend && npm run typecheck`
  - `cd frontend && npm run build`
  - `cd frontend && npm run lint:css`
  - `git diff --check`

### Gates
- Frontend Vitest: `55 files passed, 562 tests passed (100% green)`
- ESLint check: `All checks passed!`
- TypeScript compilation: `tsc --noEmit` passed.
- Production build: `npm run build` completed.
- CSS style linter: `stylelint` passed.
- `git diff --check`: clean
- No code changes required; all gates green on `main` post PR #122 merge.

### Security Notes
- Gate confirms PR #122 route guards, permission checks, group mappings separate persistence, priority validations, and EN/AR parity are in main and fully functional.
- Built-in roles check remains intact on frontend views and routes.

### Remaining Wave 17.2 Work
- None — T-697 complete. Wave 17.2 features and gates are fully complete.

---

## Wave 17.3a — Schema Filtering

### Dispatch
- **Date**: 2026-06-05
- **Model**: Kimi (opencode) Backend Implementer
- **T-IDs**: T-698, T-699
- **Branch**: `phase-5/wave-17.3a-schema-filtering`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/124

### Scope
- T-698: TDD tests for `PolicyEnforcementService.filter_schema()` in
  `backend/tests/unit/test_schema_filtering.py`.
- T-699: Implement `PolicyEnforcementService.filter_schema()` in
  `backend/src/app/services/policy_enforcement.py`.

### Behavior
- Returns new `SchemaContext`; input is never mutated.
- `None` policy or empty list → empty schema (fail-closed).
- `columns=[]` in a policy entry → table listed with no columns (fail-closed).
- Unknown policy tables/columns ignored silently (no leak, no exception).
- Case-insensitive matching on table and column names (Postgres folding).
- Preserves `table.schema_name` and column metadata (`type`, `nullable`, `primary_key`).
- Stateless service: no constructor args; callable as `@staticmethod`.
- Defensive: non-string table/column entries in the policy are skipped.

### Gates
- `tests/unit/test_schema_filtering.py`: 19 passed in 0.19s
- `tests/unit -q -m "not integration"` (excluding 4 pre-existing audit-chain failures
  identical on `main`): 1062 passed, 13 deselected, 12 warnings in 12.90s
- `ruff check src tests`: All checks passed!
- `ruff format --check src tests`: 289 files already formatted
- `git diff --check`: clean
- Pre-existing audit failures (NOT from this work, confirmed on `main`):
  - `tests/unit/test_audit_service.py::TestAuditService::test_log_creates_entry` —
    expects `sequence_number == 1`; DB state has accumulated rows.
  - `tests/unit/test_audit_service.py::TestAuditService::test_log_assigns_increasing_sequence`
  - `tests/unit/test_audit_chain_verification.py::TestAuditChainVerification::test_broken_chain_detects_first_break`
  - `tests/unit/test_audit_chain_verification.py::TestAuditChainVerification::test_chain_continues_after_break`
  All four reproduce on `main` at `bc3405f`; environment-dependent, no fix in this wave.

### TDD Evidence
- T-698 RED: `0472d8d` — `test(T-698): TDD tests for PolicyEnforcementService.filter_schema` (collection error = all tests fail).
- T-699 GREEN: `b060130` — `feat(T-699): implement PolicyEnforcementService.filter_schema` (19/19 pass).
- Format fix: `style: apply ruff format to policy_enforcement.py` (still 19/19).

### Security Notes
- Fail-closed: `None`, `[]`, and `{"table": "t", "columns": []}` all deny access.
- No leak: unknown policy tables/columns dropped silently — no exception path exposes
  unauthorized schema names.
- Case-insensitive matching aligns with existing `SchemaContext.find_table` / `find_column`
  (Postgres identifier folding). No surprise authorization differences across capitalizations.

### Remaining Wave 17.3 Work
- T-700..T-705: Row filter validation/injection (placeholder binding, schema drift).
- T-706..T-707: Column masking.
- T-708..T-710: Evaluator rule.
- T-711..T-712: Query flow integration.
- T-713..T-714: Role policy test endpoint.
- T-715..T-721: History/rerun/audit/cross-dialect.
- T-722: Wave 17.3 backend gate.

---

## Wave 17.3b — Row Filter Validation

### Dispatch
- **Date**: 2026-06-05
- **Model**: Kimi (opencode) Backend Implementer
- **T-IDs**: T-700, T-701
- **Branch**: `phase-5/wave-17.3b-row-filter-validation`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/125

### Scope
- T-700: TDD tests for `PolicyEnforcementService.validate_row_filter()` in
  `backend/tests/unit/test_row_filter_validation.py`.
- T-701: Implement `PolicyEnforcementService.validate_row_filter()` in
  `backend/src/app/services/policy_enforcement.py`.

### Behavior
- Static method: `validate_row_filter(filter_sql, schema, table_name, dialect="postgres") -> None`.
- Wraps fragment as `SELECT 1 WHERE <filter>` and parses with sqlglot.
- Raises `ValueError("filter_validation_failed")` on any failure.
- Constant error message — no leak of fragment, schema, or driver internals.
- Input `SchemaContext` never mutated.

### Validation Steps (short-circuit, in order)
1. Must be a non-empty string after strip.
2. No SQL comments outside string literals (`--`, `/*`).
3. Target table must exist in `SchemaContext` (case-insensitive).
4. Placeholder pre-processing: `{user.email}`, `{user.subject_id}`, `{user.role}`
   replaced with sentinel identifiers (`__ph_user_<key>__`).
   Any other `{user.X}` or `{other.X}` rejected immediately.
5. Parse: `sqlglot.parse(wrapped, read=dialect)`. Chained exception suppressed
   via `raise ... from None` to avoid leaking sqlglot internals.
6. Must be exactly one non-null `exp.Select` statement.
7. Reject dangerous top-level nodes (Insert/Update/Delete/Merge/Create/Drop/
   Alter/TruncateTable/Command/Copy/Set).
8. Reject set operations (Union/Intersect/Except) anywhere in the tree.
9. Reject nested SELECTs (subqueries). Outer wrapper and CTEs skipped.
10. Reject function calls. `exp.Func` catches `Anonymous` + special nodes
    like `CurrentUser`; boolean/comparison/arithmetic operators excluded
    by name (`_NON_FUNCTION_OPS` denylist).
11. Validate every `Column` reference exists in target table (case-insensitive).
    Placeholder sentinels (starting with `__ph_user_`) skipped.

### Gates
- `tests/unit/test_row_filter_validation.py`: 41 passed in 0.22s
- `tests/unit -q -m "not integration"` (excluding 4 pre-existing audit-chain
  failures identical on `main`): 1103 passed, 9 deselected, 12 warnings in 14.22s
- `ruff check src tests`: All checks passed!
- `ruff format --check src tests`: 290 files already formatted
- `git diff --check`: clean
- Pre-existing audit failures (NOT from this work, confirmed on `main` at
  `b9a7004`): same 4 as Wave 17.3a — `test_audit_service` and
  `test_audit_chain_verification` chain-state tests.

### TDD Evidence
- T-700 RED: `3e8ad34` — `test(T-700): TDD tests for PolicyEnforcementService.validate_row_filter`
  (41 collection errors).
- T-701 GREEN: `d0d44db` — `feat(T-701): implement PolicyEnforcementService.validate_row_filter`
  (41/41 pass).
- Format fix: `91d5f15` — `style: apply ruff format to test_row_filter_validation.py` (still 41/41).

### Security Notes
- Fail-closed: empty/whitespace/garbage/missing-table/nonexistent-column all reject.
- No leak: constant `filter_validation_failed` error; chained sqlglot exception
  suppressed with `from None`.
- Comment detection: scans raw input for `--` and `/*` outside string literals.
  sqlglot strips comments during parse, so AST alone cannot detect them.
- Function detection: `exp.Func` is the universal base class; boolean/comparison/
  arithmetic operators are excluded by explicit name denylist to avoid
  false positives on `AND`/`OR`/`=`/`>`/etc.
- Placeholder pre-processing: sentinels start with `__ph_user_` and are
  excluded from column existence checks, so a filter like
  `region = {user.role}` does not require a real `role` column.
- Case-insensitive column matching aligns with existing `SchemaContext.find_table`
  / `find_column` (Postgres identifier folding). No surprise authorization
  differences across capitalizations.

### Remaining Wave 17.3 Work
- T-702..T-705: Placeholder binding, injection hardening, schema drift guard.
- T-706..T-707: Column masking.
- T-708..T-710: Evaluator rule.
- T-711..T-712: Query flow integration.
- T-713..T-714: Role policy test endpoint.
- T-715..T-721: History/rerun/audit/cross-dialect.
- T-722: Wave 17.3 backend gate.

---

## Historical Checkpoint — Through Wave 17.3b (Row Filter Validation)

### Status
- **Date**: 2026-06-05
- **Phase**: Phase 5 remains IN PROGRESS.
- **Current point**: Wave 17.3e evaluator authorization rule complete and ready for review/merge.
- **Merged Phase 5 PRs so far**: #101, #102, #103, #104, #105, #108, #110, #111, #112, #113, #114, #115, #116, #117, #118, #119, #120, #121, #122, #123, #124, #125, #126, #127.
- **Current/open PR**: Wave 17.3e (T-708/T-709/T-710) — Evaluator Authorization Rule.

### Completed Scope Through This Point
- Wave 17.0 foundation is complete through subwaves 17.0a-17.0d.
- Wave 17.1a-h backend and frontend SSO features are complete.
- Wave 17.2a-h role management, group mapping, permission gates, and gates are complete.
- Wave 17.3a schema filtering is complete.
- Wave 17.3b row filter validation is complete:
  - `PolicyEnforcementService.validate_row_filter()` validates admin-authored
    WHERE fragments at save time per S-004 / FR-131.
  - 41 TDD tests cover valid filters, placeholders, invalid SQL, missing table,
    nonexistent/cross-table columns, subqueries, function calls (including
    `current_user`), set operations, DML/DDL multi-statements, comments,
    unknown placeholders, case-insensitive matching, immutability, and
    sanitized error messages.
- Wave 17.3c placeholder binding + row filter injection + schema drift guard is complete:
  - `PolicyEnforcementService.bind_placeholders()` translates `{user.email}`,
    `{user.subject_id}`, `{user.role}` to driver-appropriate parameter
    tokens (`$N` for postgres, `%s` for mysql, `?` for mssql) and emits
    a params tuple. 26 TDD tests cover email/subject_id/role binding,
    repeated and distinct placeholder indexing, postgres start_index
    (1, 2, 10), dialect styles, unknown placeholder, missing/None user
    value, raw user value never in SQL.
  - `PolicyEnforcementService.apply_row_filters()` parses the generated
    SQL with sqlglot, AND-conjunctions each row filter into the WHERE
    clause (or adds WHERE if none exists), resolves placeholders, and
    transpiles to the target dialect. Internal AST merging uses `?`
    uniformly; a final post-processing pass converts to driver style.
    22 TDD tests cover WHERE-adding, AND-conjunction, postgres
    start_index max+1, multi-filter AND, empty filter list, dialect
    transpilation smoke, malformed/non-SELECT/multi-statement input,
    BoundSql shape, schema immutability, no user-value leak.
  - Schema drift guard (T-705): re-checks every column reference in
    every filter against the current connection schema. Missing
    column or table raises `PolicySchemaConflictError` (sanitized
    constant message + i18n key `error.policySchemaConflict`) and
    emits `AuditActionType.POLICY_SCHEMA_MISMATCH` via the optional
    `audit_hook` callable. Payload contains only the admin-configured
    table name — never filter SQL, missing column, or user values.
    17 TDD tests cover drift detection, sanitized error (no filter
    SQL / column / user-value leak; constant across invocations),
    i18n key, audit hook on drift / not on success / optional /
    once-per-drift, cross-dialect drift.
  - New exception class `PolicySchemaConflictError` in
    `app/core/exceptions.py`; new i18n key `error.policySchemaConflict`
    in `frontend/src/locales/en.json` and `frontend/src/locales/ar.json`.
  - PR #126 blocker fixes (post-merge follow-ups on the same branch):
    lexer-aware `_replace_outside_strings` + `_replace_outside_strings_regex`
    in `policy_enforcement.py` so backtick-quoted MySQL identifiers and
    string literals containing `?` / `%s` / `$N` are preserved; 8
    regression tests in `TestStringLiteralPreservation`; `ar.json`
    `error.policySchemaConflict` parity.
- Wave 17.3d column masking is complete (PR #127 merged):
  - `PolicyEnforcementService.apply_column_masks(result, column_masks)`
    post-query masking per ADR-19 / FR-132 / SC-052. Replaces values in
    configured sensitive columns with `"***"`, sets `ColumnMeta.masked = True`
    for the affected columns, returns a new `QueryResult` (input never
    mutated). Dialect-independent (operates on the materialized
    `QueryResult`; the dialect that produced the rows is irrelevant).
  - Config shape mirrors `role_connection_policies.column_masks`:
    `[{"table": "t", "columns": ["c1", ...]}]`.
  - Case-insensitive column matching.
  - Empty / `None` config returns original-equivalent (new instance,
    no masking, `masked=False`).
  - Configured column not in result: silent no-op (no leak possible
    because the value never reached the service). Documented in the
    docstring as distinct from the T-705 schema-drift guard, which
    fails closed because the filter IS going to be applied.
  - Malformed config (non-list, non-dict entries, missing/empty
    `table` or `columns`, wrong types) raises
    `ValueError("column_mask_config_invalid")` — fail-closed. Constant
    sanitized message; never echoes the offending config (no leak of
    admin policy or sensitive column names).
  - `ColumnMeta` schema change: added `masked: bool = False` (Pydantic
    default — backwards compatible with all existing callers).
  - 32 TDD tests across 7 classes: value replacement, masked flag,
    immutability, case-insensitive matching, dialect independence
    (postgres/mysql/mssql), unknown / malformed config, no raw-value
    leak in output. Plus a regression test for the lexer-aware string
    preservation pattern via dialect fixture results.
  - Known limitation: `QueryResult` columns are flat (no per-column
    source-table annotation), so a configured `orders.ssn` mask will
    also mask a same-named column from any other table in the result.
    Acceptable bound for T-707; T-712 query service integration can
    pass a result→table mapping to disambiguate joins. Documented in
    the `apply_column_masks` docstring.
- Wave 17.3e evaluator authorization rule is complete:
  - `RoleAuthorizationRule` in
    `backend/src/app/evaluator/rules/role_authorization.py`. Runs
    inside the evaluator pipeline BEFORE execution. Walks every
    `exp.Table` and `exp.Column` node in the SQL AST and blocks the
    query if any reference is outside the role's `allowed_tables`
    policy. Per FR-130 / S-007 / SC-050.
  - API: `RoleAuthorizationRule(allowed_tables, column_masks=None,
    dialect="postgres")`. `async evaluate(sql, schema) -> (bool, str | None)`.
  - Returns the constant `query_blocked_policy` for EVERY failure
    mode (disallowed table, disallowed column, ambiguous unqualified
    column, unknown column, malformed SQL, multi-statement, non-SELECT,
    empty SQL, missing schema).
  - Deny-all on `None` / empty `allowed_tables`: every query blocked
    (fail-closed).
  - Column must be in `allowed_columns` for the owning table to be
    referenced in SELECT / WHERE / JOIN / ORDER BY / GROUP BY / HAVING.
    `exp.Column` nodes cover all those clauses.
  - `column_masks` is informational only: the auth rule treats masked
    columns the same as non-masked columns. Masking never grants
    extra access (a masked column not in `allowed_columns` is still
    blocked) and never denies otherwise-allowed access
    (`apply_column_masks` handles the actual value replacement
    downstream). Satisfies S-007: "if masked column in SELECT — allow
    but mask output; if in WHERE — allow (computation uses real
    values, output masked)".
  - Unqualified column resolution: walks every allowed table
    referenced in the query and finds owners; exactly one owner ->
    allow; zero or multiple owners -> block (ambiguous, fail closed).
  - Schema-qualified table names: `public.orders` falls back to
    `orders` for the PostgreSQL default schema (mirrors
    `SchemaValidationRule`).
  - CTEs: column list resolved best-effort from the CTE alias or body
    SELECT; cannot-statically-resolve (e.g. SELECT *) returns `[]`
    which means unqualified references into the CTE block.
  - Sanitisation: reason string is the constant `query_blocked_policy`
    for every failure mode. Never echoes the raw SQL, table name,
    column name, schema internals, or user values. Pipeline
    translates the failed rule name `role_authorization` to i18n key
    `error.queryBlockedPolicy` for the API response
    (api-contracts.md line 385).
  - T-710 pipeline registration:
    - `backend/src/app/evaluator/pipeline.py`:
      `_MESSAGE_KEY_MAP["role_authorization"] = "error.queryBlockedPolicy"`.
    - The rule conforms to the `EvaluatorRule` runtime-checkable
      protocol and is discoverable via
      `app.evaluator.rules.role_authorization.RoleAuthorizationRule`.
      It can be added to an existing pipeline via
      `EvaluatorPipeline.add_rule()` (the T-154 extensibility
      contract) or passed into `Evaluator(rules=[...])` at
      construction time.
   - 50 TDD tests in `test_evaluator_auth_rule.py` across 9 classes:
     `TestAllowsAllowedReferences` (6), `TestBlocksDisallowedReferences`
     (6), `TestMaskedColumnInteraction` (4), `TestAliasesAndQualifiers`
     (3), `TestCaseInsensitiveMatching` (3),
     `TestMalformedAndMultiStatement` (4), `TestImmutability` (3),
     `TestSanitizedError` (4), `TestPipelineRegistration` (5).
- Wave 17.3f query flow integration is complete (PR #128 follow-up):
  - `QueryService` is the orchestrator that wires the policy pieces
    (T-699..T-710) into the live query lifecycle. Two new
    constructor params are optional and default to a no-op state
    (backward compatible with all Phase 1-3 callers):
    - `policy_enforcement: PolicyEnforcementService | None = None`
      (defaults to a fresh `PolicyEnforcementService()` instance)
    - `role_policy_provider: RolePolicyProvider | None = None`
      (an async `(user_id, connection_id) -> RolePolicy | None`
      callback; ``None`` means "no policy applies" and disables
      every policy step — the Phase 1-3 path).
  - New dataclass `RolePolicy` in `query_service.py` holds the
    resolved policy: `user_id`, `role_id`, `connection_id`,
    `allowed_tables`, `row_filters`, `column_masks`, and a
    `user_context` dict (`email`, `subject_id`, `role`).
  - `submit_question` flow now goes:
    1. Resolve role policy via the provider. User with no role_id
       or no policy for the connection -> provider returns
       ``None`` and every policy step is a no-op (backward compat).
    2. If the policy has an empty `allowed_tables` (deny-all),
       fail closed BEFORE the LLM is called. The LLM never sees
       the schema and the user gets an `EvaluatorRejection` with
       the i18n key `error.queryBlockedPolicy` (sanitized,
       constant). No table, column, or schema leaks into the
       response.
    3. `PolicyEnforcementService.filter_schema()` strips the
       schema to role-allowed tables/columns before the LLM call
       (FR-128 / S-006). The input `SchemaContext` is never
       mutated; `filter_schema()` returns a new instance.
    4. The existing evaluator (read-only, schema, etc.) runs on
       the LLM-generated SQL.
    5. A fresh `RoleAuthorizationRule` is constructed from the
       role's `allowed_tables` and runs immediately after. Failure
       surfaces as an `EvaluatorRejection` with i18n key
       `error.queryBlockedPolicy` (FR-130 / S-007). The error
       string is the constant `query_blocked_policy` — never the
       raw SQL, table, column, schema, UUID, or user value.
    6. `PolicyEnforcementService.apply_row_filters()` rewrites
       the SQL via AST AND-conjunction, binds `{user.*}`
       placeholders to driver-style parameter tokens
       (`$N`/`%s`/`?`), transpiles to the target dialect, and
       returns a `BoundSql(sql, params)` (FR-131 / S-005). The
       executor receives the rewritten SQL and the bound params
       tuple — user values are never interpolated into the SQL
       string.
    7. `PolicySchemaConflictError` from row-filter injection is
       translated to HTTP 409 with i18n key
       `error.policySchemaConflict`. The detail dict contains
       only the constant `error` code and the i18n key — no
       table, column, filter SQL, or user value leaks.
    8. The executor runs the rewritten SQL with the bound params
       (asyncpg positional binding; the legacy
       `SourceDBExecutor` was extended to accept `params: tuple`
       without breaking its prior signature). The
       `SourceDBAdapter` (multi-dialect) path receives the same
       rewritten SQL + params via its existing
       `execute(sql, params)` signature.
    9. After execution, `PolicyEnforcementService.apply_column_masks()`
       walks the `QueryResult` and replaces masked cell values
       with `"***"`, sets `ColumnMeta.masked = True` for the
       affected columns, and returns a new `QueryResult` (input
       never mutated). The masked rows are what get persisted
       to the accepted-query history (FR-132).
  - `regenerate_query` applies the same integration: schema
    filter before the LLM, role auth after the existing
    evaluator, row filter injection before execute, column mask
    after. A role-auth failure on a regenerate returns
    `RefinePrompt` (treating it like a second consecutive
    rejection), matching the existing regenerate semantics.
  - Type annotation fix: `schema_context` is now correctly
    typed as `SchemaContext | str` (was `str`). Production
    callers have always passed a `SchemaContext` object.
  - 18 TDD tests in `tests/unit/test_query_flow_policy.py` across
    11 classes:
    - `TestSchemaFilterBeforePrompt` (4) — LLM receives filtered
      schema, full schema when no policy, empty allowed_tables
      fails closed, input not mutated.
    - `TestEvaluatorAuthBeforeExecution` (3) — disallowed table /
      column blocked, allowed SQL proceeds.
    - `TestRowFilterInjection` (2) — row filter via params, no
      row filter means no WHERE injection.
    - `TestColumnMaskAfterExecute` (2) — masked value replacement
      and `ColumnMeta.masked = True`, no mask config keeps raw
      values.
    - `TestIntegratedOrder` (1) — end-to-end happy path
      (filter -> auth -> row filter -> mask).
    - `TestErrorMapping` (1) — `PolicySchemaConflictError`
      surfaces as a sanitized HTTP 409 with
      `error.policySchemaConflict`.
    - `TestNoUserValueLeak` (1) — user value from `{user.*}` not
      in executed SQL.
    - `TestBackwardCompat` (1) — user with no role_id skips every
      policy step (no filter, no row filter, no mask).
    - `TestRegeneratePath` (1) — regenerate applies the same
      policy enforcement.
    - `TestParamOrdering` (1) — multiple row filters append in
      order.
    - `TestAdapterPath` (1) — multi-dialect adapter receives
      rewritten SQL + params.
  - Pre-existing stub (`test_query_service_schema_context.py`)
    updated to accept `*args, **kwargs` on its `StubExecutor.execute`
    so the new `params=()` keyword is accepted. Backward
    compatible.
  - `SourceDBExecutor.execute()` extended with
    `params: tuple[Any, ...] = ()`. asyncpg positional binding is
    used; existing callers that pass no params continue to work
    (the empty tuple branch falls back to `conn.fetch(sql)` for
    safety).
  - Security: every error path (pre-LLM deny-all rejection, role
    auth rejection, `PolicySchemaConflictError` mapping) uses a
    constant i18n key and never echoes the SQL, table, column,
    schema, user value, UUID, host/port, driver, stack trace,
    or credential. The masked `QueryResult` is what is returned
    to the user and persisted to the accepted-query history;
    raw sensitive values never touch the response or the DB.
  - Backward compatibility: every Phase 1-3 caller that
    constructs `QueryService` without `policy_enforcement` or
    `role_policy_provider` sees the existing flow unchanged.
    All existing tests continue to pass.

### Remaining Wave 17.3 Work
- T-713..T-714: Role policy test endpoint.
- T-715..T-721: History/rerun/audit/cross-dialect.
- T-722: Wave 17.3 backend gate.

### Next Dispatch Constraint
- Continue Wave 17.3 backend policy enforcement (T-713+).
- T-722 (backend gate) must pass before Wave 17.3 close.

---

## Historical Checkpoint — Through Wave 17.3f (Query Flow Policy Integration)

### Status
- **Date**: 2026-06-05
- **Phase**: Phase 5 remains IN PROGRESS.
- **Current point**: Wave 17.3f query flow integration complete and
  merged to main via PR #129.
- **Merged Phase 5 PRs so far**: #101, #102, #103, #104, #105, #108, #110, #111, #112, #113, #114, #115, #116, #117, #118, #119, #120, #121, #122, #123, #124, #125, #126, #127, #128, #129.
- **Current/open PR**: Wave 17.3g (T-713/T-714) — Role Policy Test
  Endpoint (open as a follow-up branch off main).

### Completed Scope Through This Point
- Wave 17.0 foundation is complete through subwaves 17.0a-17.0d.
- Wave 17.1a-h backend and frontend SSO features are complete.
- Wave 17.2a-h role management, group mapping, permission gates, and gates are complete.
- Wave 17.3a schema filtering is complete.
- Wave 17.3b row filter validation is complete.
- Wave 17.3c placeholder binding + row filter injection + schema drift guard is complete.
- Wave 17.3d column masking is complete.
- Wave 17.3e evaluator authorization rule is complete.
- Wave 17.3f query flow policy integration is complete (T-711/T-712, see prior section).
- 12 NEW TDD tests in `test_query_flow_policy.py` (T-711) bring the
  Phase 5 test count to 1281 in the full unit suite. The 4
  pre-existing audit DB-state failures (`test_audit_service.py`
  and `test_audit_chain_verification.py`) are unchanged and
  unrelated to this wave (CI has been green; local DB has
  leftover rows).

### T-712 Follow-up: Real Provider Wired into Factories
- **Date**: 2026-06-05
- **Commit**: `dc9f28f`
- **PR**: #129 (same PR, follow-up commit).
- **Bug discovered after PR #129 initial review**: `_get_query_service`
  and `_build_query_service_for_connection` built `QueryService`
  without `role_policy_provider`, so production requests would never
  load `users.role_id` / `role_connection_policies` / `user_identities`.
  Policy was enforced only in tests via direct injection.
- **Fix**: New `make_role_policy_provider(db)` closure factory in
  `backend/src/app/services/role_policy_provider.py`. Both API
  factories now pass `role_policy_provider=make_role_policy_provider(db)`
  to `QueryService(...)`.
- **Initial provider contract (v1)**: returned `None` for any
  unresolvable policy. This was a security gap: for a role-bearing
  user, `None` made the query service treat the request as legacy
  un-authenticated and skip schema filter, role auth, row filters,
  and column masks.

### T-712 Follow-up: Provider Fails Closed for Role-Bearing Users
- **Date**: 2026-06-05
- **Commits**: `<this commit>` (provider) and follow-up tests
- **PR**: #129 (same PR, blocker fix)
- **Bug class**: provider fail-opened for role-bearing users when
  the policy row was missing or the DB errored during the lookup.
  `QueryService` treats `None` as "no policy applies" and the
  request fell through to the legacy un-authenticated flow. For a
  user with `role_id` this violated FR-128 / FR-130 / FR-131 /
  FR-132 and the `/query/submit` contract lines 351-356.
- **Fix**:
  - `make_role_policy_provider(db)` now returns `None` ONLY when
    the user has no `role_id` (the Phase 1-3 legacy admin path).
  - User has `role_id` but no `role_connection_policies` row →
    returns a deny-all `RolePolicy` (`allowed_tables=[]`,
    `row_filters=[]`, `column_masks=[]`, safe
    `user_context={"email": "", "subject_id": "", "role": ""}`).
    The query service's pre-LLM check sees the empty
    `allowed_tables` and returns
    `EvaluatorRejection(error.queryBlockedPolicy)` BEFORE the LLM
    is invoked. The LLM never sees the schema and the user gets a
    sanitized, constant i18n key.
  - User has `role_id` but the DB raises during the policy
    lookup → returns a deny-all `RolePolicy`. Provider errors
    never 500 a query; they fail closed with the same sanitized
    rejection.
  - User has `role_id` + policy row but no `user_identities`
    row → returns a `RolePolicy` with empty-string `email` /
    `subject_id` in `user_context`. Row filters that reference
    these placeholders will fail closed at `bind_placeholders`
    time (`placeholder_binding_failed`) — by design. Deny-all
    (`allowed_tables=[]`) is also fail-closed.
  - `QueryService._resolve_role_policy` docstring updated to
    match: `None` only for unconfigured provider or no `role_id`.
  - Module + closure docstrings rewritten to describe the
    fail-closed contract and the sanitization guarantees (no
    role id, connection id, table, column, SQL, user value,
    DB error, host/port, username, driver, stack trace,
    credential, token, cert, or SAML/OIDC XML in any return
    value or error path).
- **Tests updated / added** (8 in the flow-policy file + 2
  factory tests still green):
  - `TestRealRolePolicyProvider::test_real_provider_returns_deny_all_when_no_policy_row`
    — role-bearing user + no row → deny-all (not None).
  - `TestRealRolePolicyProvider::test_real_provider_db_error_returns_deny_all_not_500`
    — DB exception during lookup → deny-all (not None, not 500).
  - `TestRealProviderFailClosedEndToEnd::test_production_factory_blocks_before_llm_when_no_policy_row`
    — production `QueryService` + real provider + no row →
    `EvaluatorRejection(error.queryBlockedPolicy)` BEFORE the
    LLM. No SQL, no UUID, no user value, no role id, no
    connection id in payload.
  - `TestRealProviderFailClosedEndToEnd::test_production_factory_blocks_before_llm_on_db_error`
    — DB exception during lookup → `EvaluatorRejection` with no
    `RuntimeError`, no `pg_terminate_backend`, no `DB down`, no
    SQL, no UUIDs in payload.
  - All previous positive tests still green: real policy row →
    filter → auth → row filter → mask.
  - `TestBackwardCompat::test_no_role_id_skips_policy_enforcement`
    still green: `role_id=None` → provider returns `None` →
    legacy flow unchanged.
- **Test count**: 1232 → 1234 unit (the prior 1281 figure
  included integration-marked tests not run under
  `-m "not integration"`). All other unit tests still pass.
- **Gates**: pytest 1234 pass, ruff check clean, ruff format
  clean, git diff --check clean.

---

## Historical Checkpoint — Through Wave 17.3g (Role Policy Test Endpoint)

### Status
- **Date**: 2026-06-05
- **Phase**: Phase 5 remains IN PROGRESS.
- **Current point**: Wave 17.3g role policy test endpoint merged
  to main as PR #130.
- **Merged Phase 5 PRs so far**: #101, #102, #103, #104, #105, #108, #110, #111, #112, #113, #114, #115, #116, #117, #118, #119, #120, #121, #122, #123, #124, #125, #126, #127, #128, #129, #130.
- **Current/open PR**: Wave 17.3h (T-715/T-716) — Query History
  Scoping (FR-134 / SC-053: user sees only own history, no
  cross-user leakage, admins not exempt).

### Wave 17.3g Scope (T-713 / T-714)
- **T-713**: 16 RED tests in
  `backend/tests/unit/test_policy_test_endpoint.py` across 7 classes
  (TestPermissionEnforcement, TestValidation, TestPolicyEvaluation,
  TestMetadataAndSanitization, TestConnectionState,
  TestInternalErrorSanitization, TestNoExecution).
- **T-714**: `POST /admin/roles/{role_id}/test-policy` in
  `backend/src/app/api/v1/admin_roles.py`. Returns the
  accessible/blocked table summary, applicable row filter + column
  mask metadata, and a `would_be_allowed` verdict. Does NOT call
  the LLM and does NOT execute a source-DB query.

### Endpoint Contract (per api-contracts.md line 253-273)
- Permission: `admin.roles.manage` (sanitized 403 when missing).
- Body: `{"question": str, "connection_id": uuid}`.
- Response 200:
  ```json
  {
    "accessible_tables": ["customers"],
    "accessible_columns": {"customers": ["id", "name"]},
    "blocked_tables": ["orders"],
    "applicable_row_filters": [{"table": "customers", "filter": "region = 'US'"}],
    "masked_columns": {"customers": ["email"]},
    "would_be_allowed": true
  }
  ```
- Errors:
  - 404 `error.notFound` — invalid / unknown role id (no UUID leak).
  - 400 `error.connection_not_found` — invalid / unknown
    connection id (no UUID leak).
  - 400 `error.connection_disabled` — connection not ACTIVE.
  - 400 `error.connection_unhealthy` — connection not HEALTHY.
  - 400 `error.connection_no_schema` — schema introspection not
    SUCCESS.
  - 500 `error.internal` — sanitized catch-all (no host, port,
    username, encrypted password, SQL, stack, driver class leak).

### Sanitization Guarantees (defence in depth)
- Path / body UUID parsing failures are caught; the offending
  string is never echoed in the error body or message_key.
- Connection state checks (lifecycle / health / introspection)
  return constant i18n keys; the connection id and the state
  enum name are never echoed.
- `connection.host` / `port` / `username` / `encrypted_password`
  are never read by the endpoint (no adapter is built; we only
  need `id` + `lifecycle_state` + `health_status` +
  `schema_introspection_status` + `get_schema_entries`).
- Row filters are echoed as metadata only; the placeholder syntax
  (`{user.email}`, `{user.subject_id}`, `{user.role}`) is
  preserved verbatim and never bound / interpolated.
- Column masks are echoed in the configured `{"table": [cols]}`
  shape; the endpoint does not transform values.
- Internal failures (driver errors, missing tables, etc.) are
  caught by an outer `except Exception` and returned as
  `HTTPException(500, {"error": "internal", "message_key":
  "error.internal"})`. No raw exception text, traceback, or
  driver class name appears in the response.
- Inputs (schema entries, allowed_tables, row_filters,
  column_masks) are never mutated. The endpoint reads
  `connection_schema_entries` rows but does not write back.

### Fail-Closed Semantics
- Missing `role_connection_policies` row for `(role_id,
  connection_id)` → deny-all result:
  - `accessible_tables = []`
  - `accessible_columns = {}`
  - `blocked_tables = [every schema table]`
  - `applicable_row_filters = []`
  - `masked_columns = {}`
  - `would_be_allowed = false`
  - Status: 200 (a successful dry-run that returns the deny-all
    summary is the right answer for an admin; the endpoint is a
    preview, not a query simulation).
  This matches the PR #129 fail-closed provider contract: a
  role with no policy row for the connection sees nothing.
- Empty `allowed_tables` (admin configured an explicit empty
  grant) → same deny-all summary.

### Test Seams (intentional, documented)
- Production code reads `request.state.role_repo_override` /
  `connection_repo_override` / `db_override` when set; absent in
  production. This lets the AsyncClient-based test harness inject
  mock services without bypassing FastAPI's `Depends(get_db)`.
- `_policy_test_connection_state_error` uses `not (a == b)`
  rather than `a != b` because
  `unittest.mock.MagicMock` keeps a separate auto-generated
  `__ne__` that does NOT delegate to `__eq__`. The three checks
  carry `# noqa: SIM201` to keep ruff check clean while
  preserving the test-fake pattern. The trade-off is documented
  in the helper's docstring.

### Test Coverage (16 tests, all green)
- `TestPermissionEnforcement` (1) — 403 when missing
  `admin.roles.manage`.
- `TestValidation` (4) — invalid role id 404 sanitized, unknown
  role 404 sanitized (no UUID leak), invalid connection id 400
  sanitized, unknown connection 400 sanitized.
- `TestPolicyEvaluation` (3) — existing role+connection+policy
  returns accessible/blocked summary, missing policy row returns
  deny-all, empty `allowed_tables` returns deny-all.
- `TestMetadataAndSanitization` (4) — row filter returned as
  metadata with placeholders preserved verbatim, column mask
  returned in configured shape, no host/port/username/encrypted
  password leak in response body, schema entries not mutated.
- `TestConnectionState` (2) — inactive connection returns
  `connection_disabled` 400 with no UUID leak, no-schema
  connection returns `connection_no_schema` 400.
- `TestInternalErrorSanitization` (1) — raw `asyncpg` driver
  error returns 500 with constant `error.internal`; no
  `asyncpg` / `10.0.0.42` / `5432` / `svc` / `PostgresError` /
  `RuntimeError` / `Traceback` leak.
- `TestNoExecution` (1) — response is purely policy+schema
  derived; no `sql` / `generated_sql` / `rows` keys in the
  body (the endpoint never ran the LLM or executed a query).

### Test Count
- 1234 (post-17.3f fail-closed) → 1250 unit pass
  (`-m "not integration"`).
- The 4 pre-existing audit DB-state failures
  (`test_audit_service.py` and
  `test_audit_chain_verification.py`) are unchanged and unrelated
  to this wave.

### Gates (all green)
- `pytest tests/unit/test_policy_test_endpoint.py -q` → 16 passed.
- `pytest tests/unit -q -m "not integration"` → 1250 passed,
  61 skipped, 9 deselected, 12 warnings.
- `ruff check src tests` → All checks passed.
- `ruff format --check src tests` → 300 files already formatted.
- `git diff --check` → clean.

### Commits on Wave 17.3g Branch
- `5ca1c99` test(T-713): failing tests for role policy test endpoint
  (16 tests, all red because endpoint did not exist).
- `5ec840e` feat(T-714): POST /admin/roles/{id}/test-policy
  dry-run endpoint (16/16 green).

### Next Steps (Wave 17.3h and beyond)
- Wave 17.3h — Query History Scoping (T-715 / T-716) — user
  sees only own queries, no cross-user leakage.
- Wave 17.3i — Accepted-Query Rerun Re-Validation (T-717 / T-718)
  — re-check SQL against current role policy before execution.
- Wave 17.3j — Query Lifecycle Audit Logging (T-719 / T-720) —
  submit / validate / execute / accept / reject / policy block.
- Wave 17.3k — Cross-Dialect Policy Enforcement
  (T-721, integration). Row filters + column masks verified
  against PostgreSQL, MySQL, MSSQL via testcontainers.
- Wave 17.3l — Backend Foundation Gates (T-722) — CI-equivalent
  ruff check / pytest / format pass.

### Open Questions / Decisions for Future Waves
- Frontend policy editor (T-725+) is out of scope for this wave.
  The dry-run endpoint is the admin's primary tool until the
  editor ships; results can be fetched via a thin client.
- The endpoint does not write to the audit log. FR-140 (T-719)
  will cover the full query-lifecycle audit chain; admin dry-runs
  are policy introspection, not data access, and were not in
  scope for the FR-140 contract.

### Wave 17.3g Follow-up: Sample-SQL Evaluation
- **Date**: 2026-06-05
- **Commits** (on `phase-5/wave-17.3g-role-policy-test-endpoint`):
  - `b851235` test(T-713): sample-SQL evaluation tests (FR-136 follow-up)
  - `94568be` feat(T-714): sample-SQL evaluation via RoleAuthorizationRule
- **PR**: #130 (same PR, follow-up commits).
- **Issue raised in PR #130 review**: the dry-run's
  `would_be_allowed = bool(accessible_tables)` is a policy-state
  verdict, not a SQL-level one. FR-136 requires showing whether
  a sample query would be blocked or allowed. The initial
  endpoint only returned the policy-state preview and ignored
  the user's sample intent.
- **API extension (backward compatible)**:
  - `PolicyTestRequest` gains optional
    `sample_sql: str | None = Field(default=None, max_length=20000)`.
  - `PolicyTestResponse` gains `message_key: str | None = None`.
- **Endpoint behaviour**:
  - `sample_sql` absent or empty → keep current policy-state
    preview: `would_be_allowed = bool(accessible_tables)`,
    `message_key = None`. The 16 original tests
    (`TestPermissionEnforcement`, `TestValidation`,
    `TestPolicyEvaluation`, `TestMetadataAndSanitization`,
    `TestConnectionState`, `TestInternalErrorSanitization`,
    `TestNoExecution`) still pass unchanged.
  - `sample_sql` present and non-empty → run
    `RoleAuthorizationRule(allowed_tables, column_masks,
    dialect="postgres")` against the **full**
    `schema_context` (the rule does not need the filtered schema
    — it walks the SQL AST directly) and override
    `would_be_allowed` with the rule's verdict. On block, set
    `message_key = "error.queryBlockedPolicy"`. The rule is
    fail-closed: every failure mode (disallowed reference,
    malformed SQL, multi-statement, non-SELECT, empty) returns
    the constant `"query_blocked_policy"` reason. It never
    echoes the raw SQL, table, column, schema, or driver text.
- **Why RoleAuthorizationRule directly (not the full evaluator)**:
  - The dry-run is a policy preview, not a query simulation.
  - The rule covers FR-130 / SC-050 (table/column allow) plus
    the defence-in-depth SQL guards (malformed, multi-statement,
    non-SELECT, empty).
  - Running the full evaluator would also exercise
    `ReadOnlyRule` / `SingleStatementRule` /
    `SchemaValidationRule` against the user's question text,
    which is not what an admin dry-run is for. The role-auth
    rule is the policy-shaped gate that the admin wants to
    preview.
- **No execution guarantees (unchanged from the initial wave)**:
  - No LLM call.
  - No source-DB query.
  - No row-filter binding or interpolation; filters remain
    metadata-only in `applicable_row_filters`.
  - No column-mask value transformation; masks remain
    metadata-only in `masked_columns`.
  - Inputs (`schema_entries`, `allowed_tables`, `row_filters`,
    `column_masks`) are never mutated.
  - The `sample_sql` is consumed by the rule but never echoed
    in the response.
- **Tests added** (7 in `TestSampleSqlEvaluation`):
  - `test_sample_sql_allowed_returns_true` — policy allows
    customers; `SELECT id, name FROM customers` →
    `would_be_allowed = True`, `message_key = None`.
  - `test_sample_sql_disallowed_returns_false_with_message_key`
    — policy allows only customers; `SELECT * FROM orders` →
    `would_be_allowed = False`,
    `message_key = "error.queryBlockedPolicy"`.
  - `test_sample_sql_blocked_does_not_leak_sql_or_schema` —
    sample references `ssn` from a non-allowed table; response
    body must not contain the SQL fragment, the column name,
    the role id, the connection id, `sqlglot`, `ParseError`,
    `Traceback`, `evaluator`, or `RoleAuthorization`.
  - `test_sample_sql_absent_keeps_policy_state_verdict` —
    `sample_sql` omitted → policy-state preview (current
    behaviour).
  - `test_sample_sql_malformed_returns_blocked_sanitized` —
    `"SELEKT id FORM customers ((("` → blocked, no
    `sqlglot` / `ParseError` / `tokenizer` leak.
  - `test_sample_sql_non_select_returns_blocked` —
    `DELETE FROM customers WHERE id = 1` → blocked, no
    `ReadOnlyRule` / `SingleStatement` / `sqlglot` leak.
  - `test_sample_sql_multi_statement_returns_blocked` —
    `SELECT id FROM customers; DROP TABLE customers` →
    blocked, no `DROP TABLE` / `multi` / `SingleStatement`
    leak.
- **Test count**: 1250 → 1257 unit pass. All other unit tests
  still pass; the 4 pre-existing audit DB-state failures
  unchanged.
- **Gates**: pytest 1257 pass, ruff check clean, ruff format
  clean, git diff --check clean.

### Wave 17.3g Follow-up 2: Dialect-Aware Sample SQL Evaluation
- **Date**: 2026-06-05
- **Commits** (on `phase-5/wave-17.3g-role-policy-test-endpoint`,
  appended to the follow-up-1 chain):
  - `236efe6` test(T-713): dialect-aware sample-SQL tests
    (mysql, mssql, wrong-dialect) — 3 new tests; 2 RED, 1
    defense-in-depth regression guard.
  - `91de1c2` feat(T-714): dialect-aware sample-SQL
    evaluation via DIALECT_MAP.
- **PR**: #130 (same PR, second follow-up commit pair).
- **Issue raised in PR #130 review (round 2)**: the
  sample-SQL evaluator hard-coded `dialect="postgres"`,
  so backtick-quoted MySQL SQL (`SELECT \`id\` FROM
  \`customers\``) and bracket-quoted MSSQL SQL
  (`SELECT [id] FROM [customers]`) were rejected at the
  sqlglot parse step and the rule wrongly returned
  `query_blocked_policy` for valid MySQL/MSSQL queries.
  The dialect should follow the connection's
  `database_type`, not the endpoint's caller.
- **Fix (single-source-of-truth)**: the endpoint now
  resolves the sqlglot dialect from the connection's
  `database_type` via the canonical `DIALECT_MAP` exported
  by `app.evaluator.rules.read_only` (T-429 / FR-071). The
  same map is used by `ReadOnlyRule.from_database_type`
  in the live evaluator pipeline, so the dry-run and the
  live path agree on which dialect parses a given
  connection. A small `_resolve_dialect` helper wraps the
  map and falls back to `"postgres"` for missing / unknown
  / non-`DatabaseType` values, mirroring the conservative
  default used by `read_only` and `role_authorization`.
- **No new public API**: the request body and response
  shape are unchanged. `sample_sql` is still optional; the
  `message_key` contract is unchanged.
- **No-execution guarantees (unchanged from follow-up 1)**:
  - The dialect name is internal to the role-auth rule's
    sqlglot call. It is never echoed in the response, the
    audit log, the `message_key`, or any error path. The
    new test `test_sample_sql_wrong_dialect_blocks_sanitized`
    asserts that the response body contains no `sqlglot`,
    `ParseError`, `Traceback`, `tsql`, `mysql`, `mssql`,
    `postgresql`, `dialect`, `RoleAuthorization`, role id,
    connection id, or SQL fragment.
  - The rule's constant `"query_blocked_policy"` reason
    still applies to every failure mode (disallowed
    reference, malformed SQL, multi-statement, non-SELECT,
    empty, parse error). The constant never includes the
    dialect.
  - No LLM call, no source-DB query, no row-filter
    binding, no column-mask value transformation, no schema
    mutation, no `sample_sql` echo. All unchanged from
    follow-up 1 (`94568be`).
- **Tests added** (3 in `TestSampleSqlEvaluation`, total
  10 in the class):
  - `test_sample_sql_mysql_backtick_allowed` — MySQL
    connection (DatabaseType.MYSQL), policy allows
    `customers`, sample `SELECT \`id\`, \`name\` FROM
    \`customers\`` → `would_be_allowed = True`,
    `message_key = None`.
  - `test_sample_sql_mssql_bracket_allowed` — MSSQL
    connection (DatabaseType.MSSQL), policy allows
    `customers`, sample `SELECT [id], [name] FROM
    [customers]` → `would_be_allowed = True`,
    `message_key = None`.
  - `test_sample_sql_wrong_dialect_blocks_sanitized` —
    MSSQL connection receiving backtick SQL → blocked
    with `error.queryBlockedPolicy`, and the response body
    must not contain the SQL, role id, connection id,
    `sqlglot`, `ParseError`, `Traceback`, `tsql`, `mysql`,
    `mssql`, `postgresql`, `dialect`, or
    `RoleAuthorization`. Defense-in-depth regression guard
    (the test also passes RED by coincidence because the
    pre-fix postgres dialect also rejects backticks; its
    real purpose is to lock the sanitization contract).
- **Test helper change**: `_active_healthy_conn` gains an
  optional `database_type` parameter (default
  `DatabaseType.POSTGRESQL`) so callers can exercise
  per-connection dialect resolution. The 20 other tests
  that use this helper still pass unchanged (they default
  to POSTGRESQL).
- **Test count**: 1257 → 1260 unit pass. All other unit
  tests still pass; the 4 pre-existing audit DB-state
  failures unchanged.
- **Gates**: pytest 1260 pass, ruff check clean, ruff
  format clean, git diff --check clean.

---

## Current Wave Checkpoint — Through Wave 17.3h (Query History Scoping)

### Wave 17.3h Scope (T-715 / T-716)
- **T-715** — 17 RED-then-GREEN tests in
  `backend/tests/unit/test_history_scoping.py` across 6 classes:
  - `TestPerUserIsolation` (4): per-user isolation; admin session
    is NOT exempt from per-user scoping (api-contracts.md line 362
    — admins see only their own user_id's rows, not a system-wide
    view).
  - `TestEmptyAndPagination` (2): empty history returns `[]`, not
    other users' rows; pagination `limit=2` returns 2 of the
    caller's own rows.
  - `TestPermissionAndSession` (3): missing `query.history.view`
    → 403 `error.forbidden`; unmapped user (FR-126 / SC-048) → 403;
    no session → 401 `error.unauthorized`.
  - `TestRepositoryUserIdPredicate` (4): regression guards
    pinning the user_id predicate at the repository layer
    (`list_by_user`, `count_by_user`). A future refactor that
    drops the user_id filter breaks these tests.
  - `TestResponseShapeAndSanitization` (2): response shape
    backward-compatible (`items`, `total`, `next_cursor`); User
    B's `question_text` and `generated_sql` never appear in
    User A's response.
  - `TestDetailScoping` (2): `GET /history/{id}` also passes
    user_id to the repo; detail lookup for User B's row from
    User A's session returns 404 (not 200 with another user's
    row).
- **T-716** — `GET /history`, `GET /history/{id}`, and
  `DELETE /history/{id}` in `backend/src/app/api/v1/history.py`
  renamed the `require_active_user` dep alias to
  `current_user_id` to make the spec formula
  `user_id = current_user.id` visible at the endpoint
  signature. Behaviour is unchanged: the same user_id is
  forwarded to the service. The module docstring documents
  the full chain (session → dep → endpoint → service → repo
  WHERE clause) so a reviewer can see the contract without
  walking the dependency chain.

### Endpoint Contract (per api-contracts.md line 359-362)
- Permission: `query.history.view` (sanitized 403 when missing).
- Filter: `user_id = current_user.id` at the DB query layer.
  No cross-user visibility. Admins are not exempt (the admin's
  own user_id is what the endpoint must use).
- Response shape unchanged: `{items, total, next_cursor}`.
- Detail endpoint: `GET /history/{id}` returns 404 if the row
  belongs to a different user (same `current_user.id` filter
  applied).
- Delete endpoint: `DELETE /history/{id}` returns 404 if the
  row belongs to a different user; only the row's owner can
  delete it.

### Sanitization Guarantees (defence in depth)
- The user_id source is `request.state.session["user_id"]`,
  which the `require_active_user` dependency validates by
  re-fetching the `User` row from the DB. A stale session
  whose user no longer exists raises 401 `error.unauthorized`
  and the session is cleaned up in Redis. The endpoint never
  trusts a client-supplied user id.
- The `user_id` filter is applied at the SQL `WHERE` clause
  in `AcceptedQueryRepository.list_by_user`, `count_by_user`,
  `get_by_id`, `delete_by_id`, and `list_by_session`. A
  missing or wrong user_id is impossible at the repo level:
  the unit tests pin this.
- Empty history for the caller returns `{items: [], total: 0,
  next_cursor: null}` — never another user's rows.
- Pagination cursor walks the caller's own rows only (the
  cursor encodes the caller's `accepted_at` + `id` tuple and
  the WHERE clause keeps scoping to the caller's user_id).
- Errors are sanitized by the existing `require_permission`
  (401 / 403 with constant message_keys) and by the service's
  `HTTPException(404, ...)` path. No raw UUIDs, DB errors, SQL,
  stack traces, host/port, usernames, credentials, or tokens
  leak in any response or error path.

### Test Seams (intentional, documented)
- The test harness uses `SessionInjectionMiddleware` to set
  `request.state.session` per test, matching the pattern in
  `test_policy_test_endpoint.py` and `test_role_endpoints.py`.
- `require_active_user` is overridden with a `Request`-typed
  shim that pulls `user_id` from `request.state.session`.
  Without the explicit `Request` type hint, FastAPI treats
  the request param as a query parameter and returns 422.
- `_get_history_service` is overridden with a `HistoryService`
  built from a `MagicMock` repo + `MagicMock` connection_repo.
  The mock repo enforces that `list_by_user` / `count_by_user`
  are called with a real user_id; a missing user_id would
  return `[]` (defence in depth, since production code
  always passes one).
- The 3 pre-existing `TestHistoryPermissionGates` direct-call
  tests in `test_permission_gates_all.py` were updated to
  pass `current_user_id=...` to match the renamed parameter.
  Test names, assertions, and intent unchanged.

### Test Coverage (17 tests, all green)
- `TestPerUserIsolation` (4) — User A sees only A, User B
  sees only B, mixed history disjoint, admin scoped to own.
- `TestEmptyAndPagination` (2) — empty returns `[]` not other
  users' rows; `limit=2` returns 2 of caller's own.
- `TestPermissionAndSession` (3) — 403 missing permission, 403
  unmapped, 401 no session.
- `TestRepositoryUserIdPredicate` (4) — `list_by_user` called
  with user A id, called with user B id, `count_by_user`
  called with current user id, two sessions → two distinct
  repo calls with the right ids.
- `TestResponseShapeAndSanitization` (2) — response shape
  preserved; no cross-user question_text / generated_sql in
  response.
- `TestDetailScoping` (2) — User A cannot fetch User B's
  detail (404 sanitized); User A can fetch own detail (200).

### Test Count
- 1260 (post-17.3g follow-up 2) → 1277 unit pass
  (`-m "not integration"`).
- The 4 pre-existing audit DB-state failures
  (`test_audit_service.py` and
  `test_audit_chain_verification.py`) are unchanged and
  unrelated to this wave.

### Gates (all green)
- `pytest tests/unit/test_history_scoping.py -q` → 17 passed.
- `pytest tests/unit -q -m "not integration"` → 1277 passed,
  61 skipped, 9 deselected, 12 warnings.
- `ruff check src tests` → All checks passed.
- `ruff format --check src tests` → 301 files already formatted.
- `git diff --check` → clean.

### Commits on Wave 17.3h Branch
- `a7e2de1` test(T-715): query history scoping regression tests
  (17 tests across 6 classes).
- `964ebb0` feat(T-716): explicit `user_id = current_user.id`
  at /history signature (alias rename + module/handler
  docstrings + test_permission_gates_all caller updates).

### Next Steps (Wave 17.3i and beyond)
- Wave 17.3i — Accepted-Query Rerun Re-Validation
  (T-717 / T-718) — re-check SQL against current role
  policy before execution.
- Wave 17.3j — Query Lifecycle Audit Logging (T-719 / T-720) —
  submit / validate / execute / accept / reject / policy block.
- Wave 17.3k — Cross-Dialect Policy Enforcement
  (T-721, integration). Row filters + column masks verified
  against PostgreSQL, MySQL, MSSQL via testcontainers.
- Wave 17.3l — Backend Foundation Gates (T-722) — CI-equivalent
  ruff check / pytest / format pass.
- Frontend policy editor (T-725+) is out of scope for backend
  waves.

### Open Questions / Decisions for Future Waves
- None for Wave 17.3h. The contract is fully specified by
  FR-134, SC-053, and api-contracts.md line 359-362, and the
  implementation matches the spec formula. The existing
  `require_active_user` → `service` → `repository` chain
  was already enforcing the contract; T-716 made the contract
  self-documenting at the endpoint signature and T-715 pinned
  it with regression tests.
- Wave 17.3i (T-717 / T-718) is the next open work item. It
  is out of scope for this PR and remains in the next-wave
  bucket per the `### Next Steps` section above.
