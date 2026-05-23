"""Tests for RoleConnectionPolicy ORM model (T-609)."""

from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.models.role_connection_policy import RoleConnectionPolicy


class TestRoleConnectionPolicyModel:
    """RoleConnectionPolicy ORM model metadata and instantiation."""

    def test_table_name(self):
        assert RoleConnectionPolicy.__tablename__ == "role_connection_policies"

    def test_can_instantiate(self):
        policy = RoleConnectionPolicy(
            id=uuid4(),
            role_id=uuid4(),
            connection_id=uuid4(),
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
            row_filters=[{"table": "orders", "filter": "region = 'US'"}],
            column_masks=[{"table": "customers", "columns": ["email"]}],
        )
        assert policy.allowed_tables is not None

    def test_id_column_type(self):
        assert isinstance(RoleConnectionPolicy.__table__.c.id.type, PG_UUID)

    def test_role_id_fk(self):
        fk_tables = {fk.column.table.name for fk in RoleConnectionPolicy.__table__.foreign_keys}
        assert "roles" in fk_tables

    def test_connection_id_fk(self):
        fk_tables = {fk.column.table.name for fk in RoleConnectionPolicy.__table__.foreign_keys}
        assert "source_database_connections" in fk_tables

    def test_unique_role_connection(self):
        constraints = [c for c in RoleConnectionPolicy.__table__.constraints if hasattr(c, "columns")]
        uc_names = {c.name for c in constraints if "unique" in str(type(c)).lower()}
        # There should be a unique constraint on (role_id, connection_id)
        assert any("role_id_connection_id" in (name or "") for name in uc_names)
