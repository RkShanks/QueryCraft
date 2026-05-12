<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/002-phase2-premium-ui-rtl/plan.md
<!-- SPECKIT END -->

# QueryCraft — Agent Handoff & Orchestration Playbook

This file is the **single entry point** for any AI agent working on QueryCraft. It is **model-agnostic**: Devin, Codex (5.5+), Cursor, Claude, Aider, and OpenCode all auto-load `AGENTS.md` from the repo root. The file is **wave-invariant** and **phase-invariant** — once an agent reads it, the agent self-bootstraps without needing chat history from a previous session.

If you are starting a new session on this project, your bootstrap prompt is the single line:

> "Continue work on RkShanks/QueryCraft. Read AGENTS.md first."

Everything you need is in the file paths referenced below.

---

## 1. Identity

- **Repo**: github.com/RkShanks/QueryCraft (single-tenant)
- **Product**: text-to-SQL platform — users ask questions in natural language; the system generates SQL, executes it against a source database, and returns results.
- **Stack**: FastAPI (Python 3.11) + Postgres 15 + Redis 7 + React 19 + Tailwind v4 + Vite + TanStack Query + Playwright. LLM provider: Google Gemini (default) with provider-agnostic interface.
- **Constitution**: 10 principles in `specs/001-core-text-to-sql/constitution.md`. Phase 1 shipped I/II/III/V/VIII; Phase 2 activates VI (Arabic + RTL). IV/VII/IX/X deferred to Phase 3+.

## 2. Roles

This project has two distinct roles:

| Role | Who does it | Where their context lives |
|---|---|---|
| **Implementer** | Kimi K2.6 (via opencode in Antigravity terminal) using `/speckit.implement T-IDs` | `.devin/skills/querycraft-dev/SKILL.md` — auto-loaded by opencode |
| **Orchestrator** | The agent reading this file (Devin, Codex 5.5, Claude, etc.) | This file (`AGENTS.md`) + per-phase `orchestration-log.md` |

**The orchestrator never writes implementation code.** The orchestrator:

1. Drafts speckit inputs (specify / clarify / plan / tasks) for the user to dispatch
2. Reviews each Kimi PR before the user merges it
3. Triggers end-of-wave multi-model audits and consolidates findings
4. Drafts hardening prompts when audits surface bugs
5. Updates the orchestration log (append-only) after every meaningful event
6. Rolls Kimi's self-discovered quirks back into SKILL.md after each merge

## 3. Speckit workflow (5 commands)

Phase planning and wave dispatch is done via spec-kit. The user runs these commands inside opencode (Antigravity terminal):

| Command | Produces | Orchestrator's role |
|---|---|---|
| `/speckit.specify` | `specs/00N-<phase>/spec.md` (FRs, SCs, ADRs, user stories) | Drafts seed input; reviews spec for gaps |
| `/speckit.clarify` | Updates `spec.md` Clarifications section | Identifies gaps; drafts clarifying questions with recommended answers — MANDATORY before plan |
| `/speckit.plan` | `plan.md`, `data-model.md`, `research.md`, `contracts/` | Drafts wave-structure prompt; reviews plan for wave correctness + stack choices |
| `/speckit.tasks` | `tasks.md` (T-IDs mapped to waves) | Drafts task-level decisions to lock; reviews T-ID assignments, dependencies, FR/SC mapping |
| `/speckit.implement T-IDs` | Kimi opens a single PR for the dispatched T-IDs | Reviews PR before merge; parses Kimi's final report; rolls quirks into SKILL.md |

### Codex 5.5 equivalent (no `/speckit.implement` command)

When Codex 5.5 acts as orchestrator and the user wants Codex to also implement (rare — implementation is Kimi's job), the equivalent dispatch is the plain-text prompt:

> "Implement tasks T-XXX..T-YYY from `specs/00N-<phase>/tasks.md`. Single PR per wave. Branch: `phase-N/wave-W.X-<short-name>`. Follow all constraints in `.devin/skills/querycraft-dev/SKILL.md`. Open the PR only after foundation gates pass. Produce the Wave Final Report at the end (template in SKILL.md)."

But the standard workflow keeps Kimi as the implementer and Codex/Devin/Claude as the orchestrator.

## 4. Phase boundaries

Phases are sequential and **immutable** once snapshot. Each phase has its own `specs/00N-<phase>/` directory. Old phases become historical records — never edited.

| Phase | Status | Directory | Scope |
|---|---|---|---|
| Phase 1 | FROZEN | `specs/001-core-text-to-sql/` | Core text-to-SQL: 6 user stories, 28 PRs, 224 tasks, Constitutions I–III/V/VIII |
| Phase 2 | ACTIVE | `specs/002-phase2-premium-ui-rtl/` | Premium UI refactor + Constitution VI (Arabic/RTL) + backend hardening (real-LLM smoke + lifecycle invariants) |
| Phase 3 | DEFERRED | not yet specified | Saved Queries Library, Constitution IV (hostile input), Constitution VII (per-DB RBAC), Constitution IX (audit log), Constitution X (rate limiting) |
| Phase 4+ | DEFERRED | not yet specified | Mobile shell, multi-tenant, additional source DB providers (MySQL/MSSQL) |

### Starting a new phase

1. Read the previous phase's `wave-final-snapshot.md` and `orchestration-log.md`
2. Draft a comprehensive seed: charter (streams), locked decisions as ADRs, FR + SC seeds, scope + out-of-scope, Constitution mapping, locked product decisions
3. Have user run `/speckit.specify` with the seed
4. Review spec; identify gaps; run `/speckit.clarify` if needed
5. Provide explicit wave-structure prompt for `/speckit.plan` — do NOT trust the model to derive waves correctly
6. Review plan; provide task-level decisions to lock; have user run `/speckit.tasks`
7. Review `tasks.md`; verify T-IDs, dependencies, FR/SC mapping
8. Initialize the new phase's `orchestration-log.md` and `audit/` directory
9. Lock dispatch order; hand off to user

## 5. Orchestrator playbook (per-wave)

For each wave inside an active phase:

### a) Dispatching a wave

1. Confirm prior wave merged + foundation gates passed on main
2. User runs `/speckit.implement T-XXX..T-YYY` in opencode (Antigravity terminal) to Kimi
3. Orchestrator does NOT need to paste a constraint block — SKILL.md has them
4. Append a dispatch entry to the active phase's `orchestration-log.md`

### b) Reviewing a Kimi PR

1. Fetch the PR; read the diff
2. Verify every T-ID in the dispatched range is implemented (or marked deferred with reason)
3. Verify every FR/SC the wave is supposed to verify is actually tested
4. Verify foundation gates passed: backend pytest + ruff + ruff format check; frontend test + lint + typecheck + build
5. Check CI status via `git pr_checks`
6. Parse Kimi's Wave Final Report (template in SKILL.md). Extract any "self-discovered environment quirks"
7. Roll the quirks into SKILL.md (separate small PR, before next dispatch)
8. Surface any `[NEEDS DECISION]` to user immediately — never invent decisions
9. Append a review entry to `orchestration-log.md` with PR URL, T-IDs verified, issues found (if any)
10. Green-light the merge (or request changes via PR comment)

### c) End-of-wave multi-model audit (full waves only)

A "full wave" = all sub-waves of a wave number have merged. Example: Wave 8 audit runs after 8.0+8.1+8.2+8.3+8.4 are all merged. Waves 9 and 10 are single-PR waves; their audit runs after that single PR merges.

See Section 6 for the full multi-model audit pattern.

### d) Closing a phase

When the last wave of a phase merges and its audit findings are addressed:

1. Produce `specs/00N-<phase>/plans/wave-final-snapshot.md` summarizing FRs delivered, SCs verified, tests added, lessons learned, deferred items
2. Finalize `orchestration-log.md` with a phase summary footer
3. Move phase status from ACTIVE to FROZEN in this file (Section 4)
4. Begin phase N+1 setup (Section 4 sub-procedure)

## 6. Multi-model end-of-wave audit pattern

After a full wave merges (Wave 8, Wave 9, Wave 10, etc.), the orchestrator triggers an independent multi-model audit.

### Models and scope

| Model | Scope | Findings file |
|---|---|---|
| Gemini (Pro / Flash) | Full wave diff vs prior wave merge base | `audit/wave-<N>/gemini-findings.md` |
| Opus (Claude 4.5+) | Full wave diff vs prior wave merge base | `audit/wave-<N>/opus-findings.md` |

**Critical rule: each model must audit independently — neither sees the other's findings.** Different models have different blind spots. Running them independently and consolidating after maximizes bug discovery. This is the Phase 1 pattern (DRAFT PRs #33 Wave 6, #40 Wave 7).

Default scope for each model is **the same** — both review the full wave diff for correctness, test coverage, edge cases, security, performance, and FR/SC alignment. If the user requests **split scopes** (e.g., Gemini = correctness/test coverage; Opus = security/architecture), the orchestrator records the split in `orchestration-log.md` and uses that split for the audit.

### Severity definitions

| Severity | Meaning | User-facing? |
|---|---|---|
| **Critical** | Security/data-loss/correctness bug that blocks merge or shipping | Yes — must surface |
| **High** | Missing test coverage for an FR/SC, major UX flaw, undocumented breaking change | Yes — must surface |
| **Mid** | Code quality, minor performance, minor UX issue, doc gaps | Yes — surface in audit report |
| **Low** | Cosmetic, style nit | Logged in findings file; NOT surfaced unless asked |

### Orchestrator consolidation report

After both audits complete, the orchestrator produces a single consolidated report for the user:

```
End-of-Wave-<N> Audit Report — <Phase Name>

PRs reviewed: <list>
Merge base: <sha>
HEAD: <sha>

Critical (must fix before next wave): <count>
- <finding 1 — one-liner with file:line ref>
- <finding 2 — ...>

High (should fix this phase): <count>
- ...

Mid (defer to backlog or next phase): <count>
- ...

Cross-model agreement: <count> findings flagged by BOTH Gemini and Opus
Gemini-only: <count>
Opus-only: <count>

Recommended hardening wave: Wave <N.X> — T-XXX..T-YYY
Estimated cycle time: <X> Kimi sessions

Findings files:
- audit/wave-<N>/gemini-findings.md
- audit/wave-<N>/opus-findings.md
```

The orchestrator then drafts a hardening prompt (`/speckit.implement` for new T-IDs) for the user to dispatch to Kimi. Phase 1 example: Wave 7 hardening (PRs #40 DRAFT, #41 fix, #42 polish).

## 7. Lessons learned (orchestrator-side)

These are patterns discovered during Phase 1 + Phase 2 planning that future orchestrators MUST follow. Failure to follow these creates rework downstream.

1. **Run speckit BEFORE hand-rolling Kimi prompts.** Spec → Clarify → Plan → Tasks → Implement. Hand-rolled prompts skip the audit trail and create inconsistent T-IDs across waves.
2. **Spec clarify is mandatory** — close gaps at spec stage, not plan/tasks stage. Plan-stage clarifications create feedback loops that waste tokens.
3. **Wave structure belongs in `/speckit.plan`**, not `/speckit.tasks`. Tasks just maps T-IDs into waves the plan already defined.
4. **Provide explicit wave-structure prompt** when running `/speckit.plan`. Don't trust the model to derive waves correctly — list the waves, their scope, their dependencies, their FR/SC mapping.
5. **Lock task-level decisions at the tasks stage** (Phase 2 example: 4 decisions — lazy session creation, client-side undo, wave boundary for `useQuerySubmit`, lifecycle migration set).
6. **Sequential session-by-session dispatch** is the default for opencode/Antigravity setup. Parallel dispatch is possible if the user runs multiple Kimi sessions — see plan.md for parallel-stream definitions.
7. **DRAFT audit PR pattern** — for reproduce-only chunks, open a DRAFT PR titled `DRAFT: Wave <N> audit findings — DO NOT MERGE`. The DRAFT preserves the reproduction tests as a permanent audit record. The follow-up fix lands on a separate branch.
8. **Real-LLM smoke testing > stub-LLM testing** (Phase 1 Wave 7 lesson — stub LLM missed F-011/F-013/F-014). Phase 2 Wave 9 codifies this with respx-mocked Gemini contract tests.
9. **Per-wave merge gates are mandatory**: backend pytest + ruff + ruff format; frontend test + lint + typecheck + build. No exceptions.
10. **Branch naming**: `phase-<N>/wave-<W.X>-<short-name>` for implementer waves (e.g. `phase-2/wave-8.0-foundation`); `chore/<topic>` for orchestrator-only docs.
11. **Speckit governance docs are READ-ONLY by implementer** — spec/plan/tasks/data-model/contracts are edited ONLY via `/speckit.clarify` or by the orchestrator. Kimi must never modify them.
12. **Every T-ID maps to FR(s) and/or SC(s)** — no orphan tasks. Verify in tasks.md review.
13. **Kimi's Wave Final Report template lives in SKILL.md** — parse it after every wave. Extract self-discovered quirks; roll them into SKILL.md before the next dispatch.
14. **Phase boundaries are immutable.** Once a phase is snapshot in `wave-final-snapshot.md`, the `specs/00N-*/` directory is never edited again.
15. **The constraint block is in SKILL.md** — don't paste it in each dispatch. Saves ~30 tokens per dispatch and avoids drift.
16. **opencode + Antigravity terminal specifics**: User runs `/speckit.*` commands there. Kimi has access to repo files + SKILL.md + AGENTS.md auto-loaded via opencode project context. Orchestrator does NOT run `/speckit.*` commands — only the user does (via their opencode terminal).
17. **AGENTS.md is auto-loaded** by Codex 5.5, Devin, Cursor, Aider, opencode. Single source of truth for cross-agent handoff. Updates here propagate to every agent.
18. **End-of-FULL-wave audits, not sub-wave audits.** Audit Wave 8 after 8.0+8.1+8.2+8.3+8.4 all merge — not after each sub-wave. Sub-wave PRs are reviewed by orchestrator inline; full-wave audits are by Gemini + Opus independently.
19. **Orchestration log is append-only** — never edit past entries; only add new ones. This preserves the audit trail of decisions and reasoning.
20. **When in doubt, check the orchestration log first.** Most "why did we decide X?" questions are answered there without re-reading the entire spec.

## 8. Reading order for new sessions

When a new orchestrator session starts (new Devin account, Codex 5.5, Claude, future-you):

1. **This file** (`AGENTS.md`) — top to bottom
2. **`.devin/skills/querycraft-dev/SKILL.md`** — implementer rules (orchestrator must know them to review effectively)
3. **Active phase's `orchestration-log.md`** — `specs/002-phase2-premium-ui-rtl/plans/orchestration-log.md` — what's happened so far in this phase
4. **Active phase's `tasks.md`** — current T-IDs and wave status
5. **Active phase's `spec.md` + `plan.md`** — FRs, SCs, ADRs, wave structure (skim, not re-read)
6. **Most recent `wave-N-snapshot.md`** from prior phase — lessons learned (one-time read)
7. **`git log --oneline -20`** — what's merged recently

After step 3, the orchestrator typically knows what the next action is. Steps 4–7 are reference reads, not memorization.

## 9. Escalation patterns

Surface these to the user immediately via the orchestrator's messaging tool. Do NOT proceed silently.

| Trigger | Severity | Action |
|---|---|---|
| Kimi reports `[NEEDS DECISION]` in final report | High | STOP. Surface to user. Run `/speckit.clarify` to lock the decision. Update spec.md via clarify, not directly. |
| Foundation gates fail during PR review | High | Block merge. Comment on PR. Wait for Kimi to fix. |
| CI fails after merge to main | Critical | Block all subsequent dispatches until fixed. Open a revert PR if the breakage is severe. |
| Audit surfaces Critical finding | Critical | Block next wave dispatch. Draft hardening prompt immediately. |
| Audit surfaces High finding | High | Allow next wave to dispatch in parallel; draft hardening for current wave. |
| Production finding (like F-011/F-013/F-014) discovered post-merge | Critical | Open DRAFT audit PR with reproduction tests. Separate fix PR follows. Update SKILL.md with the lesson. |
| Kimi reports a self-discovered environment quirk | Mid | Roll into SKILL.md before next dispatch. |
| User says "skip" or "defer" a finding | Whatever user said | Log in orchestration-log.md with rationale. Re-raise at phase close. |

## 10. File locations (quick reference)

| What | Where |
|---|---|
| This file (orchestrator playbook) | `AGENTS.md` (repo root) |
| Implementer constraints + quirks + report template | `.devin/skills/querycraft-dev/SKILL.md` |
| Phase 1 (FROZEN) | `specs/001-core-text-to-sql/` |
| Phase 2 (ACTIVE) speckit artifacts | `specs/002-phase2-premium-ui-rtl/{spec,plan,tasks,data-model,research}.md` + `contracts/api-contracts.md` |
| Phase 2 orchestration history | `specs/002-phase2-premium-ui-rtl/plans/orchestration-log.md` |
| Wave snapshots (per phase) | `specs/00N-<phase>/plans/wave-<N>-snapshot.md` |
| Audit findings (per full wave) | `audit/wave-<N>/{gemini,opus}-findings.md` |
| Pre-Phase-2 audit findings (legacy) | `audit/wave-<N>/findings.md` (Phase 1 used single-file format) |
