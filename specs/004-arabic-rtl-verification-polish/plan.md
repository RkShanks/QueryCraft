# Implementation Plan — Phase 4: Arabic/RTL Verification and Polish

**Created**: 2026-05-23
**Phase**: 4
**Spec**: [spec.md](file:///home/avril/QueryCraft/specs/004-arabic-rtl-verification-polish/spec.md)
**Research**: [research.md](file:///home/avril/QueryCraft/specs/004-arabic-rtl-verification-polish/research.md)
**Data Model**: [data-model.md](file:///home/avril/QueryCraft/specs/004-arabic-rtl-verification-polish/data-model.md)

---

## Technical Context

| Item | Value |
|------|-------|
| Backend | FastAPI, Python 3.12, SQLAlchemy 2, Alembic, asyncpg/asyncmy/aioodbc |
| Frontend | React 19, Tailwind v4, Vite, TanStack Query, react-i18next, lucide-react |
| i18n | `frontend/src/locales/{en,ar}.json` — 261 EN keys, 261 AR keys (100% parity at Phase 3 close) |
| RTL | `dir="rtl"` on root via `querystring` language detection; logical Tailwind directions |
| Source DBs | PostgreSQL Pagila, MySQL Sakila (PR #96), MSSQL AdventureWorksLT (PR #96) |
| LLM | Gemini (default), provider-agnostic |
| Phase 3 closure | PR #95 (closure), PR #96 (real multi-dialect hardening). All 82 tasks, 36 FRs, 11 SCs complete. |

## Constitution Check

| Principle | Phase 4 Status | Notes |
|-----------|---------------|-------|
| I — Security | ✅ RE-VERIFIED | No credential/metadata leaks in Arabic mode |
| II — Query Validation | ✅ Preserved | Evaluator works with Arabic prompts |
| III — Validated Knowledge | ✅ Preserved | No changes |
| IV — Hostile Input | ⏸️ Deferred | Phase 6 |
| V — LLM-Agnostic | ✅ Preserved | No changes |
| VI — Language ↔ Dialect | ✅ **VERIFIED** | Arabic prompts → correct PG/MySQL/T-SQL (smoke required) |
| VII — Role Auth | ⏸️ Deferred | Phase 5 |
| VIII — Brokered DB Access | ✅ Preserved | No changes |
| IX — Audit | ⏸️ Deferred | Phase 5 |
| X — Quotas | ⏸️ Deferred | Phase 5 |
| XI — Modularity | ✅ Preserved | No changes |
| XII — API Contract | ✅ Preserved | No changes |

**§11 Phased Rollout**: Principle VI (Arabic + RTL) is triggered at Phase 4. This plan verifies full compliance.

## Locked Decisions

All design decisions inherited from Phases 1–3. No new ADRs. Key Phase 4 decisions:

- **Fix-in-wave**: Smoke + fix in same wave. Bounded to i18n/RTL/CSS/polish scope.
- **Evidence format**: Text report per surface. Screenshots only for failures/ambiguity/before-after.
- **Real DBs**: All three required for closure (PG Pagila, MySQL Sakila, MSSQL AdventureWorksLT).
- **Dialect verification**: Execution success + at least one dialect-specific SQL marker per DB.
- **Backend gates**: Required only when backend code changes.
- **Absent surfaces**: Skip, document replacement. Does not block closure.
- **Zero-code closure**: Valid if all smoke/audit criteria pass clean.

---

## Wave Structure

### Wave 16.0 — Baseline Audit, Instrumentation, Plan Kickoff

**Branch**: `phase-4/wave-16.0-baseline-audit`
**Owner**: Frontend Implementer (Gemini)
**Depends on**: Phase 3 merged + FROZEN on `main`

**Goal**: Establish baseline state. Run automated audits. Confirm no regressions from Phase 3 close. Initialize orchestration log.

**Scope**:
- Run frontend foundation gates on `main` to confirm baseline green
- Run i18n key parity check: `en.json` vs `ar.json` (script or manual diff)
- Run physical CSS direction audit: grep for `left`/`right`/`margin-left`/`margin-right`/`padding-left`/`padding-right` in component stylesheets (exclude `node_modules`, test files, third-party)
- Produce baseline audit report: key count, parity status, physical-CSS count, gate status
- Initialize `specs/004-arabic-rtl-verification-polish/plans/orchestration-log.md`
- If parity or CSS issues found → document findings for Wave 16.1/16.2 respectively

**Surfaces**: None directly — this is instrumentation.

**Evidence required**:
- Frontend gate verbatim output (test, lint, typecheck, build, lint:css)
- i18n parity report (key diff)
- Physical CSS audit results (grep output or clean confirmation)
- No screenshots required (no browser work in this wave)

**Backend gates**: Not required (no backend changes).

**FRs**: FR-096 (parity baseline), FR-098 (CSS audit baseline)
**SCs**: SC-036, SC-041, SC-044, SC-045

---

### Wave 16.1 — Arabic/i18n Key Parity and Localized Error Polish

**Branch**: `phase-4/wave-16.1-i18n-error-polish`
**Owner**: Frontend Implementer (Gemini)
**Depends on**: Wave 16.0 merged

**Goal**: Close any i18n parity gaps. Verify every localized error message. Fix missing translations. Smoke every error scenario in Arabic.

**Scope**:
- Fix any EN-only or AR-only keys found in Wave 16.0
- Chrome DevTools MCP smoke each surface in Arabic (language=ar):
  1. Sign-in page — labels, placeholders, validation errors, submit
  2. Workspace `/ask` — prompt placeholder, submit, warning banners
  3. Database selector — display names, type badges, empty state
  4. Assistant response cards — header, narration labels, SQL block, table
  5. History list and detail — labels, timestamps, badges, empty state
  6. Admin connections page — column headers, status indicators, empty state
  7. Add/edit connection forms — all field labels, type selector, port default
  8. Test connection / refresh schema — loading, success, failure states
  9. Disable/enable/delete — button labels, confirmation, blocked-delete error
- Trigger error scenarios in Arabic: invalid sign-in, empty form, invalid connection, unreachable host, failed introspection, query failure, disabled connection, no connections
- Verify no raw i18n keys, no English fallback, no UUID/hostname/driver leaks
- Fix any missing translation or English fallback text found during smoke
- For surfaces confirmed absent (e.g., accept/reject/regenerate if removed): document what replaced them, skip

**Surfaces**: All 17 surfaces from spec table (rows 1–17). Row 8 (accept/reject/regenerate): skip if absent, document replacement.

**Evidence required**:
- Text report per surface: route → action → expected → observed → console/network errors
- Screenshots: only for failures, unexpected behavior, visual ambiguity, or before/after proof of fix
- Updated i18n key parity count (post-fix if any fixes made)

**Backend gates**: Required only if any backend i18n/error key changes.

**Code fix boundary**: Add/fix i18n keys in `en.json`/`ar.json`. Fix error message display components. No new endpoints, no new surfaces, no architectural changes.

**FRs**: FR-095, FR-096, FR-103, FR-104, FR-105, FR-106, FR-113, FR-114
**SCs**: SC-036, SC-037, SC-039

---

### Wave 16.2 — RTL Layout and Responsive Browser Polish

**Branch**: `phase-4/wave-16.2-rtl-responsive-polish`
**Owner**: Frontend Implementer (Gemini)
**Depends on**: Wave 16.1 merged

**Goal**: Verify RTL layout correctness on every surface. Fix any physical CSS regressions. Verify mobile responsive RTL.

**Scope**:
- Chrome DevTools MCP: verify Arabic/RTL on each surface:
  1. `dir="rtl"` on root element
  2. Text flows right-to-left
  3. Navigation/sidebar on right (logical start)
  4. Form labels/inputs RTL, validation on correct side
  5. Dropdowns open from logical-start edge
  6. SQL code blocks remain LTR, surrounding chrome is RTL
  7. Directional icons flipped where applicable
- Mobile emulation (iPhone SE, Pixel 7) in Arabic:
  - No horizontal overflow
  - All controls tappable
  - Database selector, prompt input, admin list, history fully functional
- Fix any physical CSS directions found: `left`→`start`, `right`→`end`, `margin-left`→`ms-`, etc.
- Fix any layout overflow or element overlap found
- Accessibility spot-check: tab order follows RTL, `aria-label` in Arabic, `aria-live` regions announce status

**Surfaces**: All 18 surfaces from spec table (rows 1–18, including mobile row 18).

**Evidence required**:
- Text report per surface (desktop RTL + mobile RTL): route → action → expected → observed → errors
- Screenshots: only for failures, overflow, misalignment, or before/after proof of fix
- Updated CSS audit (post-fix if any fixes made)

**Backend gates**: Not required (CSS/layout changes only).

**Code fix boundary**: CSS classes (physical→logical), Tailwind utility swaps, responsive breakpoint fixes. No new components, no new endpoints.

**FRs**: FR-097, FR-098, FR-099, FR-100, FR-107, FR-108, FR-109, FR-110, FR-111
**SCs**: SC-037, SC-040, SC-044, SC-045

---

### Wave 16.3 — Cross-Language Real DB Smoke (PostgreSQL, MySQL, MSSQL)

**Branch**: `phase-4/wave-16.3-cross-language-smoke`
**Owner**: Frontend Implementer (Gemini) — drives browser. Backend Implementer (Qwen) only if backend fixes needed.
**Depends on**: Wave 16.2 merged

**Goal**: Submit Arabic prompts against all three real local source databases. Verify Constitution VI: language decoupled from SQL dialect.

**Prerequisites**:
- All three source DB containers running:
  ```bash
  docker compose -f docker-compose.dev.yml up -d postgres-source mysql-source mssql-source
  ./scripts/restore-mssql.sh
  ```
- Source DBs registered in admin UI with correct connection params (see `dbTest/README.md`)
- Full app stack running (`./scripts/dev-up.sh --rebuild`)

**Scope**:
- For each real database, submit at least one Arabic prompt:
  - **PostgreSQL Pagila**: e.g., "أظهر لي جميع الممثلين" (Show me all actors)
    - Verify: SQL uses PostgreSQL syntax (double-quote identifiers or `LIMIT`)
    - Verify: query executes, results returned
  - **MySQL Sakila**: e.g., "أظهر لي جميع الممثلين" (Show me all actors)
    - Verify: SQL uses MySQL syntax (backtick identifiers)
    - Verify: query executes, results returned
  - **MSSQL AdventureWorksLT**: e.g., "أظهر لي جميع العملاء" (Show me all customers)
    - Verify: SQL uses T-SQL syntax (bracket identifiers or `TOP`)
    - Verify: query executes, results returned
- Verify response card: connection name + type badge displayed correctly in Arabic UI
- Verify history entries: connection display name + type, no raw UUIDs, no credential leaks
- If evaluator rejects Arabic prompt: verify retry hint/error in Arabic
- Mid-session DB switch: verify prior turns keep original metadata

**Surfaces**: Workspace `/ask`, database selector, response cards, history list/detail.

**Evidence required**:
- Per-DB text report: Arabic prompt → generated SQL (with dialect marker highlighted) → execution result → response card → history entry
- Screenshots: only if query fails, dialect marker absent, or unexpected behavior

**Backend gates**: Required only if backend changes are needed (e.g., prompt builder fix for Arabic). If all queries succeed with no backend changes, backend gates are not required.

**Code fix boundary**: Prompt builder i18n hints, error message localization. No new dialect support, no new DB types, no schema changes.

**FRs**: FR-101, FR-102, FR-103, FR-112, FR-113, FR-114
**SCs**: SC-038, SC-039

---

### Wave 16.4 — Final Audit, Closeout, and Snapshot

**Branch**: `phase-4/wave-16.4-audit-closeout`
**Owner**: Orchestrator (Opus) + Frontend Implementer (Gemini) for any final fixes
**Depends on**: Wave 16.3 merged

**Goal**: Final audit pass. Fix any remaining Critical/High findings. Produce closure artifacts.

**Scope**:
- Run final frontend foundation gates on merged `main`
- Run final backend foundation gates (only if backend code changed in Phase 4)
- Consolidate all wave evidence:
  - Wave 16.0 baseline audit
  - Wave 16.1 i18n/error smoke
  - Wave 16.2 RTL/responsive smoke
  - Wave 16.3 cross-language DB smoke
- Verify all FRs (FR-095 through FR-114) are covered by evidence
- Verify all SCs (SC-036 through SC-045) are met
- Identify any Critical/High gaps → fix before closure (bounded to polish scope)
- If any finding exceeds polish scope → mark deferred, escalate
- Produce closure artifacts:
  - `audit/wave-16/consolidation-report.md`
  - `specs/004-arabic-rtl-verification-polish/plans/wave-final-snapshot.md`
  - Append Phase 4 summary to `orchestration-log.md`
  - Move Phase 4 to FROZEN in `AGENTS.md`

**Surfaces**: None directly — this is audit and documentation.

**Evidence required**:
- Final gate verbatim output (frontend; backend only if changed)
- Consolidation report (all findings, all FRs, all SCs)
- Wave final snapshot
- No screenshots required (audit wave)

**FRs**: All (FR-095 through FR-114) — final verification
**SCs**: All (SC-036 through SC-045) — final verification, plus SC-043 (Critical/High resolution)

---

## Cross-Wave Rules

### When screenshots are required vs not

| Situation | Screenshot? |
|-----------|------------|
| Surface passes clean in Arabic/RTL | No — text report sufficient |
| Surface has a failure, regression, or unexpected behavior | Yes — capture the issue |
| Visual ambiguity (alignment unclear, partial overlap) | Yes — capture for review |
| Before/after a CSS or i18n fix | Yes — prove the fix |
| Baseline audit (Wave 16.0) or final audit (Wave 16.4) | No — gate output + reports |

### How to handle absent surfaces

1. Attempt to navigate to the surface or trigger the flow
2. If the surface no longer exists (e.g., accept/reject buttons removed):
   - Note: "Surface absent — replaced by [X]" or "Surface absent — removed in Phase [N]"
   - Does NOT block Phase 4 closure
3. Continue to next surface

### When frontend/backend gates are required

| Condition | Frontend gates | Backend gates |
|-----------|---------------|---------------|
| No code changes in wave | Required (confirm baseline) | Not required |
| Frontend-only code changes | Required | Not required |
| Backend code changes | Required | Required |
| Zero-code closure (all passes clean) | Required (Wave 16.0 + 16.4) | Not required |

### How code fixes are bounded to polish scope

Fixes allowed:
- Add/fix i18n keys in `en.json`/`ar.json`
- Swap physical CSS classes to logical (`left`→`start`, `margin-left`→`ms-`, etc.)
- Fix responsive overflow / layout issues at mobile breakpoints
- Fix `aria-label` / `aria-live` for Arabic accessibility
- Fix error message display to remove raw English fallback / UUID / driver leaks
- Fix prompt builder i18n hints for Arabic prompt handling

Fixes NOT allowed (escalate if discovered):
- New backend endpoints or API changes
- New UI components or product surfaces
- Database schema changes or migrations
- Architectural refactors
- New dialect support or cross-database joins
- SSO/RBAC/audit/quota work
- Voice input, chart axis redesign, mobile shell/PWA

### Phase 4 Exit Criteria

Phase 4 may close when ALL of the following are true:

1. ✅ i18n key parity is 100% (EN = AR, zero missing keys in either direction)
2. ✅ All shipped surfaces pass Arabic/RTL Chrome MCP smoke (text evidence per surface)
3. ✅ Zero physical directional CSS in component stylesheets (or documented exceptions for third-party)
4. ✅ Arabic prompts succeed against all three real DBs with dialect-correct SQL
5. ✅ No raw UUID, hostname, credential, or driver error visible in Arabic mode
6. ✅ Mobile RTL (≤768px) has no horizontal overflow or unusable controls
7. ✅ All frontend foundation gates pass (test, lint, typecheck, build, lint:css)
8. ✅ Backend gates pass if backend code changed; skipped if no changes
9. ✅ All Critical/High audit findings resolved
10. ✅ Wave final snapshot and orchestration log produced
11. ✅ Phase 4 status set to FROZEN in `AGENTS.md`

---

## Per-Wave Foundation Gates

### Frontend (all waves)
```bash
cd frontend && npm run test -- --run
cd frontend && npm run lint
cd frontend && npm run typecheck
cd frontend && npm run build
cd frontend && npm run lint:css
```

### Backend (only if backend code changes)
```bash
cd backend && uv run pytest -q -m "not integration"
cd backend && uv run ruff check src tests
cd backend && uv run ruff format --check src tests
```

## Explicitly Out of Scope

Voice input, new major product screens, RTL chart axis redesign, SSO/RBAC/row-column security, audit log/quotas/injection detection, admin dashboard expansion, scheduled reports, semantic search, mobile shell/PWA, multi-tenant support, new DB dialects, cross-database joins. See spec.md § Explicitly Out of Scope.
