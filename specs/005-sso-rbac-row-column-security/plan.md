# Implementation Plan — Phase 5: SSO, RBAC, Row/Column Security

**Created**: 2026-05-24
**Phase**: 5
**Spec**: [spec.md](file:///home/avril/QueryCraft/specs/005-sso-rbac-row-column-security/spec.md)
**Research**: [research.md](file:///home/avril/QueryCraft/specs/005-sso-rbac-row-column-security/research.md)
**Data Model**: [data-model.md](file:///home/avril/QueryCraft/specs/005-sso-rbac-row-column-security/data-model.md)
**API Contracts**: [api-contracts.md](file:///home/avril/QueryCraft/specs/005-sso-rbac-row-column-security/contracts/api-contracts.md)

---

## Technical Context

| Item | Value |
|------|-------|
| Backend | FastAPI, Python 3.12, SQLAlchemy 2, Alembic, asyncpg/asyncmy/aioodbc |
| Frontend | React 19, Tailwind v4, Vite, TanStack Query, react-i18next, lucide-react |
| i18n | `frontend/src/locales/{en,ar}.json` — 100% parity at Phase 4 close |
| RTL | `dir="rtl"` on root; logical Tailwind directions |
| Source DBs | PostgreSQL, MySQL, MSSQL (Phase 3) |
| LLM | Gemini (default), provider-agnostic |
| Auth (current) | Single local admin, Argon2id passwords, Redis sessions, HttpOnly cookies |
| Encryption | AES-256-GCM via `app.core.encryption` using `PLATFORM_ENCRYPTION_KEY` |
| SQL parsing | `sqlglot>=26.0.0` (already in deps) |
| Phase 4 closure | FROZEN on `main`. All 20 FRs, 10 SCs complete. |

## Constitution Check

| Principle | Phase 5 Status | Notes |
|-----------|---------------|-------|
| I — Security | ✅ **ACTIVATED** | Column masking + row filters enforce data protection by role |
| II — Query Validation | ✅ Extended | Evaluator gains role-based schema validation |
| III — Validated Knowledge | ✅ Preserved | Accepted queries scoped by user |
| IV — Hostile Input | ⏸️ Deferred | Phase 6 |
| V — LLM-Agnostic | ✅ Preserved | Role-scoped schema is provider-agnostic |
| VI — Language ↔ Dialect | ✅ Preserved | Role enforcement is dialect-agnostic |
| VII — Role Auth | ✅ **ACTIVATED** | SSO for end users, local for admins |
| VIII — Brokered DB Access | ✅ **ACTIVATED** | Row/column security enforced centrally |
| IX — Audit | ✅ **ACTIVATED** | Tamper-evident audit log, 24-month retention |
| X — Quotas | ⏸️ Deferred | Phase 6 (Constitution §11 amended) |
| XI — Modularity | ✅ Preserved | SSO/RBAC/audit as separate modules |
| XII — API Contract | ✅ Extended | New endpoints added to OpenAPI contract |

**§11 Phased Rollout**: Principles VII and IX triggered at Phase 5 ("first multi-user feature"). This plan activates both.

## Locked Decisions

### ADR-16 — SSO Library and Protocol Handling
- **OIDC**: Authlib (`authlib>=1.3.0`) for authorization code flow + ID token validation.
- **SAML**: python3-saml (`python3-saml>=1.16.0`) wrapped in abstraction layer.
- Both behind `SsoProvider` protocol for future swap.
- See [research.md R-001, R-002](file:///home/avril/QueryCraft/specs/005-sso-rbac-row-column-security/research.md).

### ADR-17 — Role Storage and Schema
- Roles stored in `roles` table with JSONB `permissions` (fixed set).
- Per-connection policies in `role_connection_policies` with JSONB `allowed_tables`, `row_filters`, `column_masks`.
- See [data-model.md](file:///home/avril/QueryCraft/specs/005-sso-rbac-row-column-security/data-model.md).

### ADR-18 — Row Filter Enforcement Strategy
- Admin-authored SQL WHERE fragments validated at save time via `sqlglot` AST parsing.
- At query time: `sqlglot` AST injection into generated SQL WHERE clause.
- `{user.email}`, `{user.subject_id}`, `{user.role}` placeholders resolved to parameterized bind values.
- Cross-dialect via `sqlglot.transpile()`.
- See [research.md R-004](file:///home/avril/QueryCraft/specs/005-sso-rbac-row-column-security/research.md).

### ADR-19 — Column Masking Strategy
- Post-query result-set masking at application layer.
- Values replaced with `"***"` before response serialization.
- `masked: true` flag on `ColumnMeta` for frontend indicator.
- See [research.md R-005](file:///home/avril/QueryCraft/specs/005-sso-rbac-row-column-security/research.md).

### ADR-20 — Session and Identity Model
- Redis session extended with `role_id`, `permissions`, `auth_provider`, `subject_id`.
- `user_identities` table links users to SSO subjects.
- Concurrent session limit per user (default 5).
- See [research.md R-007](file:///home/avril/QueryCraft/specs/005-sso-rbac-row-column-security/research.md).

### ADR-21 — Tamper-Evident Audit Log
- Application-layer SHA-256 chained hashing.
- Canonical JSON (sorted keys, no whitespace, ISO 8601 UTC microseconds).
- Genesis entry with `prev_hash="GENESIS"`.
- Single async writer with `SELECT ... FOR UPDATE` serialization.
- See [research.md R-003](file:///home/avril/QueryCraft/specs/005-sso-rbac-row-column-security/research.md).

---

## Security ADRs

### S-001: OIDC Validation Checklist
1. Validate `iss` matches configured issuer URL.
2. Validate `aud` contains configured client ID.
3. Validate signature via JWKS endpoint (key rotation supported).
4. Validate `exp` — reject expired tokens.
5. Validate `nonce` matches value stored in Redis (bound to `state`).
6. Validate `state` matches session-bound value.
7. Replay protection: `nonce` consumed on use (deleted from Redis).
8. Clock skew tolerance: 30 seconds max.

### S-002: SAML Validation Checklist
1. Validate `Issuer` matches configured IdP entity ID.
2. Validate `Audience` restriction matches SP entity ID.
3. Validate XML signature using configured IdP certificate.
4. Validate `NotBefore`/`NotOnOrAfter` timestamps.
5. Replay protection: `InResponseTo` + assertion ID cached in Redis with TTL = validity window. Reject duplicates.
6. Reject assertions without signatures (never disable signature requirement).

### S-003: Secret Storage/Redaction
- SSO client secrets + SAML certificates encrypted at rest with AES-256-GCM via `PLATFORM_ENCRYPTION_KEY`.
- API never returns decrypted secrets. GET responses show `"●●●●●●●●"`.
- Audit log entries never contain secrets, tokens, or certificates.
- Decryption only at SSO flow initiation time, in-memory only.

### S-004: Row Filter Validation/Placeholder Binding
- At save time: `sqlglot.parse()` validates fragment syntax.
- Reject: subqueries, function calls (except `LOWER`/`UPPER`/`TRIM`/`COALESCE`), `UNION`, `JOIN`, DML, comments.
- Validate all referenced columns exist in connection schema. **Reject save if any column is absent** (fail-closed).
- At query time: `{user.*}` placeholders resolved to parameterized bind values (never string interpolation).
- Filter fragments are AND-conjuncted to existing WHERE clause via AST, not string concat.
- At query time (schema drift guard): if a required filter references a column no longer in schema, **block query before execution** with localized `error.policySchemaConflict`. Emit `policy.schema_mismatch` audit event. Never execute without required filter.

### S-005: Cross-Dialect Row Filter + Mask Application
- Filters stored as dialect-agnostic fragments.
- `sqlglot` transpiles identifier quoting per dialect (`"col"` / `` `col` `` / `[col]`).
- Column masking is dialect-agnostic (post-query result replacement).
- If filter references column absent after schema drift: **block query** (fail-closed). Emit audit event. Admin must update role policy or refresh schema.

### S-006: LLM Schema Filtering
- `SchemaContext` filtered by role's `allowed_tables`/`allowed_columns` BEFORE prompt construction.
- Unauthorized tables/columns never enter LLM prompts.
- Evaluator re-validates generated SQL against same filtered schema.

### S-007: Evaluator Authorization Checks
- Before SQL execution, evaluator checks all referenced tables/columns against role policy.
- Block query if any reference is outside allowed set.
- Return localized `error.queryBlockedPolicy` error.
- Masking check: if masked column in SELECT — allow but mask output. If in WHERE — allow (computation uses real values, output masked).

### S-008: Audit Chain Verification + Recovery
- Verification: walk chain from genesis, recompute each hash, report first break.
- On broken chain: report `sequence_number` of first mismatch. Do NOT auto-repair.
- Admin decides recovery action. New entries continue appending (chain restarts from last entry regardless of break).
- Verification result itself is audit-logged.

### S-009: Built-in Admin Lockout Prevention
- Built-in admin user: `is_builtin=true`, undeletable at DB and API level.
- Local password login always available for built-in admin regardless of SSO state.
- Built-in admin role: `is_builtin=true`, undeletable, all permissions, priority=0.
- API returns 403 on attempts to delete/modify built-in role core properties.

### S-010: Session TTL/Concurrency
- Session TTL: 8h idle timeout (existing), configurable via `SESSION_IDLE_TIMEOUT_HOURS`.
- Concurrent sessions per user: max 5 (configurable). Oldest evicted on overflow.
- SSO token refresh: not implemented. Session expires at natural TTL; user re-authenticates via SSO.

---

## Wave Structure

### Wave 17.0 — Foundation: Contracts, Data Model, Auth Architecture

**Branch**: `phase-5/wave-17.0-foundation-contracts`
**Owner**: Backend Implementer (Qwen)
**Depends on**: Phase 4 FROZEN on `main`

**Goal**: Lay data model, migration, permission framework, and audit log foundation. No SSO flows yet.

**Scope**:
- Alembic migration `007_phase5_sso_rbac_security.py`: all new tables + `users` modifications
- ORM models: `SsoProvider`, `Role`, `RoleConnectionPolicy`, `SsoGroupMapping`, `UserIdentity`, `AuditLogEntry`
- Enums: `AuthProvider`, `SsoProtocol`, `AuditActionType`, `Permission`
- Permission middleware: `require_permission(*perms)` FastAPI dependency
- Audit log service: `AuditService.log(action, actor, resource, outcome, context)` with chained hashing
- Audit chain verification: `AuditService.verify_chain() -> VerificationResult`
- Foundation tests: model CRUD, permission checks, audit chain integrity, genesis entry
- Update OpenAPI spec with new types
- Backend gates: pytest, ruff check, ruff format

**FRs**: FR-140, FR-141, FR-142, FR-143, FR-144, FR-145, FR-146 (partial — models + audit)
**SCs**: SC-057, SC-059, SC-060, SC-061

**Evidence**: Gate output, migration runs clean, audit chain test passes.

---

### Wave 17.1 — OIDC/SAML SSO and Admin-Safe Local Login

**Branch**: `phase-5/wave-17.1-sso-auth`
**Owner**: Backend Implementer (Qwen) + Frontend Implementer (Gemini)
**Depends on**: Wave 17.0 merged

**Goal**: Implement OIDC and SAML sign-in flows. Restrict local login to admin. Admin lockout prevention.

**Backend scope**:
- `SsoService`: OIDC flow (Authlib), SAML flow (python3-saml)
- SSO callback handlers with full validation (S-001, S-002)
- Role resolution from SSO group claims via priority ordering
- User identity creation/update on first SSO login
- Local sign-in restriction: reject non-admin users (FR-120)
- SSO provider admin CRUD endpoints (FR-115, FR-116)
- Built-in admin lockout prevention (FR-146, S-009)
- Replay protection: Redis-based nonce/assertion ID cache
- Audit logging: login success/failure, SSO validation events
- TDD: mocked OIDC IdP (httpx respx), mocked SAML assertion validation

**Frontend scope**:
- SSO sign-in page: "Sign in with SSO" button(s) per configured provider
- SSO error handling: redirect-based error codes → localized messages
- Extended `UserProfile` with `permissions`, `role_name`, `auth_provider`
- `useAuth` hook updated for SSO flow
- Admin SSO configuration page (`/admin/sso`): OIDC + SAML provider CRUD
- Secret masking in SSO config forms
- Arabic/RTL translations for all new SSO strings
- TDD: component tests for SSO sign-in page, SSO config page

**FRs**: FR-115, FR-116, FR-117, FR-118, FR-119, FR-120, FR-121, FR-146
**SCs**: SC-046, SC-047, SC-048, SC-056, SC-057

**Evidence**: Mocked OIDC/SAML integration tests pass. Local admin login still works. SSO config admin page renders. Gates pass.

---

### Wave 17.2 — RBAC Roles, Group Mapping, Route/API Gates

**Branch**: `phase-5/wave-17.2-rbac-gates`
**Owner**: Backend Implementer (Qwen) + Frontend Implementer (Gemini)
**Depends on**: Wave 17.1 merged

**Goal**: Role CRUD, group-to-role mapping, permission-gated routes and API endpoints.

**Backend scope**:
- Role CRUD endpoints: create, read, update, delete (FR-122, FR-123, FR-124)
- Group mapping endpoints: create, list, delete (FR-125)
- Permission gate on all endpoints: `require_permission()` dependency
- Multi-group resolution: priority ordering (FR-145)
- User denial for unmapped roles (FR-126)
- Admin route protection (FR-127)
- Audit logging: role changes, mapping changes, access denied events
- TDD: role CRUD, group mapping, permission gates, multi-group resolution

**Frontend scope**:
- Role management page (`/admin/roles`): list, create, edit, delete
- Group mapping UI within role editor
- Permission-based route guards: hide/disable admin nav for non-admin users
- Arabic/RTL translations for role management strings
- TDD: role management page components

**FRs**: FR-122, FR-123, FR-124, FR-125, FR-126, FR-127, FR-145
**SCs**: SC-048, SC-049, SC-056, SC-057, SC-062

**Evidence**: Role CRUD works. Permission gates block unauthorized access. Group mapping resolves correctly. Gates pass.

---

### Wave 17.3 — Row Filters, Column Masks, LLM Schema Filtering, Evaluator Enforcement

**Branch**: `phase-5/wave-17.3-policy-enforcement`
**Owner**: Backend Implementer (Qwen) + Frontend Implementer (Gemini)
**Depends on**: Wave 17.2 merged

**Goal**: Core security enforcement. Role-scoped schema filtering, row filter injection, column masking, evaluator authorization.

**Backend scope**:
- Schema filtering service: filter `SchemaContext` by role policy before LLM prompt (FR-128, FR-129)
- Row filter validation at save time: `sqlglot` AST parsing (S-004)
- Row filter injection at query time: `sqlglot` AST manipulation + `{user.*}` placeholder binding (FR-131)
- Cross-dialect filter transpilation (S-005)
- Column masking service: post-query result replacement (FR-132)
- Evaluator extension: check SQL references against role-allowed schema (FR-130, S-007)
- Role policy test endpoint: dry-run evaluation (FR-136)
- Query history scoping by user (FR-134)
- Accepted-query rerun re-validation (FR-135)
- Audit logging: query validation pass/fail, execution, policy blocks
- TDD: schema filtering, row filter validation, filter injection (3 dialects), column masking, evaluator auth checks, history scoping, rerun validation
- Real PG/MySQL/MSSQL policy enforcement tests where feasible (testcontainers)

**Frontend scope**:
- Masked column indicator in `ResultTable`: localized "column was masked" badge (FR-133)
- Role connection policy editor: table/column selector, row filter input, column mask selector
- Schema browser within role editor (fetches connection schema for selection)
- Arabic/RTL translations for masking indicators and policy editor strings
- TDD: masked column indicator, policy editor components

**FRs**: FR-128, FR-129, FR-130, FR-131, FR-132, FR-133, FR-134, FR-135, FR-136
**SCs**: SC-050, SC-051, SC-052, SC-053, SC-056, SC-057

**Evidence**: Schema filtering excludes unauthorized tables. Row filters enforced per dialect. Column masking works. Evaluator blocks disallowed references. History scoped. Gates pass.

---

### Wave 17.4 — Tamper-Evident Audit Log and Verification UI/API

**Branch**: `phase-5/wave-17.4-audit-verification`
**Owner**: Backend Implementer (Qwen) + Frontend Implementer (Gemini)
**Depends on**: Wave 17.3 merged

**Goal**: Complete audit log coverage. Verification endpoint and admin UI. Ensure all event types are logged.

**Backend scope**:
- Verify all action types emit audit entries: logins, queries, role changes, admin config changes, access denied (FR-140)
- Audit entry immutability: application prevents UPDATE/DELETE (FR-141, SC-060)
- Secret redaction in audit entries (FR-143, SC-061)
- Verification endpoint: `POST /admin/audit/verify` (FR-141)
- Audit status endpoint: `GET /admin/audit/status`
- Chain recovery behavior on broken chain (S-008)
- TDD: comprehensive event type coverage, immutability tests, redaction tests, verification

**Frontend scope**:
- Admin audit page (`/admin/audit`): verification trigger button, status display, last verification result
- Arabic/RTL translations for audit page strings
- TDD: audit page components

**FRs**: FR-140, FR-141, FR-142, FR-143, FR-144
**SCs**: SC-059, SC-060, SC-061, SC-056, SC-057

**Evidence**: All event types logged. Chain verification detects tampering. No secrets in entries. Gates pass.

---

### Wave 17.5 — Arabic/RTL Polish, Browser Smoke, Cross-Dialect Verification, Final Audit

**Branch**: `phase-5/wave-17.5-polish-closeout`
**Owner**: Frontend Implementer (Gemini) + Orchestrator (Opus)
**Depends on**: Wave 17.4 merged

**Goal**: Full i18n parity. RTL smoke. Cross-dialect security. Final audit. Phase closure.

**Scope**:
- i18n key parity audit: `en.json` vs `ar.json` — 100% parity (FR-137, SC-054)
- CSS logical property audit: zero physical directional CSS (FR-138, SC-055)
- Chrome DevTools MCP browser smoke for all new Phase 5 screens in Arabic:
  - SSO sign-in page
  - Admin SSO configuration
  - Role management (list, create, edit)
  - Group mapping
  - Masked column indicator in results
  - Audit verification page
  - Auth error messages (no role, expired session, SSO failure)
- Cross-dialect security verification: submit query as restricted role against PG/MySQL/MSSQL, verify row filters and column masks enforce correctly
- Auth error sanitization: verify no raw IdP errors, UUIDs, hostnames, credentials in UI (FR-139)
- Final frontend gates: test, lint, typecheck, build, lint:css
- Final backend gates: pytest, ruff check, ruff format
- Consolidation report: all FRs (FR-115–FR-146), all SCs (SC-046–SC-062)
- Resolve any Critical/High findings
- Produce closure artifacts:
  - `audit/wave-17/consolidation-report.md`
  - `specs/005-sso-rbac-row-column-security/plans/wave-final-snapshot.md`
  - Append Phase 5 summary to `orchestration-log.md`
  - Move Phase 5 to FROZEN in `AGENTS.md`

**FRs**: FR-137, FR-138, FR-139 + all FRs final verification
**SCs**: SC-054, SC-055, SC-056, SC-057, SC-058 + all SCs final verification

**Evidence**: i18n parity 100%. RTL smoke clean. Cross-dialect enforcement verified. All gates pass. No Critical/High findings.

---

## Test Strategy

### Backend TDD (Qwen)
- Auth: mocked OIDC IdP (httpx respx), mocked SAML assertion builder
- RBAC: role CRUD, group mapping priority resolution, permission gates on all endpoints
- Policy validation: row filter parsing, dangerous expression rejection, placeholder binding
- Evaluator authorization: disallowed table/column blocking
- Audit chain: genesis entry, chain integrity, hash verification, broken chain detection, immutability, secret redaction
- Masking/filtering: column mask application, row filter injection per dialect
- Cross-dialect: real PG/MySQL/MSSQL testcontainers for filter/mask enforcement where feasible
- History scoping: user isolation, rerun re-validation

### Frontend TDD (Gemini)
- SSO sign-in page: provider list, error display, Arabic/RTL
- Admin SSO config: OIDC/SAML forms, secret masking, validation errors
- Role management: CRUD forms, permission selector, group mapping editor
- Policy editor: table/column selector, row filter input, column mask selector
- Masked column indicator: badge rendering, i18n
- Audit page: verification trigger, status display
- Auth guard: permission-based route hiding

### Integration Tests
- Mocked OIDC flow: full authorization code → callback → session creation
- Mocked SAML flow: full AuthnRequest → assertion → session creation
- End-to-end query with role policy: submit → filter → mask → result
- Multi-group resolution: user in 2 groups → highest priority role assigned

### Browser Verification (Chrome DevTools MCP)
- Wave 17.5: all new screens in Arabic/RTL
- Each implementation wave: spot-check new UI components

---

## Foundation Gates

### Frontend (all waves with frontend changes)
```bash
cd frontend && npm run test -- --run
cd frontend && npm run lint
cd frontend && npm run typecheck
cd frontend && npm run build
cd frontend && npm run lint:css
```

### Backend (all waves with backend changes)
```bash
cd backend && uv run pytest -q -m "not integration"
cd backend && uv run ruff check src tests
cd backend && uv run ruff format --check src tests
```

---

## Audit/Merge Gates

- No Critical or High audit findings before phase close (SC-058).
- No secrets, UUIDs, hostnames, raw driver errors, or schema internals in UI or evidence.
- Per-wave merge gates mandatory — no exceptions.
- Full-wave audit at Wave 17.5.

---

## Phase Boundary Rule

Phase 5 becomes FROZEN only after:
1. Final PR merged to `main`.
2. All FRs (FR-115–FR-146) verified.
3. All SCs (SC-046–SC-062) met.
4. Wave final snapshot produced.
5. Orchestration log closed.
6. `AGENTS.md` Phase 5 status updated to FROZEN.

---

## Arabic/RTL/i18n Requirements

All new Phase 5 screens MUST:
1. Have 100% EN/AR key parity in `locales/{en,ar}.json`.
2. Use logical CSS properties only (zero `left`/`right`/`margin-left`/`margin-right`).
3. Render correctly in RTL mode (`dir="rtl"`).
4. Show localized error messages — no English fallback, no raw IdP errors, no UUIDs/hostnames.
5. Pass `lint:css` logical property check.

New screens requiring i18n: SSO sign-in, SSO config admin, role management, group mapping, policy editor, masked column indicator, audit verification page, all new error messages.

---

## Explicitly Out of Scope

Per-user permission overrides, JIT provisioning, multi-tenant, audit log search/export UI (Phase 7), quotas (Phase 6), hostile input detection (Phase 6), admin dashboard expansion (Phase 7), scheduled reports (Phase 8), semantic search (Phase 9), cross-user query sharing, active session revocation on role change.

---

## New Dependencies

### Backend
| Package | Version | Purpose |
|---------|---------|---------|
| `authlib` | `>=1.3.0,<2.0.0` | OIDC client (authorization code flow, token validation) |
| `python3-saml` | `>=1.16.0,<2.0.0` | SAML SP (assertion validation, AuthnRequest) |

### Frontend
No new npm dependencies required. Existing react-i18next, TanStack Query, react-router-dom sufficient.
