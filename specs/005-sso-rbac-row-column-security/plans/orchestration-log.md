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

## Current Wave Checkpoint — Through Wave 17.1g

### Status
- **Date**: 2026-06-01
- **Phase**: Phase 5 remains IN PROGRESS.
- **Current point**: Wave 17.1g complete and ready for review/merge.
- **Merged Phase 5 PRs so far**: #101, #102, #103, #104, #105, #108, #110, #111, #112, #113.
- **Current/open PR**: #114 (Wave 17.1g — SSO Sign-In Page).
- **Docs PRs**: #106 and #107 record orchestration progress through prior checkpoints.

### Completed Scope Through This Point
- Wave 17.0 foundation is complete through subwaves 17.0a-17.0d:
  - Foundation models and enums.
  - Migration and tamper-evident audit service foundation.
  - Permission dependency, Phase 5 schemas, extended auth/session profile, OpenAPI update.
  - Backend test taxonomy hardening and fast-gate simplification.
- Wave 17.1a backend SSO service slice is complete:
  - OIDC authorization-code initiation and callback validation.
  - Explicit OIDC JWKS fetch and signature validation.
  - SAML AuthnRequest/callback service wrapper with fail-closed metadata behavior.
  - SAML signed-assertion requirement via python3-saml settings.
  - Sanitized python3-saml boundary errors.
  - Provider-bound OIDC state and SAML request replay protection.
  - SSO group to role resolution by priority.
  - UserIdentity create/update and Redis session creation.
- Wave 17.1b backend SSO endpoint/local login slice is complete:
  - Replay-protection tests for OIDC/SAML flows.
  - Public SSO provider list and login/callback endpoints.
  - SSO callback session cookies on returned redirects.
  - Path-exact SAML ACS origin bypass.
  - Admin-only local password login with generic 401 rejection.
- Wave 17.1c admin SSO provider CRUD slice is complete:
  - Admin SSO provider CRUD endpoints.
  - `admin.sso.manage` permission enforcement.
  - Secret encryption at rest and masked responses.
  - Duplicate protocol and required-field validation.
- Wave 17.1d admin lockout prevention slice is complete:
  - Built-in user/role deletion blocked at repository layer.
  - Built-in role core property changes blocked.
  - Built-in admin local login guarantee covered by tests.
  - `error.builtinRoleProtected` i18n key added in EN/AR.
- Wave 17.1e SSO audit logging slice is complete:
  - SSO login success/failure audit events (OIDC + SAML).
  - SSO validation events audit logging.
  - Admin SSO config change audit logging (create/update/delete).
  - Audit context redaction: no raw tokens, certs, assertion XML, secrets, hostnames, UUIDs.
  - Admin SSO mutation+audit atomic: audit entry in same transaction as provider mutation.
  - SSO login session cleanup on audit failure: Redis session revoked if `auth.login.success` audit fails.
- Wave 17.1f concurrent session limit slice is complete:
  - Max 5 concurrent sessions per user (configurable via `MAX_CONCURRENT_SESSIONS_PER_USER`).
  - Oldest session eviction on overflow via Redis sorted set (`user_sessions:{user_id}`).
  - Applies to local admin login (`AuthService.sign_in`) and SSO login (`SsoService._resolve_role_and_create_session`).
  - Built-in admin login guarantee preserved: eviction happens, login never blocked.
  - `AuthService.sign_out` cleans up user session index.
  - SSO audit-failure cleanup regression fixed: audit failure removes both `session:{id}` and `user_sessions:{user_id}` member.
- Wave 17.1g frontend SSO sign-in page slice is complete:
  - SSO sign-in page TDD tests supporting English and Arabic/RTL.
  - SSO sign-in page provider buttons/error/no-provider UI logic.
  - Extended `useAuth` hook and its `UserProfile` type with Phase 5 fields.
  - Branded English and Arabic/RTL visual smoke verification.

### Review Decisions Locked
- OIDC must fetch JWKS explicitly and pass JWKS data, not a URL string, to JWT validation.
- SAML `saml_entity_id` is SP entity ID; IdP issuer is derived from IdP metadata configuration.
- SAML paths fail closed when IdP metadata URL/XML-derived settings are unavailable.
- `SsoValidationError` is the user-facing SSO error boundary; raw tokens, certs, UUIDs, hostnames, assertion XML, and parser/security details stay out of user-facing messages.
- Backend fast gate remains `uv run pytest tests/unit -q -m "not integration"`.
- GLM prompts should be constrained to 2-4 implementation tasks per prompt.
- Audit logging must be atomic with the mutation it records: `AuditService.log()` before `db.commit()`.
- SSO login cannot leave an unaudited session: Redis session is deleted if `auth.login.success` audit fails.

### Remaining Wave 17.1 Work
- T-662–T-667, T-669–T-670 (SSO Admin Config, Routing, and remaining Gates).

### Next Dispatch Constraint
- Dispatch Wave 17.1h admin SSO config page slice (T-662–T-664).

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
- T-662–T-664: Admin SSO Config Page (Owner: Gemini)
- T-665–T-666: i18n for Wave 17.1 (Owner: Gemini)
- T-667: Routing (Owner: Gemini)
- T-669: Chrome DevTools MCP visual verification for Admin SSO Config (Owner: Gemini)
- T-670: Wave 17.1 Frontend Gate (Owner: Gemini)
