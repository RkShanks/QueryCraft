"""T-721: Cross-dialect policy enforcement tests (FR-131, FR-132, SC-051, SC-052).

End-to-end verification of row filters + column masks against real source
databases for each of the three supported dialects. The test exercises the
loop:

    1. Create a per-test table with the columns needed for filtering
       and masking.
    2. Insert known fixture rows (2 matching + 1 non-matching for the
       row filter; sensitive values for the column mask).
    3. Call ``PolicyEnforcementService.apply_row_filters`` with a
       ``{user.role}`` placeholder filter.
    4. Execute the rewritten SQL against the real source DB via the
       native async driver (asyncpg / asyncmy / aioodbc).
    5. Verify the row count and that the non-matching rows are NOT
       returned (row filter enforced at the DB level, not in app code).
    6. Call ``PolicyEnforcementService.apply_column_masks`` on the
       executed ``QueryResult``.
    7. Verify the masked cells are ``"***"`` and no raw sensitive value
       leaks into the response.
    8. Verify the dialect-specific placeholder style is present in the
       rewritten SQL (postgres ``$N``, mysql ``%s``, mssql ``?``).

Dialect coverage is per-dialect fixture. Each fixture does a real
connection check on a function-scoped engine and ``pytest.skip``s with
a precise reason if the dialect is unavailable. Function scope is
deliberate: it keeps the engine's connection pool bound to the test's
event loop (a session-scoped engine with per-test event loops triggers
``RuntimeError: ... attached to a different loop`` in asyncpg /
asyncmy / aioodbc).

Dialect env (matches ``docker-compose.dev.yml`` source services):

    PG:    localhost:5434 / pagila_user         / source_analytics
    MySQL: localhost:3306 / sakila_user         / sakila
    MSSQL: localhost:1433 / adventureworks_user / AdventureWorksLT

Table strategy (per dialect, dropped on teardown):

    PG:    CREATE TEMP TABLE qc_test_t721_<uuid> (...) ON COMMIT DROP
    MySQL: CREATE TEMPORARY TABLE qc_test_t721_<uuid> (...)
    MSSQL: CREATE TABLE #qc_test_t721_<uuid> (...) -- local temp table in tempdb

For PG the DDL, INSERTs, and SELECT are wrapped in a single transaction
so ``ON COMMIT DROP`` fires at the end (the SELECT is the last query in
the transaction). For MySQL ``TEMPORARY TABLE`` drops on connection
close. For MSSQL the local temp table drops when the connection
(session) closes. A best-effort explicit ``DROP TABLE`` runs at
teardown to clean up if the connection close drops the table.

This file is ``@pytest.mark.integration`` (auto-marked by the
``/tests/integration/`` path in ``conftest.py``). The fast backend
gate is ``tests/unit -m "not integration"`` -- this file is excluded.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import aioodbc
import asyncmy
import asyncpg
import pytest
import pytest_asyncio

from app.core.exceptions import PolicySchemaConflictError
from app.evaluator.schema_context import Column, SchemaContext, Table
from app.schemas.query import ColumnMeta, QueryResult
from app.services.policy_enforcement import PolicyEnforcementService

# ---------------------------------------------------------------------------
# Per-dialect skip helpers
# ---------------------------------------------------------------------------

# Per-dialect env defaults. Override with environment variables for CI.
_PG_HOST = os.environ.get("QC_T721_PG_HOST", "localhost")
_PG_PORT = int(os.environ.get("QC_T721_PG_PORT", "5434"))
_PG_USER = os.environ.get("QC_T721_PG_USER", "pagila_user")
_PG_PASSWORD = os.environ.get("QC_T721_PG_PASSWORD", "pagila_dev_pwd")
_PG_DB = os.environ.get("QC_T721_PG_DB", "source_analytics")

_MYSQL_HOST = os.environ.get("QC_T721_MYSQL_HOST", "localhost")
_MYSQL_PORT = int(os.environ.get("QC_T721_MYSQL_PORT", "3306"))
# Use the MySQL root user (sakila_user is read-only on the sakila
# database, so TEMPORARY TABLE creation is denied). The .env / docker
# compose default is sakila_root_dev.
_MYSQL_USER = os.environ.get("QC_T721_MYSQL_USER", "root")
_MYSQL_PASSWORD = os.environ.get("QC_T721_MYSQL_PASSWORD", "sakila_root_dev")
_MYSQL_DB = os.environ.get("QC_T721_MYSQL_DB", "sakila")

_MSSQL_HOST = os.environ.get("QC_T721_MSSQL_HOST", "localhost")
_MSSQL_PORT = int(os.environ.get("QC_T721_MSSQL_PORT", "1433"))
# Use the MSSQL sa user (adventureworks_user is read-only on the
# AdventureWorksLT database, so CREATE TABLE in user schemas is
# denied). Local temp tables (#table) live in tempdb, but we still
# need an account with CREATE rights; SA is the docker-compose
# default. The .env / docker compose default password is
# AdventureWorks_dev_1433!.
_MSSQL_USER = os.environ.get("QC_T721_MSSQL_USER", "sa")
_MSSQL_PASSWORD = os.environ.get("QC_T721_MSSQL_PASSWORD", "AdventureWorks_dev_1433!")
_MSSQL_DB = os.environ.get("QC_T721_MSSQL_DB", "AdventureWorksLT")


# User context the row filter will bind against. Mirrors
# ``test_row_filter_injection.py::USER``.
USER_CONTEXT: dict[str, str] = {
    "email": "a@b.c",
    "subject_id": "sso|x",
    "role": "east",
}

TABLE_SUFFIX = "t721"


def _table_name() -> str:
    """Per-test unique table name suffix to avoid cross-test collisions.

    ``str(uuid.uuid4())[:8]`` is short enough to stay under PG's 63-char
    identifier limit even with the ``qc_test_`` prefix.
    """
    return f"qc_test_{TABLE_SUFFIX}_{uuid.uuid4().hex[:8]}"


def _make_test_schema(table: str) -> SchemaContext:
    """Schema matching the per-test temp table created in each dialect."""
    return SchemaContext(
        tables=[
            Table(
                name=table,
                schema_name="public",
                columns=[
                    Column(name="id", type="integer", nullable=False, primary_key=True),
                    Column(name="region", type="text", nullable=False),
                    Column(name="ssn", type="text", nullable=True),
                    Column(name="secret_name", type="text", nullable=True),
                ],
            )
        ]
    )


def _row_filter(table: str) -> dict[str, str]:
    """Row filter that matches exactly 2 of the 3 fixture rows."""
    return {"table": table, "filter": "region = {user.role}"}


def _column_masks(table: str) -> list[dict[str, list[str]]]:
    """Column mask config: mask ``ssn`` and ``secret_name``."""
    return [{"table": table, "columns": ["ssn", "secret_name"]}]


def _assert_no_sensitive_leak(masked: QueryResult, fixture_ssns: set[str], fixture_names: set[str]) -> None:
    """Assert that no raw fixture SSN or secret_name value appears anywhere in
    the masked QueryResult (rows + generated_sql + question)."""
    blob_parts: list[str] = [masked.generated_sql, masked.question]
    for row in masked.rows:
        for cell in row:
            if isinstance(cell, str):
                blob_parts.append(cell)
    blob = " ".join(blob_parts)
    for ssn in fixture_ssns:
        assert ssn not in blob, f"Raw SSN '{ssn}' leaked into masked result: {masked!r}"
    for name in fixture_names:
        assert name not in blob, f"Raw secret_name '{name}' leaked into masked result: {masked!r}"


# ---------------------------------------------------------------------------
# Per-test raw-connection fixtures (function-scoped to avoid cross-event-loop)
# ---------------------------------------------------------------------------


async def _make_asyncpg_or_skip() -> Any:
    """Connect to the postgres-source dev service via raw asyncpg."""
    try:
        conn = await asyncpg.connect(
            host=_PG_HOST,
            port=_PG_PORT,
            user=_PG_USER,
            password=_PG_PASSWORD,
            database=_PG_DB,
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL source DB not reachable for T-721: {type(exc).__name__}: {exc}")
        raise  # unreachable
    return conn


async def _make_asyncmy_or_skip() -> Any:
    """Connect to the mysql-source dev service via raw asyncmy."""
    try:
        conn = await asyncmy.connect(
            host=_MYSQL_HOST,
            port=_MYSQL_PORT,
            user=_MYSQL_USER,
            password=_MYSQL_PASSWORD,
            database=_MYSQL_DB,
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"MySQL source DB not reachable for T-721: {type(exc).__name__}: {exc}")
        raise  # unreachable
    return conn


async def _make_aioodbc_or_skip() -> Any:
    """Connect to the mssql-source dev service via raw aioodbc.

    Skipped with a precise reason if the unixODBC + Microsoft ODBC
    Driver 18 system libraries are not installed.
    """
    try:
        import ctypes

        ctypes.cdll.LoadLibrary("libodbc.so.2")
    except OSError as exc:
        pytest.skip(
            "MSSQL cross-dialect test requires the unixODBC system "
            "library (`libodbc.so.2`) and Microsoft ODBC Driver 18 "
            f"for SQL Server; ctypes load failed: {exc}. "
            "Install with `apt-get install unixodbc` and the official "
            "Microsoft msodbcsql18 package."
        )
        raise  # unreachable
    dsn = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={_MSSQL_HOST},{_MSSQL_PORT};"
        f"UID={_MSSQL_USER};"
        f"PWD={_MSSQL_PASSWORD};"
        f"DATABASE={_MSSQL_DB};"
        "TrustServerCertificate=yes;"
    )
    try:
        conn = await aioodbc.connect(dsn=dsn)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"MSSQL source DB not reachable for T-721: {type(exc).__name__}: {exc}")
        raise  # unreachable
    return conn


@pytest_asyncio.fixture
async def pg_conn() -> AsyncGenerator[Any, None]:
    """asyncpg connection against the postgres-source dev service."""
    conn = await _make_asyncpg_or_skip()
    try:
        yield conn
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def mysql_conn() -> AsyncGenerator[Any, None]:
    """asyncmy connection against the mysql-source dev service."""
    conn = await _make_asyncmy_or_skip()
    try:
        yield conn
    finally:
        await conn.ensure_closed()


@pytest_asyncio.fixture
async def mssql_conn() -> AsyncGenerator[Any, None]:
    """aioodbc connection against the mssql-source dev service."""
    conn = await _make_aioodbc_or_skip()
    try:
        yield conn
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Per-test data helpers
# ---------------------------------------------------------------------------


def _pg_ddl(table: str) -> str:
    return (
        f"CREATE TEMP TABLE {table} (id INTEGER PRIMARY KEY, "
        "region TEXT NOT NULL, ssn TEXT, secret_name TEXT) ON COMMIT DROP"
    )


def _mysql_ddl(table: str) -> str:
    return f"CREATE TEMPORARY TABLE {table} (id INTEGER PRIMARY KEY, region TEXT NOT NULL, ssn TEXT, secret_name TEXT)"


def _mssql_ddl(table: str) -> str:
    # MSSQL: regular (non-temp) table. We connect as ``sa`` which has
    # CREATE rights on the user schema. (A local temp table in
    # ``tempdb`` would also work, but the ``#`` prefix would then
    # need to be threaded through the input SQL and the schema
    # context -- a regular table is simpler and matches the policy
    # pattern of an admin-named target table.)
    return (
        f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, "
        f"region NVARCHAR(50) NOT NULL, ssn NVARCHAR(50) NULL, "
        f"secret_name NVARCHAR(100) NULL)"
    )


_MSSQL_DROP_SQL = "DROP TABLE {table}"


_FIXTURE_ROWS: list[tuple[int, str, str, str]] = [
    (1, "east", "111-11-1111", "alice-secret"),
    (2, "east", "222-22-2222", "bob-secret"),
    (3, "west", "333-33-3333", "carol-secret"),
]


# ---------------------------------------------------------------------------
# End-to-end test loop
# ---------------------------------------------------------------------------


async def _execute_and_assert(
    conn: Any,
    *,
    dialect: str,
    ddl_fn,
    expected_placeholder: str,
    expected_row_count: int,
) -> QueryResult:
    """Run the full filter+execute+mask loop and assert the contract.

    The caller passes a raw async driver connection (asyncpg /
    asyncmy / aioodbc). SQLAlchemy is not used here because its
    ``text()`` does not natively bind dialect-specific placeholders
    (``$N`` / ``%s`` / ``?``).
    """
    table = _table_name()
    rows = _FIXTURE_ROWS
    ddl = ddl_fn(table)

    if dialect == "postgres":
        return await _execute_postgres(
            conn,
            table=table,
            ddl=ddl,
            rows=rows,
            expected_placeholder=expected_placeholder,
            expected_row_count=expected_row_count,
        )
    if dialect == "mysql":
        return await _execute_mysql(
            conn,
            table=table,
            ddl=ddl,
            rows=rows,
            expected_placeholder=expected_placeholder,
            expected_row_count=expected_row_count,
        )
    if dialect == "mssql":
        return await _execute_mssql(
            conn,
            table=table,
            ddl=ddl,
            rows=rows,
            expected_placeholder=expected_placeholder,
            expected_row_count=expected_row_count,
        )
    raise ValueError(f"unsupported dialect: {dialect}")


async def _build_masked_result(
    *,
    dialect: str,
    table: str,
    db_rows: list,
    db_columns: list[str],
    bound_sql: str,
    expected_row_count: int,
    expected_placeholder: str,
) -> QueryResult:
    """Common assertions + result construction shared by all dialects."""
    # Placeholder style is correct for this dialect.
    assert expected_placeholder in bound_sql, (
        f"[{dialect}] expected placeholder '{expected_placeholder}' in rewritten SQL: {bound_sql!r}"
    )
    # No leftover user-context placeholder syntax (defence in depth).
    assert "{user" not in bound_sql, f"[{dialect}] raw user placeholder leaked into SQL: {bound_sql!r}"

    # Row count: exactly the matching rows.
    assert len(db_rows) == expected_row_count, (
        f"[{dialect}] expected {expected_row_count} rows after row filter, got {len(db_rows)}: {db_rows!r}"
    )

    # Every returned row has region='east' (the bound value).
    region_idx = db_columns.index("region")
    for r in db_rows:
        assert r[region_idx] == "east", f"[{dialect}] row filter not enforced: region={r[region_idx]!r} in row {r!r}"

    # Build a QueryResult from the executed rows.
    columns_meta = [ColumnMeta(name=name, type="text") for name in db_columns]
    result = QueryResult(
        attempt_id=str(uuid.uuid4()),
        session_id="t721-session",
        question="T-721 cross-dialect enforcement test",
        generated_sql=bound_sql,
        columns=columns_meta,
        rows=[list(r) for r in db_rows],
        row_count=len(db_rows),
        attempt_number=1,
        is_last_auto_retry=False,
    )

    # Apply column masks.
    masked = PolicyEnforcementService.apply_column_masks(result=result, column_masks=_column_masks(table))

    # Verify masked cells are '***' and ColumnMeta.masked=True.
    ssn_idx = db_columns.index("ssn")
    name_idx = db_columns.index("secret_name")
    id_idx = db_columns.index("id")
    for r in masked.rows:
        assert r[ssn_idx] == "***", f"[{dialect}] ssn not masked: row={r!r}"
        assert r[name_idx] == "***", f"[{dialect}] secret_name not masked: row={r!r}"
        # Non-masked column retains its raw value (mask is column-scoped).
        assert isinstance(r[id_idx], int), f"[{dialect}] non-masked id column changed: row={r!r}"
    assert masked.columns[ssn_idx].masked is True
    assert masked.columns[name_idx].masked is True
    # id column is not masked.
    assert masked.columns[id_idx].masked is False

    # No raw sensitive value leaks into the masked QueryResult.
    fixture_ssns = {r[2] for r in _FIXTURE_ROWS}
    fixture_names = {r[3] for r in _FIXTURE_ROWS}
    _assert_no_sensitive_leak(masked, fixture_ssns, fixture_names)
    return masked


def _apply_row_filter(dialect: str, table: str) -> Any:
    """Call ``PolicyEnforcementService.apply_row_filters`` once."""
    return PolicyEnforcementService.apply_row_filters(
        sql=f"SELECT id, region, ssn, secret_name FROM {table}",
        row_filters=[_row_filter(table)],
        schema=_make_test_schema(table),
        user_context=USER_CONTEXT,
        dialect=dialect,
    )


async def _execute_postgres(
    conn: Any,
    *,
    table: str,
    ddl: str,
    rows: list[tuple],
    expected_placeholder: str,
    expected_row_count: int,
) -> QueryResult:
    """PG: DDL + INSERTs + SELECT in one transaction; ON COMMIT DROP.

    Uses the raw asyncpg connection because SQLAlchemy's ``text()``
    does not natively bind ``$N`` placeholders. asyncpg accepts
    ``$N`` directly via its prepared-statement protocol.
    """
    bound = _apply_row_filter("postgres", table)
    async with conn.transaction():
        await conn.execute(ddl)
        await conn.executemany(
            f"INSERT INTO {table} (id, region, ssn, secret_name) VALUES ($1, $2, $3, $4)",
            rows,
        )
        db_records = await conn.fetch(bound.sql, *bound.params)
    db_columns = list(db_records[0].keys()) if db_records else ["id", "region", "ssn", "secret_name"]
    db_rows = [tuple(r[c] for c in db_columns) for r in db_records]
    # Transaction committed -> ON COMMIT DROP fires -> table is gone.
    return await _build_masked_result(
        dialect="postgres",
        table=table,
        db_rows=db_rows,
        db_columns=db_columns,
        bound_sql=bound.sql,
        expected_row_count=expected_row_count,
        expected_placeholder=expected_placeholder,
    )


async def _execute_mysql(
    conn: Any,
    *,
    table: str,
    ddl: str,
    rows: list[tuple],
    expected_placeholder: str,
    expected_row_count: int,
) -> QueryResult:
    """MySQL: TEMPORARY TABLE scoped to this connection.

    Uses the raw asyncmy connection because SQLAlchemy's ``text()``
    does not natively bind ``%s`` placeholders. asyncmy expands
    ``%s`` to the bound values.
    """
    bound = _apply_row_filter("mysql", table)
    async with conn.cursor() as cur:
        await cur.execute(ddl)
        await cur.executemany(
            f"INSERT INTO {table} (id, region, ssn, secret_name) VALUES (%s, %s, %s, %s)",
            rows,
        )
        await cur.execute(bound.sql, bound.params)
        db_records = await cur.fetchall()
        db_columns = [d[0] for d in cur.description] if cur.description else []
    await conn.commit()
    db_rows = [tuple(r) for r in db_records]
    return await _build_masked_result(
        dialect="mysql",
        table=table,
        db_rows=db_rows,
        db_columns=db_columns,
        bound_sql=bound.sql,
        expected_row_count=expected_row_count,
        expected_placeholder=expected_placeholder,
    )


async def _execute_mssql(
    conn: Any,
    *,
    table: str,
    ddl: str,
    rows: list[tuple],
    expected_placeholder: str,
    expected_row_count: int,
) -> QueryResult:
    """MSSQL: regular (non-temp) table scoped to this test.

    Uses the raw aioodbc / pyodbc connection because SQLAlchemy's
    ``text()`` does not natively bind ``?`` placeholders. pyodbc
    accepts ``?`` directly via its DBAPI. The table is dropped at
    teardown (best-effort) so subsequent tests cannot collide.
    """
    bound = _apply_row_filter("mssql", table)
    try:
        async with conn.cursor() as cur:
            await cur.execute(ddl)
            insert_sql = f"INSERT INTO {table} (id, region, ssn, secret_name) VALUES (?, ?, ?, ?)"
            await cur.executemany(insert_sql, rows)
            await cur.execute(bound.sql, bound.params)
            db_records = await cur.fetchall()
            db_columns = [d[0] for d in cur.description] if cur.description else []
        await conn.commit()
    finally:
        # Best-effort cleanup. Failure here is non-fatal (the next
        # test uses a unique table name).
        try:
            async with conn.cursor() as cur:
                await cur.execute(_MSSQL_DROP_SQL.format(table=table))
            await conn.commit()
        except Exception:  # noqa: BLE001
            pass
    db_rows = [tuple(r) for r in db_records]
    return await _build_masked_result(
        dialect="mssql",
        table=table,
        db_rows=db_rows,
        db_columns=db_columns,
        bound_sql=bound.sql,
        expected_row_count=expected_row_count,
        expected_placeholder=expected_placeholder,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPostgresCrossDialectPolicy:
    """PG: row filter + column mask against a real Postgres source DB."""

    @pytest.mark.asyncio
    async def test_row_filter_and_mask_postgres(self, pg_conn: Any) -> None:
        """PG: 3 rows, filter region=east -> 2 rows, ssn + secret_name masked."""
        await _execute_and_assert(
            pg_conn,
            dialect="postgres",
            ddl_fn=_pg_ddl,
            expected_placeholder="$",
            expected_row_count=2,
        )


@pytest.mark.integration
class TestMysqlCrossDialectPolicy:
    """MySQL: row filter + column mask against a real MySQL source DB."""

    @pytest.mark.asyncio
    async def test_row_filter_and_mask_mysql(self, mysql_conn: Any) -> None:
        """MySQL: 3 rows, filter region=east -> 2 rows, ssn + secret_name masked."""
        await _execute_and_assert(
            mysql_conn,
            dialect="mysql",
            ddl_fn=_mysql_ddl,
            expected_placeholder="%s",
            expected_row_count=2,
        )


@pytest.mark.integration
class TestMssqlCrossDialectPolicy:
    """MSSQL: row filter + column mask against a real MSSQL source DB.

    Skipped when the ODBC system library is not installed. See
    ``mssql_conn`` fixture for the precise blocker.
    """

    @pytest.mark.asyncio
    async def test_row_filter_and_mask_mssql(self, mssql_conn: Any) -> None:
        """MSSQL: 3 rows, filter region=east -> 2 rows, ssn + secret_name masked."""
        await _execute_and_assert(
            mssql_conn,
            dialect="mssql",
            ddl_fn=_mssql_ddl,
            expected_placeholder="?",
            expected_row_count=2,
        )


@pytest.mark.integration
class TestPostgresSchemaDrift:
    """PG: PolicyEnforcementService.apply_row_filters fail-closed on drift.

    Mirrors the schema-drift guard (T-705). The drift must surface
    before the SQL is ever sent to the DB.
    """

    @pytest.mark.asyncio
    async def test_drift_raises_before_db_execution(self, pg_conn: Any) -> None:
        """Drift: filter references a column not in the schema."""
        table = _table_name()
        # Schema intentionally missing 'ghost_column'.
        schema = SchemaContext(
            tables=[
                Table(
                    name=table,
                    schema_name="public",
                    columns=[
                        Column(
                            name="id",
                            type="integer",
                            nullable=False,
                            primary_key=True,
                        ),
                        Column(name="region", type="text", nullable=False),
                    ],
                )
            ]
        )
        drift_filter = {"table": table, "filter": "ghost_column = {user.role}"}
        with pytest.raises(PolicySchemaConflictError):
            PolicyEnforcementService.apply_row_filters(
                sql=f"SELECT id FROM {table}",
                row_filters=[drift_filter],
                schema=schema,
                user_context=USER_CONTEXT,
                dialect="postgres",
            )
        # DB was never touched (drift raises before execution). The
        # connection should still be usable -- run a benign query as
        # a positive confirmation.
        v = await pg_conn.fetchval("SELECT 1::int AS ok")
        assert v == 1


@pytest.mark.integration
class TestDialectPlaceholderStyleUniqueness:
    """Verify the three dialect placeholder styles are mutually distinct.

    Re-uses the public ``PolicyEnforcementService.apply_row_filters``
    entry point. This is a fast sanity check that does not require any
    DB connection -- asserted at the SQL-string level only. The
    end-to-end tests in the dialect classes above are the authoritative
    "the SQL is actually accepted by the native driver" check.
    """

    @pytest.mark.asyncio
    async def test_postgres_uses_dollar_numbered(self) -> None:
        bound = _apply_row_filter("postgres", _table_name())
        assert "$1" in bound.sql
        assert "%s" not in bound.sql
        assert "?" not in bound.sql

    @pytest.mark.asyncio
    async def test_mysql_uses_percent_s(self) -> None:
        bound = _apply_row_filter("mysql", _table_name())
        assert "%s" in bound.sql
        assert "$1" not in bound.sql
        assert "?" not in bound.sql

    @pytest.mark.asyncio
    async def test_mssql_uses_question_mark(self) -> None:
        bound = _apply_row_filter("mssql", _table_name())
        assert "?" in bound.sql
        assert "$1" not in bound.sql
        assert "%s" not in bound.sql
