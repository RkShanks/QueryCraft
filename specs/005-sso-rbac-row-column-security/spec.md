# Feature Specification: SSO, RBAC, and Row/Column Security

**Feature Branch**: `005-sso-rbac-row-column-security`
**Created**: 2026-05-24
**Status**: Draft
**Input**: Phase 5 charter — Replace provisional single-admin authentication with enterprise SSO (SAML + OIDC), implement role-based access control, enforce row-level filters and column-level masking at query time, and ensure all new surfaces support Arabic/RTL.

## Context

Phases 1–4 are FROZEN. Phase 1 delivered the core text-to-SQL loop with a single provisional admin account. Phase 2 added charts and generative UI. Phase 3 added multi-dialect SQL (PostgreSQL/MySQL/MSSQL), admin connection management, and schema introspection. Phase 4 verified and polished Arabic/RTL translations, cross-language query behavior, and accessibility across all shipped surfaces.

The platform currently operates with a single local admin account. Constitution VII mandates role-appropriate authentication: admins via local accounts, end users via enterprise SSO. Constitution I mandates column masking by role. Constitution VIII mandates centrally brokered database access with row/column security enforcement.

Phase 5 replaces the provisional auth model with production-grade identity and authorization. After Phase 5, the platform supports multiple users with distinct roles, each seeing only the data their role permits.

### Phase 4 Deferred Items (carried forward only if directly supporting Phase 5)

- **SSO / RBAC / multi-user / row-column security**: **[PULLED]** — This is Phase 5's primary scope.
- **Tamper-evident audit log**: **[PULLED]** — Constitution §11 requires Principle IX by Phase 5 ("first multi-user feature"). Full tamper-evident audit log is in Phase 5 scope.
- **Quotas**: Phase 6. Not pulled. Constitution §11 amended to move Principle X trigger to Phase 6 (see Clarifications).
- **Hostile input detection**: Phase 6. Not pulled.
- **Admin dashboard (expanded)**: Phase 7. Not pulled.
- **Scheduled reports / notifications**: Phase 8. Not pulled.
- **Semantic search**: Phase 9. Not pulled.
- **Mobile shell / PWA**: Phase 10+. Not pulled.

## Clarifications

### Session 2026-05-24 (clarify)

- Q1: What is the minimum audit surface for Phase 5 given Constitution §11 triggers Principle IX at "first multi-user feature"? → **A: Pull full tamper-evident audit into Phase 5.** Constitution §11 explicitly requires it. Do not fight the constitution. Phase 5 includes a tamper-evident audit log covering all user actions, query lifecycle events, role changes, logins, and security events. 24-month retention requirement applies. Full audit log search UI deferred to Phase 7 (admin dashboard).
- Q2: Should Phase 5 include quota enforcement given Constitution §11 lists Principle X as triggered at Phase 5? → **A: No quotas in Phase 5. Amend Constitution §11 to move Principle X trigger to Phase 6.** Quotas belong in Phase 6 roadmap. Constitutional amendment required before planning.
- Q3: How should multi-group role resolution work when a user belongs to multiple SSO groups mapped to different roles? → **A: Admin-assigned priority order.** Admin assigns a numeric priority to each role. When a user matches multiple groups, the role with the highest priority (lowest number) wins. Deterministic, explicit, avoids over-permissioning, and supports messy enterprise group structures.

### Session 2026-05-24 (clarify-2)

- Q1: How are row filters expressed, validated, and parameterized? → **A: WHERE fragments validated at save; support `{user.*}` identity placeholders.** Admin authors SQL WHERE clause fragments per role per connection. At save time, the platform validates the fragment against the connection's schema (confirms referenced columns exist, rejects syntactically invalid or dangerous expressions like subqueries, function calls, UNION). Filters support `{user.email}`, `{user.subject_id}`, and `{user.role}` placeholders for dynamic row-level scoping at query time.
- Q2: What tamper-evidence mechanism for the audit log? → **A: Chained hash.** Each audit log entry includes a hash of the previous entry's hash concatenated with the current entry's content. Admin can verify chain integrity on demand. Balances cryptographic tamper-detection with implementation simplicity for a single-tenant deployment.
- Q3: What are the platform permissions that roles can grant? → **A: Fixed set.** `query.submit`, `query.history.view`, `admin.connections.manage`, `admin.roles.manage`, `admin.sso.manage`, `admin.audit.verify`. End-user roles get `query.*` permissions. Admin roles get all permissions. No free-text or extensible permission registry in Phase 5.
- Q4: What prevents admin lockout if SSO is misconfigured or all roles are deleted? → **A: Built-in admin account is undeletable; local admin login always works regardless of SSO/role configuration state.** The provisioned admin from Phase 1 is a safety net that cannot be removed or locked out by SSO/role changes.

## User Scenarios & Testing *(mandatory)*

### User Story 26 — SSO Sign-In via OIDC (Priority: P0)

As an end user, I can sign in to the platform using my organization's OIDC identity provider, and I am granted access based on my SSO group membership mapped to a platform role.

**Why this priority**: SSO is the foundation of multi-user access. Without it, no end user can authenticate.

**Independent Test**: Configure a test OIDC provider. Attempt sign-in as a user whose SSO groups map to a valid role. Verify successful login, session creation, and correct role assignment. Then attempt sign-in as a user with no mapped groups and verify access is denied with a localized error.

**Acceptance Scenarios**:

1. **Given** an OIDC provider is configured, **When** an end user clicks "Sign in with SSO", **Then** they are redirected to the IdP login page.
2. **Given** the IdP authenticates the user and returns an ID token, **When** the callback is processed, **Then** the platform validates issuer, audience, signature, expiry, nonce, and state parameters.
3. **Given** the ID token contains group claims, **When** the platform processes them, **Then** the user is assigned the platform role mapped to their SSO group.
4. **Given** the user has a valid role, **When** the session is created, **Then** the user lands on the workspace with role-appropriate access.
5. **Given** the user's SSO groups do not map to any platform role, **When** the callback is processed, **Then** the user sees a localized "no access" error and is not granted a session.

---

### User Story 27 — SSO Sign-In via SAML (Priority: P0)

As an end user, I can sign in using my organization's SAML identity provider with the same role-mapping behavior as OIDC.

**Why this priority**: Many enterprises use SAML exclusively. Supporting both protocols ensures broad compatibility.

**Independent Test**: Configure a test SAML IdP. Attempt sign-in. Verify assertion validation (issuer, audience, signature, expiry, replay protection). Verify role mapping from SAML attributes.

**Acceptance Scenarios**:

1. **Given** a SAML IdP is configured, **When** an end user initiates SSO sign-in, **Then** they are redirected to the SAML IdP login page.
2. **Given** the IdP returns a SAML assertion, **When** the callback is processed, **Then** the platform validates issuer, audience, signature, timestamps, and checks for assertion replay.
3. **Given** the assertion contains group attributes, **When** the platform processes them, **Then** the user is assigned the correct platform role.
4. **Given** the SAML assertion is expired, replayed, or has an invalid signature, **When** the callback processes it, **Then** the sign-in is rejected with a localized, sanitized error.

---

### User Story 28 — Admin Manages Roles (Priority: P0)

As an admin, I can create, edit, and delete roles that define what data and platform capabilities each user group has access to.

**Why this priority**: Roles are the central authorization primitive. Without role management, no access control is possible.

**Independent Test**: As admin, create a role with specific table/column permissions and row filters. Edit the role. Delete the role. Verify all CRUD operations persist and reflect in the role list.

**Acceptance Scenarios**:

1. **Given** the admin navigates to role management, **When** the page loads, **Then** all existing roles are listed with their name, description, and mapped SSO groups.
2. **Given** the admin clicks "Create Role", **When** they fill in role name, description, platform permissions, allowed tables/columns, row filter rules, column masking rules, and mapped SSO groups, **Then** the role is saved and appears in the list.
3. **Given** the admin edits an existing role, **When** they change permissions or filters, **Then** the changes take effect for all users mapped to that role on their next query (no active session revocation required).
4. **Given** the admin deletes a role, **When** users mapped to that role next authenticate, **Then** they are treated as unmapped (no access) until reassigned.
5. **Given** the admin configures a role, **When** they view the role detail, **Then** no raw database credentials, connection strings, or internal identifiers are visible.

---

### User Story 29 — Admin Configures SSO Provider (Priority: P0)

As an admin, I can configure OIDC and SAML identity provider settings through the admin UI without exposing secrets.

**Why this priority**: SSO configuration is required before any end user can authenticate.

**Independent Test**: As admin, configure an OIDC provider (issuer URL, client ID, client secret). Verify client secret is masked after save. Configure a SAML IdP (metadata URL or XML upload, certificate). Verify certificate content is masked.

**Acceptance Scenarios**:

1. **Given** the admin navigates to SSO configuration, **When** they configure an OIDC provider, **Then** they can enter issuer URL, client ID, and client secret.
2. **Given** the admin saves OIDC configuration, **When** they return to the settings page, **Then** the client secret is masked (never displayed in plaintext).
3. **Given** the admin configures a SAML IdP, **When** they upload or paste IdP metadata/certificate, **Then** the certificate content is stored securely and masked in the UI.
4. **Given** SSO configuration contains errors (invalid issuer, unreachable metadata URL), **When** the admin saves, **Then** a localized validation error is shown without exposing raw HTTP errors or stack traces.

---

### User Story 30 — Admin Maps SSO Groups to Roles (Priority: P0)

As an admin, I can map SSO group claims to platform roles so that user access is determined by their organizational group membership.

**Why this priority**: Group-to-role mapping is the bridge between enterprise identity and platform authorization.

**Independent Test**: As admin, map SSO group "analysts" to role "read-only-finance". Sign in as a user in that group. Verify the user has the expected role permissions.

**Acceptance Scenarios**:

1. **Given** the admin opens group mapping, **When** they map an SSO group claim value to a platform role, **Then** the mapping is saved.
2. **Given** multiple SSO groups map to different roles, **When** a user belongs to multiple groups, **Then** the platform assigns the role with the highest admin-configured priority (lowest priority number wins). The resolution is deterministic and explicitly controlled by the admin.
3. **Given** an SSO group is unmapped, **When** a user belonging only to that group signs in, **Then** they are denied access with a localized error.

---

### User Story 31 — Role-Scoped Query Generation and Execution (Priority: P0)

As an end user with a specific role, when I ask a question, the system only shows me schema I'm allowed to see, generates SQL only against allowed tables/columns, and applies row filters and column masking before I see results.

**Why this priority**: This is the core security enforcement. Without it, RBAC is cosmetic.

**Independent Test**: Create two roles with different table/column access. Sign in as each role. Ask the same question. Verify each user sees only their permitted data, masked columns show indicators, and attempts to query disallowed tables are blocked.

**Acceptance Scenarios**:

1. **Given** a role allows access to tables A and B but not C, **When** the LLM receives the schema for prompt generation, **Then** only tables A and B (and their allowed columns) are included in the schema context.
2. **Given** a role has column masking on `salary`, **When** a query returns results including `salary`, **Then** the salary values are masked and a localized "column was masked" indicator appears in the result table.
3. **Given** a role has a row filter `department = 'Sales'`, **When** a query executes, **Then** only rows matching the filter are returned, regardless of what the SQL requests.
4. **Given** the evaluator receives SQL referencing a disallowed table, **When** validation runs, **Then** the query is blocked before execution with a localized error.
5. **Given** the evaluator receives SQL referencing a masked column in a WHERE clause, **When** validation runs, **Then** the query is allowed but the column values in results are masked.
6. **Given** row filters and column masks are configured, **When** queries execute against PostgreSQL, MySQL, and MSSQL source databases, **Then** enforcement works identically across all three dialects.

---

### User Story 32 — Role-Scoped Query History (Priority: P1)

As an end user, I can only see my own query history. Accepted queries from other users are not visible unless role policy permits cross-user visibility.

**Why this priority**: History leaking across users violates data isolation.

**Independent Test**: Two users with different roles each submit and accept queries. Verify each user sees only their own history. Verify rerunning an accepted query re-validates against current role policy.

**Acceptance Scenarios**:

1. **Given** user A accepts a query, **When** user B views their history, **Then** user A's query does not appear.
2. **Given** user A accepted a query when they had broad access, **When** their role is later restricted, **Then** rerunning the accepted query re-validates against the current role and blocks if no longer permitted.
3. **Given** a user views their history, **When** entries render, **Then** no other user's data, IDs, or metadata is visible.

---

### User Story 33 — Arabic/RTL Support for All New Surfaces (Priority: P1)

As a platform user with Arabic selected, all new Phase 5 surfaces (SSO sign-in, role management, SSO configuration, group mapping, masked column indicators) are fully localized and RTL-correct.

**Why this priority**: Phase 4 established 100% i18n parity. Phase 5 must not regress.

**Independent Test**: Switch to Arabic. Navigate all new Phase 5 screens. Verify zero English fallback, correct RTL layout, logical CSS properties only.

**Acceptance Scenarios**:

1. **Given** the language is Arabic, **When** the SSO sign-in page renders, **Then** all labels and error messages are in Arabic with RTL layout.
2. **Given** the language is Arabic, **When** the role management page renders, **Then** all CRUD labels, field names, validation messages, and table headers are in Arabic.
3. **Given** the language is Arabic, **When** masked column indicators appear in results, **Then** the indicator text is in Arabic.
4. **Given** the language is Arabic, **When** any auth error renders (no role, expired session, SSO failure), **Then** the error message is in Arabic and does not expose internal details.

---

### Edge Cases

- What happens when the SSO provider is temporarily unreachable? The sign-in page shows a localized "identity provider unavailable" error. No internal URLs or timeouts are exposed.
- What happens when a user's role is deleted while they have an active session? The session remains valid until expiry or next login. On next authentication, they are treated as unmapped (no access).
- What happens when row filters reference columns that don't exist in a particular source database? The filter is skipped for that database with a warning logged internally. No error is shown to the user; queries proceed without that filter.
- What happens when an admin tries to delete a role that has active users? Deletion succeeds. Active sessions are not terminated. Users are denied on next authentication.
- What happens when the OIDC token refresh fails silently? The session expires at its natural TTL. The user is redirected to re-authenticate.
- What happens when column masking is configured but the column is used in GROUP BY? The query executes; grouped results show masked values. The masking is applied to output display, not to SQL computation.
- What happens when a user belongs to zero SSO groups? They are treated as unmapped and denied access.
- What happens when the same SSO group is mapped to multiple roles? Configuration error. The admin UI prevents saving duplicate group mappings.
- What happens when local login is attempted by a non-admin? Login is rejected with a localized error. No indication of whether the account exists.
- What happens when an admin saves a row filter with invalid SQL or references a nonexistent column? The save is rejected with a localized validation error. The filter is not persisted. The admin must correct the fragment before saving.
- What happens when the admin misconfigures SSO and locks out all SSO users? The built-in admin account always retains local login. The admin can fix SSO configuration via local login. No admin lockout is possible through SSO/role misconfiguration.

## Requirements *(mandatory)*

### Functional Requirements

#### SSO Authentication

- **FR-115**: Admin can configure OIDC provider settings (issuer URL, client ID, client secret, scopes, redirect URI) through the admin UI. Client secret is masked after initial save and never re-displayed in plaintext.
- **FR-116**: Admin can configure SAML IdP settings (metadata URL or XML upload, entity ID, certificate) through the admin UI. Certificate content is stored securely and masked in the UI.
- **FR-117**: End user can sign in via OIDC. The platform redirects to the IdP, processes the callback, validates the ID token (issuer, audience, signature, expiry, nonce/state), and creates a session.
- **FR-118**: End user can sign in via SAML. The platform redirects to the IdP, processes the callback, validates the SAML assertion (issuer, audience, signature, timestamps, replay protection), and creates a session.
- **FR-119**: SSO callback validates all security parameters. Invalid or expired tokens/assertions are rejected with a localized, sanitized error. No raw IdP errors, URLs, or cryptographic details are exposed to the user.
- **FR-120**: Local password login is restricted to admin accounts only. Non-admin local login attempts are rejected with a generic localized error that does not reveal whether the account exists.
- **FR-121**: SSO sign-in page displays configured provider(s) with localized labels. If no provider is configured, end users see a localized "SSO not configured" message.

#### Role Management

- **FR-122**: Admin can create roles with: name, description, priority, platform permissions (from fixed set: `query.submit`, `query.history.view`, `admin.connections.manage`, `admin.roles.manage`, `admin.sso.manage`, `admin.audit.verify`), allowed source database tables/columns per connection, optional row filter rules per connection, and optional column masking rules per connection.
- **FR-123**: Admin can edit existing roles. Changes take effect for affected users on their next query execution (no active session revocation required for role policy changes).
- **FR-124**: Admin can delete roles. Users mapped to the deleted role are treated as unmapped on their next authentication.
- **FR-125**: Admin can map SSO group claim values to platform roles. Each SSO group maps to exactly one role. Duplicate group mappings are prevented by validation.
- **FR-126**: Users with no mapped role are denied access to the application and all query APIs. The denial message is localized and does not expose internal role or group details.

#### Authorization Enforcement

- **FR-127**: Role permissions gate UI routes and API endpoints. Each API endpoint and UI route requires one or more permissions from the fixed set (`query.submit`, `query.history.view`, `admin.connections.manage`, `admin.roles.manage`, `admin.sso.manage`, `admin.audit.verify`). Non-admin users cannot access admin routes or endpoints. Unauthorized API calls return a sanitized error.
- **FR-128**: Schema introspection shown to the LLM prompt and to the user is filtered by the user's role. Only tables and columns the role permits are included.
- **FR-129**: Query generation prompt sent to the LLM includes only role-allowed schema and columns. The LLM never receives unauthorized schema information.
- **FR-130**: The evaluator blocks SQL that references tables or columns not in the user's role-allowed set. Blocked queries return a localized error before execution.
- **FR-131**: Query execution applies row filters defined in the user's role. Row filters are SQL WHERE clause fragments authored by the admin, validated at save time against the connection's schema, and appended to generated SQL at query time. Filters support `{user.email}`, `{user.subject_id}`, and `{user.role}` identity placeholders that are resolved to the authenticated user's values at execution. Row filters are enforced at the database query level for PostgreSQL, MySQL, and MSSQL source databases. Dangerous expressions (subqueries, function calls, UNION) are rejected at save time.
- **FR-132**: Query execution masks configured sensitive columns in the result set before data reaches the user. Masking works for all three supported database dialects.
- **FR-133**: Result table displays a localized "column was masked" indicator on any column where masking was applied. The indicator is visible in both English and Arabic.
- **FR-134**: Query history is scoped by user. Each user sees only their own accepted queries. No cross-user history leakage.
- **FR-135**: Accepted-query rerun re-validates the query against the user's current role policy. If the role has been restricted since the query was originally accepted, the rerun is blocked with a localized error.

#### Admin Testing

- **FR-136**: Admin can test a role's policy against a sample natural-language question before saving the role. The test shows which tables/columns would be accessible, which filters would apply, and whether the sample query would be blocked or allowed.

#### Internationalization

- **FR-137**: All new Phase 5 user-visible surfaces (SSO sign-in, role management, SSO configuration, group mapping, masked column indicators, auth error messages) have complete English and Arabic translations with 100% key parity.
- **FR-138**: All new Phase 5 screens use RTL layout when the language is Arabic. All CSS uses logical properties only; zero physical directional properties.
- **FR-139**: Auth and session error messages (SSO failure, no role, expired session, unauthorized access) are localized and sanitized. No raw IdP errors, UUIDs, hostnames, or credentials are exposed.

#### Tamper-Evident Audit Log

- **FR-140**: Every security-relevant action is written to a tamper-evident audit log: user logins (success and failure), SSO validation events, role assignments, role changes, query submissions, query validation outcomes, query executions, accepted/rejected decisions, admin configuration changes (SSO providers, roles, group mappings, connections), and unauthorized access attempts.
- **FR-141**: Audit log entries are tamper-evident via chained hashing. Each entry stores a hash computed from the previous entry's hash concatenated with the current entry's content. The chain starts from a known genesis hash. Once written, entries cannot be modified or deleted through the application. Admin can trigger an integrity verification that walks the chain and reports any breaks.
- **FR-142**: Audit log entries are retained for a minimum of 24 months, consistent with Constitution IX.
- **FR-143**: Audit log entries do not contain secrets, credentials, full tokens, or raw database passwords. Sensitive fields are redacted or omitted.
- **FR-144**: Audit log is accessible to admin users only. No end user can view, search, or export audit entries. Full audit log search UI is deferred to Phase 7 (admin dashboard); Phase 5 provides the storage and write path only.

#### Role Priority

- **FR-145**: Each role has an admin-configurable priority (numeric, lower number = higher priority). When a user's SSO groups map to multiple roles, the role with the lowest priority number is assigned. Admin can reorder priorities at any time.
- **FR-146**: The built-in admin account (provisioned in Phase 1) is undeletable and always retains local password login capability. SSO configuration changes, role deletions, and group mapping changes cannot lock out the built-in admin. This is the platform's safety net against misconfiguration.

### Key Entities

- **SSO Provider Configuration**: Stores OIDC or SAML provider settings (issuer, client ID, encrypted client secret, metadata, certificates). One active provider per protocol.
- **Role**: Name, description, priority (numeric), platform permissions (subset of fixed set: `query.submit`, `query.history.view`, `admin.connections.manage`, `admin.roles.manage`, `admin.sso.manage`, `admin.audit.verify`), per-connection table/column allow-lists, per-connection row filter rules, per-connection column masking rules.
- **SSO Group Mapping**: Maps an SSO group claim value to exactly one platform role.
- **User Identity**: Represents an authenticated user. Links to SSO provider, SSO subject ID, mapped role, session metadata. Admin users retain local identity.
- **Audit Log Entry**: Tamper-evident record of a platform action. Includes timestamp, actor identity, action type, affected resource, outcome, sanitized context, and chained hash (hash of previous entry hash + current content). No secrets stored.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-046**: OIDC login flow completes successfully in an automated integration test with a mocked IdP, including token validation and role assignment.
- **SC-047**: SAML login flow completes successfully in an automated integration test with a mocked IdP, including assertion validation and role assignment.
- **SC-048**: A user whose SSO groups do not map to any platform role is denied access to the application and all query APIs. Verified by automated test.
- **SC-049**: A non-admin user cannot access any admin endpoint or admin UI route. Verified by automated test covering all admin endpoints.
- **SC-050**: A query referencing a disallowed table or column is blocked before execution. Verified by automated test for each of the three database dialects.
- **SC-051**: Row filters are enforced at query time for PostgreSQL, MySQL, and MSSQL source databases. Verified by automated test showing filtered results differ from unfiltered results.
- **SC-052**: Column masking is enforced at query time for PostgreSQL, MySQL, and MSSQL source databases. Verified by automated test showing masked values in results and the presence of a masking indicator.
- **SC-053**: Query history shows only the authenticated user's queries. Accepted-query rerun re-validates against current role policy. Verified by automated test.
- **SC-054**: English/Arabic i18n key parity is 100% for all Phase 5 surfaces. No missing keys in either language.
- **SC-055**: RTL smoke passes for all new Phase 5 screens in Chrome DevTools MCP verification. Zero physical directional CSS.
- **SC-056**: Frontend foundation gates pass: tests, lint, typecheck, build, CSS logical-property lint.
- **SC-057**: Backend foundation gates pass: pytest, ruff check, ruff format.
- **SC-058**: No Critical or High audit findings remain before Phase 5 closure.
- **SC-059**: Tamper-evident audit log records all specified event types (logins, queries, role changes, admin actions). Verified by automated test.
- **SC-060**: Audit log entries cannot be modified or deleted through the application. Verified by automated test attempting mutation.
- **SC-061**: Audit log entries contain no secrets, credentials, or full tokens. Verified by automated test inspecting entry content.
- **SC-062**: Multi-group role resolution uses admin-configured priority order. Verified by automated test with a user in multiple groups.

## Assumptions

- Phases 1–4 are FROZEN. Phase 5 builds on frozen behavior without rewriting prior functionality.
- The provisional single admin account from Phase 1 remains functional for admin access. Phase 5 adds SSO for end users alongside existing admin auth.
- The platform is single-tenant. Multi-tenant support is deferred to Phase 10+.
- One OIDC provider and one SAML provider can be configured at a time. Multiple simultaneous providers of the same protocol type are not required for v1.
- SSO group claims are available in standard OIDC ID tokens (via `groups` or configurable claim name) and SAML assertions (via configurable attribute).
- Row filters are expressed as SQL WHERE clause fragments that the admin authors per role per connection. At save time, the platform validates the fragment against the connection's schema (column existence, syntax, no dangerous expressions). Filters support `{user.email}`, `{user.subject_id}`, and `{user.role}` identity placeholders resolved at query time.
- Column masking replaces sensitive column values in the result set with a placeholder (e.g., `***`) before sending to the frontend. The masking is applied post-query, not via database-level masking features.
- Session management uses the existing session infrastructure from Phase 1, extended with SSO-specific claims (role, provider, subject ID).
- Role policy changes are eventually consistent: they apply on next query, not retroactively to in-flight queries.
- The "test role policy" feature (FR-136) performs a dry-run evaluation without executing a query against the database. It validates schema access and filter applicability only.
- Browser-visible verification with Chrome DevTools MCP is required during implementation waves, consistent with Phase 3/4 practice.
- TDD is mandatory for all implementation, consistent with project protocol.

## Explicitly Out of Scope

- **Per-user permission overrides**: Forbidden by Constitution. All permissions flow through roles.
- **JIT role provisioning workflows**: Not in Phase 5 scope.
- **Multi-tenant support**: Phase 10+.
- **Audit log search and export UI**: Phase 7. Phase 5 delivers the audit log storage and write path; the search/export UI is part of the admin dashboard.
- **Token/query/cost quotas**: Phase 6. Constitution §11 amended to move Principle X trigger to Phase 6.
- **Hostile input detection and auto-suspension**: Phase 6.
- **Expanded admin dashboard with metrics and user management**: Phase 7.
- **Scheduled reports and notifications**: Phase 8.
- **Semantic search of accepted queries**: Phase 9.
- **Cross-user query visibility** (sharing accepted queries across users with compatible roles): Future enhancement, not Phase 5.
- **Active session revocation on role change**: Role changes are eventually consistent (next query). Real-time session invalidation is a future enhancement.

## Architectural Decision Records

Phase 5 will require new ADRs during planning. Anticipated ADR topics (to be formalized in `/speckit.plan`):

- **ADR-16 — SSO Library and Protocol Handling**: OIDC and SAML library selection, token/assertion validation approach.
- **ADR-17 — Role Storage and Schema**: How roles, permissions, row filters, and column masks are persisted.
- **ADR-18 — Row Filter Enforcement Strategy**: How row filters are appended to generated SQL across dialects.
- **ADR-19 — Column Masking Strategy**: Post-query result masking vs. database-level masking.
- **ADR-20 — Session and Identity Model**: How SSO identities, roles, and sessions relate to the existing auth model.

## Constitution Mapping

| Principle | Phase 5 Status |
|-----------|---------------|
| I — Security and Data Protection | **ACTIVATED** — column masking and row filters enforce data protection by role |
| II — Query Validation Before Execution | Preserved; evaluator extended with role-based schema validation |
| III — Only Validated Knowledge Persists | Preserved; accepted queries scoped by user |
| IV — Hostile Input | Deferred to Phase 6 |
| V — LLM-Agnostic Platform | Preserved; role-scoped schema is provider-agnostic |
| VI — Language Decoupled from SQL Dialect | Preserved; role enforcement is dialect-agnostic |
| VII — Role-Appropriate Authentication | **ACTIVATED** — SSO for end users, local for admins |
| VIII — Centrally Brokered Database Access | **ACTIVATED** — row/column security enforced centrally |
| IX — Observability and Auditability | **ACTIVATED** — tamper-evident audit log with 24-month retention. Search UI deferred to Phase 7 |
| X — Quotas | Deferred to Phase 6 (Constitution §11 amended to move trigger to Phase 6) |
| XI — Architectural Modularity | Preserved |
| XII — API Contract as Source of Truth | Preserved; new endpoints added to OpenAPI contract |
