"""Tests for Session model connection_id FK (T-402, FR-094)."""

from sqlalchemy import inspect

from app.db.models.session import Session


class TestSessionConnectionId:
    """Verify Session model has connection_id nullable FK."""

    def test_has_connection_id_column(self):
        mapper = inspect(Session)
        col_names = {c.key for c in mapper.column_attrs}
        assert "connection_id" in col_names

    def test_connection_id_nullable(self):
        col = Session.__table__.c.connection_id
        assert col.nullable is True

    def test_connection_id_fk_targets_source_database_connections(self):
        fks = list(Session.__table__.c.connection_id.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "source_database_connections"
