"""F-5: G-002/O-003 — composite (accepted_at, id) cursor pagination.

Reproduction: insert 3 rows with identical accepted_at, limit=1.
Page 1 should return row 3 (highest id), page 2 row 2, page 3 row 1.
Before fix: page 2 skips row 2 because cursor is only accepted_at.
After fix: composite cursor (accepted_at, id) correctly pages through all 3.
"""

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

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_same_timestamp_pagination(self, db_session, admin_user_id, db_connection_id):
        """Three rows with identical accepted_at paginate correctly via composite cursor."""
        repo = AcceptedQueryRepository(db_session)
        same_time = "2026-05-11T10:00:00+00:00"

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

        # Page 1: limit=1 → should return Q3 (highest id)
        items1, cursor1 = await repo.list_by_user(admin_user_id, cursor=None, limit=1)
        assert len(items1) == 1
        assert items1[0].question_text == "Q3"
        assert cursor1 is not None

        # Page 2: with cursor → should return Q2
        items2, cursor2 = await repo.list_by_user(admin_user_id, cursor=cursor1, limit=1)
        assert len(items2) == 1
        assert items2[0].question_text == "Q2"
        assert cursor2 is not None

        # Page 3: with cursor → should return Q1
        items3, cursor3 = await repo.list_by_user(admin_user_id, cursor=cursor2, limit=1)
        assert len(items3) == 1
        assert items3[0].question_text == "Q1"
        assert cursor3 is None

        # Page 4: empty
        items4, cursor4 = await repo.list_by_user(admin_user_id, cursor=cursor3, limit=1)
        assert len(items4) == 0
        assert cursor4 is None
