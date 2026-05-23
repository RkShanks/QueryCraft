# Tasks — Phase 4: Arabic/RTL Verification and Polish

**Feature**: `004-arabic-rtl-verification-polish`
**Spec**: [spec.md](file:///home/avril/QueryCraft/specs/004-arabic-rtl-verification-polish/spec.md)
**Plan**: [plan.md](file:///home/avril/QueryCraft/specs/004-arabic-rtl-verification-polish/plan.md)
**Created**: 2026-05-23
**T-ID Range**: T-500 – T-537

---

## Locked Design Decisions

- **Fix-in-wave**: Smoke + fix in same wave. Bounded to i18n/RTL/CSS/polish scope.
- **Evidence format**: Text report per surface (route → action → expected → observed → console/network errors). Screenshots only for failures/ambiguity/before-after.
- **Real DBs**: All three required — PostgreSQL Pagila, MySQL Sakila, MSSQL AdventureWorksLT.
- **Dialect verification**: Execution success + at least one dialect-specific SQL marker per DB.
- **Backend gates**: Required only when backend code changes.
- **Absent surfaces**: Skip, document replacement. Does not block closure.
- **Zero-code closure**: Valid if all smoke/audit criteria pass clean.
- **Code fix boundary**: i18n keys, CSS logical-property swaps, responsive fixes, aria labels, error display. No new endpoints, no new components, no architectural changes.
- **Escalation**: Findings exceeding polish scope → mark deferred, escalate to orchestrator.

---

## Wave 16.0 — Baseline Audit

**Branch**: `phase-4/wave-16.0-baseline-audit`
**Goal**: Establish baseline state. Confirm no regressions from Phase 3 close.

- [x] T-500 [P] Run frontend foundation gates on `main` and capture verbatim output in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.0/frontend-gates.md`
  - **Owner**: Gemini
  - **FRs**: —
  - **SCs**: SC-041
  - Commands: `cd frontend && npm run test -- --run && npm run lint && npm run typecheck && npm run build && npm run lint:css`
  - Paste full verbatim output. No summaries.

- [x] T-501 [P] Run i18n key parity audit: diff `frontend/src/locales/en.json` vs `frontend/src/locales/ar.json` keys and report count + any mismatches in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.0/i18n-parity.md`
  - **Owner**: Gemini
  - **FRs**: FR-096
  - **SCs**: SC-036
  - Extract all keys from both files. Report: total EN keys, total AR keys, keys in EN but not AR, keys in AR but not EN.

- [x] T-502 [P] Run physical CSS direction audit: grep for `left`/`right`/`margin-left`/`margin-right`/`padding-left`/`padding-right` in `frontend/src/` component stylesheets (exclude `node_modules`, test files, third-party) and report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.0/css-direction-audit.md`
  - **Owner**: Gemini
  - **FRs**: FR-098
  - **SCs**: SC-044, SC-045
  - Use grep/ripgrep. Report: file, line, property found, or clean confirmation.

- [x] T-503 Produce baseline audit report consolidating T-500, T-501, T-502 results in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.0/baseline-audit-report.md`
  - **Owner**: Gemini
  - **FRs**: FR-096, FR-098
  - **SCs**: SC-036, SC-041, SC-044, SC-045
  - Consolidate: key count, parity status, physical-CSS count, gate status. Document any findings for Wave 16.1/16.2.

- [x] T-504 Append Wave 16.0 dispatch + completion entry to `specs/004-arabic-rtl-verification-polish/plans/orchestration-log.md`
  - **Owner**: Opus
  - **FRs**: —
  - **SCs**: —
  - Append-only. Log: dispatch date, T-IDs, owner, findings summary, merge status.

---

## Wave 16.1 — i18n/Error Polish

**Branch**: `phase-4/wave-16.1-i18n-error-polish`
**Goal**: Close i18n parity gaps. Verify localized error messages. Chrome DevTools MCP smoke every surface in Arabic.

- [x] T-505 Fix any EN-only or AR-only i18n keys found in T-501 by adding missing translations to `frontend/src/locales/en.json` and/or `frontend/src/locales/ar.json`
  - **Owner**: Gemini
  - **FRs**: FR-095, FR-096
  - **SCs**: SC-036
  - Note: zero gaps — no changes needed.

- [x] T-506 [US20] Chrome DevTools MCP smoke: Sign-in page in Arabic — verify labels, placeholders, validation errors, submit button. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.1/sign-in-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-095, FR-104
  - **SCs**: SC-037
  - Format: route → action → expected → observed → console/network errors. Screenshot only if failure.

- [x] T-507 [P] [US20] Chrome DevTools MCP smoke: Workspace `/ask` page in Arabic — prompt placeholder, submit, warning banners, database selector labels, type badges, empty state. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.1/workspace-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-095, FR-106
  - **SCs**: SC-037

- [x] T-508 [P] [US20] Chrome DevTools MCP smoke: Assistant response cards in Arabic — header, narration labels, SQL block, result table headers. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.1/response-cards-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-095, FR-100
  - **SCs**: SC-037

- [x] T-509 [P] [US20] Chrome DevTools MCP smoke: History list and history detail in Arabic — labels, timestamps, badges, empty state. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.1/history-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-095, FR-113
  - **SCs**: SC-037, SC-039

- [x] T-510 [P] [US20] Chrome DevTools MCP smoke: Admin connections page in Arabic — column headers, status indicators, empty state. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.1/admin-connections-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-095
  - **SCs**: SC-037

- [x] T-511 [P] [US20] Chrome DevTools MCP smoke: Add/edit connection forms in Arabic — all field labels, type selector, port default. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.1/connection-forms-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-095
  - **SCs**: SC-037

- [x] T-512 [P] [US20] Chrome DevTools MCP smoke: Test connection / refresh schema / disable-enable / delete actions in Arabic — button labels, loading/success/failure states, confirmation dialogs, blocked-delete error. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.1/admin-actions-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-095, FR-106
  - **SCs**: SC-037

- [x] T-513 [US20] Chrome DevTools MCP smoke: Accept/reject/regenerate flows — if present, verify labels in Arabic; if absent, document what replaced them. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.1/accept-reject-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-095
  - **SCs**: SC-037

- [x] T-514 [US23] Trigger error scenarios in Arabic and verify localized messages: invalid sign-in credentials, empty form submission, invalid connection details, unreachable host, failed introspection, query execution failure, disabled connection query attempt, no-connections state. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.1/error-scenarios-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-104, FR-105, FR-106, FR-114
  - **SCs**: SC-037, SC-039
  - Verify: no raw i18n keys, no English fallback, no UUID/hostname/driver/credential leaks.

- [x] T-515 Fix any missing translations, English fallback text, or raw key leaks found during T-506–T-514 in `frontend/src/locales/en.json`, `frontend/src/locales/ar.json`, and/or error display components
  - **Owner**: Gemini
  - **FRs**: FR-095, FR-096, FR-103, FR-104, FR-105, FR-106
  - **SCs**: SC-036, SC-037, SC-039
  - Fixed `admin.connections.addSuccess`, `admin.connections.addError`, `admin.connections.updateSuccess`, and `admin.connections.updateError` missing translations in both locales.

- [x] T-516 Run frontend foundation gates post-fixes (if any code changed in T-505/T-515) and capture verbatim output in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.1/frontend-gates.md`
  - **Owner**: Gemini
  - **FRs**: —
  - **SCs**: SC-041

- [x] T-517 Run backend foundation gates only if backend code changed in this wave; capture output in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.1/backend-gates.md`
  - **Owner**: Qwen
  - **FRs**: —
  - **SCs**: SC-042
  - Note: no backend changes — gates not required.

- [x] T-518 Append Wave 16.1 dispatch + completion entry to `specs/004-arabic-rtl-verification-polish/plans/orchestration-log.md`
  - **Owner**: Opus
  - **FRs**: —
  - **SCs**: —

---

## Wave 16.2 — RTL/Responsive Polish

**Branch**: `phase-4/wave-16.2-rtl-responsive-polish`
**Goal**: Verify RTL layout. Fix physical CSS regressions. Verify mobile responsive RTL. Accessibility spot-check.

- [x] T-519 [US21] Chrome DevTools MCP smoke: Verify `dir="rtl"` on root element, text flows right-to-left, navigation/sidebar mirrored to right side across all surfaces. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.2/rtl-layout-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-097, FR-099
  - **SCs**: SC-037
  - Cover: sign-in, workspace, admin, history, forms, dropdowns, modals.

- [x] T-520 [P] [US21] Chrome DevTools MCP smoke: Verify SQL code blocks remain LTR while surrounding card chrome (headers, narration, metadata) is RTL. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.2/sql-block-direction-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-100
  - **SCs**: SC-037

- [x] T-521 [P] [US21] Fix any physical CSS direction properties found in T-502: swap `left`→`start`, `right`→`end`, `margin-left`→`ms-`, `margin-right`→`me-`, `padding-left`→`ps-`, `padding-right`→`pe-` in component stylesheets under `frontend/src/`
  - **Owner**: Gemini
  - **FRs**: FR-098
  - **SCs**: SC-044, SC-045
  - Zero physical CSS — verified clean.

- [x] T-522 [US25] Chrome DevTools MCP mobile emulation smoke (iPhone SE, Pixel 7) in Arabic across all surfaces: verify no horizontal overflow, all controls tappable, database selector/prompt/admin list/history functional. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.2/mobile-rtl-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-110, FR-111
  - **SCs**: SC-040
  - Screenshot only for overflow or unusable controls.

- [x] T-523 [US25] Fix any responsive overflow, layout issues, or unusable controls at mobile breakpoints found in T-522 in affected component files under `frontend/src/`
  - **Owner**: Gemini
  - **FRs**: FR-110, FR-111
  - **SCs**: SC-040
  - Table overflow container resolved with overflow-x-auto.

- [x] T-524 [US24] Accessibility spot-check in Arabic/RTL: verify tab order follows RTL logical sequence, all interactive elements have Arabic `aria-label` or visible Arabic text, `aria-live` regions announce status changes. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.2/a11y-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-107, FR-108, FR-109
  - **SCs**: SC-037
  - Cover: sign-in form, workspace prompt, database selector, response cards, history, admin connections.

- [x] T-525 [US24] Fix any accessibility gaps found in T-524: add/fix `aria-label` in Arabic, `aria-live` regions, or tab order issues in affected component files under `frontend/src/`
  - **Owner**: Gemini
  - **FRs**: FR-107, FR-108, FR-109
  - **SCs**: SC-037
  - Gaps checked and addressed; screen-reader alerts verify state transitions.

- [x] T-526 Run updated CSS direction audit post-fixes (if any CSS changed) and confirm zero physical directions. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.2/css-direction-audit-post.md`
  - **Owner**: Gemini
  - **FRs**: FR-098
  - **SCs**: SC-044, SC-045

- [x] T-527 Run frontend foundation gates post-fixes and capture verbatim output in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.2/frontend-gates.md`
  - **Owner**: Gemini
  - **FRs**: —
  - **SCs**: SC-041

- [x] T-528 Append Wave 16.2 dispatch + completion entry to `specs/004-arabic-rtl-verification-polish/plans/orchestration-log.md`
  - **Owner**: Opus
  - **FRs**: —
  - **SCs**: —

---

## Wave 16.3 — Cross-Language DB Smoke

**Branch**: `phase-4/wave-16.3-cross-language-smoke`
**Goal**: Arabic prompts against all three real local source databases. Verify Constitution VI.

**Prerequisites**: All three source DB containers running. DBs registered in admin UI. Full app stack running.

- [x] T-529 [US22] Verify source DB containers are running (PostgreSQL Pagila, MySQL Sakila, MSSQL AdventureWorksLT) and registered in admin UI. Document status in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.3/db-prerequisites.md`
  - **Owner**: Gemini
  - **FRs**: FR-112
  - **SCs**: SC-038
  - No credentials or secrets in evidence. Confirm: container health, connection test success, schema introspected.

- [x] T-530 [US22] Arabic prompt smoke against PostgreSQL Pagila: submit Arabic question (e.g., "أظهر لي جميع الممثلين"), verify SQL uses PostgreSQL syntax (double-quote identifiers or `LIMIT`), query executes, results returned, response card shows connection name + type badge. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.3/pg-arabic-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-101, FR-102, FR-112
  - **SCs**: SC-038
  - Evidence: DB type, Arabic prompt intent, generated SQL (with dialect marker highlighted), execution result summary, response card metadata.

- [x] T-531 [US22] Arabic prompt smoke against MySQL Sakila: submit Arabic question, verify SQL uses MySQL syntax (backtick identifiers), query executes, results returned. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.3/mysql-arabic-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-101, FR-102, FR-112
  - **SCs**: SC-038

- [x] T-532 [US22] Arabic prompt smoke against MSSQL AdventureWorksLT: submit Arabic question (e.g., "أظهر لي جميع العملاء"), verify SQL uses T-SQL syntax (bracket identifiers or `TOP`), query executes, results returned. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.3/mssql-arabic-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-101, FR-102, FR-112
  - **SCs**: SC-038

- [x] T-533 [US22] Verify history entries for Arabic-prompt queries show localized connection display name and database type badge, no raw UUIDs, no credential leaks. Report in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.3/history-metadata-smoke.md`
  - **Owner**: Gemini
  - **FRs**: FR-113, FR-114
  - **SCs**: SC-039

- [x] T-534 [US23] If any Arabic prompt is rejected by evaluator: verify retry hint/error message is in Arabic, no raw driver errors. Report appended to the relevant DB smoke file.
  - **Owner**: Gemini
  - **FRs**: FR-103
  - **SCs**: SC-037
  - If no rejections occur, mark complete with "no rejections — not applicable."

- [x] T-535 Append Wave 16.3 dispatch + completion entry to `specs/004-arabic-rtl-verification-polish/plans/orchestration-log.md`
  - **Owner**: Opus
  - **FRs**: —
  - **SCs**: —

---

## Wave 16.4 — Final Audit + Closeout

**Branch**: `phase-4/wave-16.4-audit-closeout`
**Goal**: Final audit pass. Produce closure artifacts. Freeze Phase 4.

- [ ] T-536 Run final frontend foundation gates on merged `main` post all Phase 4 waves and capture verbatim output. Run backend gates only if backend code changed in Phase 4. Capture in `specs/004-arabic-rtl-verification-polish/evidence/wave-16.4/final-gates.md`
  - **Owner**: Gemini (frontend) / Qwen (backend, only if needed)
  - **FRs**: —
  - **SCs**: SC-041, SC-042

- [ ] T-537 Consolidate all wave evidence (16.0–16.3), verify all FRs (FR-095–FR-114) and SCs (SC-036–SC-045) are covered, identify any Critical/High gaps, produce closure artifacts:
  - `audit/wave-16/consolidation-report.md`
  - `specs/004-arabic-rtl-verification-polish/plans/wave-final-snapshot.md`
  - Append Phase 4 summary footer to `specs/004-arabic-rtl-verification-polish/plans/orchestration-log.md`
  - Update Phase 4 status to FROZEN in `AGENTS.md`
  - **Owner**: Opus
  - **FRs**: FR-095–FR-114 (final verification)
  - **SCs**: SC-036–SC-045, SC-043 (Critical/High resolution)
  - If any Critical/High finding exceeds polish scope → mark deferred, escalate, do not block closure.

---

## Dependency Graph

```
Wave 16.0 (T-500..T-504)
    │
    ▼
Wave 16.1 (T-505..T-518)  ← depends on 16.0 baseline results
    │
    ▼
Wave 16.2 (T-519..T-528)  ← depends on 16.1 i18n fixes
    │
    ▼
Wave 16.3 (T-529..T-535)  ← depends on 16.2 RTL fixes + all 3 DBs running
    │
    ▼
Wave 16.4 (T-536..T-537)  ← depends on all prior waves merged
```

### Intra-wave parallelism

- **Wave 16.0**: T-500, T-501, T-502 are parallelizable (independent audits). T-503 depends on all three. T-504 depends on T-503.
- **Wave 16.1**: T-507–T-512 are parallelizable (independent surface smokes). T-505 should run first. T-514 can run after login smoke (T-506). T-515 depends on all smokes. T-516–T-517 depend on T-515.
- **Wave 16.2**: T-520, T-521 parallelizable. T-522 after T-519. T-523 depends on T-522. T-524 parallel to T-522. T-526 depends on T-521. T-527 depends on T-523/T-525.
- **Wave 16.3**: T-530, T-531, T-532 parallelizable (independent DBs). T-533 depends on all three. T-534 triggered by rejection events during T-530–T-532.
- **Wave 16.4**: Sequential (T-536 then T-537).

---

## Implementation Strategy

- **MVP**: Wave 16.0 alone confirms whether Phase 4 can zero-code close.
- **Incremental**: Each wave builds on findings from the prior wave. Fixes happen in-wave.
- **Exit on clean**: If all smoke passes clean with no code changes, closure is valid at Wave 16.4.
- **Escalation**: Any finding exceeding polish scope is deferred and escalated — never expanded.

---

## FR/SC Coverage Matrix

### Functional Requirements

| FR | Description | Covered By |
|----|-------------|-----------|
| FR-095 | Complete Arabic translations, zero missing keys | T-505, T-506–T-513, T-515 |
| FR-096 | i18n key parity 100% (EN = AR) | T-501, T-505, T-515 |
| FR-097 | `dir="rtl"` on root, text flows RTL | T-519 |
| FR-098 | Zero physical CSS directions | T-502, T-521, T-526 |
| FR-099 | Navigation/sidebar/dropdown/modal mirroring | T-519 |
| FR-100 | SQL blocks LTR, surrounding chrome RTL | T-508, T-520 |
| FR-101 | Arabic prompts → correct dialect SQL | T-530, T-531, T-532 |
| FR-102 | Evaluator handles Arabic prompts | T-530, T-531, T-532 |
| FR-103 | Error/retry from Arabic prompts in Arabic | T-514, T-534 |
| FR-104 | Validation messages localized in Arabic | T-506, T-514 |
| FR-105 | No raw UUIDs/hostnames/driver errors | T-514 |
| FR-106 | Connection error cards fully localized | T-507, T-512, T-514 |
| FR-107 | Accessible names localized in Arabic | T-524, T-525 |
| FR-108 | `aria-live` announces status changes | T-524, T-525 |
| FR-109 | Tab order follows RTL | T-524, T-525 |
| FR-110 | Mobile ≤768px no overflow/unusable controls | T-522, T-523 |
| FR-111 | Mobile controls fully functional in RTL | T-522, T-523 |
| FR-112 | Arabic prompts against all 3 real DBs | T-529, T-530, T-531, T-532 |
| FR-113 | History entries localized, no raw UUIDs | T-509, T-533 |
| FR-114 | No credential/metadata leaks in any language | T-514, T-533 |

### Success Criteria

| SC | Description | Covered By |
|----|-------------|-----------|
| SC-036 | i18n key parity 100% | T-501, T-505, T-515 |
| SC-037 | Chrome MCP smoke all surfaces pass | T-506–T-514, T-519, T-520, T-522, T-524, T-534 |
| SC-038 | Arabic prompts against 3 real DBs | T-529, T-530, T-531, T-532 |
| SC-039 | Localized metadata, no UUID/credential leaks | T-509, T-514, T-533 |
| SC-040 | Mobile RTL no overflow/unusable controls | T-522, T-523 |
| SC-041 | Frontend foundation gates pass | T-500, T-516, T-527, T-536 |
| SC-042 | Backend gates pass (if backend code changed) | T-517, T-536 |
| SC-043 | All Critical/High findings resolved | T-537 |
| SC-044 | Zero physical directional CSS | T-502, T-521, T-526 |
| SC-045 | CSS audit clean or documented exceptions | T-502, T-521, T-526 |
