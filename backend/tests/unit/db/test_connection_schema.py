"""T-423: ConnectionSchemaEntry ORM model tests."""

import pytest


@pytest.mark.asyncio
async def test_connection_schema_entry_model_exists() -> None:
    """ConnectionSchemaEntry model must be importable."""
    from app.db.models.connection_schema import ConnectionSchemaEntry

    assert ConnectionSchemaEntry is not None
    assert ConnectionSchemaEntry.__tablename__ == "connection_schema_entries"


@pytest.mark.asyncio
async def test_connection_schema_entry_columns() -> None:
    """ConnectionSchemaEntry has all required columns."""
    from app.db.models.connection_schema import ConnectionSchemaEntry

    columns = {c.name for c in ConnectionSchemaEntry.__table__.columns}
    expected = {
        "id",
        "connection_id",
        "table_name",
        "column_name",
        "column_data_type",
        "is_primary_key",
        "foreign_key_table",
        "foreign_key_column",
        "introspected_at",
    }
    assert columns == expected


@pytest.mark.asyncio
async def test_connection_schema_entry_fk_cascade() -> None:
    """ConnectionSchemaEntry FK to source_database_connections has CASCADE DELETE."""
    from app.db.models.connection_schema import ConnectionSchemaEntry

    fks = list(ConnectionSchemaEntry.__table__.foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.column.table.name == "source_database_connections"
