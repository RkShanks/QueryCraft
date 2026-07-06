"""T-215: /query/submit response_model accommodates both QueryResult and EvaluatorRejection.

Verifies that:
- 200 responses match the QueryResult shape
- 422 evaluator-rejection responses match the EvaluatorRejection shape
- Neither path triggers a 500 serialization error.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.integration
class TestQueryResponseModel:
    """Integration tests for POST /query/submit response shapes."""

    @pytest.mark.asyncio
    async def test_submit_success_matches_query_result(
        self,
        authenticated_client,
        query_submit_payload,
        deterministic_query_llm,
    ):
        """Valid question returns 200 with QueryResult shape."""
        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload("List customer names by city"),
            headers={"origin": "http://test"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        # QueryResult required fields per openapi.yaml
        assert data["kind"] == "result"
        assert "attempt_id" in data
        assert "question" in data
        assert "generated_sql" in data
        assert "columns" in data
        assert "rows" in data
        assert "row_count" in data
        assert "attempt_number" in data
        assert "is_last_auto_retry" in data

    @pytest.mark.asyncio
    async def test_submit_evaluator_rejection_matches_evaluator_rejection(
        self,
        authenticated_client,
        query_submit_payload,
        monkeypatch,
    ):
        """Unsafe SQL returns 422 with EvaluatorRejection shape (no 500)."""

        with patch(
            "app.api.v1.query.LLMProviderFactory.from_config",
            return_value=AsyncMock(generate_sql=AsyncMock(return_value="DROP TABLE users;")),
        ):
            response = await authenticated_client.post(
                "/api/v1/query/submit",
                json=query_submit_payload("List customer names by city"),
                headers={"origin": "http://test"},
            )
        assert response.status_code == 422, response.text
        data = response.json()
        # EvaluatorRejection required fields per openapi.yaml
        assert "message_key" in data
        assert "violations" in data
        assert isinstance(data["violations"], list)
