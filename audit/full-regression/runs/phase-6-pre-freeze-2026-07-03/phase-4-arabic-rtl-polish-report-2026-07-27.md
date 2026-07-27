# Phase 4 Arabic RTL Polish Regression Report

Run date: 2026-07-27

Scope: Phase 4 only, all twenty Arabic RTL matrix rows.

Tested product: `main` at `76a918f18239631668f7c60ec05674f40cea4622`.

## Result

All 20 required Phase 4 rows passed. The final current-head browser run used
Arabic RTL on the real local application, with service workers disabled in the
temporary browser context so it loaded the rebuilt current bundle. No browser
state, credential values, request bodies, traces, or screenshots were retained.

| ID | Task | Status | Evidence | Notes |
|---|---|---|---|---|
| P4-FR-095 | Complete Arabic shipped surfaces | Pass | Current real-browser Arabic sign-in, workspace, source selector, History, Admin Connections, and form checks; i18n gate: 10 tests | No unintended English fallback observed outside allowed technical names and SQL. |
| P4-FR-096 | EN/AR key parity | Pass | Current locale gate: 308 tests | Locale parity remained complete. |
| P4-FR-097 | RTL root and text flow | Pass | Chrome DevTools current bundle: `html[lang=ar][dir=rtl]`, `.app-shell[dir=rtl]` | Desktop and mobile RTL shell checks passed. |
| P4-FR-098 | Logical-direction CSS | Pass | Current `no-physical` gate: 4 tests; PR #212/#213 CSS uses logical properties | No new physical-direction workaround. |
| P4-FR-099 | Mirrored chrome, dropdowns, modals, forms | Pass | Chrome DevTools current bundle: sidebar at RTL logical start; selector RTL/logically aligned/all options visible; Admin form RTL/in viewport; PR #213 regression | PR #213 fixed a detected block-end selector clipping defect. |
| P4-FR-100 | SQL remains LTR in RTL chrome | Pass | Current real browser History detail: visible SQL blocks LTR while shell RTL; valid response-card evidence retained from the three-dialect run | SQL remained inspectable without document overflow. |
| P4-FR-101 | Arabic dialect SQL and execution | Pass | Real QueryCraft pipeline evidence: PostgreSQL actor count 200, MySQL actor count 200, MSSQL `TOP` query success after PR #211 | Dialect markers were appropriate; source execution was read-only. |
| P4-FR-102 | Language-independent evaluator | Pass | Controlled Arabic two-SELECT T-SQL pipeline refusal; PR #211 dialect-aware evaluator tests and green CI | Valid Arabic MSSQL `TOP` SQL reaches execution; multi-statement SQL does not. |
| P4-FR-103 | Arabic query errors/refusals | Pass | Controlled Arabic pipeline produced sanitized HTTP 422 and localized browser refusal | No result table or accepted history entry was created. |
| P4-FR-104 | Arabic validation localization | Pass | Current validation/i18n gates and Arabic Admin form validation browser check | Empty/invalid form feedback remained localized and sanitized. |
| P4-FR-105 | Sanitized user/admin errors | Pass | Controlled refusal, invalid sign-in/form/connection checks, and current browser/API leakage sweep | No UUID, host, port, driver, credential, stack, or provider detail rendered. |
| P4-FR-106 | Localized connection-state errors | Pass | Arabic health/introspection/connection-state browser coverage and current message-key gates | Disabled, unhealthy, and invalid-state feedback remains localized. |
| P4-FR-107 | Localized accessible names | Pass | Current Chrome DevTools DOM check: 19 visible interactive controls, all named; 18 Arabic names | Arabic Admin form controls were also named. |
| P4-FR-108 | `aria-live` announcements | Pass | Current real connection test: changed Arabic status contained by a visible `aria-live=polite` region; PR #209 coverage | Query, connection, and schema status controls use polite announcements. |
| P4-FR-109 | Logical keyboard tab order | Pass | Current real keyboard traversal: sidebar toggle, navigation destinations including History/Settings/Connections/Roles/Audit/Quotas/Detection, then workspace controls | All sampled focus targets were visible; no trap or skipped critical navigation control. |
| P4-FR-110 | Mobile RTL visual usability | Pass | Current real app at 375px and 768px: no document horizontal overflow, reachable toggle, reserved collapsed rail, no clipped critical control | Sidebar cycle passed at both widths. |
| P4-FR-111 | Mobile selector, prompt, Admin, History | Pass | Current real app at 375px and 768px: source selection, prompt enablement, safe Admin form open/cancel, History detail, and LTR code all worked | No page-level overflow or hidden critical action. |
| P4-FR-112 | Arabic prompts against all source DBs | Pass | Real QueryCraft pipeline results: PostgreSQL 200, MySQL 200, MSSQL 847 | Live Gemini evidence was retained where available; deterministic provider was used only for controlled evaluator refusal. |
| P4-FR-113 | Arabic History friendly metadata | Pass | Current Chrome DevTools History list/detail: friendly connection metadata and type badge; SQL LTR; no UUID | History UI chrome remained RTL. |
| P4-FR-114 | Final privacy/raw-key sweep | Pass | Current desktop/mobile DOM scans plus backend privacy/message/audit gates | No raw i18n key, internal identifier, host/port, credential, stack trace, provider error, cookie, or token was recorded. |

## Current Browser Evidence

- Desktop Arabic RTL: navigation/sidebar placement, source selector anchoring,
  Admin add form, History detail, SQL direction, accessible names, connection
  test polite live status, keyboard focus traversal, and privacy sweep passed.
- Mobile Arabic RTL: at both 375px and 768px, expanded/collapsed/expanded
  sidebar transitions kept the toggle reachable; workspace reserved the
  collapsed rail; selector and prompt worked; safe Admin form and History
  detail opened; SQL stayed LTR; and `scrollWidth <= clientWidth` held.
- Controlled Arabic safety path: a private-network temporary Ollama-compatible
  provider supplied harmless multi-statement T-SQL through the real submit
  pipeline. The evaluator rejected it with sanitized 422 before adapter
  execution, and the browser showed the localized Arabic refusal. Temporary
  provider and credential helper files were removed.

## Automated and Fix Evidence

- Current local frontend verification for PR #213: RTL Playwright suite (5
  passed), full Vitest suite (63 files, 769 tests), lint, typecheck, build, CSS
  lint, and `rtk git diff --check` all passed. The build emitted only the known
  chunk-size advisory.
- PR #209: polite `aria-live` regressions for submit, connection test, and
  schema refresh, merged with green backend and frontend CI.
- PR #211: dialect-aware single-statement evaluator, including valid MSSQL
  `TOP` execution and multi-statement rejection, merged with green CI.
- PR #212: mobile RTL sidebar reachability at 375px and 768px, merged with
  green CI.
- PR #213: source-selector viewport regression, merged with green CI. It
  changed only the selector's logical block placement and its Playwright test.

## Counts

| Status | Count |
|---|---:|
| Pass | 20 |
| Fail | 0 |
| Partial | 0 |
| Setup-dependent | 0 |
| Not run | 0 |
| Deferred | 0 |

Phase 4 is complete. Phase 5 is unblocked.
