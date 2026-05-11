"""T-116: Regenerate router integration test.

Tests POST /query/regenerate with an authenticated user.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestRegenerateRouter:
    """Regenerate router integration tests."""

    @pytest.mark.asyncio
    async def test_regenerate_success_query_result(self, authenticated_client):
        """Regenerate with fresh SQL returns QueryResult (attempt #2)."""
        # Submit a question first
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 1+1?"},
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        # Patch StubLLM to return different SQL on regenerate
        with patch("app.llm.stub.StubLLM.generate_sql", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "SELECT 2 AS id"

            regenerate_resp = await authenticated_client.post(
                "/api/v1/query/regenerate",
                json={"attempt_id": attempt_id},
                headers={"origin": "http://test"},
            )

        assert regenerate_resp.status_code == 200
        data = regenerate_resp.json()
        assert data["kind"] == "result"
        assert data["attempt_number"] == 2
        assert data["is_last_auto_retry"] is True
        assert data["generated_sql"] == "SELECT 2 AS id"

    @pytest.mark.asyncio
    async def test_regenerate_byte_equal_returns_refine_prompt(self, authenticated_client):
        """Inv 4: Regenerate with identical SQL returns RefinePrompt."""
        # Submit a question first
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 1+1?"},
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        # StubLLM always returns "SELECT 1 AS id", so this will be byte-equal
        regenerate_resp = await authenticated_client.post(
            "/api/v1/query/regenerate",
            json={"attempt_id": attempt_id},
            headers={"origin": "http://test"},
        )
        assert regenerate_resp.status_code == 200
        data = regenerate_resp.json()
        assert data["kind"] == "refine"
        assert data["message_key"] == "query.refine.message"
        assert data["should_refine"] is True

    @pytest.mark.asyncio
    async def test_regenerate_max_retry_returns_refine_prompt(self, authenticated_client):
        """Two regenerates in a row: second hits max-retry -> RefinePrompt."""
        # Submit a question first
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 1+1?"},
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        # First regenerate with patched LLM returning different SQL
        with patch("app.llm.stub.StubLLM.generate_sql", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "SELECT 2 AS id"

            regen1_resp = await authenticated_client.post(
                "/api/v1/query/regenerate",
                json={"attempt_id": attempt_id},
                headers={"origin": "http://test"},
            )

        assert regen1_resp.status_code == 200
        regen1_data = regen1_resp.json()
        assert regen1_data["kind"] == "result"
        assert regen1_data["attempt_number"] == 2
        second_attempt_id = regen1_data["attempt_id"]

        # Second regenerate on attempt #2 -> max retry
        regen2_resp = await authenticated_client.post(
            "/api/v1/query/regenerate",
            json={"attempt_id": second_attempt_id},
            headers={"origin": "http://test"},
        )
        assert regen2_resp.status_code == 200
        regen2_data = regen2_resp.json()
        assert regen2_data["kind"] == "refine"
        assert regen2_data["message_key"] == "query.refine.message"
        assert regen2_data["should_refine"] is True

    @pytest.mark.asyncio
    async def test_regenerate_attempt_not_active(self, authenticated_client):
        """G-004: Regenerate with non-active attempt_id returns 422."""
        response = await authenticated_client.post(
            "/api/v1/query/regenerate",
            json={"attempt_id": "550e8400-e29b-41d4-a716-446655440000"},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 422
        data = response.json()
        assert data["message_key"] == "error.attemptInvalid"

    @pytest.mark.asyncio
    async def test_regenerate_succeeds_while_lock_held(self, authenticated_client, redis_client):
        """G-001: Regenerate while processing lock is held succeeds."""
        # Submit first
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 2+2?"},
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        # Regenerate should succeed because lock is held by submit and active_attempt matches
        with patch("app.llm.stub.StubLLM.generate_sql", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "SELECT 2 AS id"
            regenerate_resp = await authenticated_client.post(
                "/api/v1/query/regenerate",
                json={"attempt_id": attempt_id},
                headers={"origin": "http://test"},
            )
        assert regenerate_resp.status_code == 200

    @pytest.mark.asyncio
    async def test_regenerate_unauthenticated(self, app_client):
        """Regenerate without authentication returns 401."""
        response = await app_client.post(
            "/api/v1/query/regenerate",
            json={"attempt_id": "550e8400-e29b-41d4-a716-446655440000"},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["message_key"] == "error.unauthorized"
