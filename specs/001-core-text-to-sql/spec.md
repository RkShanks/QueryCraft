# Feature Specification: Core Text-to-SQL Vertical Slice

**Feature Branch**: `001-core-text-to-sql`  
**Created**: 2026-05-03  
**Status**: In Progress (Phase 1, Wave 3 shipped — Wave 4 in planning)  
**Input**: User description: "Build the foundational core of an enterprise Text-to-SQL Analytics Platform — a vertical slice that proves the entire question-to-validated-answer loop works end-to-end before any of the enterprise features are added in later phases."

## Clarifications

### Session 2026-05-03

- Q: Which SQL dialect does Phase 1 support? → A: PostgreSQL only. FR-004 and the evaluator requirements are pinned to PostgreSQL; the Assumptions section records this.
- Q: Should regenerated SQL ever be byte-equal to rejected SQL? → A: No. SC-005 tightened to 100% uniqueness. If the LLM returns identical SQL, the system rejects that attempt and asks the user to refine.
- Q: Is there an upper bound on accepted-query history? → A: No upper bound in the data model or API contract. The 1,000-entry client-side rendering is a Phase 1 UI simplification only; server-side pagination deferred.
- Q: Does Phase 1 include Constitution Principle IX's tamper-evident audit log? → A: No. Full audit log is explicitly deferred to a later phase. FR-020's short-term diagnostic logs are not the final state.
- Q: Is there a maximum question length? → A: Yes, 2,000 characters (configurable). Longer submissions rejected client-side.
- Q: What is the default session expiration? → A: 8 hours of inactivity, configurable at deployment time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Ask, Validate, See a Table, Accept (Priority: P1)

As the platform user, I can sign in with my local administrator credentials, ask a question in plain English about data in the connected database, see a validated table result with the originating SQL, and accept it so it is saved to my personal history.

This is the irreducible core of Phase 1. Every subsequent phase builds on this question-to-validated-answer loop. If only this story works, the phase still delivers value.

**Why this priority**: This story proves the entire end-to-end loop — authentication, question submission, LLM-powered SQL generation, safety evaluation, database execution, result rendering, and persistent history. Without it, no other story has meaning.

**Independent Test**: Can be fully tested by signing in, typing a question, receiving a table result, clicking Accept, and verifying the query appears in the history list. Delivers the foundational question-to-answer value.

**Acceptance Scenarios**:

1. **Given** the user is signed in and a database is connected, **When** they type "How many orders were placed last month?" and submit, **Then** the platform sends the question plus schema context to the configured LLM provider, the returned SQL passes the evaluator, the SQL is executed with a read-only connection, and the user sees a paginated table result alongside the SQL that produced it, with Accept / Reject / Regenerate actions visible below the result.

2. **Given** the user is viewing a valid table result, **When** they click Accept, **Then** the question text, the generated SQL, a timestamp, the user's identifier, and the target database identifier are written to durable storage, the i18n key `query.accept.success.message` is displayed for a minimum of 2 seconds, and the accepted query becomes visible in the user's History view.

3. **Given** the user is not signed in, **When** they attempt to access the question input or any platform feature, **Then** they are redirected to the sign-in screen and cannot proceed until they authenticate with valid local credentials.

4. **Given** the configured LLM provider is unreachable or returns an error, **When** the user submits a question, **Then** the platform displays a clear error message explaining that the question could not be processed at this time, and invites the user to try again later. No partial or empty result is shown.

5. **Given** the database connection is unavailable, **When** the evaluator-passed SQL is about to be executed, **Then** the platform displays a clear connection error to the user and does not write any record to history.

---

### User Story 2 — Reject and One Automatic Retry (Priority: P1)

As the platform user, when I reject a generated answer because it does not look correct, the platform automatically tries once more with a freshly generated SQL statement. If I reject the second attempt as well, the platform stops auto-retrying and asks me to refine my question. Rejected attempts never appear in my history.

**Why this priority**: The reject/retry loop is integral to the core question-to-answer experience. Users must have a way to signal that an answer is wrong and get a second chance without manually resubmitting. This story is inseparable from the core value proposition.

**Independent Test**: Can be tested by submitting a question, rejecting the first result, verifying that a new (different) SQL is generated and shown, then either accepting the second attempt or rejecting it again to confirm the "please refine your question" message appears. Verify that rejected queries do not appear in History.

**Acceptance Scenarios**:

1. **Given** the user has just rejected a generated answer for a question, **When** the platform generates a new SQL attempt, **Then** the new SQL is not byte-equal to the rejected SQL, the rejected SQL is provided to the LLM as negative context, and the new SQL is itself subject to the full evaluator step before execution. If the LLM returns byte-identical SQL, the system treats it as a failed regeneration and asks the user to refine their question.

2. **Given** the user has rejected two consecutive attempts for the same question, **When** they view the screen after the second rejection, **Then** the platform does not auto-regenerate again, displays a message asking the user to refine or rephrase their question, and presents a fresh text input for a new question.

3. **Given** the user has rejected one or more attempts, **When** they open the History view, **Then** no rejected query appears and no record of rejected SQL is retained in durable storage.

4. **Given** the user clicks Regenerate instead of Reject, **When** the platform processes the action, **Then** it behaves identically to a single rejection followed by a new attempt — the same "one automatic retry, then ask the user to refine" rule applies.

5. **Given** the user has been asked to refine their question after two rejections, **When** they type and submit a new question, **Then** the retry counter resets and the normal generation flow (with up to one auto-retry on rejection) begins anew for the new question.

---

### User Story 3 — Evaluator Blocks Unsafe SQL (Priority: P1)

As the platform operator, I am guaranteed that any SQL generated by the LLM is checked for safety and basic semantic correctness before it ever reaches the source database. SQL that contains data-modifying operations, references non-existent schema objects, or matches unsafe patterns is rejected by the evaluator and never executed.

**Why this priority**: Safety is non-negotiable. The evaluator is the trust boundary between probabilistic LLM output and the customer's production data. This must work before any query is allowed through.

**Independent Test**: Can be tested by configuring the LLM to return known-unsafe SQL (e.g., containing `UPDATE`, `DROP`, or references to non-existent tables) and verifying that the evaluator blocks execution, the database is never contacted, and the user sees an appropriate safety message.

**Acceptance Scenarios**:

1. **Given** a generated SQL statement contains an `UPDATE` keyword, **When** the evaluator inspects it, **Then** the SQL is rejected, the database is not contacted, and the user sees a message explaining that their question could not be answered safely and inviting them to rephrase.

2. **Given** a generated SQL statement contains `DELETE`, `DROP`, `TRUNCATE`, `ALTER`, `INSERT`, or `CREATE`, **When** the evaluator inspects it, **Then** the SQL is rejected with the same safety behavior.

3. **Given** a generated SQL statement references a table name that does not exist in the connected database schema, **When** the evaluator inspects it, **Then** the SQL is rejected and the user is informed that the question could not be matched to available data.

4. **Given** a generated SQL statement references a column name that does not exist in the referenced table, **When** the evaluator inspects it, **Then** the SQL is rejected with a clear message.

5. **Given** a generated SQL statement is a valid read-only `SELECT` or read-only CTE that references only existing tables and columns, **When** the evaluator inspects it, **Then** the SQL passes evaluation and proceeds to execution against the database.

6. **Given** a generated SQL statement contains multiple statements separated by semicolons, **When** the evaluator inspects it, **Then** only a single statement is permitted; multi-statement SQL is rejected.

7. **Given** a query takes longer than the configured per-query execution timeout, **When** the timeout expires, **Then** the query is cancelled, the user sees a clear timeout message, and no partial result is written to history.

---

### User Story 4 — Browse and Search History (Priority: P2)

As the platform user, I can open a History view that lists all my accepted queries in reverse-chronological order. I can filter the list by typing words from the question text or the SQL. Selecting an entry shows the full question, SQL, and the date/time it was accepted.

**Why this priority**: History gives the user a way to review and reference their past successful queries. While important for day-to-day use, the core ask/validate/accept loop (P1) can stand alone without it.

**Independent Test**: Can be tested by accepting several queries, navigating to the History view, verifying they appear in reverse-chronological order, using the free-text filter to narrow results, and selecting an entry to view its details.

**Acceptance Scenarios**:

1. **Given** the user has accepted three queries today, **When** they open the History view, **Then** they see exactly three entries in reverse-chronological order, each showing its question text, SQL, and acceptance timestamp.

2. **Given** the user has accepted queries with varying question text, **When** they type a word from one question into the filter input, **Then** only the entries whose question text or SQL contains that word are shown.

3. **Given** the user selects a history entry from the list, **When** the detail view loads, **Then** it displays the full question text, the full generated SQL, and the date/time the query was accepted.

4. **Given** the user has no accepted queries, **When** they open the History view, **Then** they see an empty state with a message indicating no queries have been accepted yet.

5. **Given** the user has rejected a query, **When** they open the History view, **Then** the rejected query does not appear.

---

### User Story 5 — Configurable LLM Provider (Priority: P2)

As the platform operator, at deployment time I choose which LLM provider the platform uses — Anthropic Claude, OpenAI, Google Gemini, or a self-hosted Ollama-compatible endpoint — by configuration alone. Switching providers does not require code changes and does not invalidate stored history.

**Why this priority**: LLM agnosticism is a constitutional principle (Principle V) and a strategic requirement for enterprise deployments. While only one provider is active at any given time, the abstraction must be in place from the start.

**Independent Test**: Can be tested by deploying the platform with one provider configuration, submitting and accepting queries, then switching to a different provider configuration, restarting, and verifying that new queries use the new provider while existing history remains intact.

**Acceptance Scenarios**:

1. **Given** the platform is configured to use the self-hosted Ollama-compatible endpoint, **When** the user asks a question, **Then** the request is sent to that endpoint and not to any cloud provider.

2. **Given** the platform is reconfigured from one provider to another, **When** the platform restarts with the new configuration, **Then** previously accepted queries remain accessible in History and new questions are routed to the newly configured provider.

3. **Given** the platform configuration specifies an unsupported or invalid LLM provider, **When** the platform starts, **Then** it fails with a clear configuration error message before accepting any user traffic.

---

### User Story 6 — i18n and RTL-Ready Foundation (Priority: P3)

As the team building the Arabic/RTL phase in a later release, when I inspect the Phase 1 codebase, I find that every user-facing string is routed through a keyed internationalization layer and that no user-facing component uses hardcoded directional CSS. I can add Arabic translations and activate RTL layout without reworking any Phase 1 component.

**Why this priority**: While no user-visible Arabic content is delivered in Phase 1, establishing the i18n string layer and RTL-ready layout primitives now avoids a costly retrofit later. This is a foundation investment.

**Independent Test**: Can be tested by auditing the codebase to confirm that all user-facing strings are referenced by stable i18n keys (not inline literals), that only English translation values are present, and that all layout CSS uses logical properties (`inline-start`, `inline-end`, `block-start`, `block-end`) rather than physical directional properties (`left`, `right`, `margin-left`, `padding-right`).

**Acceptance Scenarios**:

1. **Given** a developer inspects any user-facing component, **When** they search for user-visible text, **Then** every string is a reference to an i18n key, not a hardcoded literal.

2. **Given** a developer inspects the CSS of any user-facing component, **When** they search for `left`, `right`, `margin-left`, `margin-right`, `padding-left`, or `padding-right`, **Then** no results are found; all directional styles use logical equivalents.

3. **Given** only English translations exist, **When** the platform renders, **Then** all text appears correctly in English with no missing-key placeholders or broken formatting.

---

### Edge Cases

- What happens when the LLM returns empty or null SQL? The evaluator rejects it, and the user is shown a message asking them to rephrase.
- What happens when the LLM returns valid SQL that produces zero rows? The platform displays an empty table with a message such as "No results found for your query" — this is a valid result, not an error. The user may still Accept, Reject, or Regenerate.
- What happens when the database returns an execution error for evaluator-passed SQL (e.g., a runtime type mismatch)? The platform shows a clear execution error message to the user. The failed attempt is not written to history.
- What happens when the user's session expires while viewing a result? The user is redirected to the sign-in screen. Any unsaved (not yet accepted) result is lost; accepted queries in history are unaffected.
- What happens when the user submits an empty or whitespace-only question? The platform rejects the submission client-side with a validation message and does not contact the LLM.
- What happens when the schema context for the connected database is very large? The platform includes a representation of the schema (table names, column names and types, foreign key relationships) in the LLM prompt. If the schema exceeds the LLM's context window, the platform surfaces a configuration error to the operator rather than silently truncating.
- What happens when the user rapidly submits multiple questions before the first result returns? The platform processes one question at a time per user session; subsequent submissions are queued or the submit action is disabled until the current question completes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST authenticate exactly one provisional administrator via local credentials (username and password) configured at deployment time.
- **FR-002**: The system MUST redirect unauthenticated users to a sign-in screen and prevent access to any platform feature until valid credentials are provided.
- **FR-003**: The system MUST maintain a user session after successful authentication. The session MUST expire after a configurable period of inactivity (default: 8 hours), after which the user is required to re-authenticate.
- **FR-004**: The system MUST connect to exactly one PostgreSQL source database, configured at deployment time via connection parameters (host, port, database name, credentials). Phase 1 supports PostgreSQL only; MySQL and MS SQL Server support is deferred to a later phase.
- **FR-005**: The system MUST connect to the source database using a read-only role/user. No data-modifying capability against the source database is permitted.
- **FR-006**: The system MUST provide a chat-style interface with a single text input where the user types a natural-language question in English.
- **FR-007**: The system MUST validate that the submitted question is non-empty, non-whitespace, and does not exceed a configurable maximum length (default: 2,000 characters) before sending it to the LLM provider. Submissions exceeding the maximum length MUST be rejected client-side with a clear validation message.
- **FR-008**: The system MUST send each question, together with a representation of the connected database schema (table names, column names, column types, and foreign key relationships), to the configured LLM provider.
- **FR-009**: The system MUST abstract the LLM provider behind an interface that supports Anthropic Claude, OpenAI, Google Gemini, and a self-hosted Ollama-compatible endpoint. Exactly one provider is active at any time, selected by configuration.
- **FR-010**: The system MUST run an internal evaluator on every generated SQL statement before execution. The evaluator MUST be aware of PostgreSQL dialect syntax and semantics (the only dialect supported in Phase 1). The evaluator MUST reject any SQL that:
  - (a) is not a single read-only `SELECT` statement or read-only Common Table Expression (CTE) in valid PostgreSQL syntax,
  - (b) contains data-modifying keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `TRUNCATE`, `ALTER`, `CREATE`),
  - (c) contains multiple statements separated by semicolons,
  - (d) references table names not present in the connected PostgreSQL schema,
  - (e) references column names not present in the referenced tables,
  - (f) Reject SQL containing platform-defined unsafe patterns. The initial unsafe-pattern catalog (extensible via `UnsafePatternRule.add_pattern()`):
  - (g) is `null`, empty, or whitespace-only (treated as an evaluator rejection with violation `empty_sql` and does not execute).
    - `pg_sleep`, `pg_advisory_lock`, `pg_advisory_unlock` — long-blocking calls
    - `pg_read_file`, `pg_read_binary_file`, `pg_ls_dir`, `pg_stat_file` — filesystem access
    - `pg_terminate_backend`, `pg_cancel_backend`, `pg_reload_conf` — server control
    - `lo_*` (large object functions) — bypasses normal grants
    - `COPY ... FROM PROGRAM`, `COPY ... TO PROGRAM` — shell execution via COPY
    - `dblink`, `dblink_*` — outbound network from inside DB
    - `current_setting('is_superuser')`, role-changing statements
    - `LISTEN`, `NOTIFY`, `UNLISTEN` — pub/sub channels

The catalog is enforced by `app/evaluator/rules/unsafe_pattern.py::UnsafePatternRule`. Adding a pattern requires a code change + new test in `backend/tests/unit/evaluator/test_unsafe_pattern.py`.
- **FR-011**: The evaluator MUST be designed with an extensible contract so that additional validation strategies (e.g., an LLM-based semantic judge) can be added in later phases without changing the code that calls the evaluator.
- **FR-012**: The system MUST enforce a configurable per-query execution timeout. When a query exceeds the timeout, the query MUST be cancelled, the user MUST see a clear timeout message, and no partial result MUST be written to history.
- **FR-013**: The system MUST execute evaluator-passed SQL against the source database using a read-only connection.
- **FR-014**: The system MUST present query results as a paginated table. The originating SQL MUST be visible to the user alongside the results.
- **FR-015**: Below each result, the system MUST present three actions: Accept, Reject, and Regenerate.
- **FR-016**: When the user clicks Accept, the system MUST persist the question text, the generated SQL, an acceptance timestamp, the owning user identifier, and the target database identifier to durable storage. The system MUST display the i18n key `query.accept.success.message` for a minimum of 2 seconds.
- **FR-017**: When the user clicks Reject, the system MUST discard the current attempt and automatically trigger one new SQL generation for the same question. The prior rejected SQL MUST be provided to the LLM as negative context. The new attempt MUST pass through the evaluator before execution. If the regenerated SQL is byte-equal to the rejected SQL, the system MUST treat it as a failed regeneration, discard the duplicate, and ask the user to refine or rephrase their question (the same behavior as two consecutive rejections).
- **FR-018**: If the user rejects the second consecutive attempt for the same question, the system MUST stop auto-regenerating, display a message asking the user to refine or rephrase their question, and present a fresh input.
- **FR-019**: The Regenerate action MUST behave identically to a single Reject followed by a new attempt, subject to the same one-automatic-retry limit. FR-019 (Regenerate) MUST behave identically to FR-017 (Reject) in terms of state transitions and invariant enforcement; the distinction is solely user intent (Reject = explicit dissatisfaction; Regenerate = ask for another attempt). See FR-017 for the canonical state machine.
- **FR-020**: The system MUST NOT persist rejected queries, regenerated-and-discarded attempts, or evaluator-rejected SQL to durable storage. Short-term diagnostic logs are permitted but MUST NOT function as user-facing history.
- **FR-021**: The system MUST provide a History view listing the user's accepted queries in reverse-chronological order. The persisted data model and API contract MUST impose no upper bound on the number of accepted queries stored. In Phase 1, the UI renders history as a client-side scrollable list; server-side pagination and filtering will be added in a later phase without requiring data migrations.
- **FR-022**: The History view MUST include a free-text filter that searches across question text and SQL content. In Phase 1, filtering operates client-side. The API contract MUST be designed so that server-side filtering can be introduced in a later phase without breaking changes.
- **FR-023**: Selecting a history entry MUST display the full question text, the full generated SQL, and the date/time the query was accepted.
- **FR-024**: The system MUST route every user-facing string through an internationalization (i18n) layer keyed by stable string identifiers. Only English translations are provided in this phase.
- **FR-025**: The system MUST NOT use hardcoded directional CSS properties (`left`, `right`, `margin-left`, `margin-right`, `padding-left`, `padding-right`) in user-facing components. All directional styling MUST use logical CSS equivalents (`inline-start`, `inline-end`, `block-start`, `block-end`).
- **FR-026**: The system MUST allow the active LLM provider to be switched by configuration only, without code changes and without invalidating existing accepted-query history.
- **FR-027**: The system MUST attribute every persisted record (accepted queries, session events, diagnostic log entries) to a user identifier, even in this single-user phase.
- **FR-028**: When the evaluator rejects a SQL statement, the system MUST display the i18n key `query.evaluator.rejected` and MUST NOT execute the rejected SQL against the database.
- **FR-029**: When a zero-row result is returned from the database, the system MUST display an empty table with a "No results found" message. This is a valid result and the user may Accept, Reject, or Regenerate.
- **FR-030**: The system MUST prevent concurrent question submissions within a single user session. The submit action MUST be disabled while a question is being processed.

### Key Entities

- **User**: A signed-in actor. In Phase 1, exactly one user exists (the provisional administrator), but the entity is a first-class concept with a unique identifier attached to every persisted record. Attributes: unique identifier, display name, role (administrator in Phase 1), authentication credentials (local).

- **DatabaseConnection**: The configured source database. In Phase 1, exactly one connection exists. Attributes: unique identifier, host, port, database name, connection credentials (read-only role), schema metadata (tables, columns, types, foreign keys).

- **Question**: A natural-language question submitted by a user. Attributes: question text, submitting user identifier, target database identifier, submission timestamp.

- **GenerationAttempt**: An attempt to translate a Question into SQL via the LLM. May be evaluator-rejected, evaluator-passed-then-user-rejected, or evaluator-passed-then-user-accepted. Only the last category is retained beyond short-term storage. Attributes: generated SQL, LLM provider used, evaluator result, user action (accept/reject/regenerate), attempt sequence number for the question.

- **AcceptedQuery**: A Question combined with its accepted GenerationAttempt, persisted to the user's history. Attributes: question text, generated SQL, acceptance timestamp, owning user identifier, target database identifier.

- **EvaluatorResult**: The verdict produced by the evaluator for a given GenerationAttempt. Attributes: pass/fail verdict, `violations: list[EvaluatorViolation]` (empty if passed).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can complete the full question-to-accepted-answer loop (sign in → ask → see result → accept) in under 60 seconds for a question that produces fewer than 100 result rows, excluding LLM response time.
- **SC-002**: 100% of generated SQL statements pass through the evaluator before any database contact occurs — no bypass path exists.
- **SC-003**: The evaluator correctly blocks all SQL statements containing data-modifying operations (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `TRUNCATE`, `ALTER`, `CREATE`) with a 100% detection rate.
- **SC-004**: The evaluator correctly blocks SQL referencing non-existent tables or columns with a 100% detection rate when measured against the known schema.
- **SC-005**: After rejection, the automatically regenerated SQL MUST NOT be byte-equal to the rejected SQL. If the LLM returns an identical statement, the system rejects that attempt and asks the user to refine — 100% enforcement, zero tolerance for duplicates.
- **SC-006**: Accepted queries are retrievable from the History view within 3 seconds of opening the view, for a history of up to 1,000 entries.
- **SC-007**: The free-text filter in the History view returns filtered results within 1 second of the user stopping typing.
- **SC-008**: Switching the LLM provider via configuration and restarting the platform takes under 5 minutes of operator effort and does not require any code changes.
- **SC-009**: 100% of user-facing strings are routed through the i18n layer — no inline string literals exist in user-facing components.
- **SC-010**: 0 instances of hardcoded directional CSS properties exist in user-facing components — all directional styling uses logical equivalents.
- **SC-011**: Query execution that exceeds the configured timeout is cancelled and the user sees a timeout message within 5 seconds of the timeout threshold.
- **SC-012**: No rejected, regenerated-and-discarded, or evaluator-rejected SQL is present in durable storage after a session that includes both accepted and rejected queries.
- **SC-013**: The evaluator correctly rejects `null`, empty, or whitespace-only SQL from the LLM with a 100% detection rate; no database execution is attempted.

## Assumptions

- The platform targets a single-organization deployment. Multi-tenant SaaS is out of scope.
- The provisional administrator account is the only user account in this phase. Multi-user scenarios, SSO, and RBAC are deferred.
- Phase 1 supports PostgreSQL as the only source database dialect. The evaluator, schema introspection, and SQL generation prompts are PostgreSQL-specific. MySQL and MS SQL Server support is deferred to a later phase.
- The connected database already contains data and a schema that is meaningful for analytics queries. The platform does not create, modify, or manage the source database schema.
- The default per-query execution timeout is 30 seconds. This value is configurable at deployment time.
- The default session expiration is 8 hours of inactivity. This value is configurable at deployment time.
- The default maximum question length is 2,000 characters. This value is configurable at deployment time.
- The History view's free-text filter operates client-side on the loaded history data. Server-side filtering and pagination of history are deferred to a later phase when history volumes may require it.
- The persisted data model and API contract for accepted-query history impose no upper bound on the number of entries. In Phase 1, the UI renders history as a client-side scrollable list as a simplification; server-side pagination will be added in a later phase without requiring data migrations.
- The database schema context sent to the LLM includes: table names, column names, column data types, primary keys, and foreign key relationships. Sample data values and table-level comments are not included in this phase.
- The user does see an indication that the second attempt after a rejection is the "last automatic try" — a subtle visual cue or text note accompanies the second attempt to set expectations.
- The exact wording shown to the user when the evaluator rejects a query is: "We couldn't generate a safe query for your question. Please try rephrasing it in a different way." This wording is stored as an i18n key and can be changed via translation files.
- Re-running a historical query against current data from the History view is explicitly deferred to a later phase.
- Manual editing of generated SQL by the user before execution is explicitly deferred to a later phase.

## Explicitly Out of Scope

The following are NOT covered by this specification and belong to later phases:

- SSO (SAML/OIDC), role-based access control, role-to-database-role mapping, row-level security, column masking, and any multi-user permission concept
- Charts, chart-type selection, or any non-table result rendering
- MySQL or MS SQL Server source databases, or connecting to more than one database
- Arabic UI translations or RTL layout activation (only the i18n/RTL foundations are in scope)
- Token quotas, query quotas, or usage-based throttling
- Tamper-evident audit log as required by Constitution Principle IX, audit search, audit export. Phase 1 uses short-term diagnostic logs only (FR-020); the full audit log with 24-month retention, tamper evidence, and administrative review is deferred to a later phase. FR-020's diagnostic-log allowance is not the final state.
- Prompt-injection or SQL-injection detection beyond the basic read-only evaluator check
- Auto-suspension of users
- Admin dashboard, system metrics, security incident review, chat history review by an administrator
- Scheduled reports, email delivery, Telegram delivery, WhatsApp delivery
- Semantic search of past queries, cross-user search, or any vector-based retrieval memory
- Manual editing of the generated SQL by the user before execution
- Re-running a historical query against current data from the History view
