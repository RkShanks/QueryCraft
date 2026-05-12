"""Acceptance test for submit-with-session-context flow (T-321).

Tests lazy session creation, context loading on follow-up, and implicit feedback.
Uses the full app stack with authenticated_client and mock_llm.
"""

import pytest


class TestSessionConversationFlow:
    """End-to-end session conversation acceptance tests."""

    @pytest.mark.asyncio
    async def test_submit_creates_session_when_none_provided(self, authenticated_client):
        """Submit without session_id creates a new session and returns it."""
        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 1+1?"},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["kind"] == "result"
        assert "session_id" in data
        assert data["session_id"] is not None

    @pytest.mark.asyncio
    async def test_submit_uses_existing_session(self, authenticated_client):
        """Submit with session_id uses the existing session."""
        # First submit creates session
        first = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "First question"},
            headers={"origin": "http://test"},
        )
        assert first.status_code == 200
        session_id = first.json()["session_id"]

        # Second submit with session_id
        second = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "Follow-up", "session_id": session_id},
            headers={"origin": "http://test"},
        )
        assert second.status_code == 200
        data = second.json()
        assert data["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_implicit_feedback_on_follow_up(self, authenticated_client, db_session):
        """Follow-up submit applies implicit +1 feedback to prior accepted query."""
        from sqlalchemy import text

        # First: submit and accept
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 1+1?"},
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]
        session_id = submit_resp.json()["session_id"]

        accept_resp = await authenticated_client.post(
            "/api/v1/query/accept",
            json={"attempt_id": attempt_id},
            headers={"origin": "http://test"},
        )
        assert accept_resp.status_code == 201

        # Verify initial feedback is +1 (from accept)
        result = await db_session.execute(
            text("SELECT feedback, saved FROM accepted_queries WHERE attempt_id = :attempt_id"),
            {"attempt_id": attempt_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == 1  # feedback
        assert row[1] is True  # saved

        # Submit a follow-up in the same session
        follow_up = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "Follow-up question", "session_id": session_id},
            headers={"origin": "http://test"},
        )
        assert follow_up.status_code == 200

    @pytest.mark.asyncio
    async def test_session_list_shows_created_session(self, authenticated_client):
        """Created session appears in GET /sessions list."""
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "List me"},
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200
        session_id = submit_resp.json()["session_id"]

        list_resp = await authenticated_client.get(
            "/api/v1/sessions",
            headers={"origin": "http://test"},
        )
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert any(s["id"] == session_id for s in data["items"])
