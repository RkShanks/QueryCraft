"""Tests for Role ORM model (T-607)."""

from uuid import uuid4

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from app.db.models.role import Role


class TestRoleModel:
    """Role ORM model metadata and instantiation."""

    def test_table_name(self):
        assert Role.__tablename__ == "roles"

    def test_can_instantiate(self):
        role = Role(
            id=uuid4(),
            name="Analyst",
            description="Read-only",
            priority=10,
            permissions=["query.submit", "query.history.view"],
        )
        assert role.name == "Analyst"
        assert role.priority == 10

    def test_id_column_type(self):
        assert isinstance(Role.__table__.c.id.type, PG_UUID)

    def test_name_unique(self):
        assert Role.__table__.c.name.unique is True

    def test_priority_unique(self):
        assert Role.__table__.c.priority.unique is True

    def test_is_builtin_default(self):
        role = Role(name="Test", priority=100, permissions=[])
        assert role.is_builtin is False

    def test_permissions_jsonb(self):
        assert isinstance(Role.__table__.c.permissions.type, JSONB)
