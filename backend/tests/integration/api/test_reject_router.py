"""T-114: Reject router integration test.

Tests POST /query/reject with an authenticated user.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


class TestRejectRouter:
    """Reject router integration tests."""

    @pytest.mark.asyncio
    async def test_reject_success_refine_prompt(self, authenticated_client):
        """Reject on first attempt returns RefinePrompt (byte-equal with StubLLM)."""
        # Submit a question first
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 1+1?"},
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        # Reject the attempt
        reject_resp = await authenticated_client.post(
            "/api/v1/query/reject",
            json={"attempt_id": attempt_id},
            headers={"origin": "http://test"},
        )
        assert reject_resp.status_code == 200
        data = reject_resp.json()
        assert data["kind"] == "refine"
        assert data["message_key"] == "query.refine.message"
        assert data["should_refine"] is True

    @pytest.mark.asyncio
    async def test_reject_attempt_not_found(self, authenticated_client):
        """Reject with non-existent attempt_id returns 400."""
        response = await authenticated_client.post(
            "/api/v1/query/reject",
            json={"attempt_id": "550e8400-e29b-41d4-a716-446655440000"},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["message_key"] == "error.attemptInvalid"

    @pytest.mark.asyncio
    async def test_reject_cross_session_ownership(self, app_client, redis_client):
        """Rejecting an attempt from a different session returns 400."""
        # Sign in as session A
        resp_a = await app_client.post(
            "/api/v1/auth/sign-in",
            json={"username": "admin", "password": "admin123"},
            headers={"origin": "http://test"},
        )
        assert resp_a.status_code == 200
        cookies_a = resp_a.cookies

        # Submit as A
        submit_resp = await app_client.post(
            "/api/v1/query/submit",
            json={"question": "Ownership test?"},
            headers={"origin": "http://test"},
            cookies=cookies_a,
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        # Sign in as B (same user, new session)
        app_b = create_app()
        transport_b = ASGITransport(app=app_b)
        async with AsyncClient(transport=transport_b, base_url="http://test") as client_b:
            resp_b = await client_b.post(
                "/api/v1/auth/sign-in",
                json={"username": "admin", "password": "admin123"},
                headers={"origin": "http://test"},
            )
            assert resp_b.status_code == 200

            # Attempt to reject with B's session
            reject_resp = await client_b.post(
                "/api/v1/query/reject",
                json={"attempt_id": attempt_id},
                headers={"origin": "http://test"},
            )
            assert reject_resp.status_code == 400
            data = reject_resp.json()
            assert data["message_key"] == "error.attemptInvalid"

    @pytest.mark.asyncio
    async def test_reject_concurrent_session_busy(self, authenticated_client, redis_client):
        """Reject while processing lock is held returns 409."""
        # Submit first
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 2+2?"},
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        # Get session_id from cookie
        session_id = authenticated_client.cookies.get("session_id")
        assert session_id

        # Manually acquire the processing lock
        lock_key = f"processing_lock:{session_id}"
        await redis_client.set(lock_key, "1", nx=True, ex=60)

        try:
            reject_resp = await authenticated_client.post(
                "/api/v1/query/reject",
                json={"attempt_id": attempt_id},
                headers={"origin": "http://test"},
            )
            assert reject_resp.status_code == 409
            data = reject_resp.json()
            assert data["message_key"] == "error.concurrent"
        finally:
            await redis_client.delete(lock_key)

        # After releasing the lock, reject should succeed
        reject_resp = await authenticated_client.post(
            "/api/v1/query/reject",
            json={"attempt_id": attempt_id},
            headers={"origin": "http://test"},
        )
        assert reject_resp.status_code == 200

    @pytest.mark.asyncio
    async def test_reject_unauthenticated(self, app_client):
        """Reject without authentication returns 401."""
        response = await app_client.post(
            "/api/v1/query/reject",
            json={"attempt_id": "550e8400-e29b-41d4-a716-446655440000"},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["message_key"] == "error.unauthorized"
