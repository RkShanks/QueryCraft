# Feature Specification: Arabic, RTL, and Cross-Language Verification and Polish

**Feature Branch**: `004-arabic-rtl-verification-polish`
**Created**: 2026-05-23
**Status**: Draft
**Input**: Phase 4 charter — verify and polish Arabic UI translations, RTL layout correctness, cross-language natural language query behavior, localized error/validation messages, and accessibility across every surface shipped in Phases 1–3. Fix any gaps discovered. This is a verification/polish phase, not a new product expansion.

## Context

Phases 1–3 are FROZEN. Phase 1 (PR-series through Phase 1 closure) delivered the core text-to-SQL loop with English UI and RTL-ready CSS architecture. Phase 2 (FROZEN, PR #67) shipped premium dark-mode conversational UI, Constitution VI (Arabic + RTL plumbing), real-LLM contract testing, and lifecycle invariant framework. Phase 3 (FROZEN, PR #95 closure, PR #96 real multi-dialect hardening) delivered multi-dialect SQL (PostgreSQL/MySQL/MSSQL), admin connection management, schema introspection, workspace database selector, and comprehensive i18n/RTL coverage for all new surfaces.

Phase 3 Wave 15 confirmed:
- 261 EN keys, 261 AR keys — full i18n parity.
- RTL layout mirroring verified in Chrome DevTools MCP smoke.
- All frontend gates pass (434 tests, lint/typecheck/build/stylelint clean).
- All backend gates pass (617 tests, ruff clean).
- E2E: 41 scenarios green.
- No unresolved Critical/High audit findings.

Phase 4 exists to close any remaining Arabic, RTL, cross-language, localization, accessibility, or visual polish gaps across the entire shipped product. If prior phases left zero gaps, Phase 4 becomes a pure regression-confirmation wave: smoke every surface, produce audit evidence, and close.

### Phase 3 Deferred Items (carried forward only if directly supporting Phase 4)

The following items were deferred from Phase 3. Only items marked **[PULLED]** are included in Phase 4 scope; all others remain deferred:

- **Real MySQL service smoke test**: Deferred from Phase 3. **[PULLED]** — Phase 4 multi-dialect Arabic prompt tests require real MySQL Sakila fixture (available via PR #96).
- **Real MSSQL service smoke test**: Deferred from Phase 3. **[PULLED]** — Phase 4 multi-dialect Arabic prompt tests require real MSSQL AdventureWorksLT fixture (available via PR #96).
- **`DB_CREDENTIAL_KEY` pydantic validator (M-3)**: Deferred from Phase 3. Not pulled (low severity, non-blocking).
- **`AsyncMock` test warning (L-2)**: Deferred from Phase 3. Not pulled (test-only, no production impact).
- **SSO / RBAC / multi-user**: Phase 5. Not pulled.
- **Tamper-evident audit log**: Phase 5/6. Not pulled.
- **Quotas**: Phase 5. Not pulled.
- **Hostile input detection**: Phase 6. Not pulled.
- **Mobile shell / PWA**: Phase 10+. Not pulled. (Responsive layout verification is in scope; native mobile shell is not.)

## Clarifications

None yet. Phase 4 scope is narrowly defined as verification/polish of existing behavior. Clarification questions, if any, will arise during `/speckit.clarify`.

## User Scenarios & Testing *(mandatory)*

### User Story 20 — Arabic UI Translation Completeness Across All Surfaces (Priority: P1)

As a platform user with Arabic selected as the UI language, every label, button, placeholder, tooltip, status message, error message, and empty-state message I see is in Arabic, with no English fallback text, raw i18n keys, or missing translations.

**Why this priority**: Missing translations are the most visible localization failure. A single English string in an Arabic session breaks user trust in the localization.

**Independent Test**: Switch the application language to Arabic. Navigate through every shipped surface: sign-in, workspace `/ask`, database selector, prompt input, assistant response cards, SQL/result display, accept/reject/regenerate flows, history list, history detail, admin connections page, add/edit connection form, test connection button, refresh schema button, disable/enable/delete actions, and any settings surfaces. Screenshot or record each surface. Verify zero English fallback text appears.

**Acceptance Scenarios**:

1. **Given** the user language is set to Arabic, **When** the sign-in page renders, **Then** all labels, placeholders, validation messages, and the submit button are in Arabic.

2. **Given** the user language is set to Arabic, **When** the workspace `/ask` page renders with a database selected, **Then** the prompt placeholder, database selector labels, all warning/error banners, and the submit button are in Arabic.

3. **Given** the user language is set to Arabic, **When** the assistant returns a response card, **Then** the card header (connection name, database type badge), narration text, SQL label, result table headers, and any metadata are all in Arabic where applicable. Connection display names are user-provided and remain as-is.

4. **Given** the user language is set to Arabic, **When** the history list and history detail pages render, **Then** all labels, timestamps, status indicators, database type badges, and empty-state messages are in Arabic.

5. **Given** the user language is set to Arabic, **When** the admin connections page renders (list, add form, edit form, test connection, refresh schema, disable/enable/delete), **Then** every UI string is in Arabic. No raw i18n key (e.g., `admin.connections.form.createTitle`) appears as visible text.

6. **Given** the user language is set to Arabic and any error occurs (invalid credentials, unreachable host, schema introspection failure, query execution failure), **When** the error message renders, **Then** the error is localized in Arabic with correct RTL layout.

---

### User Story 21 — RTL Layout Activation and Mirroring (Priority: P1)

As a platform user using an RTL language (Arabic), the entire UI mirrors correctly: navigation, text alignment, directional icons, form layout, dropdowns, modals, and responsive breakpoints all reflect right-to-left reading order with no physical left/right CSS regressions.

**Why this priority**: Incorrect mirroring makes the application unusable for RTL users. Even one misaligned element signals incomplete localization.

**Independent Test**: Set the language to Arabic. On each surface, verify: text aligns to the right (start), navigation and sidebars mirror, form labels and inputs are RTL, dropdown menus open from the correct edge, icons that imply direction are flipped, and no element overlaps or overflows.

**Acceptance Scenarios**:

1. **Given** the language is Arabic, **When** any page renders, **Then** the `dir="rtl"` attribute is set on the root element, and all text flows right-to-left.

2. **Given** the language is Arabic, **When** the sidebar or navigation renders, **Then** it appears on the right side (logical start), and all menu items are right-aligned.

3. **Given** the language is Arabic, **When** any form renders (sign-in, add/edit connection), **Then** labels are right-aligned, inputs flow RTL, validation messages appear on the correct side, and submit buttons are in the expected position for RTL.

4. **Given** the language is Arabic, **When** the database selector dropdown opens, **Then** it aligns to the correct edge (logical start) and the selected item indicator is on the correct side.

5. **Given** the language is Arabic, **When** response cards with SQL code blocks render, **Then** the code block content remains LTR (code is always LTR), but the surrounding card layout (headers, metadata, narration) is RTL.

6. **Given** the language is Arabic, **When** any page is viewed at mobile breakpoints (≤768px), **Then** the RTL layout does not cause horizontal overflow, unusable controls, or cut-off text.

7. **Given** the codebase is inspected, **When** CSS properties are audited, **Then** zero physical `left`/`right`/`margin-left`/`margin-right`/`padding-left`/`padding-right` directional properties exist in component stylesheets. All directional styling uses logical properties (`ms-`/`me-`/`ps-`/`pe-`/`start-`/`end-`/`inset-inline-start`/`inset-inline-end`/`text-start`/`text-end`).

---

### User Story 22 — Cross-Language Natural Language Query Behavior (Priority: P1)

As a platform user, I can submit natural language questions in Arabic (or any non-English language) and receive correctly generated SQL and result narration, regardless of the target database dialect (PostgreSQL, MySQL, MSSQL).

**Why this priority**: Constitution VI mandates language-to-SQL dialect decoupling. Arabic prompts must work as well as English prompts against all three database types.

**Independent Test**: For each of the three database types (PostgreSQL Pagila, MySQL Sakila, MSSQL AdventureWorksLT), submit the same question in Arabic (e.g., "أظهر لي جميع الممثلين" / "Show me all actors"). Verify the generated SQL is in the correct dialect, the query executes, results are returned, and the response narration is in Arabic.

**Acceptance Scenarios**:

1. **Given** the user submits an Arabic question targeting a PostgreSQL connection, **When** the LLM generates SQL, **Then** the SQL is valid PostgreSQL syntax and executes successfully against the Pagila database.

2. **Given** the user submits an Arabic question targeting a MySQL connection, **When** the LLM generates SQL, **Then** the SQL is valid MySQL syntax (backtick identifiers, MySQL functions) and executes successfully against the Sakila database.

3. **Given** the user submits an Arabic question targeting an MSSQL connection, **When** the LLM generates SQL, **Then** the SQL is valid T-SQL syntax (bracket identifiers, `TOP` instead of `LIMIT`) and executes successfully against the AdventureWorksLT database.

4. **Given** the LLM returns a narration alongside the SQL result, **When** the user's language is Arabic, **Then** the narration is in Arabic or at minimum the UI wrapper labels are in Arabic.

5. **Given** the user submits an Arabic question that causes a dialect validation failure, **When** the evaluator rejects and retries, **Then** the retry hint, error messages, and any refusal card are in Arabic.

---

### User Story 23 — Localized Validation and Error Messages (Priority: P1)

As a platform user or administrator using Arabic, every validation message, error banner, and status notification is localized — no raw English error text, no raw i18n keys, no UUID fallbacks, and no internal metadata leaks.

**Why this priority**: Unlocalized error messages break the Arabic experience and may leak internal information (UUIDs, hostnames, driver errors).

**Independent Test**: Trigger every known error scenario in Arabic: invalid sign-in credentials, empty form submission, invalid connection details, unreachable host, failed introspection, query execution failure, disabled connection query attempt, and no-connections state. Verify all messages are in Arabic and contain no leaked internal metadata.

**Acceptance Scenarios**:

1. **Given** the user's language is Arabic and sign-in credentials are invalid, **When** the sign-in form submits, **Then** the error message is in Arabic.

2. **Given** the admin's language is Arabic and they add a connection with invalid credentials, **When** they test the connection, **Then** the error message is in Arabic and does not expose the raw driver error or password.

3. **Given** any error message renders in Arabic, **When** the message text is inspected, **Then** it contains no raw UUIDs, no raw hostnames/ports, no raw driver error strings, and no English-only fallback text.

4. **Given** the workspace shows a connection-related error (disabled, unhealthy, no schema, no connections), **When** the error card renders, **Then** the message and suggested action are in Arabic.

5. **Given** the admin's language is Arabic and a hard-delete is blocked due to referential integrity, **When** the error message renders, **Then** it is in Arabic and explains the constraint without exposing database internals.

---

### User Story 24 — Accessibility for Arabic/RTL Flows (Priority: P2)

As a platform user using assistive technology (screen reader, keyboard navigation) with Arabic selected, all interactive elements are labeled, focusable, and navigable in RTL order, and status changes are announced via live regions.

**Why this priority**: Accessibility ensures all Arabic-speaking users, including those with disabilities, can use the platform. While not blocking for launch, RTL accessibility gaps are difficult to retrofit.

**Independent Test**: Use a screen reader (or ARIA inspection tool) with Arabic selected. Tab through the sign-in form, workspace prompt, database selector, response cards, history list, and admin connections page. Verify logical tab order follows RTL, all interactive elements have Arabic `aria-label` or visible Arabic text, and live regions announce status updates.

**Acceptance Scenarios**:

1. **Given** the language is Arabic, **When** the user tabs through any form (sign-in, add/edit connection), **Then** focus order follows RTL logical sequence (right-to-left, top-to-bottom).

2. **Given** the language is Arabic, **When** the database selector is focused, **Then** the listbox role, options, and selected state are announced in Arabic.

3. **Given** the language is Arabic, **When** a status change occurs (connection tested, schema refreshed, query submitted), **Then** an `aria-live` region announces the update.

4. **Given** the language is Arabic, **When** interactive elements are inspected, **Then** all have `aria-label` attributes with Arabic text, or have visible Arabic text labels that serve as the accessible name.

---

### User Story 25 — Responsive RTL Mobile Layout (Priority: P2)

As a platform user on a mobile device with Arabic selected, the entire UI is usable: no horizontal overflow, no cut-off text, no unusable controls, and navigation remains accessible.

**Why this priority**: Mobile responsive layout in RTL is a common regression point. Overflow and control occlusion make the app unusable.

**Independent Test**: Open every shipped surface in Chrome DevTools mobile emulation (iPhone SE, Pixel 7) with Arabic selected. Verify no horizontal scrollbar, no text cutoff, all buttons are tappable, and navigation works.

**Acceptance Scenarios**:

1. **Given** the language is Arabic and the viewport is ≤768px, **When** the sign-in page renders, **Then** the form is fully visible with no horizontal overflow.

2. **Given** the language is Arabic and the viewport is ≤768px, **When** the workspace renders with database selector and prompt, **Then** all controls are usable, the selector opens without overflow, and the prompt input is full-width.

3. **Given** the language is Arabic and the viewport is ≤768px, **When** the admin connections page renders, **Then** the connection list is scrollable, action buttons are accessible, and no content is cut off.

4. **Given** the language is Arabic and the viewport is ≤768px, **When** the history list and detail pages render, **Then** all content is visible and scrollable without horizontal overflow.

---

### Edge Cases

- What happens when an i18n key exists in EN but not AR? The i18n framework falls back to the EN string, which appears as English text in an Arabic session. Phase 4 treats this as a defect and fixes it.
- What happens when an i18n key exists in AR but not EN? Reverse parity gap. Phase 4 fixes by adding the missing EN key.
- What happens when the LLM narration is in English despite an Arabic prompt? The LLM's response language is not fully controllable. The UI wrapper labels (card headers, metadata) must be in Arabic. If the LLM responds in English, that is acceptable for Phase 4; forcing LLM response language is out of scope.
- What happens when a database-type badge displays a technical identifier in Arabic mode? The badge text (e.g., "PostgreSQL", "MySQL", "MSSQL") is a technical brand name and remains as-is regardless of language. Only the surrounding UI labels are localized.
- What happens when a connection display name is in English but the UI is Arabic? Display names are user-provided and remain as entered. The surrounding chrome (labels, headers, actions) must be in Arabic.
- What happens when the user switches language mid-session? The UI re-renders in the selected language. Existing chat turns retain their content but UI chrome (headers, labels, metadata) updates to the new language.

## Requirements *(mandatory)*

### Functional Requirements

#### Arabic Translation Completeness

- **FR-095**: Every shipped UI surface (sign-in, workspace `/ask`, database selector, prompt input, warning/error banners, assistant response cards, SQL/result display, accept/reject/regenerate flows, history list, history detail, admin connections page, add/edit connection form, test connection button, refresh schema button, disable/enable/delete actions, settings/admin surfaces) MUST have complete Arabic translations with zero missing i18n keys. No English fallback text may appear when the language is set to Arabic.
- **FR-096**: Every English i18n key MUST have a corresponding Arabic key, and vice versa. Key parity MUST be 100%.

#### RTL Layout Correctness

- **FR-097**: When the UI language is set to Arabic (or any RTL language), `dir="rtl"` MUST be applied to the root element, and all text MUST flow right-to-left.
- **FR-098**: All CSS directional styling MUST use logical properties exclusively. Zero physical `left`/`right`/`margin-left`/`margin-right`/`padding-left`/`padding-right` properties may exist in component stylesheets. Tailwind classes must use `ms-`/`me-`/`ps-`/`pe-`/`start-`/`end-`/`text-start`/`text-end`/`rounded-ss-`/`rounded-se-`/`rounded-es-`/`rounded-ee-`.
- **FR-099**: Navigation, sidebars, dropdowns, modals, and form layouts MUST mirror correctly in RTL mode. Dropdown menus MUST open from the logical-start edge.
- **FR-100**: SQL code blocks within response cards MUST remain LTR (code is universally LTR). Surrounding card chrome (headers, narration, metadata) MUST be RTL.

#### Cross-Language Query Behavior

- **FR-101**: Arabic natural language prompts MUST produce correctly generated SQL in the target database dialect (PostgreSQL, MySQL, T-SQL) without dialect regression compared to English prompts.
- **FR-102**: The evaluator MUST handle Arabic prompts without rejecting them due to language-specific parsing issues. Dialect validation rules MUST be language-agnostic (they validate SQL structure, not prompt language).
- **FR-103**: Error messages, retry hints, and refusal cards resulting from Arabic prompt submissions MUST be in Arabic when the UI language is Arabic.

#### Localized Error and Validation Messages

- **FR-104**: All validation messages (form validation, empty fields, invalid input) MUST be localized in Arabic when the UI language is Arabic.
- **FR-105**: All error messages surfaced to the user or admin MUST NOT expose raw UUIDs, raw hostnames/ports, raw driver error strings, raw stack traces, or credentials. This applies to both English and Arabic.
- **FR-106**: Connection-related error cards in the workspace (disabled, unhealthy, no schema, no connections, query failure) MUST be fully localized.

#### Accessibility

- **FR-107**: All interactive elements MUST have accessible names (via `aria-label` or visible text) that are localized in Arabic when the UI language is Arabic.
- **FR-108**: Status changes (connection tested, schema refreshed, query submitted, error occurred) MUST be announced via `aria-live` regions.
- **FR-109**: Keyboard tab order MUST follow the logical RTL sequence when the language is Arabic.

#### Responsive RTL

- **FR-110**: At mobile viewports (≤768px) with Arabic selected, no surface may exhibit horizontal overflow, cut-off text, or unusable controls.
- **FR-111**: The database selector, prompt input, admin connections list, and history list MUST remain fully functional at mobile breakpoints in RTL mode.

#### Multi-Dialect Arabic Prompts (Smoke)

- **FR-112**: Arabic prompts MUST be tested against all three real local source databases (PostgreSQL Pagila, MySQL Sakila, MSSQL AdventureWorksLT) using the fixtures delivered in PR #96. SQL MUST generate in the correct dialect and execute successfully.
- **FR-113**: History entries for Arabic-prompt queries MUST show localized connection display name and database type badge, not raw UUIDs or internal metadata.

#### Security — No Metadata Leaks

- **FR-114**: No credential, internal identifier, raw UUID, or internal metadata field may leak to the frontend in any language mode. This is a re-verification of Constitution I across all surfaces in both English and Arabic.

### Key Entities

No new entities are introduced in Phase 4. This phase operates on existing entities:

- **i18n locale files** (`en.json`, `ar.json`): Verified and patched for parity and translation quality.
- **CSS stylesheets and Tailwind classes**: Audited and fixed for logical-property compliance.
- **Existing UI components**: All components from Phases 1–3 are smoke-tested, not redesigned.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-036**: i18n key parity is 100% (EN and AR have identical key sets). No missing keys in either language.
- **SC-037**: Chrome DevTools MCP smoke passes for all listed surfaces (sign-in, workspace, database selector, prompt input, response cards, SQL display, history list, history detail, admin connections, add/edit form, test connection, refresh schema, disable/enable/delete) in Arabic/RTL mode — zero console errors related to missing keys, zero English fallback text visible.
- **SC-038**: Arabic prompts work against PostgreSQL (Pagila), MySQL (Sakila), and MSSQL (AdventureWorksLT) without dialect regression. Correct SQL dialect is generated and executed for each.
- **SC-039**: Response cards, history entries, and admin surfaces show localized friendly metadata in Arabic mode — no raw UUID fallback, no credential leaks, no internal identifiers visible.
- **SC-040**: Mobile RTL layout (≤768px) has no horizontal overflow or unusable controls on any shipped surface.
- **SC-041**: All frontend foundation gates pass: `npm run test`, `npm run lint`, `npm run typecheck`, `npm run build`, `npm run lint:css`.
- **SC-042**: Backend foundation gates pass if any backend changes are required: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`.
- **SC-043**: All Critical/High audit findings from Phase 4 audit are resolved before Phase 4 closure.
- **SC-044**: Zero physical directional CSS properties (`left`/`right`/`margin-left`/`margin-right`/`padding-left`/`padding-right`) exist in shipped component stylesheets.
- **SC-045**: CSS audit produces a clean report or a documented exception list (e.g., third-party library styles that cannot be modified).

## Assumptions

- Phases 1–3 are FROZEN and their code is the starting baseline.
- The i18n framework (react-i18next) is already configured with `querystring` language detection and locale files at `frontend/src/locales/{en,ar}.json`.
- PR #96 has already merged and `main` includes MySQL Sakila + MSSQL AdventureWorksLT local source DB fixtures.
- The provisional admin remains the only user. SSO/RBAC is Phase 5.
- LLM response language is not fully controllable. If the LLM narrates in English despite an Arabic prompt, that is acceptable. UI wrapper labels must be in Arabic.
- Database-type badge text ("PostgreSQL", "MySQL", "MSSQL") is a technical brand name and stays as-is in both languages.
- Connection display names are user-provided and remain as entered regardless of UI language.
- Code (SQL) within code blocks always renders LTR regardless of UI language direction.
- "Responsive" means the existing responsive breakpoints from Phases 1–3; no new mobile-specific layouts are designed.
- If zero gaps are found during smoke/audit, Phase 4 closes with a clean audit report and no code changes beyond test evidence.
- Chart axis flipping for RTL is explicitly out of scope (charts may stay LTR in v1).

## Explicitly Out of Scope

The following are NOT covered by this specification and belong to later phases:

- **Voice input**: Not on current roadmap.
- **New major product screens**: Phase 4 is verification/polish only.
- **Right-to-left chart axis flipping**: Charts stay LTR for v1.
- **SSO / RBAC / multi-user / row-column security**: Phase 5.
- **Tamper-evident audit log / quotas / injection detection**: Phase 6.
- **Admin dashboard (expanded)**: Phase 7.
- **Scheduled reports and notifications**: Phase 8.
- **Semantic search of accepted queries**: Phase 9.
- **Mobile shell / PWA**: Phase 10+.
- **Multi-tenant support**: Phase 10+.
- **Saved Queries Library page**: Deferred from Phase 2. Not pulled.
- **Session rename UX**: Deferred from Phase 2. Not pulled.
- **DB_CREDENTIAL_KEY pydantic validator (M-3)**: Deferred from Phase 3. Not pulled.
- **AsyncMock test warning (L-2)**: Deferred from Phase 3. Not pulled.
- **Automatic/periodic schema re-introspection**: Future enhancement.
- **Forcing LLM response language**: Out of scope; LLM narration language is best-effort.

## Architectural Decision Records

No new ADRs are introduced. Phase 4 operates within existing architecture. The following prior ADRs remain in effect:

- **ADR-9 — DB Credential Storage**: LOCKED (Phase 3). Credentials remain Fernet-encrypted.
- **ADR-10 — Driver/Library Choices**: LOCKED (Phase 3). asyncpg/asyncmy/aioodbc remain.
- **ADR-13 — Selected Connection UX**: LOCKED (Phase 3). Per-session selection persists.
- **ADR-14 — Frontend Icon Library**: LOCKED (Phase 3). lucide-react only.
- **ADR-15 — Chrome DevTools MCP Smoke Requirements**: LOCKED (Phase 3). MCP smoke required for every surface.

## Constitution Mapping

| Principle | Phase 4 Status |
|-----------|---------------|
| I — Security and Data Protection | Re-verified; no credential/metadata leaks in Arabic mode |
| II — Query Validation Before Execution | Preserved; evaluator works with Arabic prompts |
| III — Only Validated Knowledge Persists | Preserved; no changes |
| IV — Hostile Input | Deferred to Phase 6 |
| V — LLM-Agnostic Platform | Preserved |
| VI — Language Decoupled from SQL Dialect | **VERIFIED**; Arabic prompts → correct PG/MySQL/T-SQL |
| VII — Role-Appropriate Authentication | Deferred to Phase 5 |
| VIII — Centrally Brokered Database Access | Preserved |
| IX — Observability and Auditability | Deferred to Phase 5 |
| X — Quotas | Deferred to Phase 5 |
| XI — Architectural Modularity | Preserved |
| XII — API Contract as Source of Truth | Preserved |

## Surfaces to Verify

The following is the exhaustive list of UI surfaces that must be smoke-tested in Arabic/RTL:

| # | Surface | Notes |
|---|---------|-------|
| 1 | Sign-in page | Labels, placeholders, validation, submit button |
| 2 | Workspace `/ask` | Prompt input, placeholder, submit button |
| 3 | Database selector | Display names, type badges, empty state |
| 4 | Prompt input area | Placeholder, disabled state message, submit |
| 5 | Warning/error banners | All banner variants |
| 6 | Assistant response cards | Header, narration, SQL block, result table |
| 7 | SQL/result display | Code block LTR, table headers localized |
| 8 | Accept/reject/regenerate flows | If still present, button labels |
| 9 | History list | Connection names, types, timestamps, empty state |
| 10 | History detail | Full query detail view |
| 11 | Admin connections page | Column headers, status indicators, empty state |
| 12 | Add connection form | All field labels, type selector, port default |
| 13 | Edit connection form | Pre-filled fields, password placeholder |
| 14 | Test connection button | Loading, success, failure states |
| 15 | Refresh schema button | Loading, success, failure states |
| 16 | Disable/enable actions | Button labels, confirmation |
| 17 | Delete action | Confirmation dialog, blocked-delete error |
| 18 | Mobile layout (≤768px) | All above at mobile breakpoints |
