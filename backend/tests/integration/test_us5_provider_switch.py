"""T-174: Acceptance — provider switch preserves accepted_queries (FR-026, SC-008).

Tests that switching the LLM provider via configuration does not invalidate
existing accepted-query history, and that new submissions route to the newly
configured provider.
"""

import pytest
import respx
from httpx import Response


@pytest.mark.integration
class TestProviderSwitchPreservesHistory:
    """Provider switch integration test."""

    @pytest.mark.asyncio
    async def test_switch_provider_preserves_history(self, authenticated_client, monkeypatch):
        """Switching LLM provider does not invalidate accepted-query history."""
        with respx.mock:
            # Phase 1: Ollama
            ollama_route = respx.post("http://localhost:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": "SELECT 1 AS id"},
                )
            )

            # Submit and accept a query with Ollama
            submit_resp = await authenticated_client.post(
                "/api/v1/query/submit",
                json={"question": "What is 1+1?"},
                headers={"origin": "http://test"},
            )
            assert submit_resp.status_code == 200
            attempt_id = submit_resp.json()["attempt_id"]

            accept_resp = await authenticated_client.post(
                "/api/v1/query/accept",
                json={"attempt_id": attempt_id},
                headers={"origin": "http://test"},
            )
            assert accept_resp.status_code == 201

            # Phase 2: Switch to OpenAI
            monkeypatch.setenv("LLM_PROVIDER", "openai")
            monkeypatch.setenv("LLM_API_KEY_OPENAI", "fake-openai-key")
            from app.core.config import get_settings

            get_settings.cache_clear()

            openai_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
                return_value=Response(
                    200,
                    json={"choices": [{"message": {"content": "SELECT 2 AS id"}}]},
                )
            )

            # GET history — old query must still be present
            history_resp = await authenticated_client.get(
                "/api/v1/history",
                headers={"origin": "http://test"},
            )
            assert history_resp.status_code == 200
            history_data = history_resp.json()
            assert len(history_data["items"]) == 1
            assert history_data["items"][0]["question_text"] == "What is 1+1?"

            # Submit NEW question — must route to OpenAI
            new_submit_resp = await authenticated_client.post(
                "/api/v1/query/submit",
                json={"question": "What is 2+2?"},
                headers={"origin": "http://test"},
            )
            assert new_submit_resp.status_code == 200
            assert new_submit_resp.json()["generated_sql"] == "SELECT 2 AS id"

            # Routing assertions
            assert ollama_route.called
            assert openai_route.called
