"""Unit tests for SessionRepository (T-316).

Tests create, list_by_user, get_by_id, delete, update_last_activity,
update_preview_text against real PostgreSQL via db_session fixture.
"""

import uuid

import pytest
from sqlalchemy import text

from app.repositories.session_repository import SessionRepository


class TestSessionRepository:
    """SessionRepository unit tests."""

    @pytest.fixture
    async def admin_user_id(self, db_session):
        """Fetch the seeded admin user's UUID."""
        result = await db_session.execute(text("SELECT id FROM users WHERE username = 'admin'"))
        row = result.fetchone()
        assert row is not None
        return row[0]

    @pytest.mark.asyncio
    async def test_create_persists_row(self, db_session, admin_user_id):
        """Creating a session should persist it."""
        repo = SessionRepository(db_session)
        session = await repo.create(user_id=admin_user_id, preview_text="Hello world")
        assert session.id is not None
        assert session.preview_text == "Hello world"
        assert session.user_id == admin_user_id

    @pytest.mark.asyncio
    async def test_list_by_user_returns_reverse_chrono(self, db_session, admin_user_id):
        """list_by_user returns sessions in reverse chronological order."""
        repo = SessionRepository(db_session)
        s1 = await repo.create(user_id=admin_user_id, preview_text="First")
        s2 = await repo.create(user_id=admin_user_id, preview_text="Second")
        items = await repo.list_by_user(admin_user_id)
        assert len(items) == 2
        assert items[0].id == s2.id
        assert items[1].id == s1.id

    @pytest.mark.asyncio
    async def test_get_by_id_returns_row(self, db_session, admin_user_id):
        """get_by_id returns the correct session."""
        repo = SessionRepository(db_session)
        created = await repo.create(user_id=admin_user_id, preview_text="Find me")
        found = await repo.get_by_id(created.id, admin_user_id)
        assert found is not None
        assert found.id == created.id

    @pytest.mark.asyncio
    async def test_get_by_id_wrong_user_returns_none(self, db_session, admin_user_id):
        """get_by_id with wrong user_id returns None."""
        repo = SessionRepository(db_session)
        created = await repo.create(user_id=admin_user_id, preview_text="Private")
        found = await repo.get_by_id(created.id, uuid.UUID("550e8400-e29b-41d4-a716-446655440002"))
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_removes_row(self, db_session, admin_user_id):
        """delete removes the session."""
        repo = SessionRepository(db_session)
        created = await repo.create(user_id=admin_user_id, preview_text="To delete")
        deleted = await repo.delete(created.id, admin_user_id)
        assert deleted is True
        found = await repo.get_by_id(created.id, admin_user_id)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_wrong_user_returns_false(self, db_session, admin_user_id):
        """delete with wrong user_id returns False."""
        repo = SessionRepository(db_session)
        created = await repo.create(user_id=admin_user_id, preview_text="Protected")
        deleted = await repo.delete(created.id, uuid.UUID("550e8400-e29b-41d4-a716-446655440002"))
        assert deleted is False

    @pytest.mark.asyncio
    @pytest.mark.lifecycle
    async def test_update_last_activity_changes_timestamp(self, db_session, admin_user_id):
        """update_last_activity changes last_activity_at."""
        repo = SessionRepository(db_session)
        created = await repo.create(user_id=admin_user_id, preview_text="Touch me")
        original = created.last_activity_at
        updated = await repo.update_last_activity(created.id, admin_user_id)
        assert updated is True
        await db_session.refresh(created)
        assert created.last_activity_at > original

    @pytest.mark.asyncio
    async def test_update_preview_text_truncates_long_text(self, db_session, admin_user_id):
        """update_preview_text truncates to 60 chars + ellipsis."""
        repo = SessionRepository(db_session)
        created = await repo.create(user_id=admin_user_id, preview_text="")
        long_text = "a" * 100
        updated = await repo.update_preview_text(created.id, admin_user_id, long_text)
        assert updated is True
        await db_session.refresh(created)
        assert created.preview_text == long_text[:60] + "..."
