"""Tests for UserIdentity ORM model (T-613)."""

from uuid import uuid4

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from app.db.models.enums import AuthProvider
from app.db.models.user_identity import UserIdentity


class TestUserIdentityModel:
    """UserIdentity ORM model metadata and instantiation."""

    def test_table_name(self):
        assert UserIdentity.__tablename__ == "user_identities"

    def test_can_instantiate(self):
        ident = UserIdentity(
            id=uuid4(),
            user_id=uuid4(),
            provider=AuthProvider.OIDC,
            subject_id="sub-123",
            email="user@example.com",
            sso_groups=["analysts"],
        )
        assert ident.subject_id == "sub-123"
        assert ident.provider == AuthProvider.OIDC

    def test_id_column_type(self):
        assert isinstance(UserIdentity.__table__.c.id.type, PG_UUID)

    def test_user_id_fk(self):
        fk_tables = {fk.column.table.name for fk in UserIdentity.__table__.foreign_keys}
        assert "users" in fk_tables

    def test_unique_provider_subject(self):
        constraints = [c for c in UserIdentity.__table__.constraints if hasattr(c, 'columns')]
        uc_names = {c.name for c in constraints if 'unique' in str(type(c)).lower()}
        assert any("provider_subject" in (name or "") for name in uc_names)
