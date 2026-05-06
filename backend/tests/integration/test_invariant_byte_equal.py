"""T-121b: Invariant 4 — Byte-Equal Duplicate addendum test (gap-fix closure).

Stubs the LLM to return identical SQL on submit and regenerate.
Verifies that regenerate returns RefinePrompt WITHOUT calling evaluator
or executor.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestInvariantByteEqual:
    """Invariant 4: Byte-equal duplicate detection integration test."""

    @pytest.mark.asyncio
    async def test_byte_equal_duplicate_returns_refine_prompt(self, authenticated_client):
        """Regenerate with byte-equal SQL returns RefinePrompt; evaluator/executor not called."""
        # Stub LLM to always return the same SQL
        with patch("app.llm.stub.StubLLM.generate_sql", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "SELECT 1 AS id"

            # Initial submit
            submit_resp = await authenticated_client.post(
                "/api/v1/query/submit",
                json={"question": "What is 1+1?"},
                headers={"origin": "http://test"},
            )
            assert submit_resp.status_code == 200
            attempt_id = submit_resp.json()["attempt_id"]

        # Now regenerate with the same StubLLM (which returns identical SQL)
        # Patch evaluator and executor to verify they are NOT called
        with (
            patch("app.llm.stub.StubLLM.generate_sql", new_callable=AsyncMock) as mock_llm,
            patch("app.evaluator.pipeline.Evaluator.evaluate") as mock_eval,
            patch("app.source_db.executor.SourceDBExecutor.execute") as mock_exec,
        ):
            mock_llm.return_value = "SELECT 1 AS id"

            regen_resp = await authenticated_client.post(
                "/api/v1/query/regenerate",
                json={"attempt_id": attempt_id},
                headers={"origin": "http://test"},
            )

            assert regen_resp.status_code == 200
            data = regen_resp.json()
            assert data["kind"] == "refine"
            assert data["message_key"] == "query.refine.message"

            # Byte-equal check happens BEFORE evaluator and executor
            mock_eval.assert_not_awaited()
            mock_exec.assert_not_awaited()
