# Feature Specification: Multi-Dialect SQL and Multiple Source Databases

**Feature Branch**: `003-multi-dialect-source-dbs`
**Created**: 2026-05-18
**Status**: Draft
**Input**: Phase 3 charter — admins can connect more than one source database (PostgreSQL, MySQL, MS SQL Server). Each query targets a chosen database; generated SQL dialect must match the selected connection. Admin connection management UI, schema introspection per connection, dialect-aware SQL generation, user database selector, and frontend polish.

## Context

Phase 2 (FROZEN, PR #67) shipped: premium dark-mode conversational UI, Constitution VI (Arabic + RTL), real-LLM contract testing (respx), and lifecycle invariant framework. FRs FR-031–FR-058 and SCs SC-014–SC-024 are complete. The platform currently supports a single PostgreSQL source database, hardcoded during deployment. Phase 3 expands this to admin-managed multi-database connections with dialect-aware SQL generation, directly fulfilling the Phase 3 scope in `docs/Implementation_Plan.md` and progressing Constitution VI (dialect awareness), VIII (centrally brokered DB access), and XI (architectural modularity).

### Phase 2 Deferred Items (carried forward only if directly supporting Phase 3)

The following items were deferred from Phase 2. Only items marked **[PULLED]** are included in Phase 3 scope; all others remain deferred:

- **Constitution IV (Hostile Input)**: Deferred → Phase 6. Not pulled.
- **Constitution VII (Per-Database Auth / SSO / RBAC)**: Deferred → Phase 5. Not pulled. Phase 3 retains the single provisional admin.
- **Constitution IX (Tamper-evident Audit Log)**: Deferred → Phase 5. Not pulled.
- **Constitution X (Quotas)**: Deferred → Phase 5. Not pulled.
- **Saved Queries Library page**: Deferred → Phase 3+. Not pulled (not directly supporting multi-database).
- **Session rename UX**: Deferred → Phase 3+. Not pulled.
- **Full mobile shell**: Deferred → Phase 4+. Not pulled.
- **T-375 (weekly real Gemini API contract run)**: Deferred. Not pulled.

## Clarifications

### Session 2026-05-18 (specify)

- Q1: Should Phase 3 use Fernet-based encryption with an environment variable key, or integrate with an external secrets manager? → A: Implement Fernet encryption now via `cryptography` library with `DB_CREDENTIAL_KEY` from env var, behind a small credential-encryption/provider abstraction so Phase 5+ can swap to an external secrets manager without rewriting connection services. Never expose plaintext credentials after save. If credentials exist and the key is missing/invalid, fail startup or block credential use with a typed configuration error. Key rotation is deferred but should be documented.
- Q2: Confirm async driver choices for MySQL and MS SQL Server. → A: Use `asyncmy` for MySQL and `aioodbc` for MS SQL Server. Document MSSQL system dependencies (`unixODBC` + FreeTDS/ODBC driver) in setup/Docker/CI planning. Use parameterized queries only. If real MySQL/MSSQL services are not available in CI, unit-test dialect/introspection behavior with adapters/fakes and keep real-service integration tests optional/manual.

### Session 2026-05-18 (clarify)

- Q1: What lifecycle states should a connection have, and what is the delete behavior? → A: Three lifecycle states: **active**, **disabled**, **hard-delete**. Hard-delete is allowed only when the connection has no referenced query attempts, sessions, or schema-cache rows; if referenced, hard-delete is blocked with a typed localized error and the admin must disable instead. Disabled connections are hidden from the user DB selector and cannot be queried, but remain visible to admins and preserve historical metadata. Health status (`untested`, `healthy`, `unhealthy`) is a separate dimension from lifecycle state, not another lifecycle state.
- Q2: How should legacy Phase 1/2 historical query attempts (which have no `connection_id`) be handled? → A: Migrate the existing Phase 1/2 hardcoded PostgreSQL connection as the first `source_database_connections` row during the database migration. Backfill all existing query attempt/history rows with that connection's ID, then enforce `connection_id` as NOT NULL going forward. Historical UI shows the migrated legacy connection name and dialect, not "Unknown". Migration tests MUST prove existing rows are backfilled and new attempts require a connection.
- Q3: What should the evaluator do when dialect-specific parsing fails or confidence is low? → A: Reject the attempt and enter the existing reject/retry regeneration path (FR-017/FR-019) with an explicit dialect correction hint and the selected connection's dialect/schema context. Never execute SQL that failed dialect validation. After the configured retry limit is exhausted, surface a localized assistant refusal/error card rather than executing.
- Q4: When should schema introspection run relative to saving a new connection? → A: Auto-introspect on first successful save: run a health check first, and if it passes, automatically run initial schema introspection so the connection is immediately usable. If health check or introspection fails, keep the connection saved but mark status accordingly with a localized admin error and retry action. After initial introspection, schema refresh is explicit/manual only. Track `schema_last_refreshed_at` and stale/error status for UI display.
- Q5: Does the database selection persist globally or per-session? → A: Per-session only. Store `connection_id` on the session record. Each new session starts with no selected connection and must prompt the user to choose before the first query. Exception: when exactly one active connection exists, auto-select it. Switching databases mid-session affects only subsequent queries; prior turns keep their original connection metadata. No global user default in Phase 3.

## User Scenarios & Testing *(mandatory)*

### User Story 14 — Admin Manages Source Database Connections (Priority: P1)

As the platform administrator, I can add, edit, test, and remove source database connections through a dedicated management interface, so the platform can query more than one database.

**Why this priority**: Multi-database support is the core Phase 3 deliverable. Every other feature (schema introspection, dialect routing, database selector) depends on connection records existing in the system.

**Independent Test**: Sign in as admin, navigate to the database connections management page, add a PostgreSQL connection, add a MySQL connection, add an MS SQL Server connection. Verify each connection appears in the list with its type, name, and health status. Edit one connection's display name. Remove one connection. Verify the list updates correctly throughout.

**Acceptance Scenarios**:

1. **Given** the admin navigates to the database connections page, **When** the page loads, **Then** a list of all configured source database connections is displayed, showing for each: display name, database type (PostgreSQL / MySQL / MS SQL Server), host, database name, and connection health indicator.

2. **Given** the admin clicks "Add Connection", **When** the connection form appears, **Then** the form includes fields for: display name, database type selector, host, port (pre-filled with dialect default), database name, username, and password. All fields have localized labels and validation messages (English and Arabic).

3. **Given** the admin fills in valid connection details and clicks "Save", **When** the system processes the request, **Then** the connection is saved, the password is never stored in plaintext (encrypted at rest or stored via server-side secret management), and the new connection appears in the list.

4. **Given** the admin edits an existing connection, **When** the edit form opens, **Then** all fields are pre-filled except the password field, which shows a placeholder indicating the existing credential is retained unless a new value is entered.

5. **Given** the admin clicks "Remove" on an unreferenced connection, **When** a confirmation prompt is acknowledged, **Then** the connection and its cached schema metadata are permanently deleted.

6. **Given** the admin clicks "Remove" on a connection that has referenced query attempts or sessions, **When** the system checks referential integrity, **Then** hard-delete is blocked with a typed localized error message instructing the admin to disable the connection instead.

7. **Given** the admin clicks "Disable" on an active connection, **When** the action completes, **Then** the connection is hidden from the user database selector, cannot be queried, but remains visible in the admin connection list with a "disabled" indicator. Historical query results referencing this connection continue to display the connection name.

8. **Given** the admin clicks "Enable" on a disabled connection, **When** the action completes, **Then** the connection returns to active state and reappears in the user database selector.

---

### User Story 15 — Admin Validates Connection Health and Schema Introspection (Priority: P1)

As the platform administrator, I can test a database connection's health and trigger schema introspection, so I can verify connectivity and ensure the LLM has up-to-date schema context for SQL generation.

**Why this priority**: Schema introspection feeds the LLM prompt builder. Without accurate, per-connection schema data, dialect-aware SQL generation cannot produce valid queries.

**Independent Test**: Add a new database connection, click "Test Connection", verify a health check result (success or failure with error details). Click "Refresh Schema", verify schema metadata (tables, columns, types) is fetched and stored. View the introspected schema summary for the connection.

**Acceptance Scenarios**:

1. **Given** a configured connection, **When** the admin clicks "Test Connection", **Then** the system attempts a lightweight connectivity check (e.g., `SELECT 1` or dialect equivalent) and displays the result: success with latency, or failure with a localized error message describing the issue (network unreachable, authentication failed, database not found, etc.).

2. **Given** a connection that passes the health check, **When** the admin clicks "Refresh Schema", **Then** the system introspects the database's schema (tables, columns, column data types, primary keys, foreign key relationships) and stores the metadata associated with that connection.

3. **Given** schema introspection completes, **When** the admin views the connection detail, **Then** a summary of discovered tables and column count per table is displayed.

4. **Given** schema introspection fails (e.g., insufficient permissions), **When** the system processes the error, **Then** a localized error message is displayed to the admin with enough detail to diagnose the issue, and the connection's schema status is marked as "introspection failed" rather than silently using stale data.

5. **Given** schema metadata already exists for a connection, **When** the admin triggers "Refresh Schema" again, **Then** the previous metadata is replaced with the freshly introspected data. The system does not merge old and new schemas.

6. **Given** the admin saves a brand-new connection, **When** the save succeeds, **Then** the system automatically runs a health check followed by schema introspection. If both succeed, the connection is immediately usable in the database selector. If either fails, the connection is saved with appropriate health/schema error status and the admin sees a localized error with a retry action.

---

### User Story 16 — User Selects a Target Database Before Asking a Question (Priority: P1)

As a platform user, I can select which connected database my question targets before submitting it, so my query is generated in the correct SQL dialect and run against the right data source.

**Why this priority**: The database selector is the user-facing entry point for the entire multi-database feature. Without it, users have no way to direct queries to a specific connection.

**Independent Test**: With 2+ database connections configured, open a new chat session. Verify the database selector shows all available connections with their display names and database types. Select a MySQL connection, ask a question, verify the generated SQL uses MySQL dialect. Switch to a PostgreSQL connection in the same session, ask a question, verify PostgreSQL dialect is used.

**Acceptance Scenarios**:

1. **Given** the user opens a new chat session with multiple active connections, **When** the workspace loads, **Then** a database selector is visible near the prompt input area prompting the user to select a connection. The prompt input MUST be disabled until a connection is selected. No global default is carried from other sessions.

2. **Given** exactly one active connection exists, **When** the user opens a new chat session, **Then** that connection is auto-selected in the database selector and the prompt input is immediately enabled.

3. **Given** multiple database connections are configured, **When** the user opens the database selector, **Then** all **active** connections (not disabled) with a healthy status and successfully introspected schema are listed, each showing display name and database type icon/badge. Disabled connections are excluded.

4. **Given** the user selects a database connection, **When** they submit a question, **Then** the system uses the selected connection's schema for LLM context and generates SQL in the matching dialect. The selected `connection_id` is stored on the session record.

5. **Given** no database connections are configured or all are unhealthy, **When** the user attempts to ask a question, **Then** the system displays a localized message explaining that no database is available and suggesting the user contact an administrator.

6. **Given** a connection becomes unhealthy after the user selected it, **When** the user submits a question, **Then** the system detects the connection failure before or during query execution and displays a localized error message rather than crashing or returning garbled results.

---

### User Story 17 — Dialect-Specific SQL Generation and Result Attribution (Priority: P1)

As a platform user, when I ask a question targeting a specific database, the system generates SQL in the correct dialect (PostgreSQL, MySQL, or MS SQL Server), executes it against that database, and clearly shows me which database was queried in the response.

**Why this priority**: Correct dialect generation is the core technical requirement of Phase 3. Without it, multi-database support is cosmetic rather than functional.

**Independent Test**: Configure one PostgreSQL and one MySQL connection. Target the PostgreSQL connection and ask "show all tables" — verify PostgreSQL-specific SQL (e.g., `information_schema` queries with PG syntax). Target the MySQL connection and ask the same question — verify MySQL-specific SQL (e.g., backtick quoting). Verify each response card displays the connection name and type.

**Acceptance Scenarios**:

1. **Given** the user targets a PostgreSQL connection, **When** they submit a question, **Then** the generated SQL uses PostgreSQL dialect conventions (double-quote identifiers, `LIMIT`, PG-specific functions, `::` casting, etc.).

2. **Given** the user targets a MySQL connection, **When** they submit a question, **Then** the generated SQL uses MySQL dialect conventions (backtick identifiers, `LIMIT`, MySQL-specific functions like `IFNULL`, etc.).

3. **Given** the user targets an MS SQL Server connection, **When** they submit a question, **Then** the generated SQL uses T-SQL dialect conventions (bracket identifiers `[]`, `TOP` instead of `LIMIT`, T-SQL-specific functions like `ISNULL`, etc.).

4. **Given** a query result is returned, **When** the response card renders, **Then** the connection display name and database type badge are visible in the response card header, indicating which database was queried.

5. **Given** the user regenerates a query, **When** the regeneration occurs, **Then** the regenerated SQL uses the same dialect as the original attempt (the connection context is preserved).

---

### User Story 18 — Connection, Introspection, and Query Error Handling (Priority: P1)

As a platform user or administrator, when a database connection, schema introspection, or query execution error occurs, I receive a clear, localized error message that helps me understand what went wrong and what to do next.

**Why this priority**: Multi-database introduces new failure modes (wrong credentials, network partitions, dialect mismatches) that Phase 1's single-DB error handling does not cover. Clean error messages are essential for usability and diagnostics.

**Independent Test**: Simulate connection failure (wrong password), verify error message in both English and Arabic. Simulate schema introspection timeout, verify appropriate error. Simulate query execution failure against an unavailable connection, verify the user sees a clear error in the response card. Verify no raw stack traces or dialect driver errors leak to the UI.

**Acceptance Scenarios**:

1. **Given** the admin adds a connection with invalid credentials, **When** they test the connection, **Then** the system displays a localized error message indicating authentication failure without exposing the raw driver error or password.

2. **Given** a configured connection's host becomes unreachable, **When** the user submits a query targeting it, **Then** the system returns a localized error within the chat conversation indicating the database is unreachable and suggesting the user try again later or contact an administrator.

3. **Given** schema introspection times out, **When** the admin reviews the connection status, **Then** the connection shows "introspection failed" with a localized timeout message and the option to retry.

4. **Given** a query execution error occurs (e.g., permission denied on a specific table), **When** the response card renders, **Then** the error message is localized and does not expose internal schema details, raw driver errors, or SQL injection attack surface.

5. **Given** any error scenario described above, **When** the user's language is set to Arabic, **Then** the error message is displayed in Arabic with correct RTL layout.

---

### User Story 19 — Frontend Polish: Multi-DB Selector UI, Admin Connection Form, Updated Login UI, and Consistent Iconography (Priority: P2)

As a platform user, the multi-database selector, admin connection management interface, login page, and all new UI elements are visually consistent with the Phase 2 premium dark-mode aesthetic, use consistent iconography from a single icon library, and meet the same RTL/i18n standards.

**Why this priority**: Visual consistency and UX polish ensure the multi-database features integrate seamlessly into the existing premium UI rather than feeling bolted on.

**Independent Test**: Navigate through all new UI surfaces (connection list, connection form, database selector, login page) in both LTR and RTL modes. Verify premium styling (dark mode, accent colors, gradient borders). Verify all icons come from the lucide-react library. Verify no missing i18n keys. Conduct Chrome DevTools MCP smoke tests for each flow.

**Acceptance Scenarios**:

1. **Given** the admin views the database connections page, **When** the page renders, **Then** the design follows Phase 2 premium dark-mode styling: dark background, accent-colored borders, gradient elements, consistent typography, and proper spacing.

2. **Given** the user interacts with the database selector, **When** the selector renders, **Then** it uses smooth dropdown or popover animations, displays database type icons from lucide-react, and correctly mirrors in RTL mode.

3. **Given** the login page renders, **When** the user views it, **Then** the login UI has been refreshed to align with the Phase 2/3 premium aesthetic (dark mode, accent glow, branded elements).

4. **Given** any new component renders in RTL mode, **When** the layout is inspected, **Then** all directional styling uses logical properties, all icons are properly mirrored where appropriate, and no physical `left`/`right` CSS properties are used.

5. **Given** a Chrome DevTools MCP smoke test runs against each new page/flow, **When** the test completes, **Then** no console errors, no missing i18n keys, no broken layouts, and all interactive elements respond correctly.

---

### Edge Cases

- What happens when the admin disables a connection that a user currently has selected? The user's next query attempt detects the disabled connection and displays a localized error prompting them to select a different database. The selector is automatically updated to exclude the disabled connection.
- What happens when the admin tries to hard-delete a connection that has referenced query attempts? Hard-delete is blocked with a typed localized error. The admin must disable the connection instead. Disabled connections preserve all historical metadata and query references.
- What happens when schema introspection returns zero tables? The connection is marked as "no tables found" and the admin is shown a warning. Users can still select the connection but will receive an error when submitting a query (LLM cannot generate SQL without schema context).
- What happens when a user switches databases mid-session? The next query uses the newly selected database's schema and dialect. Prior turns in the session remain associated with their original connection. The LLM context builder sends only schema for the currently selected connection.
- What happens when two connections have the same display name? The system allows it (display names are not unique identifiers) but shows the database type badge alongside the name to help users distinguish them.
- What happens when a database connection's password needs rotation? The admin edits the connection and provides the new password. The system updates the stored encrypted credential. Existing active queries against the old credential may fail and surface a connection error.
- What happens when the admin saves a connection without testing it first? On initial save, the system auto-runs a health check + introspection. If the health check fails, the connection is saved with "unhealthy" status and "introspection: none". The admin sees a localized error with retry. Users can select the connection but queries will fail at runtime with a clear error.
- What happens when the initial auto-introspection fails after a successful health check? The connection is saved as "healthy" but with schema status "failed". The admin sees a localized introspection error with retry action. Users can select the connection but queries will fail because the LLM has no schema context.
- What happens when the schema changes on the remote database after introspection? The system uses stale schema until the admin triggers "Refresh Schema". No automatic schema polling occurs in Phase 3.
- What happens when the evaluator cannot parse the generated SQL for the target dialect? The evaluator rejects the attempt and triggers regeneration with a dialect correction hint. After the retry limit is exhausted, a localized error card is shown. Unvalidated SQL is never executed.

## Requirements *(mandatory)*

### Functional Requirements

#### Connection Management

- **FR-059**: The system MUST allow the administrator to add a new source database connection by specifying: display name, database type (PostgreSQL, MySQL, or MS SQL Server), host, port, database name, username, and password.
- **FR-060**: The system MUST allow the administrator to edit an existing source database connection. All fields are editable. When editing, the password field MUST NOT display the stored credential; instead it MUST show a placeholder indicating the existing credential is retained unless a new value is entered.
- **FR-061**: The system MUST allow the administrator to hard-delete a source database connection only when it has no referenced query attempts or sessions. Hard-delete MUST require explicit confirmation. Upon hard-delete, cached schema metadata for that connection MUST be deleted. If the connection is referenced, hard-delete MUST be blocked with a typed localized error directing the admin to disable instead.
- **FR-089**: The system MUST allow the administrator to disable an active connection and re-enable a disabled connection. Disabled connections MUST be hidden from the user database selector, MUST reject query submissions, and MUST remain visible in the admin connection management list with a "disabled" indicator. Disabling MUST preserve all historical query references and schema metadata.
- **FR-090**: Connection lifecycle state (active, disabled) and health status (untested, healthy, unhealthy) MUST be tracked as independent dimensions. A connection can be active+unhealthy or disabled+healthy, etc.
- **FR-062**: The system MUST NOT store database connection passwords in plaintext. Passwords MUST be encrypted at rest using a server-side encryption key or delegated to a secrets management mechanism. The password MUST NOT appear in API responses, logs, or frontend state after initial submission.
- **FR-063**: The system MUST allow the administrator to test a database connection's health by executing a lightweight connectivity check (e.g., `SELECT 1`). The result MUST be returned as success (with latency) or failure (with a categorized, localized error message).
- **FR-064**: The system MUST persist each connection's most recent health check result (status, timestamp, error category if failed) and display it in the connection list.

#### Schema Introspection

- **FR-065**: The system MUST support schema introspection for PostgreSQL, MySQL, and MS SQL Server connections, extracting at minimum: table names, column names, column data types, primary key indicators, and foreign key relationships.
- **FR-066**: The system MUST store introspected schema metadata per connection. Schema data MUST be refreshable on admin demand. Refreshing MUST fully replace prior metadata (no merge).
- **FR-067**: The system MUST display a summary of introspected schema to the admin: list of tables with column count per table.
- **FR-068**: The system MUST handle schema introspection failures gracefully with localized error messages. A failed introspection MUST NOT silently use stale data; the connection's schema status MUST be updated to reflect the failure.
- **FR-093**: When a new connection is saved for the first time, the system MUST automatically run a health check. If the health check passes, schema introspection MUST run automatically so the connection is immediately usable in the workspace database selector. If health check or introspection fails, the connection MUST be saved with the appropriate health/schema error status and a localized error with retry action shown to the admin. After initial introspection, all subsequent schema refreshes are manual (admin-triggered "Refresh Schema" only).

#### Dialect-Aware SQL Generation

- **FR-069**: The system MUST generate SQL in the dialect matching the user's selected database connection type. Supported dialects: PostgreSQL, MySQL (including MariaDB-compatible subset), T-SQL (MS SQL Server).
- **FR-070**: The LLM prompt builder MUST include the selected connection's introspected schema (tables, columns, types, relationships) and an explicit dialect instruction identifying the target SQL dialect.
- **FR-071**: The evaluator MUST validate generated SQL against the dialect of the selected connection. SQL containing constructs invalid for the target dialect (e.g., `LIMIT` in T-SQL) MUST be rejected by the evaluator. If dialect-specific parsing fails, parser confidence is low, or the evaluator cannot prove the SQL is safe read-only SQL for the selected dialect, the evaluator MUST reject the attempt and trigger the existing reject/retry regeneration path (FR-017/FR-019) with an explicit dialect correction hint and the connection's dialect/schema context. SQL that fails dialect validation MUST NEVER be executed.
- **FR-072**: Generated SQL MUST remain read-only. The existing security invariant (no INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE) MUST apply across all dialects.
- **FR-092**: When the evaluator's dialect-rejection retry limit is exhausted (per the configured max regenerate attempts), the system MUST surface a localized assistant refusal/error card in the chat conversation rather than executing unvalidated SQL.

#### Database Selection UX

- **FR-073**: The user interface MUST display a database selector near the prompt input area, allowing the user to choose which configured connection their question targets.
- **FR-074**: The database selector MUST display each connection's display name and database type (with a distinguishing icon or badge).
- **FR-075**: When a user submits a question, the system MUST associate the query attempt with the selected connection ID. This association MUST be persisted on both the session record and the query attempt so the response card can display which database was queried.
- **FR-076**: The response card MUST display the connection display name and database type badge, indicating which database was queried for that result.
- **FR-077**: When no database connections are configured or all connections are unhealthy, the system MUST display a localized message in the prompt area explaining that no database is available.
- **FR-094**: Database selection MUST be per-session scoped. Each new session starts with no selected connection; the user MUST select one before the first query (prompt input disabled until selection). Exception: if exactly one active connection exists, it is auto-selected. The selected `connection_id` MUST be stored on the session record. Switching databases mid-session updates the session's `connection_id` and affects only subsequent queries; prior query attempts retain their original `connection_id`. No global user default is persisted in Phase 3.

#### Error Handling

- **FR-078**: All error messages surfaced to the user or admin for connection, introspection, and query execution failures MUST be localized (English and Arabic) and MUST NOT expose raw driver errors, stack traces, or credentials.
- **FR-079**: Connection errors during query execution MUST be surfaced inline within the chat conversation as an error response card, not as a full-page error or silent failure.

#### Frontend Polish

- **FR-080**: The admin database connections management page MUST follow Phase 2 premium dark-mode styling conventions.
- **FR-081**: The database selector component MUST use smooth animations, correctly mirror in RTL, and display database type icons from the lucide-react library.
- **FR-082**: The login page UI MUST be refreshed to align with the Phase 2/3 premium aesthetic. The refresh MUST NOT break existing authentication flow or i18n support.
- **FR-083**: All new icons introduced in Phase 3 MUST use the lucide-react library unless an alternative is explicitly justified and added via the package manager. No inline SVGs or multiple icon libraries.
- **FR-084**: All new user-facing strings MUST be extracted to i18n keys with both English and Arabic translations present.
- **FR-085**: All new components MUST use logical directional CSS properties exclusively. No physical `left`/`right` properties.
- **FR-086**: Chrome DevTools MCP smoke tests MUST be conducted for each new user-facing flow: admin connection CRUD, connection health test, schema introspection, database selector interaction, query submission with dialect verification, and login page.

#### Migrations and Backward Compatibility

- **FR-087**: A new database migration MUST introduce tables for source database connections and per-connection schema metadata. The existing Phase 1/2 hardcoded PostgreSQL source database MUST be migrated as the first row in the new `source_database_connections` table. All existing query attempt and history rows MUST be backfilled with this legacy connection's ID. After backfill, `connection_id` MUST be NOT NULL on the query attempt table.
- **FR-088**: The existing single-source-database behavior MUST be preserved as a degenerate case: if only one connection exists, it is auto-selected and the database selector may be hidden or shown in a simplified state.
- **FR-091**: Migration tests MUST verify: (a) existing query attempt rows are backfilled with the legacy connection ID, (b) new query attempts require a non-null `connection_id`, (c) the legacy connection record is created with correct type (PostgreSQL) and credentials from the existing configuration.

### Key Entities

- **SourceDatabaseConnection**: A configured connection to an external database. Attributes: unique identifier, display name, database type enum (PostgreSQL, MySQL, MS SQL Server), host, port, database name, username, encrypted password, **lifecycle state enum (active, disabled)**, health status enum (untested, healthy, unhealthy), last health check timestamp, schema introspection status enum (none, success, failed, stale), **schema_last_refreshed_at** timestamp (nullable), created timestamp, updated timestamp. Hard-deleted connections are physically removed from the database (no soft-delete row).

- **ConnectionSchema**: Introspected schema metadata for a connection. Attributes: connection identifier (FK), table name, column name, column data type, is primary key, foreign key references (nullable), introspected timestamp. One-to-many from connection to schema entries. Cascade-deletes when parent connection is deleted.

- **QueryAttempt** (extended): Gains a `connection_id` NOT NULL foreign key to track which source database was targeted for each query attempt. Historical attempts from Phase 1/2 are backfilled with the migrated legacy connection's ID.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-025**: An administrator can add, test, edit, and remove database connections for all three supported types (PostgreSQL, MySQL, MS SQL Server) through the management UI without errors.
- **SC-026**: Schema introspection completes successfully for each supported database type and stores table/column metadata viewable by the admin.
- **SC-027**: A user can submit the same natural-language question against a PostgreSQL and a MySQL connection in separate turns and receive syntactically distinct SQL matching each dialect.
- **SC-028**: All generated SQL across all dialects passes the read-only security check — no write/DDL operations are permitted.
- **SC-029**: Database connection passwords are never returned in API responses, never logged, and are stored encrypted at rest.
- **SC-030**: Every new user-facing string has both English and Arabic translations; no missing i18n keys appear in either language.
- **SC-031**: All new components pass RTL layout validation — zero physical directional CSS properties.
- **SC-032**: Chrome DevTools MCP smoke tests pass for all new flows: admin connection management, database selector, dialect-aware query submission, and login page.
- **SC-033**: All foundation quality gates (backend linting, backend tests, frontend tests, frontend linting, frontend type checking, frontend build) pass on every Phase 3 pull request.
- **SC-034**: The existing single-database workflow continues to function without regression when exactly one connection is configured.
- **SC-035**: Error messages for connection failures, introspection failures, and query execution errors are localized and do not expose raw driver details or credentials.

## Assumptions

- The platform remains single-user (provisional administrator) throughout Phase 3. Multi-user / SSO / RBAC is deferred to Phase 5.
- The provisional admin is the only user who can manage database connections. Non-admin users can select and query connections but cannot create, edit, or remove them.
- Connection pooling configuration is not exposed to the admin. The system uses sensible defaults internally.
- Cross-database joins are not supported. Each query targets exactly one connection.
- Read replicas and replication configuration are out of scope.
- Schema introspection is admin-triggered for refreshes after the initial auto-introspection on first save. No automatic or periodic re-introspection. Stale schema is possible between manual refreshes.
- The encryption key for database passwords is configured server-side (e.g., via environment variable). Key management and rotation procedures are outside Phase 3 scope.
- MySQL dialect support covers MySQL 5.7+ and MariaDB 10.3+ through the common SQL subset.
- MS SQL Server support covers SQL Server 2017+.
- The database selector default behavior: if only one connection is configured, it is auto-selected. If multiple connections exist, the user must explicitly select one (no arbitrary default).
- lucide-react is the existing icon library from Phase 2. No new icon library is introduced unless explicitly justified.
- Phase 2 UI/RTL/i18n/session behavior is fully preserved. Phase 3 adds new surfaces but does not modify Phase 2 components.

## Explicitly Out of Scope

The following are NOT covered by this specification and belong to later phases:

- **SSO / RBAC / multi-user**: Phase 5. Single provisional admin remains.
- **Tamper-evident audit log**: Phase 5/6 (Constitution IX).
- **Hostile input detection / auto-suspension**: Phase 6 (Constitution IV).
- **Token/query/cost quotas**: Phase 5 (Constitution X).
- **Cross-database joins**: Not on roadmap.
- **Read replicas / replication management**: Not on roadmap.
- **Connection pooling tuning UI**: Phase 7.
- **Charts / visualizations**: Phase 2 original roadmap; not in Phase 3 scope.
- **Scheduled reports**: Phase 8.
- **Semantic search of past queries**: Phase 9.
- **Mobile shell / PWA**: Phase 4+.
- **Saved Queries Library page**: Deferred from Phase 2. Not pulled into Phase 3.
- **Automatic/periodic schema re-introspection**: Could be added later as enhancement.
- **Database-specific connection options** (SSL mode, connection timeout tuning, etc.): Can be added incrementally in future phases.

## Architectural Decision Records

The following ADR seeds require resolution during `/speckit.clarify` or `/speckit.plan`:

- **ADR-9 — DB Credential Storage**: Database connection passwords MUST be encrypted at rest using Fernet symmetric encryption (via `cryptography` library) with a server-side encryption key loaded from environment variable `DB_CREDENTIAL_KEY`. A credential-encryption provider abstraction MUST be introduced so Phase 5+ can swap to an external secrets manager (e.g., HashiCorp Vault) without rewriting connection services. If stored encrypted credentials exist and `DB_CREDENTIAL_KEY` is missing or invalid at startup, the system MUST fail startup or block credential use with a typed configuration error — never silently serve unencrypted data. Key rotation is deferred to a future phase but the abstraction layer should document the rotation interface. **LOCKED.**
- **ADR-10 — Driver/Library Choices**: PostgreSQL: `asyncpg` (existing). MySQL: `asyncmy`. MS SQL Server: `aioodbc` with `unixODBC` + FreeTDS/ODBC driver. Each driver MUST support async execution and parameterized queries only (no string interpolation). MSSQL system dependencies (`unixODBC`, FreeTDS/ODBC driver packages) MUST be documented in setup guides, Dockerfile, and CI configuration. If real MySQL/MSSQL services are not available in CI, dialect/introspection behavior MUST be unit-tested with adapters/fakes; real-service integration tests remain optional/manual. **LOCKED.**
- **ADR-11 — Schema Introspection Strategy**: Use `information_schema` views (standard across all three dialects) as the primary introspection mechanism. Fall back to dialect-specific system catalogs only where `information_schema` is insufficient (e.g., foreign key details in older MySQL versions). Schema metadata is stored in application database tables, not cached in Redis.
- **ADR-12 — Dialect Routing**: The LLM prompt builder includes an explicit `TARGET_DIALECT: <dialect>` instruction along with the connection's schema. The evaluator's validation rules are parameterized by dialect (e.g., `LIMIT` allowed for PostgreSQL/MySQL but not T-SQL). Connection-to-dialect mapping is derived from the `database_type` enum on the connection record.
- **ADR-13 — Selected Connection UX**: The database selector is a dropdown/popover near the prompt input, showing connection display name + database type icon. Selection is per-session scoped: stored as `connection_id` on the session record. Each new session starts unselected (user must choose before first query). Exception: single active connection is auto-selected. Switching databases mid-session is allowed and takes effect on the next query; prior turns retain their original connection. No global user default in Phase 3. **LOCKED.**
- **ADR-14 — Frontend Icon Library**: Continue using lucide-react (already installed in Phase 2). New database-type icons (PostgreSQL elephant, MySQL dolphin, SQL Server logo) may use lucide-react's generic `Database`, `Server`, or `HardDrive` icons combined with text labels/badges rather than brand logos. Brand SVGs are not introduced.
- **ADR-15 — Chrome DevTools MCP Smoke Requirements**: Gemini (frontend implementer) MUST conduct Chrome DevTools MCP smoke tests for every new user-facing flow. Smoke evidence includes: page load without console errors, interactive element responsiveness, i18n key resolution in both languages, RTL layout correctness, and correct API response rendering.

## Constitution Mapping

| Principle | Phase 3 Status |
|-----------|---------------|
| I — Security and Data Protection | Extended; DB credentials encrypted at rest, never exposed in API/logs |
| II — Query Validation Before Execution | Preserved; evaluator now parameterized by dialect |
| III — Only Validated Knowledge Persists | Preserved; no changes to retrieval memory |
| IV — Hostile Input | Deferred to Phase 6 |
| V — LLM-Agnostic Platform | Preserved |
| VI — Language Decoupled from SQL Dialect | **EXTENDED**; dialect-aware generation for PostgreSQL, MySQL, T-SQL |
| VII — Role-Appropriate Authentication | Deferred to Phase 5 |
| VIII — Centrally Brokered Database Access | **EXTENDED**; admin manages multiple connections centrally |
| IX — Observability and Auditability | Deferred to Phase 5 |
| X — Quotas | Deferred to Phase 5 |
| XI — Architectural Modularity | **EXTENDED**; dialect routing, driver abstraction, per-connection schema |
| XII — API Contract as Source of Truth | Preserved; new endpoints added to OpenAPI contract |
