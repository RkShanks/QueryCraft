"""T-121: Invariant 3 — No concurrent submissions.

Tests submit blocks when lock held, accept releases lock,
reject/regenerate verify active attempt, lock TTL expiry allows retry.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestInvariantNoConcurrent:
    """Invariant 3: No concurrent submissions integration test."""

    @pytest.mark.asyncio
    async def test_submit_concurrent_returns_409(
        self,
        authenticated_client,
        redis_client,
        query_submit_payload,
        deterministic_query_llm,
    ):
        """Submit while processing lock is held returns 409."""
        session_id = authenticated_client.cookies.get("session_id")
        assert session_id

        lock_key = f"processing_lock:{session_id}"
        await redis_client.set(lock_key, "1", nx=True, ex=60)

        try:
            response = await authenticated_client.post(
                "/api/v1/query/submit",
                json=query_submit_payload("Concurrent test?"),
                headers={"origin": "http://test"},
            )
            assert response.status_code == 409
            data = response.json()
            assert data["message_key"] == "error.concurrent"
        finally:
            await redis_client.delete(lock_key)

        # After releasing the lock, submit should succeed
        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload("Concurrent test?"),
            headers={"origin": "http://test"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_reject_succeeds_while_lock_held(
        self,
        authenticated_client,
        redis_client,
        query_submit_payload,
        deterministic_query_llm,
    ):
        """Reject while processing lock is held succeeds (G-001)."""
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload("Concurrent reject test?"),
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        session_id = authenticated_client.cookies.get("session_id")
        assert session_id

        # Lock is held by submit; reject should succeed
        with patch(
            "app.api.v1.query.LLMProviderFactory.from_config",
            return_value=AsyncMock(generate_sql=AsyncMock(return_value="SELECT 2 AS id")),
        ):
            response = await authenticated_client.post(
                "/api/v1/query/reject",
                json={"attempt_id": attempt_id},
                headers={"origin": "http://test"},
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_regenerate_succeeds_while_lock_held(
        self,
        authenticated_client,
        redis_client,
        query_submit_payload,
        deterministic_query_llm,
    ):
        """Regenerate while processing lock is held succeeds (G-001)."""
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload("Concurrent regenerate test?"),
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        session_id = authenticated_client.cookies.get("session_id")
        assert session_id

        # Lock is held by submit; regenerate should succeed
        with patch(
            "app.api.v1.query.LLMProviderFactory.from_config",
            return_value=AsyncMock(generate_sql=AsyncMock(return_value="SELECT 2 AS id")),
        ):
            response = await authenticated_client.post(
                "/api/v1/query/regenerate",
                json={"attempt_id": attempt_id},
                headers={"origin": "http://test"},
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_lock_ttl_expires_allows_retry(
        self,
        authenticated_client,
        redis_client,
        query_submit_payload,
        deterministic_query_llm,
    ):
        """If the lock TTL expires, a subsequent request should succeed."""
        session_id = authenticated_client.cookies.get("session_id")
        assert session_id

        lock_key = f"processing_lock:{session_id}"
        # Set lock with a very short TTL (1 second)
        await redis_client.set(lock_key, "1", nx=True, ex=1)

        # Wait for TTL to expire
        import asyncio

        await asyncio.sleep(1.5)

        # Verify lock is gone
        assert await redis_client.get(lock_key) is None

        # Request should now succeed
        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload("TTL test?"),
            headers={"origin": "http://test"},
        )
        assert response.status_code == 200
