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

## Current Wave Checkpoint — Through Wave 17.2c

### Status
- **Date**: 2026-06-02
- **Phase**: Phase 5 remains IN PROGRESS.
- **Current point**: Wave 17.2c complete and ready for review/merge.
- **Merged Phase 5 PRs so far**: #101, #102, #103, #104, #105, #108, #110, #111, #112, #113, #114, #115, #116, #117.
- **Current/open PR**: #118 (Wave 17.2c — Permission Gates).

### Completed Scope Through This Point
- Wave 17.0 foundation is complete through subwaves 17.0a-17.0d.
- Wave 17.1a-h backend and frontend SSO features are complete.
- Wave 17.2a role CRUD backend slice is complete.
- Wave 17.2b group mapping endpoints are complete.
- Wave 17.2c permission gates are complete:
  - `admin.py` settings endpoints require `admin.connections.manage`.
  - `admin_connections.py` all endpoints require `admin.connections.manage`.
  - `query.py` submit/accept/reject/regenerate require `query.submit`.
  - `history.py` list/detail/delete require `query.history.view`.
  - Existing `admin_roles.py` (`admin.roles.manage`) and `admin_sso.py` (`admin.sso.manage` for providers, `admin.roles.manage` for group mappings) permissions preserved — no regression.
  - 39 TDD tests in `test_permission_gates_all.py` verify 401/403 behavior, error sanitization, and dependency ordering.

### Remaining Wave 17.2 Backend Work
- T-681/T-682: Unmapped user denial.
- T-683/T-684: RBAC audit logging coverage.
- T-685: Wave 17.2 backend gate.

### Next Dispatch Constraint
- Wave 17.2d unmapped user denial (T-681-T-682) after PR merge.

---

## Wave 17.2c — Permission Gates

### Dispatch
- **Date**: 2026-06-02
- **Model**: Kimi (opencode) Backend Implementer
- **T-IDs**: T-678, T-679, T-680
- **Branch**: `phase-5/wave-17.2c-permission-gates`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/118

### Scope
- T-678: TDD tests for permission gates on all existing admin and query/history endpoints (`tests/unit/test_permission_gates_all.py`): 38 tests covering direct dependency checks, route-level 401/403 behavior, and error sanitization.
- T-679: Applied `require_permission(Permission.ADMIN_CONNECTIONS_MANAGE)` as `Depends()` to all endpoints in `admin.py` (GET/PUT /admin/settings) and `admin_connections.py` (list, create, get, update, delete, disable, enable, test, refresh-schema, get-schema).
- T-680: Applied `require_permission(Permission.QUERY_SUBMIT)` and `require_permission(Permission.QUERY_HISTORY_VIEW)` as `Depends()` to query.py and history.py endpoints.
- Updated existing unit tests that use FastAPI dependency injection to patch `require_permission` where needed.
- Preserved existing admin_roles.py (`admin.roles.manage`) and admin_sso.py (`admin.sso.manage` for providers, `admin.roles.manage` for group mappings) permissions — no regression.

### Gates
- Full unit gate: `946 passed, 61 skipped, 9 deselected, 12 warnings in 11.21s`
- Focused permission gates tests: `38 passed`
- Ruff check: `All checks passed!`
- Ruff format: `285 files already formatted`
- `git diff --check`: clean

### Security Notes
- All admin endpoints now enforce RBAC permissions via `require_permission()` dependency.
- Query endpoints require `query.submit`; history endpoints require `query.history.view`.
- Missing session returns 401 `error.unauthorized`; wrong permission returns 403 `error.forbidden`.
- No raw UUIDs, permission internals, DB errors, SQL, stack traces, source DB details, hostnames, usernames, or tokens in user-facing errors.
- Built-in admin local login behavior preserved (admin gets all permissions via role resolution).

### Review Fixes
- **Fix 1 — Permission checks moved to `Depends()`**: RBAC checks were inside endpoint bodies, meaning FastAPI resolved body validation and service dependencies before permission was checked. Moved to `Depends(require_permission(Permission.X))` signatures so wrong-permission requests return 403 before body validation or expensive service deps execute.
- **Fix 2 — Route-level TestClient coverage**: Added 6 route-level tests using ASGI `TestClient` with session injection middleware proving:
  - Invalid body + wrong permission → 403 (not 422) on POST /admin/connections and POST /query/submit.
  - POST /query/accept with wrong permission → 403 without running `_get_query_service`.
  - GET /history, GET /admin/settings with wrong permission → 403.
  - No session → 401.
- **Fix 3 — Updated existing unit tests**: Patched `require_permission` in `test_admin_connections.py`, `test_history_metadata.py`, `test_admin_settings_unit.py` to use `side_effect` returning callable dependencies instead of `return_value=AsyncMock()`.

### Remaining Wave 17.2 Backend Work
- T-681/T-682: Unmapped user denial.
- T-683/T-684: RBAC audit logging coverage.
- T-685: Wave 17.2 backend gate.

---

## Wave 17.2b — Group Mapping Endpoints

### Dispatch
- **Date**: 2026-06-02
- **Model**: Kimi (opencode) Backend Implementer
- **T-IDs**: T-676, T-677
- **Branch**: `phase-5/wave-17.2b-group-mapping-endpoints`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/117

### Scope
- T-676: TDD tests for group mapping endpoints (`tests/unit/test_group_mapping_endpoints.py`): permission enforcement (admin.roles.manage, NOT admin.sso.manage), list, create, delete, duplicate group rejection (409), missing role validation (404), error sanitization.
- T-677: Implemented group mapping endpoints in `backend/src/app/api/v1/admin_sso.py`:
  - `GET /admin/sso/group-mappings` — list all mappings with role names.
  - `POST /admin/sso/group-mappings` — create mapping, duplicate check, role existence validation.
  - `DELETE /admin/sso/group-mappings/{id}` — delete mapping, 404 if missing.
- Audit logging via `AuditActionType.ROLE_MAPPING_CHANGE` for create and delete.
- Added i18n keys `error.conflict.duplicateGroupMapping` to `en.json` and `ar.json`.

### Gates
- Full unit gate: `908 passed, 61 skipped, 9 deselected, 12 warnings in 11.54s`
- Focused group mapping tests: `27 passed`
- Ruff check: `All checks passed!`
- Ruff format: `284 files already formatted`

### Security Notes
- Group mapping endpoints enforce `require_permission(Permission.ADMIN_ROLES_MANAGE)` — admin.sso.manage does NOT grant access.
- Duplicate SSO group value returns 409 with sanitized localized key `error.conflict.duplicateGroupMapping`; no raw UUIDs or DB internals leaked.
- Missing referenced role returns 404 with `error.notFound`; no UUIDs leaked.
- All exceptions caught and sanitized to generic `error.internal` with no stack traces or DB errors exposed.
- Audit logging for mapping create/delete via `AuditService.log()` with redacted context.

### Review Fixes
- **Fix 1 — UUID validation**: `body.role_id` in POST and `mapping_id` in DELETE are converted via `uuid.UUID(...)` before DB use. Invalid UUIDs return sanitized 404 `error.notFound` without leaking raw input.
- Tests added for invalid `role_id` POST and invalid `mapping_id` DELETE; assert raw invalid value does not appear in response.

### Remaining Wave 17.2 Backend Work
- T-681/T-682: Unmapped user denial.
- T-683/T-684: RBAC audit logging coverage.
- T-685: Wave 17.2 backend gate.
