# Research — Phase 4: Arabic/RTL Verification and Polish

**Created**: 2026-05-23
**Phase**: 4

---

## Summary

Phase 4 is verification/polish — no new architecture, no new endpoints, no new entities. All research reduces to confirming baseline state from Phases 1–3.

## Baseline State (from Phase 3 closure)

| Item | Value |
|------|-------|
| EN keys | 261 |
| AR keys | 261 |
| i18n parity | 100% (confirmed Wave 15) |
| RTL layout | Verified in Chrome MCP smoke (Wave 15) |
| Frontend tests | 434 passed (51 files) |
| Backend tests | 617 passed |
| E2E scenarios | 41 green |
| Physical CSS audit | SC-031 verified clean (Wave 15) |
| Audit findings | All Critical/High resolved |

## Decisions

### D-1: Evidence format
- **Decision**: Text report per surface (route → action → expected → observed → errors). Screenshots only for failures/ambiguity/before-after.
- **Rationale**: Consistent with Phase 3 Chrome MCP smoke format. Reduces audit overhead for clean surfaces.

### D-2: Real DB requirement
- **Decision**: All three required — PostgreSQL Pagila, MySQL Sakila, MSSQL AdventureWorksLT.
- **Rationale**: Phase 3 deferred real MySQL/MSSQL smoke (services unavailable). PR #96 delivered fixtures. Phase 4 closes this gap.

### D-3: Fix-in-wave policy
- **Decision**: Fix discovered polish gaps in same wave. No separate hardening wave. Bounded to Phase 4 scope.
- **Rationale**: Small verification phase; separate fix waves add overhead without value.

### D-4: Backend gate trigger
- **Decision**: Backend gates required only if backend code changes. Zero-code closure is valid.
- **Rationale**: Phase 4 may be frontend-only or pure audit. Running backend gates without changes wastes time.

### D-5: Absent surface handling
- **Decision**: Skip, document what replaced it. Does not block closure.
- **Rationale**: UI evolved across 3 phases; some surfaces may have been reworked or removed.

## No Unknowns

All technical decisions are locked from prior phases. No new dependencies, no new APIs, no new data models.
