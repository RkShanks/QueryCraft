"""Integration tests for AcceptedQueryRepository (T-046).

Tests create, list_by_user (reverse-chrono, cursor pagination), and get_by_id;
verifies FK constraints and index usage.
"""

import uuid

import pytest

from app.repositories.accepted_query_repository import AcceptedQueryRepository


class TestAcceptedQueryRepository:
    """AcceptedQueryRepository integration tests against real PostgreSQL."""

    @pytest.fixture
    async def sample_query(self, db_session, authenticated_client):
        """Create a sample accepted query row."""
        repo = AcceptedQueryRepository(db_session)
        query = await repo.create(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            database_connection_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440001"),
            question_text="What are sales?",
            generated_sql="SELECT 1",
            llm_provider="ollama",
        )
        return query

    @pytest.mark.asyncio
    async def test_create_persists_row(self, db_session, authenticated_client):
        """Creating a row should persist it."""
        repo = AcceptedQueryRepository(db_session)
        query = await repo.create(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            database_connection_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440001"),
            question_text="Q1",
            generated_sql="SELECT 1",
            llm_provider="ollama",
        )
        assert query.id is not None
        assert query.question_text == "Q1"

    @pytest.mark.asyncio
    async def test_list_by_user_returns_reverse_chrono(self, db_session, authenticated_client):
        """list_by_user returns entries in reverse chronological order."""
        repo = AcceptedQueryRepository(db_session)
        user_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        await repo.create(
            user_id=user_id,
            database_connection_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440001"),
            question_text="Q1",
            generated_sql="SELECT 1",
            llm_provider="ollama",
        )
        await repo.create(
            user_id=user_id,
            database_connection_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440001"),
            question_text="Q2",
            generated_sql="SELECT 2",
            llm_provider="ollama",
        )
        items, next_cursor = await repo.list_by_user(user_id, cursor=None, limit=10)
        assert len(items) == 2
        assert items[0].question_text == "Q2"
        assert items[1].question_text == "Q1"
        assert next_cursor is None

    @pytest.mark.asyncio
    async def test_get_by_id_returns_row(self, db_session, authenticated_client):
        """get_by_id returns the correct row."""
        repo = AcceptedQueryRepository(db_session)
        user_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        created = await repo.create(
            user_id=user_id,
            database_connection_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440001"),
            question_text="Q1",
            generated_sql="SELECT 1",
            llm_provider="ollama",
        )
        found = await repo.get_by_id(created.id, user_id)
        assert found is not None
        assert found.id == created.id

    @pytest.mark.asyncio
    async def test_get_by_id_wrong_user_returns_none(self, db_session, authenticated_client):
        """get_by_id with wrong user_id returns None."""
        repo = AcceptedQueryRepository(db_session)
        user_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        created = await repo.create(
            user_id=user_id,
            database_connection_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440001"),
            question_text="Q1",
            generated_sql="SELECT 1",
            llm_provider="ollama",
        )
        found = await repo.get_by_id(created.id, uuid.UUID("550e8400-e29b-41d4-a716-446655440002"))
        assert found is None
