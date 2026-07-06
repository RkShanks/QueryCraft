"""T-176: Acceptance — Ollama-exclusive routing (FR-009).

Tests that when the platform is configured to use Ollama, all LLM traffic is
routed exclusively to the Ollama endpoint and zero calls are made to any
cloud provider endpoint.
"""

import pytest
import respx
from httpx import Response


@pytest.mark.integration
class TestOllamaExclusiveRouting:
    """Ollama-exclusive routing integration test."""

    @pytest.mark.asyncio
    async def test_ollama_routes_exclusively(self, authenticated_client, query_submit_payload):
        """When configured for Ollama, no cloud provider endpoints are contacted."""
        with respx.mock:
            ollama_route = respx.post("http://localhost:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": "SELECT 1 AS id"},
                )
            )
            openai_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
                return_value=Response(200, json={"choices": [{"message": {"content": "SELECT 1"}}]})
            )
            anthropic_route = respx.post("https://api.anthropic.com/v1/messages").mock(
                return_value=Response(200, json={"content": [{"text": "SELECT 1"}]})
            )
            gemini_route = respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
            ).mock(
                return_value=Response(
                    200,
                    json={"candidates": [{"content": {"parts": [{"text": "SELECT 1"}]}}]},
                )
            )

            submit_resp = await authenticated_client.post(
                "/api/v1/query/submit",
                json=query_submit_payload("Show me something"),
                headers={"origin": "http://test"},
            )
            assert submit_resp.status_code == 200

            # Only Ollama may be contacted
            assert ollama_route.called
            assert not openai_route.called
            assert not anthropic_route.called
            assert not gemini_route.called
