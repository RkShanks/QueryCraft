# Wave 15 Backend Audit Findings

**Scope:**
- Phase 3 backend: source DB connections, credential storage, dialect routing, introspection, evaluator, query/session/history APIs.
- Date: 2026-05-22
- Branch: `phase-3/wave-15.0-hardening`
- Commit: `HEAD` at audit time (fixes applied in same branch)

---

## Critical

### C-1: Password embedded in PostgreSQL DSN URL
- **File:** `backend/src/app/services/connection_service.py`
- **Line:** 242 (pre-fix)
- **Impact:** If `asyncpg.connect()` raises an exception, the driver error or Python traceback may include the full connection URL, leaking the plaintext password to logs, monitoring systems, or exception trackers.
- **Reproduction:** Review `test_connection()` method constructing `f"postgresql://{conn.username}:{decrypted_password}@{conn.host}..."`.
- **Fix:** Pass connection parameters as keyword arguments (host, port, database, user, password) instead of building a DSN string. Applied in commit.

---

## High

### H-1: Raw sqlglot ParseError leaked to user-facing API responses
- **File:** `backend/src/app/evaluator/rules/dialect_validation.py`
- **Lines:** 54, 56 (pre-fix)
- **Impact:** SQL snippets or internal parser details may leak to end users via HTTP 422 responses, aiding reconnaissance.
- **Reproduction:** `DialectValidationRule` returned `f"SQL failed to parse as {self.dialect}: {exc}"` — the `exc` string contains raw SQL fragments.
- **Fix:** Return generic messages without raw exception text: `f"SQL failed to parse as {self.dialect}"`. Applied in commit.

### H-2: Raw driver errors propagated to admin API via introspection
- **File:** `backend/src/app/api/v1/admin_connections.py`
- **Line:** 232 (pre-fix)
- **Impact:** `str(e)` returned in HTTP 502 detail for introspection failures. If `e` contains a raw driver error (especially from MSSQL with embedded connection string), credentials leak to the API consumer.
- **Reproduction:** `refresh_schema` endpoint returned `{"detail": str(e)}` for `SchemaIntrospectionError`.
- **Fix:** Remove `str(e)` from the response; use only `message_key`. Applied in commit.

### H-3: MSSQL ODBC connection string embeds plaintext password
- **File:** `backend/src/app/source_db/adapters.py`
- **Lines:** 237–245
- **Impact:** `aioodbc.create_pool(dsn=conn_str)` where `conn_str` contains `PWD={password}`. Driver diagnostic records may include the full connection string on failure.
- **Reproduction:** Review `MSSQLAdapter.connect()` building the ODBC DSN.
- **Fix:** Added exception wrapping in `connect()` to catch and sanitize `aioodbc` errors before re-raising, stripping connection string content. Applied in commit.

---

## Mid

### M-1: ReadOnlyRule defaults to postgres dialect
- **File:** `backend/src/app/evaluator/rules/read_only.py`
- **Line:** 25 (pre-fix)
- **Impact:** Legacy `_get_query_service` instantiates `ReadOnlyRule()` without a dialect, meaning SQL for MySQL/MSSQL is parsed as PostgreSQL. Creates defense-in-depth gap where dialect-specific syntax might be interpreted differently.
- **Fix:** Removed default value; dialect is now required. Updated all callers and tests. Applied in commit.

### M-2: DialectValidationRule defaults to postgres dialect
- **File:** `backend/src/app/evaluator/rules/dialect_validation.py`
- **Line:** 20 (pre-fix)
- **Impact:** Same as M-1 — default dialect could lead to misconfiguration.
- **Fix:** Removed default value; dialect is now required. Updated all tests. Applied in commit.

### M-3: DB_CREDENTIAL_KEY lacks pydantic validator
- **File:** `backend/src/app/core/config.py`
- **Line:** 30
- **Impact:** If set to empty/whitespace, the app crashes during lifespan startup rather than failing at configuration load time.
- **Fix:** Startup guard in `main.py` catches this. Pydantic validator deferred to future hardening (non-blocking for Phase 3 closure).

---

## Low

### L-1: SourceDBConnectionFailed uses incorrect message key
- **File:** `backend/src/app/core/exceptions.py`
- **Line:** 124 (pre-fix)
- **Impact:** Users see `error.llmUnavailable` message when a source DB connection fails, which is confusing.
- **Fix:** Changed to `error.sourceDbConnectionFailed`. Added corresponding i18n keys in `en.json` and `ar.json`. Applied in commit.

### L-2: AsyncMock warning in schema introspector test
- **File:** `backend/src/app/source_db/schema_introspector.py`
- **Line:** 117
- **Impact:** Test-only warning; no production impact. `AsyncMockMixin._execute_mock_call` never awaited in test fixture.
- **Fix:** Test fixture issue; non-blocking for Phase 3 closure.

---

## Verification

### Commands Run

```bash
cd backend && uv run ruff check src tests
# All checks passed!

cd backend && uv run ruff format --check src tests
# 229 files already formatted

cd backend && uv run pytest -q --ignore=tests/integration --ignore=tests/acceptance --ignore=tests/contract -m "not integration"
# 617 passed, 9 deselected, 2 warnings in 6.43s
```

### Integration Tests Status
- T-472 (MySQL integration): **UNAVAILABLE** — no MySQL service running in environment.
- T-473 (MSSQL integration): **UNAVAILABLE** — no MSSQL service running in environment.
- Both documented as optional/manual per plan.md ADR-10.

---

## No Findings (Verified Areas)

- **Credential leakage in API responses:** `ConnectionResponse` and `UserConnectionResponse` correctly exclude `encrypted_password`.
- **User-facing endpoint safety:** `GET /connections` returns only `id`, `display_name`, `database_type`.
- **Hard-delete guard:** Correctly checks `is_referenced_by_accepted_queries`, `is_referenced_by_sessions`, `has_schema_entries`.
- **Disabled/unhealthy rejection:** `query.py` correctly rejects non-active, non-healthy, or un-introspected connections.
- **Schema isolation:** Prompt builder only includes selected connection's schema.
- **Read-only enforcement:** INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE blocked across all dialects.
- **Startup guard:** `main.py` calls `init_credential_provider()` which raises `ConfigurationError` on missing/invalid keys.
- **Parameterized queries:** All adapters use parameterized queries only (no string interpolation).

---

## Critical/High Finding Status

| Finding | Severity | Status |
|---------|----------|--------|
| C-1: Password in DSN | Critical | **FIXED** |
| H-1: ParseError leak | High | **FIXED** |
| H-2: Raw error in admin API | High | **FIXED** |
| H-3: MSSQL password in DSN | High | **FIXED** (sanitized) |

All Critical and High findings from the backend audit have been fixed in this branch.
