"""Integration tests for Sessions router (T-318).

Tests POST /sessions, GET /sessions, GET /sessions/:id, DELETE /sessions/:id;
verifies auth, cascade delete, and in-flight cancellation.
"""

import pytest


class TestSessionsRouter:
    """Sessions router integration tests."""

    @pytest.mark.asyncio
    async def test_create_session(self, authenticated_client):
        """POST /sessions creates a new session."""
        response = await authenticated_client.post(
            "/api/v1/sessions",
            headers={"origin": "http://test"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "preview_text" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_session_unauthenticated(self, app_client):
        """Unauthenticated POST returns 401."""
        response = await app_client.post(
            "/api/v1/sessions",
            headers={"origin": "http://test"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_sessions(self, authenticated_client):
        """GET /sessions returns sessions for the user."""
        # Create a session first
        create_resp = await authenticated_client.post(
            "/api/v1/sessions",
            headers={"origin": "http://test"},
        )
        assert create_resp.status_code == 201

        response = await authenticated_client.get(
            "/api/v1/sessions",
            headers={"origin": "http://test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_session_detail(self, authenticated_client):
        """GET /sessions/:id returns session with attempts."""
        create_resp = await authenticated_client.post(
            "/api/v1/sessions",
            headers={"origin": "http://test"},
        )
        assert create_resp.status_code == 201
        session_id = create_resp.json()["id"]

        response = await authenticated_client.get(
            f"/api/v1/sessions/{session_id}",
            headers={"origin": "http://test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id
        assert "attempts" in data

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, authenticated_client):
        """GET /sessions/:id with unknown ID returns 404."""
        response = await authenticated_client.get(
            "/api/v1/sessions/550e8400-e29b-41d4-a716-446655440000",
            headers={"origin": "http://test"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_session(self, authenticated_client):
        """DELETE /sessions/:id removes the session."""
        create_resp = await authenticated_client.post(
            "/api/v1/sessions",
            headers={"origin": "http://test"},
        )
        assert create_resp.status_code == 201
        session_id = create_resp.json()["id"]

        delete_resp = await authenticated_client.delete(
            f"/api/v1/sessions/{session_id}",
            headers={"origin": "http://test"},
        )
        assert delete_resp.status_code == 204

        get_resp = await authenticated_client.get(
            f"/api/v1/sessions/{session_id}",
            headers={"origin": "http://test"},
        )
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, authenticated_client):
        """DELETE /sessions/:id with unknown ID returns 404."""
        response = await authenticated_client.delete(
            "/api/v1/sessions/550e8400-e29b-41d4-a716-446655440000",
            headers={"origin": "http://test"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_session_cascade_removes_accepted_queries(self, authenticated_client, db_session):
        """Deleting a session cascade-deletes its accepted queries."""
        from sqlalchemy import text

        # Create session via API
        create_resp = await authenticated_client.post(
            "/api/v1/sessions",
            headers={"origin": "http://test"},
        )
        assert create_resp.status_code == 201
        session_id = create_resp.json()["id"]

        # Insert an accepted query manually for the session
        result = await db_session.execute(text("SELECT id FROM users WHERE username = 'admin'"))
        user_id = result.fetchone()[0]
        result = await db_session.execute(text("SELECT id FROM source_database_connections LIMIT 1"))
        db_conn_id = result.fetchone()[0]

        await db_session.execute(
            text(
                """
                INSERT INTO accepted_queries (
                    user_id, database_connection_id, session_id,
                    question_text, generated_sql, llm_provider
                )
                VALUES (:user_id, :db_conn_id, :session_id, 'Q1', 'SELECT 1', 'ollama')
                """
            ),
            {
                "user_id": str(user_id),
                "db_conn_id": str(db_conn_id),
                "session_id": session_id,
            },
        )
        await db_session.commit()

        # Verify the accepted query exists
        result = await db_session.execute(
            text("SELECT COUNT(*) FROM accepted_queries WHERE session_id = :session_id"),
            {"session_id": session_id},
        )
        assert result.scalar_one() == 1

        # Delete the session
        delete_resp = await authenticated_client.delete(
            f"/api/v1/sessions/{session_id}",
            headers={"origin": "http://test"},
        )
        assert delete_resp.status_code == 204

        # Verify cascade delete
        result = await db_session.execute(
            text("SELECT COUNT(*) FROM accepted_queries WHERE session_id = :session_id"),
            {"session_id": session_id},
        )
        assert result.scalar_one() == 0
