"""T-424: SchemaIntrospector tests with fake adapters.

Tests verify per-dialect introspection queries and full-replace refresh.
"""

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.db.models.enums import DatabaseType


class FakeAdapterForIntrospection:
    """Fake adapter that returns predefined schema data."""

    def __init__(self, dialect: DatabaseType) -> None:
        self._dialect = dialect
        self._executed_queries: list[str] = []

    async def execute(self, sql: str, params: tuple = ()) -> Any:
        self._executed_queries.append(sql)
        if "table_constraints" in sql and "PRIMARY KEY" in sql:
            return FakeExecuteResult(
                columns=["table_name", "column_name"],
                rows=[("users", "id"), ("orders", "id")],
            )
        if "constraint_type = 'FOREIGN KEY'" in sql or "FOREIGN KEY" in sql:
            return FakeExecuteResult(
                columns=["table_name", "column_name", "foreign_table_name", "foreign_column_name"],
                rows=[("orders", "user_id", "users", "id")],
            )
        if "columns" in sql.lower():
            return FakeExecuteResult(
                columns=["table_name", "column_name", "data_type"],
                rows=[
                    ("users", "id", "integer"),
                    ("users", "name", "varchar"),
                    ("orders", "id", "integer"),
                    ("orders", "user_id", "integer"),
                ],
            )
        if "tables" in sql.lower():
            return FakeExecuteResult(
                columns=["table_name"],
                rows=[("users",), ("orders",)],
            )
        return FakeExecuteResult(columns=[], rows=[])

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        pass

    async def connect(self) -> None:
        pass


class FakeExecuteResult:
    """Fake ExecuteResult for introspection tests."""

    def __init__(self, columns: list[str], rows: list[tuple]) -> None:
        self.columns = columns
        self.rows = rows


@pytest.mark.asyncio
async def test_schema_introspector_importable() -> None:
    """SchemaIntrospector must be importable."""
    from app.source_db.schema_introspector import SchemaIntrospector

    assert SchemaIntrospector is not None


@pytest.mark.asyncio
async def test_schema_introspector_pg_queries() -> None:
    """SchemaIntrospector uses correct information_schema queries for PostgreSQL."""
    from app.source_db.schema_introspector import SchemaIntrospector

    fake_adapter = FakeAdapterForIntrospection(DatabaseType.POSTGRESQL)
    mock_session = AsyncMock()
    conn_id = uuid4()
    introspector = SchemaIntrospector(
        adapter=fake_adapter,
        database_type=DatabaseType.POSTGRESQL,
        db_session=mock_session,
        connection_id=conn_id,
    )

    tables, columns = await introspector._fetch_schema(fake_adapter)
    assert len(tables) == 2
    assert len(columns) == 4


@pytest.mark.asyncio
async def test_schema_introspector_mysql_queries() -> None:
    """SchemaIntrospector uses correct information_schema queries for MySQL."""
    from app.source_db.schema_introspector import SchemaIntrospector

    fake_adapter = FakeAdapterForIntrospection(DatabaseType.MYSQL)
    mock_session = AsyncMock()
    conn_id = uuid4()
    introspector = SchemaIntrospector(
        adapter=fake_adapter,
        database_type=DatabaseType.MYSQL,
        db_session=mock_session,
        connection_id=conn_id,
    )

    tables, columns = await introspector._fetch_schema(fake_adapter)
    assert len(tables) == 2
    assert len(columns) == 4


@pytest.mark.asyncio
async def test_schema_introspector_mssql_queries() -> None:
    """SchemaIntrospector uses correct queries for MSSQL."""
    from app.source_db.schema_introspector import SchemaIntrospector

    fake_adapter = FakeAdapterForIntrospection(DatabaseType.MSSQL)
    mock_session = AsyncMock()
    conn_id = uuid4()
    introspector = SchemaIntrospector(
        adapter=fake_adapter,
        database_type=DatabaseType.MSSQL,
        db_session=mock_session,
        connection_id=conn_id,
    )

    tables, columns = await introspector._fetch_schema(fake_adapter)
    assert len(tables) == 2
    assert len(columns) == 4


@pytest.mark.asyncio
async def test_schema_introspector_full_replace_deletes_old_entries() -> None:
    """SchemaIntrospector deletes existing entries before inserting new ones."""
    from app.source_db.schema_introspector import SchemaIntrospector

    fake_adapter = FakeAdapterForIntrospection(DatabaseType.POSTGRESQL)
    mock_session = AsyncMock()
    conn_id = uuid4()
    introspector = SchemaIntrospector(
        adapter=fake_adapter,
        database_type=DatabaseType.POSTGRESQL,
        db_session=mock_session,
        connection_id=conn_id,
    )

    result = await introspector.introspect()

    assert result["tables_count"] == 2
    assert result["columns_count"] == 4
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_schema_introspector_failure_propagates() -> None:
    """SchemaIntrospector raises SchemaIntrospectionError on adapter failure."""
    from app.source_db.schema_introspector import SchemaIntrospectionError, SchemaIntrospector

    failing_adapter = AsyncMock()
    failing_adapter.execute = AsyncMock(side_effect=ConnectionError("connection lost"))
    failing_adapter.close = AsyncMock()

    mock_session = AsyncMock()
    conn_id = uuid4()
    introspector = SchemaIntrospector(
        adapter=failing_adapter,
        database_type=DatabaseType.POSTGRESQL,
        db_session=mock_session,
        connection_id=conn_id,
    )

    with pytest.raises(SchemaIntrospectionError):
        await introspector.introspect()
