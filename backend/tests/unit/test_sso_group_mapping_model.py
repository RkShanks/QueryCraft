"""Tests for SsoGroupMapping ORM model (T-611)."""

from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.models.sso_group_mapping import SsoGroupMapping


class TestSsoGroupMappingModel:
    """SsoGroupMapping ORM model metadata and instantiation."""

    def test_table_name(self):
        assert SsoGroupMapping.__tablename__ == "sso_group_mappings"

    def test_can_instantiate(self):
        mapping = SsoGroupMapping(
            id=uuid4(),
            sso_group_value="analysts",
            role_id=uuid4(),
        )
        assert mapping.sso_group_value == "analysts"

    def test_id_column_type(self):
        assert isinstance(SsoGroupMapping.__table__.c.id.type, PG_UUID)

    def test_sso_group_value_unique(self):
        assert SsoGroupMapping.__table__.c.sso_group_value.unique is True

    def test_role_id_fk(self):
        fk_tables = {fk.column.table.name for fk in SsoGroupMapping.__table__.foreign_keys}
        assert "roles" in fk_tables
