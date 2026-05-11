# QueryCraft — Development Environment Quirks

When working on the QueryCraft repo (Phase 1 text-to-SQL platform), the items below have been hit before by previous sessions. Following them avoids re-discovering known friction.

## Frontend tooling

- **NEVER run `npm install` or `npm ci` from the repo root.** This pollutes the root with a stray `node_modules/` and causes "two different versions of @playwright/test" errors. Always `cd frontend/` first.
- **Playwright browsers persist across PC restarts** because `package.json` has a postinstall hook: `"postinstall": "playwright install chromium"`. After `npm ci` in `frontend/`, browsers auto-install to `~/.cache/ms-playwright/` (WSL-persistent).
- **Playwright OS deps** are usually already present in the standard dev environment. If they're missing on a fresh WSL install, run `sudo npx playwright install --with-deps chromium` (the `--with-deps` flag requires sudo). Without sudo, plain `npx playwright install chromium` still works if OS deps are satisfied.

## Backend tooling

- **Always use `uv sync --extra dev` for dev work.** Plain `uv sync` strips pytest, ruff, and other dev tools (uv defaults to prod-only sync). Symptom: `uv run pytest` fails with "command not found" after a plain `uv sync`.
- **Run pytest from `backend/`**, not the repo root. Use `cd backend && uv run pytest -q -m "not integration"` for the CI-equivalent run. Integration tests require docker stack (postgres-source on 5434, postgres-platform on 5433, redis); they're deselected in CI until T-231 lands.
- **Run ruff from `backend/` too**: `cd backend && uv run ruff check src tests`.

## sqlglot AST quirks

When writing/extending `unsafe_pattern.py` rules:

- Built-in PostgreSQL functions like `current_user()`, `current_schema()`, `current_database()` are parsed as **special AST nodes** (e.g., `exp.CurrentUser`, `exp.CurrentSchema`), NOT as `exp.Anonymous`. A generic `find_all(exp.Anonymous)` loop will MISS them.
- **Always add explicit `find_all(exp.SpecificFunctionNode)` checks** for every special function you want to block, in addition to the generic forbidden-name walker.
- Same lesson applied to quoted identifiers (`"current_user"` parses as `exp.Identifier`, not `exp.Column.name`). Wave 4 G-001 surfaced this pattern; Wave 5 Chunk 5.2 generalized it for T-235.

## Test file layout

- This repo uses **co-located test files** (e.g., `HistoryList.test.tsx` alongside `HistoryList.tsx`), NOT `__tests__/` subdirectories.
- If you find a stray `__tests__/Component.test.tsx`, consolidate its tests into the co-located file and delete the `__tests__/` copy. Wave 5 Chunk 5.4 did this cleanup.

## Git / monorepo hygiene

- Foundation gates checklist (run before any commit/push):
  ```bash
  cd backend && uv run pytest -q -m "not integration" && uv run ruff check src tests && cd ..
  cd frontend && npm run test -- --run && npm run lint && npm run typecheck && npm run build && cd ..
  ```
- After fetching, always `git pull --ff-only` to surface any merge needs explicitly.
- Write scratch files to `<repo>/tmp/` (gitignored), NEVER `~/`.

## Chunk report — "Self-discovered environment quirks" section

When completing any chunk prompt, include this block in the final report between **Problems encountered** and **BLOCKED markers**:

```
== Self-discovered environment quirks (durable knowledge candidates) ==
List anything you had to figure out on the fly that wasn't in the prompt and
that a future session would also hit. Format:
  1. <symptom you saw>
     <command/fix that worked>
     <suggested SKILL doc location, if obvious>
(or "None")
```

The orchestrator rolls these into this SKILL.md so future sessions don't re-discover them. Zero tax on tokens; major payoff on velocity.

## Spec-kit commands available

- `/speckit.constitution`, `/speckit.specify`, `/speckit.clarify`, `/speckit.plan`, `/speckit.tasks`, `/speckit.analyze`, `/speckit.checklist`, `/speckit.implement`.
- NO `/speckit.audit` or `/speckit.review` exists (PR #2043 was closed unmerged). Audit chunks use plain-text prompts to the model.

## Common file paths

- Spec: `specs/001-core-text-to-sql/spec.md`
- Plan: `specs/001-core-text-to-sql/plan.md`
- Tasks: `specs/001-core-text-to-sql/tasks.md`
- Constitution: `specs/001-core-text-to-sql/constitution.md`
- Wave plans: `specs/001-core-text-to-sql/plans/wave-N.md` and `wave-N-snapshot.md`
- OpenAPI contract: `specs/001-core-text-to-sql/contracts/openapi.yaml`
- Audit findings (DRAFT branches never merged): `audit/wave-N/{gemini,opus}-findings.md`
