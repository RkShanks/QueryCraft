"""F-2: O-001 — regenerate stores state="EXECUTED" so accept-after-regenerate works.

Reproduction: submit → reject (regenerate) → accept regenerated attempt.
Before fix: accept returns 422 (attempt_state_invalid).
After fix: accept returns 201.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.source_db.adapters import ExecuteResult


class TestRegenerateThenAccept:
    """Integration test for accept-after-regenerate flow."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_regenerate_then_accept(self, authenticated_client, query_submit_payload):
        """Submit, reject (regenerate), then accept regenerated result — expect 201."""
        with (
            patch(
                "app.api.v1.query.LLMProviderFactory.from_config",
                return_value=AsyncMock(generate_sql=AsyncMock(side_effect=["SELECT 1 AS id", "SELECT 2 AS id"])),
            ),
            patch(
                "app.source_db.adapters.PostgresAdapter.execute",
                new=AsyncMock(return_value=ExecuteResult(columns=["id"], rows=[(1,)])),
            ),
        ):
            # Submit a question
            submit_resp = await authenticated_client.post(
                "/api/v1/query/submit",
                json=query_submit_payload("What is 1+1?"),
                headers={"origin": "http://test"},
            )
            assert submit_resp.status_code == 200
            attempt_id = submit_resp.json()["attempt_id"]

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
