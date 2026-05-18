# QueryCraft — Orchestrator Playbook

**Audience**: Opus 4.6 (or any model acting as orchestrator).
Read `AGENTS.md` first, then this file.

---

## 1. Speckit Workflow (5 commands)

The user runs these in opencode (Antigravity terminal):

| Command | Produces | Orchestrator role |
|---|---|---|
| `/speckit.specify` | `specs/00N-<phase>/spec.md` | Draft seed; review for gaps |
| `/speckit.clarify` | Updates spec.md Clarifications | Identify gaps; draft Q+A — **mandatory** before plan |
| `/speckit.plan` | `plan.md`, `data-model.md`, `research.md`, `contracts/` | Draft wave-structure prompt; review plan |
| `/speckit.tasks` | `tasks.md` (T-IDs mapped to waves) | Draft task-level decisions; review T-ID assignments |
| `/speckit.implement T-IDs` | Implementer opens a single PR | Review PR; parse final report; roll quirks into skills |

### Plain-text equivalent (no `/speckit.implement`)

> "Implement tasks T-XXX..T-YYY from `specs/00N-<phase>/tasks.md`. Single PR per wave. Branch: `phase-N/wave-W.X-<short-name>`. Follow `.agents/IMPLEMENTER.md`. Open PR only after gates pass. Produce Wave Final Report."

---

## 2. Per-Wave Playbook

### a) Dispatching

1. Confirm prior wave merged + foundation gates green on main.
2. User runs `/speckit.implement T-XXX..T-YYY`.
3. Append dispatch entry to the active phase's `orchestration-log.md`.

### b) Reviewing a PR

1. Fetch PR; read diff.
2. Verify every dispatched T-ID is implemented (or deferred with reason).
3. Verify every FR/SC the wave covers is actually tested.
4. Verify foundation gates passed (backend: pytest + ruff + ruff format; frontend: test + lint + typecheck + build).
5. Check CI via `git pr_checks`.
6. Parse Wave Final Report. Extract self-discovered quirks.
7. Roll quirks into the relevant skill file (separate small PR before next dispatch).
8. Surface any `[NEEDS DECISION]` to user immediately — never invent decisions.
9. Append review entry to `orchestration-log.md`.
10. Green-light merge or request changes.

### c) End-of-wave audit (full waves only)

A "full wave" = all sub-waves merged. Example: audit Wave 8 after 8.0–8.4 all merge.

See §3 below.

### d) Closing a phase

1. Produce `specs/00N-<phase>/plans/wave-final-snapshot.md`.
2. Finalize `orchestration-log.md` with phase summary footer.
3. Move phase status to FROZEN in `AGENTS.md`.
4. Begin phase N+1 setup.

---

## 3. Multi-Model Audit Pattern

### Models

| Model | Scope | Findings file |
|---|---|---|
| Gemini (Pro/Flash) | Full wave diff vs merge base | `audit/wave-<N>/gemini-findings.md` |
| Opus (Claude 4.5+) | Full wave diff vs merge base | `audit/wave-<N>/opus-findings.md` |

**Critical**: Each model audits independently — neither sees the other's findings.

Default scope is identical for both: correctness, test coverage, edge cases, security, performance, FR/SC alignment. If user requests split scopes, record the split in `orchestration-log.md`.

### Severity

| Sev | Meaning | Surface? |
|---|---|---|
| **Critical** | Security/data-loss/correctness — blocks merge | Yes |
| **High** | Missing FR/SC coverage, major UX flaw | Yes |
| **Mid** | Code quality, minor perf, doc gaps | Yes |
| **Low** | Cosmetic, style nit | Logged only |

### Consolidation report template

```
End-of-Wave-<N> Audit Report — <Phase Name>

PRs reviewed: <list>
Merge base: <sha>  HEAD: <sha>

Critical (must fix before next wave): <count>
High (should fix this phase): <count>
Mid (defer to backlog): <count>

Cross-model agreement: <count>
Gemini-only: <count>  Opus-only: <count>

Recommended hardening wave: Wave <N.X> — T-XXX..T-YYY

Findings files:
- audit/wave-<N>/gemini-findings.md
- audit/wave-<N>/opus-findings.md
```

---

## 4. Orchestration-Log Rules

- **Append-only** — never edit past entries.
- Location: `specs/00N-<phase>/plans/orchestration-log.md`.
- Log: dispatches, PR reviews, audit results, decisions, phase events.
- Most "why did we decide X?" questions are answered here.

---

## 5. Per-Wave Dispatch Prompt Template

```
Wave <N.X> dispatch — <Short Name>

Model: <implementer model> in opencode
Command: /speckit.implement T-XXX..T-YYY

== Read `.agents/IMPLEMENTER.md` before starting ==

Steps: pre-flight → branch → commit-triple per task → caller sweep →
       regression sweep → foundation gates → push → PR → final report

== Wave-specific context ==
(Insert: design decisions, constraints, ADR links, branch name)
```

Update this template if a wave surfaces a new universal constraint.
