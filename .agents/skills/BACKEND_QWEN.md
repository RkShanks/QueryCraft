# Qwen 3.6 Plus — Backend Implementer Skill

**Audience**: Qwen 3.6 Plus (backend implementer via opencode).
Read after: `AGENTS.md` → `.agents/IMPLEMENTER.md` → this file.

---

## Ownership

Qwen owns **all backend T-IDs**: FastAPI, SQLAlchemy, Alembic, services, OpenAPI, Redis, Postgres.

## Tooling

- **Always** `uv sync --extra dev` — plain `uv sync` strips pytest/ruff.
- Run CI-equivalent pytest from `backend/`: `cd backend && uv run pytest tests/unit -q -m "not integration"`.
- Run ruff from `backend/`: `cd backend && uv run ruff check src tests`.
- Scratch files → `<repo>/tmp/` (gitignored), never `~/`.

## Backend Gates

```bash
cd backend && uv run pytest tests/unit -q -m "not integration"
cd backend && uv run ruff check src tests
cd backend && uv run ruff format --check src tests
```

Integration, acceptance, and contract tests require live services or full app fixtures. The fast gate runs only `tests/unit` and excludes any test explicitly marked `integration` (some service-dependent tests live under `tests/unit` for organizational reasons).

## Alembic Rules

- Drift guard: backend refuses to start when `alembic current < head` → `migration_drift_detected`.
- After adding migration: ensure `alembic upgrade head` in setup/dev scripts.
- After `git pull`: run `./scripts/dev-up.sh` (auto-migrates).

## OpenAPI / Generated Client

- `@hey-api/openapi-ts v0.95.0` may exit 0 but write no files. Generated `types.gen.ts` is checked in.
- Only regenerate when schema semantics change. Verify file mtimes after running.

## Backend Quirks

| Quirk | Rule |
|---|---|
| respx mock | Use `async with respx.mock() as router:` (context-manager), not decorator — decorator silently fails with async fixtures |
| `get_settings()` cache | Call `get_settings.cache_clear()` after `monkeypatch.setenv`, before reading settings |
| Schemathesis + OpenAPI 3.1 | Add `schemathesis.experimental.OPEN_API_3_1.enable()` at module top |
| ruff SIM105 | Use `contextlib.suppress(Exception)`, never bare `try/except/pass` |
| SQLAlchemy 2 defaults | `mapped_column(default=..., server_default=...)` does not populate normal ORM instance attrs at `__init__`; tests should inspect column metadata or flush/refresh |

## sqlglot AST Quirks

- `current_user()`, `current_schema()`, `current_database()` → special AST nodes (`exp.CurrentUser`, etc.), NOT `exp.Anonymous`.
- Add explicit `find_all(exp.SpecificNode)` checks for each function to block.
- Quoted identifiers (`"current_user"`) → `exp.Identifier`, not `exp.Column.name`.

## Phase 3: Dialect/Introspection Tests

When multi-dialect T-IDs land, add dialect-specific introspection tests for PostgreSQL, MySQL, and MSSQL.

## Docker Quirks

| Quirk | Symptom | Fix |
|---|---|---|
| Image staleness after `git pull` | Old behavior persists | `./scripts/dev-up.sh --rebuild` |
| `.env` staleness after edit | Env changes ignored | `docker compose up -d --force-recreate backend` |
| Alembic drift after `git pull` | `UndefinedColumnError` / 500s | `alembic upgrade head` or `./scripts/dev-up.sh` |
