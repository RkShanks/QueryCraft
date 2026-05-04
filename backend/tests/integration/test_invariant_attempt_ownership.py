"""Invariant 6: Ephemeral attempt ownership.

Sign in as user A, submit a question, capture the attempt_id from Redis,
sign in as user B (new session), POST /query/accept with the attempt_id
and assert HTTP 400 (per OpenAPI contract). Not 404, not 403.
"""

import pytest


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
