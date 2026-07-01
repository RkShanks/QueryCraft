"""RED unit tests for QuotaRepository (T-795).

These tests define the contract for QuotaRepository:
- get(role_id) returns RoleQuota or None
- upsert creates new row when role has no quota
- upsert updates existing row when quota exists
- delete removes row and returns True/False
- list returns all configured roles with quota data
"""

import uuid

import pytest

from app.repositories.quota_repository import QuotaRepository
from app.schemas.quota import RoleQuotaUpsert


def _role_name(base: str, role_id: uuid.UUID) -> str:
    return f"{base}-{role_id.hex[:12]}"


def _role_priority(role_id: uuid.UUID) -> int:
    return 100_000 + role_id.int % 900_000_000


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
            name=_role_name("TestRole", role_id),
            description="test",
            priority=_role_priority(role_id),
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
            name=_role_name("NewRole", role_id),
            description="test",
            priority=_role_priority(role_id),
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
            name=_role_name("ExistingRole", role_id),
            description="test",
            priority=_role_priority(role_id),
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
            name=_role_name("NullFieldsRole", role_id),
            description="test",
            priority=_role_priority(role_id),
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
            name=_role_name("DeleteRole", role_id),
            description="test",
            priority=_role_priority(role_id),
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


class TestQuotaRepositoryUpsertUncap:
    """QuotaRepository.upsert() can clear a limit back to null (uncapped)."""

    @pytest.mark.asyncio
    async def test_create_with_limit_then_null_clears_it(self, db_session):
        role_id = uuid.uuid4()
        from app.db.models.role import Role

        role = Role(
            id=role_id,
            name=_role_name("UncapRole", role_id),
            description="test",
            priority=_role_priority(role_id),
            permissions=["query.submit"],
        )
        db_session.add(role)
        await db_session.flush()

        repo = QuotaRepository(db_session)

        # Create with a numeric limit
        data = RoleQuotaUpsert(daily_query_limit=5)
        result = await repo.upsert(role_id, data)
        assert result.daily_query_limit == 5

        # PUT with explicit null to uncap
        data2 = RoleQuotaUpsert(daily_query_limit=None)
        result2 = await repo.upsert(role_id, data2, fields_set={"daily_query_limit"})
        assert result2.daily_query_limit is None

    @pytest.mark.asyncio
    async def test_fields_set_excludes_unchanged_fields(self, db_session):
        role_id = uuid.uuid4()
        from app.db.models.role import Role

        role = Role(
            id=role_id,
            name=_role_name("PartialUncapRole", role_id),
            description="test",
            priority=_role_priority(role_id),
            permissions=["query.submit"],
        )
        db_session.add(role)
        await db_session.flush()

        repo = QuotaRepository(db_session)

        # Create with all three limits
        data = RoleQuotaUpsert(daily_query_limit=10, daily_execution_limit=20, daily_export_limit=30)
        result = await repo.upsert(role_id, data)
        assert result.daily_query_limit == 10
        assert result.daily_execution_limit == 20
        assert result.daily_export_limit == 30

        # Update only query_limit to null, execution and export should be preserved
        data2 = RoleQuotaUpsert(daily_query_limit=None)
        result2 = await repo.upsert(role_id, data2, fields_set={"daily_query_limit"})
        assert result2.daily_query_limit is None
        assert result2.daily_execution_limit == 20
        assert result2.daily_export_limit == 30


class TestQuotaRepositoryListAll:
    """QuotaRepository.list_all() returns all configured quotas."""

    @pytest.mark.asyncio
    async def test_list_returns_all_configured_roles(self, db_session, make_role_quota):
        from app.db.models.role import Role

        role_ids = []
        for i in range(1, 3):
            role_id = uuid.uuid4()
            role_ids.append(role_id)
            role = Role(
                id=role_id,
                name=_role_name(f"ListRole{i}", role_id),
                description="test",
                priority=_role_priority(role_id),
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
