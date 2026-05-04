"""Integration tests for UserRepository (T-044).

Tests get_by_username returns the seeded admin user and returns None for unknown username,
using testcontainers PostgreSQL.
"""

import pytest

from app.repositories.user_repository import UserRepository


class TestUserRepository:
    """UserRepository integration tests against real PostgreSQL."""

    @pytest.mark.asyncio
    async def test_get_by_username_returns_admin(self, db_session):
        """Should return the seeded admin user."""
        repo = UserRepository(db_session)
        user = await repo.get_by_username("testadmin")
        assert user is not None
        assert user.username == "testadmin"
        assert user.display_name == "Test Admin"
        assert user.role == "admin"

    @pytest.mark.asyncio
    async def test_get_by_username_returns_none_for_unknown(self, db_session):
        """Should return None for non-existent username."""
        repo = UserRepository(db_session)
        user = await repo.get_by_username("nonexistent")
        assert user is None
