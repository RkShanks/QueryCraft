"""T-215: /query/submit response_model accommodates both QueryResult and EvaluatorRejection.

Verifies that:
- 200 responses match the QueryResult shape
- 422 evaluator-rejection responses match the EvaluatorRejection shape
- Neither path triggers a 500 serialization error.
"""

import pytest


@pytest.mark.integration
class TestQueryResponseModel:
    """Integration tests for POST /query/submit response shapes."""

    @pytest.mark.asyncio
    async def test_submit_success_matches_query_result(self, authenticated_client):
        """Valid question returns 200 with QueryResult shape."""
        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "Show me all users"},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 200
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
        self, authenticated_client, monkeypatch
    ):
        """Unsafe SQL returns 422 with EvaluatorRejection shape (no 500)."""

        class BadLLM:
            async def generate_sql(self, question, schema_context, negative_examples=None):
                return "DROP TABLE users;"

        monkeypatch.setattr(
            "app.api.v1.query.LLMProviderFactory.from_config",
            lambda _settings: BadLLM(),
        )

        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "Drop table"},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 422
        data = response.json()
        # EvaluatorRejection required fields per openapi.yaml
        assert "message_key" in data
        assert "violations" in data
        assert isinstance(data["violations"], list)
