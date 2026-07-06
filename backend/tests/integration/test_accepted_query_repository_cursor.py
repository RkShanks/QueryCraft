"""F-5: G-002/O-003 — composite (accepted_at, id) cursor pagination.

Reproduction: insert 3 rows with identical accepted_at, limit=1.
Page 1 should return row 3 (highest id), page 2 row 2, page 3 row 1.
Before fix: page 2 skips row 2 because cursor is only accepted_at.
After fix: composite cursor (accepted_at, id) correctly pages through all 3.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.repositories.accepted_query_repository import AcceptedQueryRepository


class TestCompositeCursorPagination:
    """Integration tests for composite cursor pagination."""

    @pytest.fixture
    async def admin_user_id(self, db_session):
        """Fetch the seeded admin user's UUID."""
        result = await db_session.execute(text("SELECT id FROM users WHERE username = 'admin'"))
        row = result.fetchone()
        assert row is not None
        return row[0]

    @pytest.fixture
    async def db_connection_id(self, db_session):
        """Insert a source_database_connections row and return its UUID."""
        result = await db_session.execute(
            text(
                """
                INSERT INTO source_database_connections (
                    display_name, host, port, database_name, username,
                    encrypted_password, database_type, lifecycle_state,
                    health_status, schema_introspection_status
                )
                VALUES (
                    'test_conn', 'localhost', 5432, 'test', 'user', 'enc',
                    'postgresql', 'active', 'healthy', 'success'
                )
                RETURNING id
                """
            )
        )
        row = result.fetchone()
        return row[0]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_same_timestamp_pagination(self, db_session, admin_user_id, db_connection_id):
        """Three rows with identical accepted_at paginate correctly via composite cursor."""
        repo = AcceptedQueryRepository(db_session)
        same_time = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)

        # Create 3 rows with identical accepted_at
        for i in range(3):
            await repo.create(
                user_id=admin_user_id,
                database_connection_id=db_connection_id,
                question_text=f"Q{i + 1}",
                generated_sql=f"SELECT {i + 1}",
                llm_provider="ollama",
            )

        # Force identical accepted_at via raw SQL (flush then update)
        await db_session.execute(
            text("UPDATE accepted_queries SET accepted_at = :t WHERE user_id = :uid"),
            {"t": same_time, "uid": admin_user_id},
        )
        await db_session.commit()
        expected_items, expected_cursor = await repo.list_by_user(admin_user_id, cursor=None, limit=3)
        expected_order = [item.question_text for item in expected_items]
        assert sorted(expected_order) == ["Q1", "Q2", "Q3"]
        assert expected_cursor is None

        # Page 1: limit=1 → should return highest id
        items1, cursor1 = await repo.list_by_user(admin_user_id, cursor=None, limit=1)
        assert len(items1) == 1
        assert items1[0].question_text == expected_order[0]
        assert cursor1 is not None

        # Page 2: with cursor → should return next highest id
        items2, cursor2 = await repo.list_by_user(admin_user_id, cursor=cursor1, limit=1)
        assert len(items2) == 1
        assert items2[0].question_text == expected_order[1]
        assert cursor2 is not None

        # Page 3: with cursor → should return lowest id
        items3, cursor3 = await repo.list_by_user(admin_user_id, cursor=cursor2, limit=1)
        assert len(items3) == 1
        assert items3[0].question_text == expected_order[2]
        assert cursor3 is None
