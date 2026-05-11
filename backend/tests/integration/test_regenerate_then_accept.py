"""F-2: O-001 — regenerate stores state="EXECUTED" so accept-after-regenerate works.

Reproduction: submit → reject (regenerate) → accept regenerated attempt.
Before fix: accept returns 422 (attempt_state_invalid).
After fix: accept returns 201.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestRegenerateThenAccept:
    """Integration test for accept-after-regenerate flow."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_regenerate_then_accept(self, authenticated_client):
        """Submit, reject (regenerate), then accept regenerated result — expect 201."""
        # Submit a question
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 1+1?"},
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        # Regenerate with different SQL
        with patch("app.llm.stub.StubLLM.generate_sql", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "SELECT 2 AS id"

            regenerate_resp = await authenticated_client.post(
                "/api/v1/query/regenerate",
                json={"attempt_id": attempt_id},
                headers={"origin": "http://test"},
            )

        assert regenerate_resp.status_code == 200
        regen_data = regenerate_resp.json()
        assert regen_data["kind"] == "result"
        new_attempt_id = regen_data["attempt_id"]

        # Accept the regenerated attempt
        accept_resp = await authenticated_client.post(
            "/api/v1/query/accept",
            json={"attempt_id": new_attempt_id},
            headers={"origin": "http://test"},
        )
        assert accept_resp.status_code == 201, f"Expected 201, got {accept_resp.status_code}: {accept_resp.text}"
        data = accept_resp.json()
        assert data["question_text"] == "What is 1+1?"
