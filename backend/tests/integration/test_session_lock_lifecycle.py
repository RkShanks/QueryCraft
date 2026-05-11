"""F-1: G-001+G-004 — session lock spans attempt lifetime.

Reproduction:
1. Submit A → lock held.
2. Submit B (same session) → 409 (lock held).
3. Accept A → succeeds.
4. Submit B → succeeds (lock free).

G-004:
1. Submit A.
2. Reject A (regenerate) → new attempt C.
3. Accept old A → 410/422 (no longer active).
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestSessionLockLifecycle:
    """Integration tests for session lock lifecycle."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_submit_blocks_concurrent_submit(self, authenticated_client):
        """Submit A then immediately submit B → 409."""
        submit_a = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 1+1?"},
            headers={"origin": "http://test"},
        )
        assert submit_a.status_code == 200

        submit_b = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 2+2?"},
            headers={"origin": "http://test"},
        )
        assert submit_b.status_code == 409
        assert submit_b.json()["message_key"] == "error.concurrent"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_accept_releases_lock(self, authenticated_client):
        """Accept A then submit B → 200."""
        submit_a = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 1+1?"},
            headers={"origin": "http://test"},
        )
        assert submit_a.status_code == 200
        attempt_id = submit_a.json()["attempt_id"]

        accept_resp = await authenticated_client.post(
            "/api/v1/query/accept",
            json={"attempt_id": attempt_id},
            headers={"origin": "http://test"},
        )
        assert accept_resp.status_code == 201

        submit_b = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 2+2?"},
            headers={"origin": "http://test"},
        )
        assert submit_b.status_code == 200

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_accept_old_attempt_after_regenerate_fails(self, authenticated_client):
        """G-004: Submit A, reject A, accept old A → 410/422."""
        submit_a = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 1+1?"},
            headers={"origin": "http://test"},
        )
        assert submit_a.status_code == 200
        attempt_id = submit_a.json()["attempt_id"]

        with patch("app.llm.stub.StubLLM.generate_sql", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "SELECT 2 AS id"

            reject_resp = await authenticated_client.post(
                "/api/v1/query/reject",
                json={"attempt_id": attempt_id},
                headers={"origin": "http://test"},
            )
            assert reject_resp.status_code == 200

        # Try to accept the original attempt_id
        accept_resp = await authenticated_client.post(
            "/api/v1/query/accept",
            json={"attempt_id": attempt_id},
            headers={"origin": "http://test"},
        )
        assert accept_resp.status_code in (410, 422)
