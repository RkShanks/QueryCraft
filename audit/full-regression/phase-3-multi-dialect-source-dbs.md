# Phase 3 - Multi-Dialect Source DB Regression

Source scope: `specs/003-multi-dialect-source-dbs/`.

## Scope Summary

Phase 3 adds admin-managed PostgreSQL, MySQL, and MSSQL source database
connections; encrypted credentials; schema introspection; per-session database
selection; dialect-aware prompt/evaluator/execution routing; connection lifecycle
states; and multi-database UI polish.

## Regression Task Matrix

Use `Status` values `Pending`, `Pass`, `Fail`, or `Skipped`. Fill `Evidence`
with command output paths, screenshot/trace paths, or short notes during the run.

| Task | Status | Evidence |
|---|---|---|
| Admin can add, edit, test, disable, enable, and hard-delete eligible source connections. | Pending | |
| Passwords are encrypted at rest and never returned after save. | Pending | |
| First successful save runs health check and initial schema introspection. | Pending | |
| Schema refresh replaces prior metadata and reports failures without using stale data silently. | Pending | |
| Workspace database selector is per-session, disabled until selected when multiple active connections exist, and auto-selects when exactly one exists. | Pending | |
| Generated/evaluated SQL matches selected dialect: PostgreSQL, MySQL, or T-SQL. | Pending | |
| Response cards and history show friendly connection name and database type. | Pending | |
| Legacy Phase 1/2 rows are backfilled with the migrated PostgreSQL connection. | Pending | |
| Localized errors sanitize raw driver details and credentials. | Pending | |

## Backend Commands

```bash
cd backend && rtk uv run pytest tests/unit/db/test_migration_006_phase3.py tests/unit/db/test_source_database_connection_model.py tests/unit/db/test_connection_schema.py tests/unit/db/test_session_connection_id.py tests/unit/source_db tests/unit/api/test_admin_connections.py tests/unit/api/test_connections.py tests/unit/api/test_session_connection.py tests/unit/api/test_query_connection_routing.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/evaluator/test_dialect_evaluator.py tests/unit/evaluator/test_dialect_validation.py tests/unit/evaluator/test_read_only.py tests/unit/test_cross_dialect_verification.py tests/unit/api/test_admin_refresh_schema.py -x --tb=short
cd backend && rtk uv run ruff check src tests
cd backend && rtk uv run ruff format --check src tests
```

## Frontend Commands

```bash
cd frontend && rtk npm test -- --run
cd frontend && rtk npm run lint
cd frontend && rtk npm run typecheck
cd frontend && rtk npm run build
cd frontend && rtk npm run lint:css
cd frontend && rtk npm run test:e2e -- wave_16_3_smoke.spec.ts
```

## Browser / Manual Smoke Checks

- Admin connection list loads with PostgreSQL, MySQL, and MSSQL entries.
- Add/edit form masks existing password and validates required fields.
- Test connection and refresh schema success/failure states render localized
  messages.
- Workspace selector lists only active, usable connections and persists the
  selected connection on the session.
- Ask the same question against PostgreSQL and MySQL; inspect generated SQL for
  dialect-specific shape and response-card attribution.
- Disable a selected connection, then verify the next query asks the user to
  select a different database.

## API Checks

- `/api/v1/admin/connections` CRUD, health, schema refresh, disable/enable, and
  blocked hard-delete.
- `/api/v1/connections` user selector list filters disabled/unusable
  connections.
- Query submit/execute persists and respects `connection_id`.
- API responses never include plaintext password, connection string, raw driver
  stack, or credential values.

## Real LLM Smoke

Applicable for dialect routing. With all source DB services running and a real
provider configured, submit one small question against PostgreSQL, MySQL, and
MSSQL. Capture generated SQL and at least one dialect marker or documented valid
dialect evidence per database.

## Expected Pass Criteria

- Commands pass.
- All three source DB adapters/introspection paths work or any service-specific
  failure is clearly marked as environment setup.
- Unvalidated SQL is never executed after dialect parse failure.
- Single-connection behavior remains compatible with earlier phases.

## Known Local Skips / Limitations

- Real MySQL/MSSQL service tests require `mysql-source` and `mssql-source`
  compose services plus ODBC dependencies for host-run MSSQL checks.
- Duplicate display names are allowed; UI must disambiguate with database type.
- Schema refresh is manual after initial save.

## Evidence To Capture

- Docker compose status for all three source DBs.
- Command logs.
- Screenshots for admin connection list/form, schema summary, selector, and
  response-card connection badge.
- Redacted API payloads showing no plaintext credentials.
- Generated SQL snippets for PostgreSQL, MySQL, and MSSQL smoke.

## Update Notes For Future Waves

If new source dialects are added, extend this file with adapter, evaluator,
introspection, selector, and real-smoke checks. Do not weaken the three existing
dialect checks.
