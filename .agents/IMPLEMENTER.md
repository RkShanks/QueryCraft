# QueryCraft — Implementer Protocol

**Audience**: Any model implementing tasks (Qwen 3.6 Plus, Gemini, or fallback).
Read `AGENTS.md` first, then this file + your role-specific skill.

---

## Step 0 — Pre-flight

```bash
git fetch origin && git checkout main && git pull --ff-only
git log --oneline -20
grep -nE "^- \[[X ]\] T-" specs/00*/tasks.md | head -50
```

- All dispatched T-IDs `[X]` → STOP, report done.
- Some `[X]` → resume from first `[ ]`.
- None `[X]` → start fresh.

## Step 1 — Branch (BEFORE any edits)

```bash
git checkout -b phase-<N>/wave-<W.X>-<short-name>   # new
# OR
git fetch origin <branch>:<branch> && git checkout <branch> && git rebase main  # resume
```

Never edit files on `main` then branch later.

## Step 2 — One task at a time (commit triple)

**TDD is mandatory.** Read `.agents/skills/TDD.md` for the full workflow.

For each T-ID in dependency order:

1. **RED** — write failing test(s), commit:
   ```
   git commit -m "test(T-XXX): <desc>" -m "<FR/SC ref>"
   ```
2. **GREEN** — implement to pass, commit:
   ```
   git commit -m "feat(T-XXX): <desc>" -m "Implements T-XXX."
   ```
   Use `fix`/`chore`/`docs` as appropriate. Conventional Commits required.
3. **Mark complete** in tasks.md, commit:
   ```
   git commit -m "docs(T-XXX): mark task complete in tasks.md"
   ```

One T-ID = one triple. Exception: truly inseparable T-IDs (e.g. single Alembic migration for two tables).

## Step 3 — Signature-change caller sweep

On ANY public signature/constructor/protocol/schema change:

```bash
git grep -n "<symbol>(" backend/ frontend/ tests/
```

Update **every** caller. Commit: `refactor(T-XXX): update all <symbol> callers`.

> Wave 8.0 lesson: `QueryService.__init__` gained args but `_get_query_service` wasn't updated → CI crash.

## Step 4 — Regression sweep (per sub-wave)

Before gates/push, identify every module that imports/extends what you changed — including untouched files. Run their tests explicitly. Fix failures before pushing.

## Step 5 — Foundation gates

Run against committed tree. **Paste verbatim output** in report — no summaries.

```bash
cd backend && uv run pytest -q -m "not integration"
cd backend && uv run ruff check src tests
cd backend && uv run ruff format --check src tests
cd ../frontend && npm run test -- --run
cd ../frontend && npm run lint
cd ../frontend && npm run typecheck
cd ../frontend && npm run build
```

If any gate fails → STOP, fix code (not tests unless genuinely wrong). Never push broken code.

## Step 5b — Browser smoke (frontend changes only)

Use Chrome DevTools MCP after build/serve. Record: route → action → expected → observed → console/network errors. If MCP unavailable, state explicitly in report and fall back to Playwright.

## Step 6 — Push per sub-wave

```bash
git push -u origin <branch>
```

Don't hoard locally. Push gives orchestrator visibility + remote backup.

## Step 7 — Open PR before reporting

Open a PR using the available GitHub tooling (CLI, web UI, or API). Target `main`, head is your wave branch.

**Title**: `Phase <N> — Wave <W.X>: <Name> (T-XXX..T-YYY)`

**Body must include**: Summary, T-IDs, FR/SC verified, verbatim gates, quirks, BLOCKED markers.

## Step 8 — Wave Final Report

```
Final report — Wave <N.X> <Short Name>
- Branch: <branch>
- HEAD sha: <40-char>
- PR URL: <url>

T-IDs implemented:
- T-XXX: <summary> (or "deferred: <reason>")

FRs / SCs verified:
- FR-XXX, SC-XXX

Foundation gates:
Backend: <pytest output> | <ruff check> | <ruff format>
Frontend: <vitest> | <lint> | <typecheck> | <build>

Problems encountered: <list or None>

Self-discovered environment quirks:
1. <symptom> → <fix> → <suggested skill location>
(or None)

BLOCKED markers: <list or None>
```

---

## Universal Constraints

- **Single PR per sub-wave.** All dispatched T-IDs in one PR.
- **Branch**: `phase-<N>/wave-<W.X>-<short-name>`.
- **Every commit references T-ID** in subject (Conventional Commits) and body.
- **PR description references T-IDs + FR/SC numbers.**
- **Governance docs READ-ONLY** — never modify spec/plan/data-model/research/contracts. **Exception**: `tasks.md` toggle `[ ]` → `[X]` only.
- **`[NEEDS DECISION]`** → STOP and report. Never invent product decisions.
- **Locked design decisions** from tasks.md apply verbatim.
- **Logical Tailwind directions**: `ms-`/`me-`/`ps-`/`pe-`/`start-`/`end-`/`text-start`/`rounded-ee-`.
- **Co-located tests**: `Foo.test.tsx` next to `Foo.tsx`, not `__tests__/`.

## Security Non-Negotiables (Constitution I)

- No API keys/tokens in URL query params — use headers.
- No raw request/response body logging without redaction.
- Lock release in `try/finally` on every exit path (Redis, DB).
- Alembic startup drift guard must remain enabled.

## DRAFT Audit PR Pattern

For audit-only dispatches: open DRAFT PR titled `DRAFT: Wave <N> audit findings — DO NOT MERGE`. Fix lands on separate branch.
