# Feature Specification: Premium Dark-Mode UI Refactor + Constitution VI (Arabic + RTL) + Backend Hardening

**Feature Branch**: `002-phase2-premium-ui-rtl`
**Created**: 2026-05-12
**Status**: Draft
**Input**: Phase 2 charter — premium QueryCraft dark-mode UI with conversational sessions, Constitution VI Arabic/RTL activation, real-LLM integration smoke harness, and lifecycle invariant cross-call test framework.

## Context

Phase 1 (PR #38) shipped the core Text-to-SQL platform: 6 user stories, 5 Constitution principles (I–III, V, VIII), 28 PRs merged, 224 tasks closed. Wave 7 (PRs #40–#42) hardened Phase 1 against 3 production findings. Real-LLM smoke testing during Wave 7 surfaced two gaps: the UI is functional but visually basic, and the Phase 1 stub-LLM audit missed 3 production-grade bugs. Phase 2 closes both gaps while activating Constitution VI (Arabic + RTL), which was deferred from Phase 1 but has scaffolding (T-180/T-181/T-182) already in place.

## Clarifications

### Session 2026-05-12

- Q: Does Phase 2 introduce multi-user support? → A: No. Single provisional administrator remains the only user. Multi-user is deferred to Phase 3+.
- Q: Is a "Saved Queries Library" page included? → A: No. `saved=true` is a metadata flag only (ADR-4). Dedicated library page deferred to Phase 3.
- Q: Does mobile layout ship in Phase 2? → A: No. Desktop-first with basic responsive breakpoints so layouts don't crash on small screens. Full mobile shell deferred to Phase 4+.
- Q: Are session previews LLM-generated summaries? → A: No. Preview = first user message, hard-truncated to 60 chars + ellipsis (ADR-2).
- Q: Can users rename sessions? → A: Not in Phase 2 UX. Backend already supports PUT /sessions/:id; rename UX deferred to Phase 3+.
- Q: For FR-035, when loading the last N attempts for context, what should the prompt builder do with in-flight (pending) attempts that have no SQL yet? → A: Skip pending attempts entirely; only completed (accepted/rejected) attempts count toward the cap N.
- Q: Should the edge case describing session deletion with an in-flight query be promoted to a numbered Functional Requirement? → A: Yes — promoted to FR-058.
- Q: SC-022 specifies a 90-second time-bound for a multi-step flow. Should this be kept, removed, or replaced? → A: Replaced with a qualitative criterion: the flow completes without requiring the user to wait for any UI animation longer than 300ms.

## User Scenarios & Testing *(mandatory)*

### User Story 7 — Conversational Sessions with Premium UI (Priority: P1)

As the platform user, I can create chat sessions, switch between them via a sidebar, and carry on multi-turn conversations where the system remembers prior turns. The entire experience is presented in a polished dark-mode interface with cyan/purple/fuchsia neon accents that feels premium and modern.

**Why this priority**: The conversational session model is the backbone of Phase 2. Every other feature (feedback, RTL, sidebar interactions) depends on sessions existing and rendering correctly in the new UI shell.

**Independent Test**: Create a new session via "New Chat", submit a question, receive a response, submit a follow-up question, verify the LLM receives prior turns as context. Switch to another session and verify isolation. Confirm the dark-mode UI renders with the specified aesthetic.

**Acceptance Scenarios**:

1. **Given** the user is signed in, **When** they click "New Chat", **Then** a new session is created, the workspace clears, and the prompt input receives focus. The sidebar shows the new session with preview text derived from the first message once submitted.

2. **Given** the user has submitted a question in a session, **When** they submit a follow-up question in the same session, **Then** the system loads the last N prior attempts (where N is the admin-configured LLM context cap, default 3) and passes them to the prompt builder as conversational history. The LLM response reflects awareness of prior turns.

3. **Given** the user has multiple sessions, **When** they click a different session in the sidebar, **Then** the workspace loads that session's conversation history. The previously active session's state is preserved.

4. **Given** the user is viewing the application, **When** the page renders, **Then** the UI displays a 2-column desktop layout (collapsible sidebar + workspace) with dark-mode styling, gradient text logo, and cyan/purple accent colors throughout.

5. **Given** the LLM context cap is set to 0, **When** the user submits a follow-up, **Then** no prior turns are sent to the LLM — the question is treated as standalone.

---

### User Story 8 — Session Management (Priority: P1)

As the platform user, I can see my sessions grouped chronologically in the sidebar, and I can delete sessions I no longer need with a safe undo mechanism.

**Why this priority**: Session management is essential for the conversational model to be usable beyond a single conversation. Without chronological grouping and deletion, the sidebar becomes an unmanageable list.

**Independent Test**: Create sessions across different dates, verify chronological grouping (Today / Previous 7 Days / Older). Delete a session, verify the undo toast appears for 5 seconds, confirm undo restores the session, confirm expiry of toast permanently removes the session.

**Acceptance Scenarios**:

1. **Given** the user has sessions from today, 3 days ago, and 2 weeks ago, **When** they view the sidebar, **Then** sessions are grouped under "Today", "Previous 7 Days", and "Older" headings in reverse-chronological order within each group.

2. **Given** the user hovers over a session item, **When** the trash icon appears, **Then** clicking it immediately removes the session from the sidebar (optimistic delete) and shows a 5-second undo toast at the bottom of the screen.

3. **Given** the undo toast is visible, **When** the user clicks "Undo" within 5 seconds, **Then** the session is restored to the sidebar in its original position and all conversation data is preserved.

4. **Given** the undo toast is visible, **When** 5 seconds elapse without the user clicking "Undo", **Then** the session and all its associated data (attempts, feedback) are permanently deleted via cascade.

5. **Given** the user deletes the currently active session, **When** the delete completes (toast expires or no undo), **Then** the workspace transitions to a "New Chat" state.

---

### User Story 9 — Response Cards with Feedback and Actions (Priority: P1)

As the platform user, each response from the system appears as a rich card with syntax-highlighted SQL, a scrollable result table, and action buttons for copying SQL, regenerating, and providing explicit feedback (thumbs up/down). Implicit feedback signals are also captured based on my interactions.

**Why this priority**: The response card is the primary surface for user interaction with query results. Feedback signals (both explicit and implicit) are the foundation for future quality improvements and the data layer that Phase 3's audit log builds upon.

**Independent Test**: Submit a question, verify the response card renders with highlighted SQL (custom theme), a result table with alternating rows, and action buttons. Test each action: copy SQL to clipboard, regenerate (verify old attempt gets feedback=-1), thumbs up (verify +1 + saved=true), thumbs down (verify -1). Verify implicit feedback: submit a follow-up and confirm prior attempt gets +1 if its feedback was null.

**Acceptance Scenarios**:

1. **Given** the system returns a successful query result, **When** the response card renders, **Then** it displays: (a) SQL code block with syntax highlighting using a custom dark theme, (b) an action bar with Copy, Regenerate, and ThumbsDown icons, (c) a horizontally scrollable result table with alternating row tinting, (d) a bottom feedback bar with ThumbsUp and ThumbsDown buttons.

2. **Given** the user clicks Copy on the SQL action bar, **When** the clipboard write completes, **Then** the generated SQL text is on the system clipboard and a brief confirmation indicator appears on the Copy button.

3. **Given** the user clicks Regenerate, **When** the system processes the action, **Then** the old attempt receives feedback=-1, a new SQL generation is triggered following the existing reject/retry rules (FR-017/FR-019), and the new attempt appears in the conversation.

4. **Given** the user clicks ThumbsUp on a response, **When** the feedback is recorded, **Then** the attempt receives feedback=+1 and saved=true. The ThumbsUp button shows a selected state.

5. **Given** the user clicks ThumbsDown on a response, **When** the feedback is recorded, **Then** the attempt receives feedback=-1. The ThumbsDown button shows a selected state.

6. **Given** the user submits a follow-up question in the same session, **When** the prior attempt's feedback is null, **Then** the prior attempt receives implicit feedback=+1 and saved=true. If the prior attempt already has explicit feedback, implicit feedback does not override it.

7. **Given** the user has been idle for 5+ minutes with no follow-up, **When** the idle threshold passes, **Then** no implicit feedback signal is recorded.

---

### User Story 10 — Arabic Language and RTL Layout (Priority: P1)

As a user who prefers Arabic, I can switch the interface language to Arabic and the entire layout flips to right-to-left, with all text, icons, navigation, and interactive elements correctly mirrored. No element is visually broken or misaligned in RTL mode.

**Why this priority**: Constitution VI mandates first-class Arabic and RTL support. Activating it during the UI refactor is significantly cheaper than retrofitting later, and the Phase 1 RTL lint scaffolding is already in place.

**Independent Test**: Switch language to Arabic, verify: (a) all strings render in Arabic, (b) sidebar appears on the right, (c) chat bubbles flip alignment, (d) prompt input Send button moves to the left, (e) all rounded corners, padding, and margins flip correctly, (f) no visual breakage in any component.

**Acceptance Scenarios**:

1. **Given** the user selects Arabic as their language, **When** the interface re-renders, **Then** the `dir` attribute is set to `rtl`, the sidebar appears on the right side, and all text is right-aligned by default.

2. **Given** the interface is in RTL mode, **When** the user views a chat conversation, **Then** user bubbles are end-aligned (appearing on the left in RTL), assistant response cards are start-aligned (appearing on the right in RTL), and the prompt input's Send button appears on the left (the logical end side).

3. **Given** the interface is in RTL mode, **When** the user views any component, **Then** all padding, margins, borders, and rounded corners use logical directions and render correctly mirrored. No element uses physical left/right properties.

4. **Given** Arabic translations exist for all UI strings, **When** the interface is in Arabic mode, **Then** no English fallback text or missing-key placeholder appears anywhere in the interface.

5. **Given** the user switches between LTR and RTL, **When** the layout re-renders, **Then** the transition is smooth with no layout jump or flash of unstyled content.

---

### User Story 11 — Admin LLM Context Configuration (Priority: P2)

As the platform administrator, I can configure how many prior conversation turns are sent to the LLM as context, so I can balance response quality against token cost and latency.

**Why this priority**: Context cap is an operational control that directly impacts LLM costs and response quality. It must be configurable without code changes.

**Independent Test**: Navigate to admin settings, change LLM context cap from default 3 to 5, submit a follow-up in a long session, verify 5 turns are included. Set to 0, verify no turns are sent.

**Acceptance Scenarios**:

1. **Given** the admin navigates to the Settings page, **When** they view LLM settings, **Then** the current context cap value is displayed (default: 3) with an input to change it.

2. **Given** the admin sets the context cap to a value between 0 and 10, **When** they save, **Then** the new value takes effect immediately for subsequent queries without requiring a restart.

3. **Given** the admin attempts to set the context cap to a value outside 0–10, **When** they try to save, **Then** the system rejects the input with a clear validation message.

---

### User Story 12 — Real-LLM Contract Verification (Priority: P2)

As the development team, we have a suite of contract tests that verify our LLM integration against the actual wire format of the configured provider, catching protocol-level regressions that stub-only testing misses.

**Why this priority**: Phase 1 audits using a stub LLM missed 3 production-grade bugs. A contract test suite against realistic wire formats is essential for catching integration regressions pre-merge.

**Independent Test**: Run the contract test suite and verify: happy-path response parsing, 429 rate-limit handling, 5xx server error handling, malformed response handling, and schema-context-too-long handling all pass.

**Acceptance Scenarios**:

1. **Given** the test suite runs, **When** a simulated happy-path response is received, **Then** the system correctly parses the SQL from the response body and proceeds through the normal pipeline.

2. **Given** the test suite runs, **When** a simulated 429 rate-limit response is received, **Then** the system surfaces a clear rate-limit error to the caller without crashing or retrying indefinitely.

3. **Given** the test suite runs, **When** a simulated 5xx server error is received, **Then** the system surfaces a clear service-unavailable error.

4. **Given** the test suite runs, **When** a simulated malformed response is received (invalid JSON, missing fields), **Then** the system handles it gracefully without crashing.

5. **Given** the test suite runs, **When** a schema context exceeding the provider's token limit is sent, **Then** the system detects the condition and surfaces a clear error.

---

### User Story 13 — Lifecycle Invariant Testing (Priority: P2)

As the development team, we have a test framework that detects cross-test state leaks (lock leaks, feedback-state leaks, session-touch leaks), ensuring each test runs in a clean environment and catching the class of bugs exemplified by F-011.

**Why this priority**: F-011 (lock leak) was a production finding that existing test patterns failed to catch. A lifecycle invariant framework prevents this entire class of bugs.

**Independent Test**: Run the lifecycle test suite, verify that lock-leak, feedback-state-leak, and session-touch-leak invariants are checked between test boundaries, and that intentionally introduced leaks are detected.

**Acceptance Scenarios**:

1. **Given** a test completes, **When** the next test begins, **Then** the framework asserts that no processing locks remain held from the prior test.

2. **Given** a test completes, **When** the next test begins, **Then** the framework asserts that no unexpected feedback state changes leaked from the prior test.

3. **Given** a test completes, **When** the next test begins, **Then** the framework asserts that no session timestamps were modified outside the prior test's expected scope.

4. **Given** the framework is documented, **When** a developer reads the documentation, **Then** they can add new invariant checks following the documented pattern.

---

### Edge Cases

- What happens when the user deletes a session while a query is in-flight? Behaviour defined in FR-058. The in-flight query is cancelled, the session is removed optimistically, and the undo toast appears. If the user undoes within 5 seconds, the session is restored but the cancelled query result is permanently lost (the attempt is not resumable).
- What happens when the user switches sessions while a query is in-flight? The in-flight query continues processing in the background. When the user switches back, the result is displayed if it completed.
- What happens when the undo toast for session deletion is active and the user tries to delete another session? Each deletion gets its own independent undo toast. Multiple toasts stack.
- What happens when the user gives explicit feedback on an attempt that already has implicit feedback? Explicit feedback overrides implicit feedback. The most recent signal wins.
- What happens when the LLM context cap is changed while a session has an in-flight query? The change applies to the next query, not the in-flight one.
- What happens when the user rapidly toggles between LTR and RTL? The layout re-renders correctly each time with no state corruption or visual artifacts.
- What happens when an Arabic translation key is missing? The system falls back to the English translation and logs a warning. No raw key identifier is shown to the user.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-031**: The system MUST allow the user to create a new chat session via a "New Chat" button. Creating a session clears the workspace and focuses the prompt input.
- **FR-032**: The system MUST allow the user to switch between sessions via a sidebar list. Switching loads the selected session's full conversation history into the workspace.
- **FR-033**: The system MUST allow the user to delete a session with optimistic UI removal and a 5-second undo toast. If the user does not undo within 5 seconds, the session and all associated data (attempts, feedback records) are permanently deleted via cascade. Destructive delete without undo is not permitted.
- **FR-034**: The session list in the sidebar MUST group sessions chronologically under "Today", "Previous 7 Days", and "Older" headings, with sessions in reverse-chronological order within each group.
- **FR-035**: When the user submits a follow-up query in an existing session, the system MUST load the last N completed (accepted or rejected) attempts from that session (where N equals the admin-configured LLM context cap, default 3, range 0–10) and pass them to the prompt builder as conversational history. Pending/in-flight attempts (those with no generated SQL yet) MUST be excluded from the context window and do not count toward the cap.
- **FR-036**: The system MUST apply implicit feedback rules: (a) follow-up submission in the same session assigns +1 and saved=true to the prior attempt only if its feedback is null; (b) Accept click assigns +1 and saved=true; (c) Reject click assigns -1; (d) Regenerate click assigns -1 to the old attempt, new attempt starts with feedback=null; (e) explicit ThumbsUp assigns +1 and saved=true; (f) explicit ThumbsDown assigns -1; (g) idle 5+ minutes with no follow-up produces no signal.
- **FR-037**: The system MUST allow the user to copy generated SQL to the clipboard from the response card action bar. A brief visual confirmation MUST appear on the Copy button upon success.
- **FR-038**: The system MUST allow the user to regenerate SQL via the action bar. The old attempt receives feedback=-1 and a new generation is triggered following existing reject/retry rules (FR-017/FR-019 from Phase 1).
- **FR-039**: The system MUST allow the user to vote thumbs up or thumbs down on responses via the feedback bar. Explicit feedback overrides any prior implicit signal on the same attempt.
- **FR-040**: The system MUST provide an admin-accessible settings interface to configure the LLM context cap (integer, range 0–10). Changes take effect immediately for subsequent queries without requiring a restart.
- **FR-041**: All user-facing strings MUST render correctly in both English (LTR) and Arabic (RTL). All new components MUST use logical directional properties exclusively. All new strings MUST be extracted to i18n keys with both English and Arabic translations populated.
- **FR-042**: SQL code blocks in response cards MUST be rendered with syntax highlighting using a custom dark-themed highlighter. The highlighter MUST be lazy-loaded to avoid impacting initial page load performance.
- **FR-043**: Session preview text MUST equal the first user message in the session, hard-truncated to 60 characters with ellipsis appended if truncated. No LLM-generated summary is used.
- **FR-044**: The sessions table MUST support cascade delete: deleting a session removes all associated accepted_queries, attempts, and feedback records.
- **FR-045**: The accepted_queries table MUST include a session foreign key, a saved flag, and a feedback column to support the session and feedback data model.
- **FR-046**: The system MUST provide admin endpoints for reading and updating the LLM context cap setting. These endpoints MUST respect existing authorization controls.
- **FR-047**: The system MUST include contract tests that verify LLM integration against the actual wire format of the configured provider, covering: happy path, 429 rate limit, 5xx server error, malformed response, and schema-context-too-long scenarios.
- **FR-048**: The system MUST include a lifecycle invariant test framework that observes system state (locks, database records) at test boundaries and asserts no state leaks between tests. The framework MUST document at least 3 example invariants and be used by at least 5 existing tests.
- **FR-049**: The desktop layout MUST be a 2-column design (collapsible sidebar + workspace) with basic responsive breakpoints to prevent layout breakage on smaller screens. Full mobile optimization is deferred.
- **FR-050**: The response card MUST display a gradient-bordered container with: (a) a SQL code block with an action bar (Copy, Regenerate, ThumbsDown), (b) a horizontally scrollable result table with alternating row tinting, and (c) a bottom feedback bar (ThumbsUp, ThumbsDown).
- **FR-051**: The sidebar MUST display: (a) a QueryCraft logo with gradient text and glow effect, (b) a collapse/expand toggle, (c) a "New Chat" call-to-action with accent glow border, and (d) the chronologically grouped session list.
- **FR-052**: The prompt input MUST be a rounded text area with an integrated Send button positioned on the logical end side (right in LTR, left in RTL). Focus state MUST show an accent glow ring.
- **FR-053**: User message bubbles MUST be end-aligned, rounded, dark-styled containers. Alignment MUST flip automatically in RTL mode.
- **FR-054**: The filter debounce interval MUST be defined as a named constant rather than a magic number.
- **FR-055**: The physical-direction lint rule MUST extend to cover `left:`, `right:`, `float:`, and `border-*` physical directional properties.
- **FR-056**: The i18n key completeness test MUST validate that all keys present in the primary locale file exist in every secondary locale file.
- **FR-057**: The `defaultValue` fallback parameter MUST be removed from translation function calls. A `saveMissing` handler MUST be configured to catch untranslated keys during development.
- **FR-058**: When the user deletes a session with an in-flight query, the system MUST cancel the in-flight query, optimistically remove the session, and show the undo toast. If the user undoes within 5 seconds, the session is restored but the cancelled query result is permanently lost (the attempt is not resumable).

### Key Entities

- **Session**: A container for a multi-turn conversation. Attributes: unique identifier, owning user identifier, creation timestamp, last-activity timestamp, preview text (first user message truncated to 60 chars).

- **AcceptedQuery** (extended): Gains session foreign key, saved boolean flag, and feedback integer column. Cascade-deletes when parent session is deleted.

- **FeedbackSignal**: A recorded signal on an attempt. Attributes: feedback value (+1 or -1), source (implicit or explicit), timestamp. Stored as a column on the attempt/accepted_query record rather than a separate entity.

- **AppConfig** (extended): Gains `llm_context_cap` setting (integer 0–10, default 3). Readable and writable via admin endpoints.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-014**: The foundational backend and UI shell changes merge with no visible regression — all existing Phase 1 pages continue to render and pass their existing test suites.
- **SC-015**: The full QueryCraft premium UI replaces old pages. All RTL visual snapshots pass. Desktop performance score is 85 or higher on a standard performance audit.
- **SC-016**: 5 real-LLM contract tests pass against simulated provider wire formats covering happy path, rate limit, server error, malformed response, and oversized context.
- **SC-017**: The lifecycle invariant framework documents 3 example invariants and is integrated into at least 5 existing tests.
- **SC-018**: All Phase 2 pull requests reference task identifiers in their commit messages.
- **SC-019**: All foundation quality gates (backend linting, backend tests, frontend tests, frontend linting, frontend type checking, frontend build) pass on every Phase 2 pull request.
- **SC-020**: 100% of new user-facing strings are extracted to i18n keys with both English and Arabic translations present — no inline string literals exist in new components.
- **SC-021**: 0 instances of physical directional CSS or utility classes exist in new components — all directional styling uses logical equivalents.
- **SC-022**: The session creation → question → follow-up → switch-session → delete-session flow completes without requiring the user to wait for any UI animation longer than 300ms.
- **SC-023**: Session deletion with undo completes the full optimistic-remove → toast → permanent-delete cycle in exactly 5 seconds (±500ms tolerance).
- **SC-024**: The LLM context cap change via admin settings takes effect on the next query without any application restart.

## Assumptions

- The platform remains single-user (provisional administrator) throughout Phase 2. Multi-user scenarios are deferred.
- PostgreSQL remains the only supported source database dialect in Phase 2.
- Arabic translations may be machine-translated stubs during initial development waves; a final quality pass is expected before the phase closes.
- The syntax highlighter is loaded on-demand (lazy-loaded) and does not impact initial page load performance.
- The "Saved Queries Library" is not a separate page in Phase 2 — `saved=true` is a metadata flag on accepted_queries for future use.
- Session preview text generation is deterministic (first message truncation) and requires no LLM involvement.
- The existing Phase 1 i18n scaffolding (T-180/T-181/T-182) provides lint rules that Phase 2 components must pass.
- Desktop-first layout with responsive breakpoints prevents layout breakage on small screens but does not constitute a full mobile experience.
- The real-LLM contract tests use HTTP-level simulation (not live API calls) to verify wire format compatibility without incurring API costs.
- Cascade delete on sessions is handled at the database level via foreign key constraints, not application-level deletion loops.
- The lifecycle invariant test framework is a testing utility, not a runtime feature — it runs only during the test suite.

## Explicitly Out of Scope

The following are NOT covered by this specification and belong to later phases:

- "Saved Queries Library" dedicated page (Phase 3)
- Session rename UX (Phase 3+; backend already supports PUT /sessions/:id)
- Full mobile shell and mobile-optimized interactions (Phase 4+)
- Constitution VII — per-database authentication and role-based access control (Phase 3)
- Constitution IV — hostile input detection and auto-suspension (Phase 3)
- Constitution IX — tamper-evident audit log with 24-month retention (Phase 3; Phase 2 lays the foundation via feedback table)
- Constitution X — token/query/cost quotas (Phase 3)
- Multi-user collaborative sessions (never — single-tenant by design)
- Source database connection management UI changes (existing UI not touched in Phase 2)
- Charts, visualizations, or any non-table result rendering
- MySQL or MS SQL Server source database support
- Cross-user search, vector-based retrieval memory, or semantic search
- SSO (SAML/OIDC) integration
- Manual editing of generated SQL before execution
- Re-running historical queries against current data

## Architectural Decision Records

The following decisions are locked for Phase 2 and MUST NOT be re-litigated during planning or implementation:

- **ADR-1**: Sessions table introduced (migration 004); accepted_queries gets session_id FK + saved + feedback columns. Cascade delete on session.
- **ADR-2**: Session preview text = first user message, hard-truncated to 60 chars + ellipsis. No LLM-generated summary.
- **ADR-3**: Implicit feedback truth table as defined in FR-036.
- **ADR-4**: saved=true is a metadata flag. No separate "Saved Queries Library" page in Phase 2.
- **ADR-5**: LLM context is conversational. Context cap configurable via admin setting (default 3, range 0–10).
- **ADR-6**: Desktop-first. Basic responsive breakpoints only.
- **ADR-7**: Syntax highlighter is lazy-loaded on SQL code block components with a custom dark theme.
- **ADR-8**: Optimistic delete with 5-second undo toast. Destructive without recovery is unacceptable.

## Constitution Mapping

| Principle | Phase 2 Status |
|-----------|---------------|
| I — Security and Data Protection | Preserved; new admin endpoints respect existing authorization |
| II — Query Validation Before Execution | Preserved; no changes to evaluator pipeline |
| III — Only Validated Knowledge Persists | Extended; sessions group attempts but each attempt remains a discrete lifecycle |
| IV — Hostile Input | Deferred to Phase 3 |
| V — LLM-Agnostic Platform | Extended; real-LLM contract tests verify wire format compatibility |
| VI — Arabic + RTL | **ACTIVATED** in Phase 2 |
| VII — Role-Appropriate Authentication | Deferred to Phase 3 |
| VIII — Centrally Brokered Database Access | Preserved |
| IX — Observability and Auditability | Foundation laid via feedback table; full audit log deferred to Phase 3 |
| X — Quotas | Deferred to Phase 3 |
| XI — Architectural Modularity | Preserved |
| XII — API Contract as Source of Truth | Preserved; new endpoints added to OpenAPI contract |
