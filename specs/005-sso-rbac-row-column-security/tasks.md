# Tasks — Phase 5: SSO, RBAC, Row/Column Security

**Phase**: 5
**Task ID Range**: T-600 – T-778
**Spec**: [spec.md](file:///home/avril/QueryCraft/specs/005-sso-rbac-row-column-security/spec.md)
**Plan**: [plan.md](file:///home/avril/QueryCraft/specs/005-sso-rbac-row-column-security/plan.md)
**Data Model**: [data-model.md](file:///home/avril/QueryCraft/specs/005-sso-rbac-row-column-security/data-model.md)
**API Contracts**: [api-contracts.md](file:///home/avril/QueryCraft/specs/005-sso-rbac-row-column-security/contracts/api-contracts.md)

---

## Phase Governance — Orchestration Log Initialization

### Orchestration Log (Owner: Opus Orchestrator)

- [x] T-600 Create and initialize `specs/005-sso-rbac-row-column-security/plans/orchestration-log.md` with Phase 5 metadata: link to spec.md, plan.md, research.md, data-model.md, contracts/api-contracts.md, tasks.md; prior phase status (Phases 1–4 FROZEN); wave structure (17.0–17.5); dispatch order; date initialized — SC-058

---

## Wave 17.0 — Foundation: Contracts, Data Model, Auth Architecture

**Branch**: `phase-5/wave-17.0-foundation-contracts`
**Owner**: Backend Implementer (Kimi ( opencode ))
**Depends on**: Phase 4 FROZEN on `main`, T-600 complete
**FRs**: FR-140, FR-141, FR-142, FR-143, FR-144, FR-145, FR-146
**SCs**: SC-057, SC-059, SC-060, SC-061

### Enums and Constants

- [x] T-601 [US28] Create `Permission` enum with fixed set (`query.submit`, `query.history.view`, `admin.connections.manage`, `admin.roles.manage`, `admin.sso.manage`, `admin.audit.verify`) in `backend/src/app/db/models/enums.py` — FR-122, FR-127
- [x] T-602 [US28] Create `AuthProvider` enum (`local`, `oidc`, `saml`) in `backend/src/app/db/models/enums.py` — FR-117, FR-118
- [x] T-603 [US28] Create `SsoProtocol` enum (`oidc`, `saml`) in `backend/src/app/db/models/enums.py` — FR-115, FR-116
- [x] T-604 [US28] Create `AuditActionType` enum (all 22 action types from data-model.md) in `backend/src/app/db/models/enums.py` — FR-140

### ORM Models

- [x] T-605 [US29] Write TDD tests for `SsoProvider` model CRUD in `backend/tests/unit/test_sso_provider_model.py` — FR-115, FR-116
- [x] T-606 [US29] Create `SsoProvider` ORM model in `backend/src/app/db/models/sso_provider.py` per data-model.md — FR-115, FR-116
- [x] T-607 [US28] Write TDD tests for `Role` model CRUD in `backend/tests/unit/test_role_model.py` — FR-122, FR-145
- [x] T-608 [US28] Create `Role` ORM model in `backend/src/app/db/models/role.py` per data-model.md — FR-122, FR-145
- [x] T-609 [US31] Write TDD tests for `RoleConnectionPolicy` model CRUD in `backend/tests/unit/test_role_connection_policy_model.py` — FR-128, FR-131, FR-132
- [x] T-610 [US31] Create `RoleConnectionPolicy` ORM model in `backend/src/app/db/models/role_connection_policy.py` per data-model.md — FR-128, FR-131, FR-132
- [x] T-611 [US30] Write TDD tests for `SsoGroupMapping` model CRUD in `backend/tests/unit/test_sso_group_mapping_model.py` — FR-125
- [x] T-612 [US30] Create `SsoGroupMapping` ORM model in `backend/src/app/db/models/sso_group_mapping.py` per data-model.md — FR-125
- [x] T-613 [US26] Write TDD tests for `UserIdentity` model CRUD in `backend/tests/unit/test_user_identity_model.py` — FR-117, FR-118
- [x] T-614 [US26] Create `UserIdentity` ORM model in `backend/src/app/db/models/user_identity.py` per data-model.md — FR-117, FR-118
- [x] T-615 [US28] Write TDD tests for `AuditLogEntry` model (append-only, chained hash) in `backend/tests/unit/test_audit_log_entry_model.py` — FR-140, FR-141
- [x] T-616 [US28] Create `AuditLogEntry` ORM model in `backend/src/app/db/models/audit_log_entry.py` per data-model.md — FR-140, FR-141
- [x] T-617 [US28] Update `backend/src/app/db/models/__init__.py` to export all new models — FR-140

### Migration

- [x] T-618 Write Alembic migration `007_phase5_sso_rbac_security.py` in `backend/src/app/db/migrations/versions/`: create all new tables, modify `users` table (add `role_id`, `is_builtin`, `auth_provider`; make `password_hash` nullable), seed built-in admin role + genesis audit entry per data-model.md migration notes — FR-145, FR-146, FR-141

### Audit Service

- [x] T-619 [US28] Write TDD tests for `AuditService` (log entry creation, chained hashing, genesis entry, canonical JSON, secret redaction) in `backend/tests/unit/test_audit_service.py` — FR-140, FR-141, FR-143, SC-059, SC-061
- [x] T-620 [US28] Implement `AuditService` in `backend/src/app/services/audit_service.py`: `log()` with SHA-256 chained hashing (canonical JSON, sorted keys, ISO 8601 UTC microseconds), `verify_chain()` returning `VerificationResult`, genesis handling, `SELECT ... FOR UPDATE` serialization — FR-140, FR-141, FR-142, FR-143
- [x] T-621 [US28] Write TDD tests for audit chain verification (intact chain, broken chain detection, first break reporting) in `backend/tests/unit/test_audit_chain_verification.py` — FR-141, SC-060
- [x] T-622 [US28] Write TDD tests for audit entry immutability (application-layer UPDATE/DELETE prevention) in `backend/tests/unit/test_audit_immutability.py` — FR-141, SC-060
- [x] T-623 [US28] Write TDD tests for audit secret redaction (no secrets, credentials, full tokens in entries) in `backend/tests/unit/test_audit_redaction.py` — FR-143, SC-061

### Permission Middleware

- [ ] T-624 [US28] Write TDD tests for `require_permission()` FastAPI dependency in `backend/tests/unit/test_permission_middleware.py` — FR-127
- [ ] T-625 [US28] Implement `require_permission(*perms)` FastAPI dependency in `backend/src/app/api/dependencies/permissions.py`: check session permissions against required set, return 403 with `error.forbidden` on failure — FR-127

### Pydantic Schemas

- [ ] T-626 [US28] Create Phase 5 Pydantic request/response schemas in `backend/src/app/schemas/sso.py`: `SsoProviderResponse`, `SsoProviderCreate`, `SsoProviderUpdate`, `SsoProviderPublic` — FR-115, FR-116
- [ ] T-627 [US28] Create Phase 5 Pydantic schemas in `backend/src/app/schemas/roles.py`: `RoleResponse`, `RoleCreate`, `RoleUpdate`, `RoleDetailResponse`, `ConnectionPolicyCreate`, `PolicyTestRequest`, `PolicyTestResponse` — FR-122, FR-136
- [ ] T-628 [US28] Create Phase 5 Pydantic schemas in `backend/src/app/schemas/audit.py`: `AuditVerifyResponse`, `AuditStatusResponse` — FR-141, FR-144
- [ ] T-629 [US28] Create Phase 5 Pydantic schemas in `backend/src/app/schemas/group_mapping.py`: `GroupMappingResponse`, `GroupMappingCreate` — FR-125
- [ ] T-630 [US28] Extend `UserProfileResponse` in `backend/src/app/schemas/auth.py` with `role_id`, `role_name`, `permissions`, `auth_provider` fields — FR-127

### Session Extension

- [ ] T-631 [US26] Write TDD tests for extended Redis session data (role_id, permissions, auth_provider, subject_id) in `backend/tests/unit/test_session_extension.py` — FR-127
- [ ] T-632 [US26] Extend session creation/read in `backend/src/app/services/auth_service.py` and `backend/src/app/repositories/session_repository.py` to include `role_id`, `role_name`, `permissions`, `auth_provider`, `subject_id`, `email` per data-model.md Redis session structure — FR-127

### OpenAPI Update

- [ ] T-633 Update OpenAPI spec in `backend/openapi.yaml` with all new Phase 5 types, endpoints, and error codes per api-contracts.md — FR-127

### Wave 17.0 Backend Gate

- [ ] T-634 Run backend foundation gates: `cd backend && uv run pytest -q -m "not integration"` + `uv run ruff check src tests` + `uv run ruff format --check src tests` — SC-057

---

## Wave 17.1 — OIDC/SAML SSO and Admin-Safe Local Login

**Branch**: `phase-5/wave-17.1-sso-auth`
**Depends on**: Wave 17.0 merged
**FRs**: FR-115, FR-116, FR-117, FR-118, FR-119, FR-120, FR-121, FR-146
**SCs**: SC-046, SC-047, SC-048, SC-056, SC-057

### Backend — SSO Service (Owner: Kimi ( opencode ))

- [ ] T-635 [US26] Write TDD tests for OIDC authorization code flow initiation (state/nonce generation, Redis storage, redirect URL) in `backend/tests/unit/test_sso_oidc_flow.py` — FR-117, SC-046
- [ ] T-636 [US26] Write TDD tests for OIDC callback (ID token validation per S-001: issuer, audience, signature, expiry, nonce, state, replay protection) in `backend/tests/unit/test_sso_oidc_callback.py` — FR-117, FR-119, SC-046
- [ ] T-637 [US26] Write TDD tests for OIDC error cases (expired token, bad signature, wrong audience, missing nonce, replayed nonce) in `backend/tests/unit/test_sso_oidc_errors.py` — FR-119
- [ ] T-638 [US27] Write TDD tests for SAML AuthnRequest initiation in `backend/tests/unit/test_sso_saml_flow.py` — FR-118, SC-047
- [ ] T-639 [US27] Write TDD tests for SAML callback (assertion validation per S-002: issuer, audience, signature, timestamps, replay) in `backend/tests/unit/test_sso_saml_callback.py` — FR-118, FR-119, SC-047
- [ ] T-640 [US27] Write TDD tests for SAML error cases (expired assertion, replayed assertion, invalid signature, missing signature) in `backend/tests/unit/test_sso_saml_errors.py` — FR-119
- [ ] T-641 [US26] Implement `SsoService` in `backend/src/app/services/sso_service.py`: OIDC flow via Authlib (authorization code + ID token validation per S-001), SAML flow via python3-saml (AuthnRequest + assertion validation per S-002), behind `SsoProvider` protocol — FR-117, FR-118, FR-119
- [ ] T-642 [US30] Write TDD tests for role resolution from SSO group claims (single group, multi-group priority ordering, no matching group) in `backend/tests/unit/test_role_resolution.py` — FR-145, SC-062
- [ ] T-643 [US30] Implement role resolution logic in `backend/src/app/services/sso_service.py`: resolve SSO groups → role via priority ordering, create/update `UserIdentity` on first login — FR-145, SC-062
- [ ] T-644 [US26] Write TDD tests for replay protection (Redis nonce/assertion ID cache with TTL) in `backend/tests/unit/test_replay_protection.py` — FR-119

### Backend — SSO Endpoints (Owner: Kimi ( opencode ))

- [ ] T-645 [US26] Implement SSO auth endpoints in `backend/src/app/api/v1/sso_auth.py`: `GET /auth/sso/providers` (public), `GET /auth/sso/oidc/login`, `GET /auth/sso/oidc/callback`, `GET /auth/sso/saml/login`, `POST /auth/sso/saml/callback` per api-contracts.md — FR-117, FR-118, FR-121
- [ ] T-646 [US26] Register SSO auth router in `backend/src/app/main.py` — FR-117

### Backend — Local Login Restriction (Owner: Kimi ( opencode ))

- [ ] T-647 [US26] Write TDD tests for local login restriction (admin-only, reject non-admin, generic error, no account existence leak) in `backend/tests/unit/test_local_login_restriction.py` — FR-120
- [ ] T-648 [US26] Modify `POST /auth/sign-in` in `backend/src/app/api/v1/auth.py`: reject non-admin local login with generic 401 — FR-120

### Backend — Admin SSO Config Endpoints (Owner: Kimi ( opencode ))

- [ ] T-649 [US29] Write TDD tests for SSO provider CRUD endpoints (create OIDC, create SAML, update, delete, secret masking in responses, duplicate protocol rejection) in `backend/tests/unit/test_sso_admin_endpoints.py` — FR-115, FR-116
- [ ] T-650 [US29] Implement SSO admin CRUD endpoints in `backend/src/app/api/v1/admin_sso.py`: `GET/POST /admin/sso/providers`, `PUT/DELETE /admin/sso/providers/{id}` per api-contracts.md, with `require_permission('admin.sso.manage')`, secret encryption via `app.core.encryption`, masked responses per S-003 — FR-115, FR-116
- [ ] T-651 [US29] Register SSO admin router in `backend/src/app/main.py` — FR-115

### Backend — Lockout Prevention (Owner: Kimi ( opencode ))

- [ ] T-652 [US26] Write TDD tests for built-in admin lockout prevention (undeletable user, undeletable role, local login always works, SSO changes cannot lock out admin) in `backend/tests/unit/test_admin_lockout_prevention.py` — FR-146, S-009
- [ ] T-653 [US26] Implement lockout prevention guards in relevant services: reject delete of `is_builtin=true` user/role with 403 `error.builtinRoleProtected` — FR-146

### Backend — SSO Audit Logging (Owner: Kimi ( opencode ))

- [ ] T-654 [US26] Write TDD tests for SSO audit logging (login success, login failure, SSO validation events, SSO config changes) in `backend/tests/unit/test_sso_audit_logging.py` — FR-140
- [ ] T-655 [US26] Add audit logging calls in SSO service and SSO admin endpoints for all SSO-related events — FR-140

### Backend — Concurrent Session Limit (Owner: Kimi ( opencode ))

- [ ] T-656 [US26] Write TDD tests for concurrent session limit (max 5, oldest evicted on overflow) in `backend/tests/unit/test_concurrent_sessions.py` — FR-127, SC-057
- [ ] T-657 [US26] Implement concurrent session limit in `backend/src/app/repositories/session_repository.py`: max sessions per user (configurable, default 5), evict oldest on overflow — FR-127, SC-057

### Wave 17.1 Backend Gate

- [ ] T-658 Run backend foundation gates: `cd backend && uv run pytest -q -m "not integration"` + `uv run ruff check src tests` + `uv run ruff format --check src tests` — SC-057

### Frontend — SSO Sign-In Page (Owner: Gemini)

- [ ] T-659 [US26] Write TDD tests for SSO sign-in page (provider list rendering, SSO button clicks, error code→i18n mapping, no-provider message, RTL layout) in `frontend/src/pages/SignInPage.test.tsx` (extend existing) — FR-121, FR-119
- [ ] T-660 [US26] Update `frontend/src/pages/SignInPage.tsx`: add "Sign in with SSO" button(s) from `GET /auth/sso/providers`, display error codes from redirect query params as localized messages, show `error.ssoNotConfigured` when no providers — FR-121, FR-119
- [ ] T-661 [US26] Extend `useAuth` hook in `frontend/src/hooks/useAuth.ts`: add `UserProfile` fields (`permissions`, `role_name`, `auth_provider`), add SSO provider fetch — FR-127

### Frontend — Admin SSO Config Page (Owner: Gemini)

- [ ] T-662 [US29] Write TDD tests for SSO config page (OIDC form, SAML form, secret masking display, validation errors, CRUD operations) in `frontend/src/pages/AdminSsoPage.test.tsx` — FR-115, FR-116
- [ ] T-663 [US29] Create admin SSO config page `frontend/src/pages/AdminSsoPage.tsx`: OIDC provider form (issuer, client ID, secret, scopes, redirect URI, group claim), SAML provider form (entity ID, metadata URL/XML, certificate), secret masking (`●●●●●●●●`), validation error display — FR-115, FR-116
- [ ] T-664 [US29] Create `useAdminSso` hook in `frontend/src/hooks/useAdminSso.ts` for SSO provider CRUD via TanStack Query — FR-115, FR-116

### Frontend — i18n for Wave 17.1 (Owner: Gemini)

- [ ] T-665 [US33] Add all Wave 17.1 i18n keys to `frontend/src/locales/en.json` and `frontend/src/locales/ar.json`: SSO sign-in labels, SSO error messages, SSO config page labels, all new `error.*` keys per api-contracts.md error codes — FR-137, FR-139
- [ ] T-666 [US33] Verify 100% EN/AR key parity for Wave 17.1 keys via `frontend/src/locales/localeCoverage.test.ts` — FR-137, SC-054

### Frontend — Routing (Owner: Gemini)

- [ ] T-667 [US29] Add `/admin/sso` route to `frontend/src/App.tsx` with permission guard — FR-115

### Frontend — Browser Evidence (Owner: Gemini)

- [ ] T-668 [US26] Chrome DevTools MCP: verify SSO sign-in page renders provider buttons, error messages display correctly, Arabic/RTL layout correct — FR-121, SC-055
- [ ] T-669 [US29] Chrome DevTools MCP: verify admin SSO config page renders OIDC/SAML forms, secret masking works, Arabic/RTL correct — FR-115, SC-055

### Wave 17.1 Frontend Gate

- [ ] T-670 Run frontend foundation gates: `cd frontend && npm run test -- --run` + `npm run lint` + `npm run typecheck` + `npm run build` + `npm run lint:css` — SC-056

---

## Wave 17.2 — RBAC Roles, Group Mapping, Route/API Gates

**Branch**: `phase-5/wave-17.2-rbac-gates`
**Depends on**: Wave 17.1 merged
**FRs**: FR-122, FR-123, FR-124, FR-125, FR-126, FR-127, FR-145
**SCs**: SC-048, SC-049, SC-056, SC-057, SC-062

### Backend — Role CRUD (Owner: Kimi ( opencode ))

- [ ] T-671 [US28] Write TDD tests for role CRUD endpoints (create, read, update, delete, built-in role protection, duplicate name/priority rejection, permission validation) in `backend/tests/unit/test_role_endpoints.py` — FR-122, FR-123, FR-124
- [ ] T-672 [US28] Create `RoleRepository` in `backend/src/app/repositories/role_repository.py`: CRUD operations, built-in protection, uniqueness checks — FR-122, FR-123, FR-124
- [ ] T-673 [US28] Create `RoleService` in `backend/src/app/services/role_service.py`: role CRUD with validation, built-in role guard, audit logging — FR-122, FR-123, FR-124
- [ ] T-674 [US28] Implement role CRUD endpoints in `backend/src/app/api/v1/admin_roles.py`: `GET/POST /admin/roles`, `GET/PUT/DELETE /admin/roles/{id}` per api-contracts.md with `require_permission('admin.roles.manage')` — FR-122, FR-123, FR-124
- [ ] T-675 [US28] Register roles admin router in `backend/src/app/main.py` — FR-122

### Backend — Group Mapping (Owner: Kimi ( opencode ))

- [ ] T-676 [US30] Write TDD tests for group mapping endpoints (create, list, delete, duplicate group rejection) in `backend/tests/unit/test_group_mapping_endpoints.py` — FR-125
- [ ] T-677 [US30] Implement group mapping endpoints in `backend/src/app/api/v1/admin_sso.py` (extend): `GET/POST /admin/sso/group-mappings`, `DELETE /admin/sso/group-mappings/{id}` per api-contracts.md with `require_permission('admin.roles.manage')` — FR-125

### Backend — Permission Gates (Owner: Kimi ( opencode ))

- [ ] T-678 [US28] Write TDD tests for permission gates on ALL admin endpoints (connections, roles, SSO, audit) and query endpoints in `backend/tests/unit/test_permission_gates_all.py`: verify 403 for missing permissions, no admin access for end users — FR-127, SC-049
- [ ] T-679 [US28] Apply `require_permission()` dependency to all existing admin endpoints in `backend/src/app/api/v1/admin.py`, `admin_connections.py` — FR-127
- [ ] T-680 [US28] Apply `require_permission('query.submit')` to query endpoints, `require_permission('query.history.view')` to history endpoints in `backend/src/app/api/v1/query.py`, `history.py` — FR-127

### Backend — User Denial (Owner: Kimi ( opencode ))

- [ ] T-681 [US28] Write TDD tests for unmapped user denial (user with no role_id denied all API access) in `backend/tests/unit/test_unmapped_user_denial.py` — FR-126, SC-048
- [ ] T-682 [US28] Implement unmapped user denial: middleware/dependency checks `role_id` is not null, returns 403 `error.forbidden` for unmapped users — FR-126

### Backend — RBAC Audit Logging (Owner: Kimi ( opencode ))

- [ ] T-683 [US28] Write TDD tests for RBAC audit events (role create/update/delete, mapping changes, access denied) in `backend/tests/unit/test_rbac_audit_logging.py` — FR-140
- [ ] T-684 [US28] Add audit logging calls to role CRUD and group mapping endpoints for all RBAC-related events — FR-140

### Wave 17.2 Backend Gate

- [ ] T-685 Run backend foundation gates: `cd backend && uv run pytest -q -m "not integration"` + `uv run ruff check src tests` + `uv run ruff format --check src tests` — SC-057

### Frontend — Role Management Page (Owner: Gemini)

- [ ] T-686 [US28] Write TDD tests for role management page (role list, create form, edit form, delete confirmation, permission selector, priority input, built-in role indicator, group mapping editor) in `frontend/src/pages/AdminRolesPage.test.tsx` — FR-122, FR-123, FR-124
- [ ] T-687 [US28] Create role management page `frontend/src/pages/AdminRolesPage.tsx`: role list with name/description/priority/permissions/group count, create/edit form with all fields per api-contracts.md, delete with confirmation, built-in role protection indicator — FR-122, FR-123, FR-124
- [ ] T-688 [US30] Create group mapping UI component `frontend/src/components/admin/GroupMappingEditor.tsx`: inline within role editor, add/remove SSO group values — FR-125
- [ ] T-689 [US28] Create `useAdminRoles` hook in `frontend/src/hooks/useAdminRoles.ts` for role CRUD + group mapping via TanStack Query — FR-122, FR-125

### Frontend — Permission-Based Route Guards (Owner: Gemini)

- [ ] T-690 [US28] Write TDD tests for permission-based route guards (admin nav hidden for non-admin, routes redirect unauthorized users) in `frontend/src/components/auth/PermissionGuard.test.tsx` — FR-127
- [ ] T-691 [US28] Create `PermissionGuard` component in `frontend/src/components/auth/PermissionGuard.tsx`: wrap admin routes, check `permissions` from `useAuth`, redirect or hide — FR-127
- [ ] T-692 [US28] Update `frontend/src/App.tsx`: wrap admin routes (`/admin/*`) with `PermissionGuard`, add `/admin/roles` route — FR-127

### Frontend — i18n for Wave 17.2 (Owner: Gemini)

- [ ] T-693 [US33] Add all Wave 17.2 i18n keys to `frontend/src/locales/en.json` and `frontend/src/locales/ar.json`: role management labels, group mapping labels, permission names, validation messages — FR-137
- [ ] T-694 [US33] Verify 100% EN/AR key parity for Wave 17.2 keys via locale coverage test — FR-137, SC-054

### Frontend — Browser Evidence (Owner: Gemini)

- [ ] T-695 [US28] Chrome DevTools MCP: verify role management page renders list/create/edit/delete, Arabic/RTL layout correct — FR-122, SC-055
- [ ] T-696 [US30] Chrome DevTools MCP: verify group mapping editor renders within role form, Arabic/RTL correct — FR-125, SC-055

### Wave 17.2 Frontend Gate

- [ ] T-697 Run frontend foundation gates: `cd frontend && npm run test -- --run` + `npm run lint` + `npm run typecheck` + `npm run build` + `npm run lint:css` — SC-056

---

## Wave 17.3 — Row Filters, Column Masks, LLM Schema Filtering, Evaluator Enforcement

**Branch**: `phase-5/wave-17.3-policy-enforcement`
**Depends on**: Wave 17.2 merged
**FRs**: FR-128, FR-129, FR-130, FR-131, FR-132, FR-133, FR-134, FR-135, FR-136
**SCs**: SC-050, SC-051, SC-052, SC-053, SC-056, SC-057

### Backend — Schema Filtering (Owner: Kimi ( opencode ))

- [ ] T-698 [US31] Write TDD tests for schema filtering service (filter `SchemaContext` by role policy, exclude unauthorized tables/columns) in `backend/tests/unit/test_schema_filtering.py` — FR-128, FR-129, SC-050
- [ ] T-699 [US31] Implement `PolicyEnforcementService.filter_schema()` in `backend/src/app/services/policy_enforcement.py`: filter `SchemaContext` by role's `allowed_tables`/`allowed_columns` before LLM prompt construction per S-006 — FR-128, FR-129

### Backend — Row Filter Validation (Owner: Kimi ( opencode ))

- [ ] T-700 [US31] Write TDD tests for row filter validation at save time (`sqlglot` AST parsing, column existence check, reject subqueries/functions/UNION/DML/comments, fail-closed on absent columns) in `backend/tests/unit/test_row_filter_validation.py` — FR-131, S-004
- [ ] T-701 [US31] Implement row filter validation in `backend/src/app/services/policy_enforcement.py`: `validate_row_filter()` per S-004 — parse with `sqlglot`, reject dangerous expressions, validate column existence against connection schema, fail-closed — FR-131
- [ ] T-702 [US31] Write TDD tests for `{user.*}` placeholder binding (email, subject_id, role) resolved to parameterized bind values in `backend/tests/unit/test_placeholder_binding.py` — FR-131, S-004

### Backend — Row Filter Injection (Owner: Kimi ( opencode ))

- [ ] T-703 [US31] Write TDD tests for row filter injection at query time (`sqlglot` AST AND-conjunction into WHERE, cross-dialect identifier quoting for PG/MySQL/MSSQL) in `backend/tests/unit/test_row_filter_injection.py` — FR-131, SC-051
- [ ] T-704 [US31] Implement row filter injection in `backend/src/app/services/policy_enforcement.py`: `apply_row_filters()` — parse generated SQL via `sqlglot`, inject filter via AST AND-conjunction, resolve `{user.*}` to parameterized values, transpile per dialect per S-005 — FR-131
- [ ] T-705 [US31] Write TDD tests for schema drift guard (filter references column no longer in schema → block query, emit `policy.schema_mismatch` audit event, return `error.policySchemaConflict`) in `backend/tests/unit/test_schema_drift_guard.py` — FR-131, S-004, S-005

### Backend — Column Masking (Owner: Kimi ( opencode ))

- [ ] T-706 [US31] Write TDD tests for column masking service (replace values with `***`, add `masked: true` to `ColumnMeta`, works for all 3 dialects) in `backend/tests/unit/test_column_masking.py` — FR-132, SC-052
- [ ] T-707 [US31] Implement column masking in `backend/src/app/services/policy_enforcement.py`: `apply_column_masks()` — post-query result replacement per ADR-19, set `masked` flag on `ColumnMeta` — FR-132, FR-133

### Backend — Evaluator Extension (Owner: Kimi ( opencode ))

- [ ] T-708 [US31] Write TDD tests for evaluator authorization rule (check SQL table/column references against role-allowed schema, block if outside set, allow masked columns in WHERE) in `backend/tests/unit/test_evaluator_auth_rule.py` — FR-130, S-007, SC-050
- [ ] T-709 [US31] Create evaluator authorization rule in `backend/src/app/evaluator/rules/role_authorization.py`: check SQL references against role policy, block disallowed with `error.queryBlockedPolicy`, allow masked columns per S-007 — FR-130
- [ ] T-710 [US31] Register `RoleAuthorizationRule` in evaluator pipeline in `backend/src/app/evaluator/pipeline.py` — FR-130

### Backend — Query Flow Integration (Owner: Kimi ( opencode ))

- [ ] T-711 [US31] Write TDD tests for integrated query flow (schema filter → LLM prompt → evaluator auth → row filter injection → execute → column mask → response) in `backend/tests/unit/test_query_flow_policy.py` — FR-128, FR-129, FR-130, FR-131, FR-132
- [ ] T-712 [US31] Integrate policy enforcement into query service in `backend/src/app/services/query_service.py`: call `filter_schema()` before prompt, `apply_row_filters()` before execution, `apply_column_masks()` after execution — FR-128, FR-131, FR-132

### Backend — Role Policy Test (Owner: Kimi ( opencode ))

- [ ] T-713 [US28] Write TDD tests for role policy test endpoint (dry-run evaluation showing accessible/blocked tables, filters, masks) in `backend/tests/unit/test_policy_test_endpoint.py` — FR-136
- [ ] T-714 [US28] Implement `POST /admin/roles/{id}/test-policy` in `backend/src/app/api/v1/admin_roles.py` per api-contracts.md — FR-136

### Backend — Query History Scoping (Owner: Kimi ( opencode ))

- [ ] T-715 [US32] Write TDD tests for query history scoping (user sees only own queries, no cross-user leakage) in `backend/tests/unit/test_history_scoping.py` — FR-134, SC-053
- [ ] T-716 [US32] Modify `GET /history` in `backend/src/app/api/v1/history.py`: filter by `user_id = current_user.id` — FR-134

### Backend — Accepted Query Rerun Revalidation (Owner: Kimi ( opencode ))

- [ ] T-717 [US32] Write TDD tests for accepted-query rerun re-validation (role restricted since acceptance → block rerun) in `backend/tests/unit/test_rerun_revalidation.py` — FR-135, SC-053
- [ ] T-718 [US32] Implement rerun re-validation in query service: re-check SQL against current role policy before execution — FR-135

### Backend — Query/Policy Audit Logging (Owner: Kimi ( opencode ))

- [ ] T-719 [US31] Write TDD tests for query lifecycle audit events (submit, validate pass/fail, execute, accept, reject, policy block) in `backend/tests/unit/test_query_audit_logging.py` — FR-140
- [ ] T-720 [US31] Add audit logging calls to query service for all query lifecycle events — FR-140

### Backend — Cross-Dialect Enforcement Tests (Owner: Kimi ( opencode ))

- [ ] T-721 [US31] Write cross-dialect policy enforcement tests (row filters + column masks verified against PostgreSQL, MySQL, MSSQL via testcontainers where feasible) in `backend/tests/integration/test_cross_dialect_policy.py` — FR-131, FR-132, SC-051, SC-052

### Wave 17.3 Backend Gate

- [ ] T-722 Run backend foundation gates: `cd backend && uv run pytest -q -m "not integration"` + `uv run ruff check src tests` + `uv run ruff format --check src tests` — SC-057

### Frontend — Masked Column Indicator (Owner: Gemini)

- [ ] T-723 [US31] Write TDD tests for masked column indicator in `ResultTable` (localized badge, renders for masked columns, EN/AR text) in `frontend/src/components/query/ResultTable.test.tsx` (extend) — FR-133
- [ ] T-724 [US31] Implement masked column indicator in `frontend/src/components/query/ResultTable.tsx`: render localized "column was masked" badge when `ColumnMeta.masked === true` — FR-133

### Frontend — Policy Editor (Owner: Gemini)

- [ ] T-725 [US31] Write TDD tests for role connection policy editor (table/column selector, row filter input, column mask selector, schema browser) in `frontend/src/components/admin/PolicyEditor.test.tsx` — FR-122, FR-131, FR-132
- [ ] T-726 [US31] Create policy editor component `frontend/src/components/admin/PolicyEditor.tsx`: table/column multi-select from connection schema, row filter text input with validation feedback, column mask selector — FR-122, FR-131, FR-132
- [ ] T-727 [US31] Create `useConnectionSchema` hook in `frontend/src/hooks/useConnectionSchema.ts` to fetch connection schema for policy editor — FR-128

### Frontend — i18n for Wave 17.3 (Owner: Gemini)

- [ ] T-728 [US33] Add all Wave 17.3 i18n keys to `frontend/src/locales/en.json` and `frontend/src/locales/ar.json`: masking indicator, policy editor labels, filter validation messages, policy error messages — FR-137
- [ ] T-729 [US33] Verify 100% EN/AR key parity for Wave 17.3 keys via locale coverage test — FR-137, SC-054

### Frontend — Browser Evidence (Owner: Gemini)

- [ ] T-730 [US31] Chrome DevTools MCP: verify masked column indicator renders in result table, Arabic/RTL correct — FR-133, SC-055
- [ ] T-731 [US31] Chrome DevTools MCP: verify policy editor renders table/column selector, row filter input, Arabic/RTL correct — FR-122, SC-055

### Wave 17.3 Frontend Gate

- [ ] T-732 Run frontend foundation gates: `cd frontend && npm run test -- --run` + `npm run lint` + `npm run typecheck` + `npm run build` + `npm run lint:css` — SC-056

---

## Wave 17.4 — Tamper-Evident Audit Log Coverage and Verification UI/API

**Branch**: `phase-5/wave-17.4-audit-verification`
**Depends on**: Wave 17.3 merged
**FRs**: FR-140, FR-141, FR-142, FR-143, FR-144
**SCs**: SC-059, SC-060, SC-061, SC-056, SC-057

### Backend — Audit Event Coverage (Owner: Kimi ( opencode ))

- [ ] T-733 [US28] Write comprehensive TDD tests verifying ALL 21 audit action types emit entries (logins, SSO validation, queries, role CRUD, mapping changes, SSO config changes, connection changes, access denied, audit verification) in `backend/tests/unit/test_audit_event_coverage.py` — FR-140, SC-059
- [ ] T-734 [US28] Review and add any missing audit logging calls across all services/endpoints to ensure complete coverage of all 21 action types — FR-140

### Backend — Audit Immutability and Redaction (Owner: Kimi ( opencode ))

- [ ] T-735 [US28] Write TDD tests verifying audit entry immutability (application-level UPDATE/DELETE rejected) in `backend/tests/unit/test_audit_immutability_comprehensive.py` — FR-141, SC-060
- [ ] T-736 [US28] Write TDD tests verifying no secrets/credentials/tokens in any audit entry context across all action types in `backend/tests/unit/test_audit_redaction_comprehensive.py` — FR-143, SC-061

### Backend — Audit Verification Endpoint (Owner: Kimi ( opencode ))

- [ ] T-737 [US28] Write TDD tests for audit verification endpoint (`POST /admin/audit/verify`) and status endpoint (`GET /admin/audit/status`) in `backend/tests/unit/test_audit_endpoints.py` — FR-141, FR-144
- [ ] T-738 [US28] Implement audit endpoints in `backend/src/app/api/v1/admin_audit.py`: `POST /admin/audit/verify` (triggers chain walk, returns `VerificationResult`), `GET /admin/audit/status` (returns last verification + entry count) per api-contracts.md, with `require_permission('admin.audit.verify')` — FR-141, FR-144
- [ ] T-739 [US28] Register audit admin router in `backend/src/app/main.py` — FR-144
- [ ] T-740 [US28] Implement chain recovery behavior on broken chain (report `sequence_number` of first mismatch, no auto-repair, continue appending, log verification result as audit event) per S-008 — FR-141

### Backend — Retention Config (Owner: Kimi ( opencode ))

- [ ] T-741 [US28] Add `AUDIT_RETENTION_MONTHS` config setting (default 24) to `backend/src/app/core/config.py` — FR-142

### Wave 17.4 Backend Gate

- [ ] T-742 Run backend foundation gates: `cd backend && uv run pytest -q -m "not integration"` + `uv run ruff check src tests` + `uv run ruff format --check src tests` — SC-057

### Frontend — Audit Verification Page (Owner: Gemini)

- [ ] T-743 [US28] Write TDD tests for audit verification page (verify button, status display, last verification result, broken chain warning) in `frontend/src/pages/AdminAuditPage.test.tsx` — FR-141, FR-144
- [ ] T-744 [US28] Create audit verification page `frontend/src/pages/AdminAuditPage.tsx`: verification trigger button, entry count, last verification timestamp, result (verified/broken + first break location), loading state — FR-141, FR-144
- [ ] T-745 [US28] Create `useAdminAudit` hook in `frontend/src/hooks/useAdminAudit.ts` for audit verify/status via TanStack Query — FR-141, FR-144
- [ ] T-746 [US28] Add `/admin/audit` route to `frontend/src/App.tsx` with permission guard for `admin.audit.verify` — FR-144

### Frontend — i18n for Wave 17.4 (Owner: Gemini)

- [ ] T-747 [US33] Add all Wave 17.4 i18n keys to `frontend/src/locales/en.json` and `frontend/src/locales/ar.json`: audit page labels, verification status messages, chain integrity messages — FR-137
- [ ] T-748 [US33] Verify 100% EN/AR key parity for Wave 17.4 keys via locale coverage test — FR-137, SC-054

### Frontend — Browser Evidence (Owner: Gemini)

- [ ] T-749 [US28] Chrome DevTools MCP: verify audit verification page renders button/status/results, Arabic/RTL correct — FR-141, SC-055

### Wave 17.4 Frontend Gate

- [ ] T-750 Run frontend foundation gates: `cd frontend && npm run test -- --run` + `npm run lint` + `npm run typecheck` + `npm run build` + `npm run lint:css` — SC-056

---

## Wave 17.5 — Arabic/RTL Polish, Browser Smoke, Cross-Dialect Verification, Final Audit

**Branch**: `phase-5/wave-17.5-polish-closeout`
**Depends on**: Wave 17.4 merged
**FRs**: FR-137, FR-138, FR-139 + all FRs final verification
**SCs**: SC-054, SC-055, SC-056, SC-057, SC-058 + all SCs final verification

### i18n Parity Audit (Owner: Gemini)

- [ ] T-751 [US33] Run full i18n key parity audit: compare all keys in `frontend/src/locales/en.json` vs `frontend/src/locales/ar.json`, fix any missing keys to achieve 100% parity — FR-137, SC-054
- [ ] T-752 [US33] Verify zero English fallback strings render in Arabic mode across all Phase 5 screens — FR-137

### CSS Logical Property Audit (Owner: Gemini)

- [ ] T-753 [US33] Run CSS logical property audit on all Phase 5 components: verify zero physical directional CSS (`left`/`right`/`margin-left`/`margin-right`), all logical properties — FR-138, SC-055

### Chrome DevTools MCP Browser Smoke — All Phase 5 Screens in Arabic (Owner: Gemini)

- [ ] T-754 [US33] Chrome DevTools MCP: verify SSO sign-in page in Arabic/RTL — all labels, buttons, error messages in Arabic, correct RTL layout — FR-137, FR-138, SC-055
- [ ] T-755 [US33] Chrome DevTools MCP: verify admin SSO config page in Arabic/RTL — form labels, validation messages, secret masking — FR-137, FR-138, SC-055
- [ ] T-756 [US33] Chrome DevTools MCP: verify role management page (list, create, edit) in Arabic/RTL — FR-137, FR-138, SC-055
- [ ] T-757 [US33] Chrome DevTools MCP: verify group mapping editor in Arabic/RTL — FR-137, FR-138, SC-055
- [ ] T-758 [US33] Chrome DevTools MCP: verify masked column indicator in results table in Arabic/RTL — FR-137, FR-138, SC-055
- [ ] T-759 [US33] Chrome DevTools MCP: verify audit verification page in Arabic/RTL — FR-137, FR-138, SC-055
- [ ] T-760 [US33] Chrome DevTools MCP: verify auth error messages (no role, expired session, SSO failure) in Arabic/RTL — no raw IdP errors, no UUIDs, no hostnames — FR-139, SC-055

### Auth Error Sanitization Verification (Owner: Gemini)

- [ ] T-761 [US33] Verify no raw IdP errors, UUIDs, hostnames, credentials, or internal schema details appear in any UI error message or browser-visible evidence across all Phase 5 screens — FR-139

### Cross-Dialect Security Verification (Owner: Kimi ( opencode ))

- [ ] T-762 [US31] Run cross-dialect policy enforcement verification: submit query as restricted role against PostgreSQL, verify row filters and column masks enforce correctly — FR-131, FR-132, SC-051, SC-052
- [ ] T-763 [US31] Run cross-dialect policy enforcement verification: submit query as restricted role against MySQL, verify row filters and column masks enforce correctly — FR-131, FR-132, SC-051, SC-052
- [ ] T-764 [US31] Run cross-dialect policy enforcement verification: submit query as restricted role against MSSQL, verify row filters and column masks enforce correctly — FR-131, FR-132, SC-051, SC-052

### Security/Privacy Evidence (Owner: Kimi ( opencode ) + Gemini)

- [ ] T-765 Verify no secrets in any API response, UI rendering, or audit log entry — FR-143, SC-061
- [ ] T-766 Verify no raw UUIDs exposed to end users in UI or error messages — FR-139
- [ ] T-767 Verify no hostnames or internal URLs exposed in user-facing errors — FR-139
- [ ] T-768 Verify no raw IdP/driver errors exposed to users (all errors are localized i18n keys) — FR-119, FR-139
- [ ] T-769 Verify no unauthorized schema internals visible in UI or evidence — FR-128, FR-129

### Final Backend Gate (Owner: Kimi ( opencode ))

- [ ] T-770 Run final backend foundation gates: `cd backend && uv run pytest -q -m "not integration"` + `uv run ruff check src tests` + `uv run ruff format --check src tests` — SC-057

### Final Frontend Gate (Owner: Gemini)

- [ ] T-771 Run final frontend foundation gates: `cd frontend && npm run test -- --run` + `npm run lint` + `npm run typecheck` + `npm run build` + `npm run lint:css` — SC-056

### FR/SC Final Verification (Owner: Opus Orchestrator)

- [ ] T-772 Verify all FRs (FR-115 through FR-146) have passing evidence — all FRs
- [ ] T-773 Verify all SCs (SC-046 through SC-062) are met with documented evidence — all SCs
- [ ] T-774 Verify no Critical or High audit findings remain — SC-058

### Closeout Artifacts (Owner: Opus Orchestrator)

- [ ] T-775 Create consolidation report at `audit/wave-17/consolidation-report.md`: all FR/SC evidence, gate results, audit findings disposition — SC-058
- [ ] T-776 Append Phase 5 summary to `specs/005-sso-rbac-row-column-security/plans/orchestration-log.md` — SC-058, all FRs (FR-115–FR-146), all SCs (SC-046–SC-062)
- [ ] T-777 Create wave final snapshot at `specs/005-sso-rbac-row-column-security/plans/wave-final-snapshot.md` — SC-058, all FRs (FR-115–FR-146), all SCs (SC-046–SC-062)
- [ ] T-778 Update `AGENTS.md` Phase 5 status from `IN PROGRESS` to `FROZEN` (only after final PR merged to `main`) — SC-058

---

## Dependency Graph

```
Wave 17.0 (Foundation)
  └── Wave 17.1 (SSO Auth)
       └── Wave 17.2 (RBAC Gates)
            └── Wave 17.3 (Policy Enforcement)
                 └── Wave 17.4 (Audit Verification)
                      └── Wave 17.5 (Polish + Closeout)
```

All waves are strictly sequential. No parallel dispatch.

---

## Task Summary

| Wave | Tasks | Range | Backend (Kimi ( opencode )) | Frontend (Gemini) | Orchestrator (Opus) |
|------|-------|-------|-----------------|-------------------|---------------------|
| Gov. | 1 | T-600 | 0 | 0 | 1 |
| 17.0 | 34 | T-601 – T-634 | 34 | 0 | 0 |
| 17.1 | 36 | T-635 – T-670 | 24 | 12 | 0 |
| 17.2 | 27 | T-671 – T-697 | 15 | 12 | 0 |
| 17.3 | 35 | T-698 – T-732 | 25 | 10 | 0 |
| 17.4 | 18 | T-733 – T-750 | 10 | 8 | 0 |
| 17.5 | 28 | T-751 – T-778 | 8 | 13 | 7 |
| **Total** | **179** | **T-600 – T-778** | **116** | **55** | **8** |

### User Story Coverage

| Story | Tasks | Key Waves |
|-------|-------|-----------|
| US26 (SSO OIDC) | T-613–T-614, T-631–T-632, T-635–T-661, T-668 | 17.0, 17.1 |
| US27 (SSO SAML) | T-638–T-640, T-641 | 17.1 |
| US28 (Roles) | T-601–T-604, T-607–T-608, T-615–T-634, T-671–T-697, T-713–T-714, T-733–T-750 | 17.0, 17.2, 17.3, 17.4 |
| US29 (SSO Config) | T-605–T-606, T-649–T-651, T-662–T-669 | 17.0, 17.1 |
| US30 (Group Mapping) | T-611–T-612, T-642–T-643, T-676–T-677, T-688, T-696 | 17.0, 17.1, 17.2 |
| US31 (Policy Enforcement) | T-609–T-610, T-698–T-732, T-762–T-764 | 17.0, 17.3, 17.5 |
| US32 (History Scoping) | T-715–T-718 | 17.3 |
| US33 (Arabic/RTL) | T-665–T-666, T-693–T-694, T-728–T-729, T-747–T-748, T-751–T-761 | 17.1–17.5 |

### FR → Task Mapping

All 32 FRs (FR-115 through FR-146) are covered. No orphan tasks. No task mapped only to ADR/security labels.

### SC → Task Mapping

All 17 SCs (SC-046 through SC-062) are covered. Final verification in T-772–T-774.

### Format Validation

✅ All 179 tasks follow checklist format: `- [ ] [TaskID] [Story?] Description with file path`
✅ TDD tests precede implementation tasks
✅ Contract/schema tasks precede endpoint/integration tasks
✅ Migration/model tasks precede service/endpoint tasks
✅ Backend gates at end of every backend wave
✅ Frontend gates at end of every frontend wave
✅ Browser evidence tasks for all UI waves
✅ Security/privacy evidence tasks included
✅ Closeout artifacts included
