"""T-123: Invariant 6 — Ephemeral attempt ownership.

Sign in as user A, submit a question, capture the attempt_id from Redis,
sign in as user B (new session), attempt reject/regenerate/accept with the
attempt_id and assert HTTP 400 (AttemptOwnershipViolation).

GET /attempts/{id} is not defined in openapi.yaml so we skip that path.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


class TestEphemeralAttemptOwnership:
    """Ephemeral attempt ownership integration test."""

    @pytest.mark.asyncio
    async def test_accept_with_wrong_session_returns_400(self, app_client, redis_client):
        """Accepting another session's attempt returns 400."""
        # Sign in as user A
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
        resp_b = await app_client.post(
            "/api/v1/auth/sign-in",
            json={"username": "admin", "password": "admin123"},
            headers={"origin": "http://test"},
        )
        assert resp_b.status_code == 200
        cookies_b = resp_b.cookies

        # Attempt to accept with B's session
        accept_resp = await app_client.post(
            "/api/v1/query/accept",
            json={"attempt_id": attempt_id},
            headers={"origin": "http://test"},
            cookies=cookies_b,
        )
        assert accept_resp.status_code == 400
        assert accept_resp.json()["message_key"] == "error.attemptInvalid"

    @pytest.mark.asyncio
    async def test_reject_with_wrong_session_returns_400(self, app_client, redis_client):
        """Rejecting another session's attempt returns 400."""
        # Sign in as user A
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
            json={"question": "Ownership reject test?"},
            headers={"origin": "http://test"},
            cookies=cookies_a,
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        # Sign in as B (new session)
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
            assert reject_resp.json()["message_key"] == "error.attemptInvalid"

    @pytest.mark.asyncio
    async def test_regenerate_with_wrong_session_returns_400(self, app_client, redis_client):
        """Regenerating another session's attempt returns 400."""
        # Sign in as user A
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
            json={"question": "Ownership regenerate test?"},
            headers={"origin": "http://test"},
            cookies=cookies_a,
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        # Sign in as B (new session)
        app_b = create_app()
        transport_b = ASGITransport(app=app_b)
        async with AsyncClient(transport=transport_b, base_url="http://test") as client_b:
            resp_b = await client_b.post(
                "/api/v1/auth/sign-in",
                json={"username": "admin", "password": "admin123"},
                headers={"origin": "http://test"},
            )
            assert resp_b.status_code == 200

            # Attempt to regenerate with B's session
            regen_resp = await client_b.post(
                "/api/v1/query/regenerate",
                json={"attempt_id": attempt_id},
                headers={"origin": "http://test"},
            )
            assert regen_resp.status_code == 400
            assert regen_resp.json()["message_key"] == "error.attemptInvalid"

    @pytest.mark.asyncio
    async def test_session_a_still_works_after_ownership_violation(self, app_client, redis_client):
        """Session A can still reject its own attempt after B's violation."""
        # Sign in as user A
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
            json={"question": "Idempotency test?"},
            headers={"origin": "http://test"},
            cookies=cookies_a,
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        # Sign in as B and attempt reject (fails)
        app_b = create_app()
        transport_b = ASGITransport(app=app_b)
        async with AsyncClient(transport=transport_b, base_url="http://test") as client_b:
            resp_b = await client_b.post(
                "/api/v1/auth/sign-in",
                json={"username": "admin", "password": "admin123"},
                headers={"origin": "http://test"},
            )
            assert resp_b.status_code == 200

            reject_resp = await client_b.post(
                "/api/v1/query/reject",
                json={"attempt_id": attempt_id},
                headers={"origin": "http://test"},
            )
            assert reject_resp.status_code == 400

        # Session A can still reject its own attempt
        reject_resp_a = await app_client.post(
            "/api/v1/query/reject",
            json={"attempt_id": attempt_id},
            headers={"origin": "http://test"},
            cookies=cookies_a,
        )
        assert reject_resp_a.status_code == 200
