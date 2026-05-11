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

## Backend tooling / test quirks

- **respx.mock context-manager pattern** (Chunk 6.2). `respx.mock(...)` as a decorator silently fails to register routes when combined with async fixtures. Use `async with respx.mock() as router:`, register routes on the router inside the block, and call the function under test inside the block. Rule of thumb: prefer the context-manager form for httpx mocking; the decorator form has gotchas with async fixtures.
- **get_settings.cache_clear() after env monkeypatch** (Chunk 6.2). Monkeypatching env vars in tests has no effect on the `@lru_cache`'d `get_settings()`. Call `get_settings.cache_clear()` immediately after `monkeypatch.setenv`, before reading settings. Rule of thumb: `get_settings()` is cached; bust the cache or your env mutation is invisible.
- **@hey-api/openapi-ts v0.95.0 silent failure** (Chunk 6.4). `npm run gen:api` returns exit 0 but writes no files. Generated `types.gen.ts` is checked in; only regenerate when OpenAPI schema semantics change, and verify file mtimes after running. Rule of thumb: treat the generator as advisory; verify checked-in types by hand when in doubt.
- **Schemathesis requires OPEN_API_3_1.enable()** (Chunk 6.4). Schemathesis fails with "Open API 3.1.0 is currently not fully supported" after bumping the spec to 3.1.0. In contract test setup, add `schemathesis.experimental.OPEN_API_3_1.enable()` at module top. Rule of thumb: the experimental flag is mandatory when the OpenAPI version moves to 3.1.
- **ruff SIM105 / contextlib.suppress in test files** (Chunk 6.9). ruff fails tests with `SIM105: Use contextlib.suppress(Exception) instead of try-except-pass`. Replace `try: ... except Exception: pass` with `with contextlib.suppress(Exception): ...`. Rule of thumb: never use bare `try/except/pass` in this repo; always use `contextlib.suppress`.

## Frontend tooling / test quirks

- **Tailwind v4 `@source not` for test/fixture exclusion** (Chunk 6.3). Built CSS still contains physical-direction utilities even after fixing source files because Tailwind v4 JIT picks up class-name-shaped strings from test assertion literals. Add `@source not` directives in `frontend/src/index.css` to exclude `tests/**`, `coverage/**`, `eslint-rules/**`, and `stylelint-fixtures/**`. Rule of thumb: when a Tailwind v4 build leaks unexpected utilities, suspect test-file scans first.
- **ESLint flat config (v10) temp-file project-base constraint** (Chunk 6.3). ESLint Node API refuses to lint temp files outside the project base, and flat config globally ignores files under custom directories like `eslint-rules/__fixtures__/`. Write programmatic lint fixtures to `frontend/tmp/` (gitignored but inside the project base). Rule of thumb: in the flat-config era, all programmatic lint must use in-project paths.
- **`vi.useFakeTimers()` conflicts with TanStack Query** (Chunk 6.5). Page-level integration tests that mount TanStack-Query-backed components flake or hang after switching to fake timers. Limit `vi.useFakeTimers()` to pure component unit tests (where TQ is not in the tree). For page/integration tests, use real timer delays: `await new Promise(r => setTimeout(r, 350))`. Rule of thumb: fake timers + TQ = pick one; if TQ is in the tree, use real delays.

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
