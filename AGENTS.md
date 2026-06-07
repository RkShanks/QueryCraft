<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/005-sso-rbac-row-column-security/plan.md
<!-- SPECKIT END -->

# QueryCraft — Agent Handoff

Universal entrypoint for all AI agents. Model-agnostic, phase-invariant.

Bootstrap prompt: `"Continue work on RkShanks/QueryCraft. Read AGENTS.md first."`

---

## 1. Identity

- **Repo**: github.com/RkShanks/QueryCraft (single-tenant)
- **Product**: Text-to-SQL — natural language → SQL → execute → results.
- **Stack**: FastAPI (Python 3.12) · Postgres 15 · Redis 7 · React 19 · Tailwind v4 · Vite · TanStack Query · Playwright. LLM: Google Gemini (default), provider-agnostic interface.
- **Constitution**: 12 principles in `.specify/memory/constitution.md`. Shipped: I/II/III/V/VI/VII/VIII/IX. Deferred: IV (Phase 6), X (Phase 6).

## 2. Roles & Models

| Role | Model | Reads on bootstrap |
|---|---|---|
| **Orchestrator** | Opus 4.6 | `AGENTS.md` → `.agents/ORCHESTRATOR.md` |
| **Backend Implementer** | Kimi/GLM (opencode) | `AGENTS.md` → `.agents/skills/BACKEND_IMPLEMENTER.md` → `.agents/skills/KARPATHY.md` |
| **Frontend Implementer** | Gemini (Chrome DevTools MCP) | `AGENTS.md` → `.agents/IMPLEMENTER.md` → `.agents/skills/FRONTEND_GEMINI.md` → `.agents/skills/TDD.md` → `.agents/skills/KARPATHY.md` |

**Orchestrator** never writes product code. Orchestrator: drafts speckit inputs, reviews PRs, triggers audits, updates orchestration log, rolls quirks into skill files.

**Implementers** follow their role skill for protocol, TDD-mandatory commit triple, foundation gates, and stack-specific quirks.

## 3. Phase Boundaries

Phases are sequential and **immutable** once snapshot.

| Phase | Status | Directory | Scope |
|---|---|---|---|
| 1 | FROZEN | `specs/001-core-text-to-sql/` | Core text-to-SQL: 6 stories, 28 PRs, 224 tasks |
| 2 | FROZEN | `specs/002-phase2-premium-ui-rtl/` | Premium UI + Arabic/RTL + backend hardening |
| 3 | FROZEN | `specs/003-multi-dialect-source-dbs/` | Multi-dialect SQL (PG/MySQL/MSSQL), admin DB management, schema introspection |
| 4 | FROZEN | `specs/004-arabic-rtl-verification-polish/` | Arabic/RTL verification and polish on shipped surfaces |
| 5 | FROZEN | `specs/005-sso-rbac-row-column-security/` | SSO, RBAC, row/column security, tamper-evident audit log |
| 6 | PLANNED | — | Quotas, hostile input/injection detection, audit search/export hardening |
| 7 | PLANNED | — | Admin dashboard |
| 8 | PLANNED | — | Scheduled reports and notifications |
| 9 | PLANNED | — | Semantic search of accepted queries |
| 10+ | DEFERRED | — | Mobile shell, multi-tenant foundation |

### Starting a new phase

1. Read prior phase's `wave-final-snapshot.md` + `orchestration-log.md`.
2. Draft seed: charter, ADRs, FR/SC seeds, scope, Constitution mapping.
3. `/speckit.specify` → review → `/speckit.clarify` (mandatory) → `/speckit.plan` (with explicit wave structure) → `/speckit.tasks`.
4. Initialize `orchestration-log.md` + `audit/` dir. Lock dispatch order.

## 4. File Locations

| What | Where |
|---|---|
| This file | `AGENTS.md` |
| Orchestrator playbook | `.agents/ORCHESTRATOR.md` |
| Implementer protocol (legacy/source) | `.agents/IMPLEMENTER.md` |
| Frontend skill (Gemini) | `.agents/skills/FRONTEND_GEMINI.md` |
| Backend implementer skill (combined) | `.agents/skills/BACKEND_IMPLEMENTER.md` |
| Backend skill (legacy/source) | `.agents/skills/BACKEND_QWEN.md` |
| TDD skill | `.agents/skills/TDD.md` → `.agents/skills/tdd/` |
| Karpathy guidelines | `.agents/skills/KARPATHY.md` |
| Devin skill (legacy) | `.devin/skills/querycraft-dev/SKILL.md` |
| Phase 1 (FROZEN) | `specs/001-core-text-to-sql/` |
| Phase 2 (FROZEN) | `specs/002-phase2-premium-ui-rtl/` |
| Phase 3 (FROZEN) | `specs/003-multi-dialect-source-dbs/` |
| Phase 4 (FROZEN) | `specs/004-arabic-rtl-verification-polish/` |
| Orchestration log | `specs/<phase>/plans/orchestration-log.md` |
| Audit findings | `audit/wave-<N>/{gemini,opus}-findings.md` |

## 5. Lessons Learned

1. Run speckit BEFORE hand-rolling prompts. Spec → Clarify → Plan → Tasks → Implement.
2. Spec clarify is mandatory — close gaps at spec stage, not plan/tasks.
3. Wave structure belongs in `/speckit.plan`, not `/speckit.tasks`.
4. Provide explicit wave-structure prompt for `/speckit.plan`.
5. Lock task-level decisions at the tasks stage.
6. Sequential dispatch is default. Parallel only with multiple sessions.
7. DRAFT audit PR pattern for reproduce-only chunks.
8. Real-LLM smoke > stub-LLM testing.
9. Per-wave merge gates are mandatory. No exceptions.
10. Branch naming: `phase-<N>/wave-<W.X>-<short-name>` (impl); `chore/<topic>` (docs).
11. Speckit governance docs are READ-ONLY by implementer.
12. Every T-ID maps to FR(s) and/or SC(s) — no orphan tasks.
13. Parse Wave Final Report after every wave. Roll quirks into skill files.
14. Phase boundaries are immutable once snapshot.
15. Constraint block lives in `.agents/IMPLEMENTER.md` — single source of truth.
16. opencode + Antigravity: user runs `/speckit.*`. Orchestrator does NOT run them.
17. AGENTS.md is auto-loaded by all agents. Role files loaded per §2 table.
18. Full-wave audits, not sub-wave audits.
19. Orchestration log is append-only.
20. When in doubt, check the orchestration log first.

## 6. Escalation Patterns

| Trigger | Sev | Action |
|---|---|---|
| `[NEEDS DECISION]` in report | High | STOP. `/speckit.clarify` to lock. |
| Gates fail during PR review | High | Block merge. Wait for fix. |
| CI fails after merge to main | Critical | Block all dispatches. Revert if severe. |
| Audit: Critical finding | Critical | Block next wave. Draft hardening. |
| Audit: High finding | High | Allow parallel dispatch; draft hardening. |
| Post-merge production finding | Critical | DRAFT audit PR + separate fix PR. |
| Self-discovered quirk | Mid | Roll into skill file before next dispatch. |
| User says "skip"/"defer" | As stated | Log in orchestration-log. Re-raise at phase close. |
