"""RED unit tests for QuotaRepository (T-795).

These tests define the contract for QuotaRepository:
- get(role_id) returns RoleQuota or None
- upsert creates new row when role has no quota
- upsert updates existing row when quota exists
- delete removes row and returns True/False
- list returns all configured roles with quota data
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.role_quota import RoleQuota
from app.repositories.quota_repository import QuotaRepository
from app.schemas.quota import RoleQuotaUpsert


class TestQuotaRepositoryGet:
    """QuotaRepository.get() returns RoleQuota or None."""

    @pytest.mark.asyncio
    async def test_returns_none_for_unconfigured_role(self, db_session):
        repo = QuotaRepository(db_session)
        result = await repo.get(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_role_quota_for_configured_role(self, db_session, make_role_quota):
        role_id = uuid.uuid4()
        from app.db.models.role import Role

        role = Role(
            id=role_id,
            name="TestRole",
            description="test",
            priority=100,
            permissions=["query.submit"],
        )
        db_session.add(role)
        await db_session.flush()

        quota = make_role_quota(role_id=role_id, daily_query_limit=10)
        db_session.add(quota)
        await db_session.flush()

        repo = QuotaRepository(db_session)
        result = await repo.get(role_id)
        assert result is not None
        assert result.role_id == role_id
        assert result.daily_query_limit == 10


class TestQuotaRepositoryUpsert:
    """QuotaRepository.upsert() creates or updates quota config."""

    @pytest.mark.asyncio
    async def test_upsert_creates_new_row_when_role_has_no_quota(self, db_session):
        role_id = uuid.uuid4()
        from app.db.models.role import Role

        role = Role(
            id=role_id,
            name="NewRole",
            description="test",
            priority=101,
            permissions=["query.submit"],
        )
        db_session.add(role)
        await db_session.flush()

        repo = QuotaRepository(db_session)
        data = RoleQuotaUpsert(daily_query_limit=5, daily_execution_limit=20)
        result = await repo.upsert(role_id, data)

        assert result is not None
        assert result.role_id == role_id
        assert result.daily_query_limit == 5
        assert result.daily_execution_limit == 20
        assert result.daily_export_limit is None

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_row(self, db_session, make_role_quota):
        role_id = uuid.uuid4()
        from app.db.models.role import Role

        role = Role(
            id=role_id,
            name="ExistingRole",
            description="test",
            priority=102,
            permissions=["query.submit"],
        )
        db_session.add(role)
        await db_session.flush()

        quota = make_role_quota(role_id=role_id, daily_query_limit=10, daily_execution_limit=5)
        db_session.add(quota)
        await db_session.flush()

        repo = QuotaRepository(db_session)
        data = RoleQuotaUpsert(daily_query_limit=20, daily_execution_limit=15)
        result = await repo.upsert(role_id, data)

        assert result.daily_query_limit == 20
        assert result.daily_execution_limit == 15

    @pytest.mark.asyncio
    async def test_upsert_preserves_unset_fields_as_null(self, db_session):
        role_id = uuid.uuid4()
        from app.db.models.role import Role

        role = Role(
            id=role_id,
            name="NullFieldsRole",
            description="test",
            priority=103,
            permissions=["query.submit"],
        )
        db_session.add(role)
        await db_session.flush()

        repo = QuotaRepository(db_session)
        data = RoleQuotaUpsert(daily_query_limit=5)
        result = await repo.upsert(role_id, data)

        assert result.daily_query_limit == 5
        assert result.daily_execution_limit is None
        assert result.daily_export_limit is None


class TestQuotaRepositoryDelete:
    """QuotaRepository.delete() removes quota config."""

    @pytest.mark.asyncio
    async def test_delete_removes_row(self, db_session, make_role_quota):
        role_id = uuid.uuid4()
        from app.db.models.role import Role

        role = Role(
            id=role_id,
            name="DeleteRole",
            description="test",
            priority=104,
            permissions=["query.submit"],
        )
        db_session.add(role)
        await db_session.flush()

        quota = make_role_quota(role_id=role_id, daily_query_limit=10)
        db_session.add(quota)
        await db_session.flush()

        repo = QuotaRepository(db_session)
        result = await repo.delete(role_id)
        assert result is True

        verify = await repo.get(role_id)
        assert verify is None

    @pytest.mark.asyncio
    async def test_delete_returns_false_for_missing_role(self, db_session):
        repo = QuotaRepository(db_session)
        result = await repo.delete(uuid.uuid4())
        assert result is False


class TestQuotaRepositoryListAll:
    """QuotaRepository.list_all() returns all configured quotas."""

    @pytest.mark.asyncio
    async def test_list_returns_all_configured_roles(self, db_session, make_role_quota):
        from app.db.models.role import Role

        role_ids = []
        for i, prio in enumerate([200, 201], start=1):
            role_id = uuid.uuid4()
            role_ids.append(role_id)
            role = Role(
                id=role_id,
                name=f"ListRole{i}",
                description="test",
                priority=prio,
                permissions=["query.submit"],
            )
            db_session.add(role)
            await db_session.flush()

            quota = make_role_quota(role_id=role_id, daily_query_limit=i * 10)
            db_session.add(quota)
            await db_session.flush()

        repo = QuotaRepository(db_session)
        results = await repo.list_all()

        assert len(results) >= 2
        returned_ids = {r.role_id for r in results}
        for rid in role_ids:
            assert rid in returned_ids
