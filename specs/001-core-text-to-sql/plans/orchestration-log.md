# Phase 1 Orchestration Log — Core Text-to-SQL Platform (FROZEN)

**Phase**: 001-core-text-to-sql
**Status**: FROZEN — Phase 1 shipped via PR #38; Wave 7 hardening completed via PRs #40/#41/#42.
**Backfilled**: 2026-05-12 (after Phase 1 close) — entries reconstructed from PRs and wave snapshots.

This log is for historical reference. Phase 1 used a single-file audit format (`audit/wave-N/findings.md`) instead of the per-model split (`audit/wave-N/{gemini,opus}-findings.md`) adopted from Phase 2 onward.

---

## Phase 1 wave summary

| Wave | PRs | Outcome | Findings |
|---|---|---|---|
| 0 — Setup | various | Repo scaffold, CI, Constitution v1.0 drafted | — |
| 3 — US-1 / US-2 audit | DRAFT (preserved) | Audit pass on US-1 (auth) + US-2 (source DB connection management) | minor findings, fixed inline |
| 4 — US-3 audit + fix | DRAFT preserved + fix merged | Query submit + LLM provider abstraction | G-001 sqlglot AST quirk (current_user() parses as exp.CurrentUser, not exp.Anonymous) |
| 5 — US-4 audit + fix | DRAFT preserved + fix merged | Query history + filters + replay | T-235 quoted identifier pattern; Chunk 5.4 cleaned up `__tests__/` subdirs to co-located test pattern |
| 6 — US-5 + US-6 + polish audit | DRAFT #33 (preserved, never merged) + fix PRs | Accept / reject / feedback + production polish | 12 findings across security, observability, and code quality |
| 7 — Real-LLM hardening | DRAFT #40 audit + #41 fix + #42 polish | Real-LLM smoke testing surfaced 3 production-grade bugs that stub-LLM audits missed | F-011 (lock leak, Critical), F-013 (migration drift, High), F-014 (API key in URL, High Constitution I) |
| Ship gate | (no PR — gate doc) | Phase 1 verdict = GREEN | All FR-001..FR-030 + SC-001..SC-013 verified |

**Phase 1 totals**: 28 PRs merged. 224 tasks closed (T-001..T-252; T-253..T-260 deferred to Phase 2). 311 backend tests + 128 frontend tests + 36 E2E tests passing.

---

## Phase 1 lessons (rolled into Phase 2 planning)

1. **Stub-LLM audits miss production bugs.** F-011/F-013/F-014 were only surfaced by real-LLM smoke testing on a developer workstation. Phase 2 Wave 9 adds a respx-mocked Gemini contract suite to catch this class of bug pre-merge.

2. **Lifecycle invariants need cross-call test coverage.** Foundation tests reset Redis between tests, making lock-leak bugs invisible. Phase 2 Wave 10 adds a pytest fixture framework that observes state at the end of test N and asserts at the start of test N+1.

3. **Schema drift needs runtime guards.** F-013 fix: backend now refuses to start when `alembic current < head` and emits `migration_drift_detected`. Codified in SKILL.md security non-negotiables.

4. **API keys NEVER in URL query params.** F-014 root cause was httpx logging full URLs at INFO. Fix: Gemini key moved from `?key=...` to `x-goog-api-key` header. Codified in SKILL.md security non-negotiables (Constitution I).

5. **Long-running locks MUST use try/finally on every exit path.** F-011 root cause was 4 paths where the processing lock leaked. Fix: try/finally wrap every acquire. Codified in SKILL.md security non-negotiables.

6. **DRAFT audit PRs preserved as historical record.** Pattern: open `DRAFT: Wave <N> audit findings — DO NOT MERGE` with reproduction tests; follow up with a separate fix PR on a new branch. Phase 1 examples: PRs #33 (Wave 6), #40 (Wave 7). Phase 2 inherits this pattern.

7. **Polish backlog must be tracked across phases.** T-253..T-260 deferred from Wave 6; re-mapped into Phase 2 Wave 8.4 as T-364..T-368, T-312, T-305, T-368.

---

## File locations (Phase 1)

| What | Where |
|---|---|
| Spec | `specs/001-core-text-to-sql/spec.md` |
| Plan | `specs/001-core-text-to-sql/plan.md` |
| Tasks | `specs/001-core-text-to-sql/tasks.md` |
| Constitution | `specs/001-core-text-to-sql/constitution.md` |
| Wave plans | `specs/001-core-text-to-sql/plans/wave-N.md` |
| Wave snapshots | `specs/001-core-text-to-sql/plans/wave-N-snapshot.md` |
| Ship gate verdict | `specs/001-core-text-to-sql/plans/phase-1-ship-gate.md` |
| Audit findings (legacy single-file format) | `audit/wave-N/findings.md` |
| OpenAPI contract | `specs/001-core-text-to-sql/contracts/openapi.yaml` |

---

**Phase 1 is FROZEN. Do not edit this directory.** New work belongs to `specs/002-phase2-premium-ui-rtl/` or later phases.
