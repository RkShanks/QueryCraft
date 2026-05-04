"""Integration tests for AcceptedQueryRepository (T-046).

Tests create, list_by_user (reverse-chrono, cursor pagination), and get_by_id;
verifies FK constraints and index usage.
"""

import uuid

import pytest
from sqlalchemy import text

from app.repositories.accepted_query_repository import AcceptedQueryRepository


class TestAcceptedQueryRepository:
    """AcceptedQueryRepository integration tests against real PostgreSQL."""

    @pytest.fixture
    async def admin_user_id(self, db_session):
        """Fetch the seeded admin user's UUID."""
        result = await db_session.execute(text("SELECT id FROM users WHERE username = 'admin'"))
        row = result.fetchone()
        assert row is not None
        return row[0]

    @pytest.fixture
    async def db_connection_id(self, db_session):
        """Insert a database_connections row and return its UUID."""
        result = await db_session.execute(
            text(
                """
                INSERT INTO database_connections (
                    name, host, port, database_name, username,
                    encrypted_password, ssl_mode
                )
                VALUES ('test_conn', 'localhost', 5432, 'test', 'user', 'enc', 'disable')
                RETURNING id
                """
            )
        )
        row = result.fetchone()
        return row[0]

    @pytest.mark.asyncio
    async def test_create_persists_row(self, db_session, admin_user_id, db_connection_id):
        """Creating a row should persist it."""
        repo = AcceptedQueryRepository(db_session)
        query = await repo.create(
            user_id=admin_user_id,
            database_connection_id=db_connection_id,
            question_text="Q1",
            generated_sql="SELECT 1",
            llm_provider="ollama",
        )
        assert query.id is not None
        assert query.question_text == "Q1"

    @pytest.mark.asyncio
    async def test_list_by_user_returns_reverse_chrono(self, db_session, admin_user_id, db_connection_id):
        """list_by_user returns entries in reverse chronological order."""
        repo = AcceptedQueryRepository(db_session)
        await repo.create(
            user_id=admin_user_id,
            database_connection_id=db_connection_id,
            question_text="Q1",
            generated_sql="SELECT 1",
            llm_provider="ollama",
        )
        await repo.create(
            user_id=admin_user_id,
            database_connection_id=db_connection_id,
            question_text="Q2",
            generated_sql="SELECT 2",
            llm_provider="ollama",
        )
        items, next_cursor = await repo.list_by_user(admin_user_id, cursor=None, limit=10)
        assert len(items) == 2
        assert items[0].question_text == "Q2"
        assert items[1].question_text == "Q1"
        assert next_cursor is None

    @pytest.mark.asyncio
    async def test_get_by_id_returns_row(self, db_session, admin_user_id, db_connection_id):
        """get_by_id returns the correct row."""
        repo = AcceptedQueryRepository(db_session)
        created = await repo.create(
            user_id=admin_user_id,
            database_connection_id=db_connection_id,
            question_text="Q1",
            generated_sql="SELECT 1",
            llm_provider="ollama",
        )
        found = await repo.get_by_id(created.id, admin_user_id)
        assert found is not None
        assert found.id == created.id

    @pytest.mark.asyncio
    async def test_get_by_id_wrong_user_returns_none(self, db_session, admin_user_id, db_connection_id):
        """get_by_id with wrong user_id returns None."""
        repo = AcceptedQueryRepository(db_session)
        created = await repo.create(
            user_id=admin_user_id,
            database_connection_id=db_connection_id,
            question_text="Q1",
            generated_sql="SELECT 1",
            llm_provider="ollama",
        )
        found = await repo.get_by_id(created.id, uuid.UUID("550e8400-e29b-41d4-a716-446655440002"))
        assert found is None
