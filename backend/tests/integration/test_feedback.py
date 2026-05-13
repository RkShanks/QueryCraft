"""Integration tests for Feedback router (T-319).

Tests PATCH /feedback/:attempt_id; verifies auth, validation, and persistence.
"""

import pytest
from sqlalchemy import text


class TestFeedbackRouter:
    """Feedback router integration tests."""

    @pytest.fixture
    async def accepted_query_id(self, db_session):
        """Insert an accepted query and return its UUID."""
        result = await db_session.execute(text("SELECT id FROM users WHERE username = 'admin'"))
        user_id = result.fetchone()[0]
        result = await db_session.execute(text("SELECT id FROM database_connections LIMIT 1"))
        db_conn_id = result.fetchone()[0]

        result = await db_session.execute(
            text(
                """
                INSERT INTO accepted_queries (
                    user_id, database_connection_id,
                    question_text, generated_sql, llm_provider
                )
                VALUES (:user_id, :db_conn_id, 'Q1', 'SELECT 1', 'ollama')
                RETURNING id
                """
            ),
            {"user_id": str(user_id), "db_conn_id": str(db_conn_id)},
        )
        row = result.fetchone()
        await db_session.commit()
        return str(row[0])

    @pytest.mark.lifecycle("feedback")
    @pytest.mark.asyncio
    async def test_update_feedback_success(self, authenticated_client, accepted_query_id):
        """PATCH /feedback/:id updates feedback."""
        response = await authenticated_client.patch(
            f"/api/v1/feedback/{accepted_query_id}",
            json={"feedback": 1},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["feedback"] == 1
        assert data["saved"] is True  # feedback=1 defaults saved to True

    @pytest.mark.asyncio
    async def test_update_feedback_negative(self, authenticated_client, accepted_query_id):
        """PATCH /feedback/:id accepts -1 — does not force saved=true."""
        response = await authenticated_client.patch(
            f"/api/v1/feedback/{accepted_query_id}",
            json={"feedback": -1},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["feedback"] == -1
        assert data["saved"] is False  # feedback=-1 does not force saved=true

    @pytest.mark.asyncio
    async def test_update_feedback_saved_true_explicit(self, authenticated_client, accepted_query_id):
        """PATCH /feedback/:id with feedback=1 and saved=true sets both."""
        response = await authenticated_client.patch(
            f"/api/v1/feedback/{accepted_query_id}",
            json={"feedback": 1, "saved": True},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["feedback"] == 1
        assert data["saved"] is True

    @pytest.mark.asyncio
    async def test_update_feedback_saved_false_explicit(self, authenticated_client, accepted_query_id):
        """PATCH /feedback/:id with feedback=1 and saved=false respects explicit override."""
        response = await authenticated_client.patch(
            f"/api/v1/feedback/{accepted_query_id}",
            json={"feedback": 1, "saved": False},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["feedback"] == 1
        assert data["saved"] is False

    @pytest.mark.asyncio
    async def test_update_feedback_validation_out_of_range(self, authenticated_client, accepted_query_id):
        """PATCH /feedback/:id with out-of-range value returns 422."""
        response = await authenticated_client.patch(
            f"/api/v1/feedback/{accepted_query_id}",
            json={"feedback": 5},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_feedback_not_found(self, authenticated_client):
        """PATCH /feedback/:id with unknown ID returns 404."""
        response = await authenticated_client.patch(
            "/api/v1/feedback/550e8400-e29b-41d4-a716-446655440000",
            json={"feedback": 1},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_feedback_unauthenticated(self, app_client, accepted_query_id):
        """Unauthenticated PATCH returns 401."""
        response = await app_client.patch(
            f"/api/v1/feedback/{accepted_query_id}",
            json={"feedback": 1},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 401
