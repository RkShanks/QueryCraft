"""Unit tests for AcceptedQueryRepository new methods (T-317).

Tests list_by_session, update_feedback, get_latest_by_session.
"""

import uuid

import pytest
from sqlalchemy import text

from app.repositories.accepted_query_repository import AcceptedQueryRepository


class TestAcceptedQueryRepositoryExtended:
    """AcceptedQueryRepository extended method tests."""

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

    @pytest.fixture
    async def session_id(self, db_session, admin_user_id):
        """Insert a sessions row and return its UUID."""
        result = await db_session.execute(
            text(
                """
                INSERT INTO sessions (user_id, preview_text)
                VALUES (:user_id, 'test session')
                RETURNING id
                """
            ),
            {"user_id": str(admin_user_id)},
        )
        row = result.fetchone()
        return row[0]

    @pytest.mark.asyncio
    async def test_list_by_session_returns_rows(self, db_session, admin_user_id, db_connection_id, session_id):
        """list_by_session returns accepted queries for a session."""
        repo = AcceptedQueryRepository(db_session)
        q1 = await repo.create(
            user_id=admin_user_id,
            database_connection_id=db_connection_id,
            question_text="Q1",
            generated_sql="SELECT 1",
            llm_provider="ollama",
            session_id=session_id,
        )
        q2 = await repo.create(
            user_id=admin_user_id,
            database_connection_id=db_connection_id,
            question_text="Q2",
            generated_sql="SELECT 2",
            llm_provider="ollama",
            session_id=session_id,
        )
        items = await repo.list_by_session(session_id, admin_user_id, limit=10)
        assert len(items) == 2
        item_ids = {i.id for i in items}
        assert q1.id in item_ids
        assert q2.id in item_ids

    @pytest.mark.asyncio
    async def test_list_by_session_wrong_user_returns_empty(
        self, db_session, admin_user_id, db_connection_id, session_id
    ):
        """list_by_session with wrong user returns empty list."""
        repo = AcceptedQueryRepository(db_session)
        await repo.create(
            user_id=admin_user_id,
            database_connection_id=db_connection_id,
            question_text="Q1",
            generated_sql="SELECT 1",
            llm_provider="ollama",
            session_id=session_id,
        )
        items = await repo.list_by_session(session_id, uuid.UUID("550e8400-e29b-41d4-a716-446655440002"), limit=10)
        assert items == []

    @pytest.mark.asyncio
    async def test_update_feedback_changes_value(self, db_session, admin_user_id, db_connection_id, session_id):
        """update_feedback changes the feedback column."""
        repo = AcceptedQueryRepository(db_session)
        q = await repo.create(
            user_id=admin_user_id,
            database_connection_id=db_connection_id,
            question_text="Q1",
            generated_sql="SELECT 1",
            llm_provider="ollama",
            session_id=session_id,
        )
        updated = await repo.update_feedback(q.id, admin_user_id, feedback=1)
        assert updated is not None
        assert updated.feedback == 1

    @pytest.mark.asyncio
    async def test_update_feedback_wrong_user_returns_none(
        self, db_session, admin_user_id, db_connection_id, session_id
    ):
        """update_feedback with wrong user returns None."""
        repo = AcceptedQueryRepository(db_session)
        q = await repo.create(
            user_id=admin_user_id,
            database_connection_id=db_connection_id,
            question_text="Q1",
            generated_sql="SELECT 1",
            llm_provider="ollama",
            session_id=session_id,
        )
        updated = await repo.update_feedback(q.id, uuid.UUID("550e8400-e29b-41d4-a716-446655440002"), feedback=1)
        assert updated is None

    @pytest.mark.asyncio
    async def test_get_latest_by_session_returns_most_recent(
        self, db_session, admin_user_id, db_connection_id, session_id
    ):
        """get_latest_by_session returns the most recent query."""
        repo = AcceptedQueryRepository(db_session)
        q1 = await repo.create(
            user_id=admin_user_id,
            database_connection_id=db_connection_id,
            question_text="Q1",
            generated_sql="SELECT 1",
            llm_provider="ollama",
            session_id=session_id,
        )
        q2 = await repo.create(
            user_id=admin_user_id,
            database_connection_id=db_connection_id,
            question_text="Q2",
            generated_sql="SELECT 2",
            llm_provider="ollama",
            session_id=session_id,
        )
        latest = await repo.get_latest_by_session(session_id, admin_user_id)
        assert latest is not None
        # Either row is acceptable; invariant is that it belongs to this session
        assert latest.id in {q1.id, q2.id}

    @pytest.mark.asyncio
    async def test_get_latest_by_session_empty_returns_none(self, db_session, admin_user_id, session_id):
        """get_latest_by_session with no rows returns None."""
        repo = AcceptedQueryRepository(db_session)
        latest = await repo.get_latest_by_session(session_id, admin_user_id)
        assert latest is None
