# QueryCraft — Devin Skill File

> This file is retained for **Devin sessions only**. All other agents read `AGENTS.md` → role docs in `.agents/`.

## Role docs (canonical source of truth)

- **Implementer protocol**: `.agents/IMPLEMENTER.md` (Steps 0–8, commit triple, gates, TDD mandate)
- **Frontend rules**: `.agents/skills/FRONTEND_GEMINI.md`
- **Backend rules**: `.agents/skills/BACKEND_QWEN.md`
- **TDD workflow**: `.agents/skills/TDD.md` → `~/.agents/skills/tdd/`
- **Coding guidelines**: `.agents/skills/KARPATHY.md`

## Speckit commands

`/speckit.constitution`, `/speckit.specify`, `/speckit.clarify`, `/speckit.plan`, `/speckit.tasks`, `/speckit.analyze`, `/speckit.checklist`, `/speckit.implement`.

No `/speckit.audit` or `/speckit.review` exists.

## Common file paths

| What | Path |
|---|---|
| Phase 1 spec | `specs/001-core-text-to-sql/spec.md` |
| Phase 1 plan | `specs/001-core-text-to-sql/plan.md` |
| Phase 1 tasks | `specs/001-core-text-to-sql/tasks.md` |
| Constitution | `specs/001-core-text-to-sql/constitution.md` |
| Phase 2 spec | `specs/002-phase2-premium-ui-rtl/spec.md` |
| Phase 3 spec | `specs/003-multi-dialect-source-dbs/spec.md` |
| OpenAPI contract | `specs/001-core-text-to-sql/contracts/openapi.yaml` |
| Audit findings | `audit/wave-N/{gemini,opus}-findings.md` |

## Devin-specific environment notes

- **NEVER run `npm install` from repo root.** Always `cd frontend/` first.
- **Playwright browsers** persist in `~/.cache/ms-playwright/` via postinstall hook.
- **`uv sync --extra dev`** for dev work — plain `uv sync` strips test tools.
- **Run pytest/ruff from `backend/`**, not repo root.
- Scratch files → `<repo>/tmp/`, never `~/`.
