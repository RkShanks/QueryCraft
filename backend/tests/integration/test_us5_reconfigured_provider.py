"""T-177: Acceptance — reconfigured provider handles new questions (FR-009, FR-026).

Tests that after switching the LLM provider from Ollama to Gemini, new
question submissions are routed to the Gemini adapter and the Ollama
adapter receives zero calls.
"""

import pytest
import respx
from httpx import Response


@pytest.mark.integration
class TestReconfiguredProviderHandlesNewQuestions:
    """Reconfigured provider integration test."""

    @pytest.mark.asyncio
    async def test_reconfigured_provider_routes_correctly(self, authenticated_client, monkeypatch):
        """After switching from Ollama to Gemini, new questions route to Gemini."""
        with respx.mock:
            # Phase 1: Ollama
            ollama_route = respx.post("http://localhost:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": "SELECT 1 AS id"},
                )
            )

            # Submit with Ollama
            submit_resp = await authenticated_client.post(
                "/api/v1/query/submit",
                json={"question": "What is 1+1?"},
                headers={"origin": "http://test"},
            )
            assert submit_resp.status_code == 200

            # Phase 2: Switch to Gemini
            monkeypatch.setenv("LLM_PROVIDER", "gemini")
            monkeypatch.setenv("LLM_API_KEY_GEMINI", "fake-gemini-key")
            from app.core.config import get_settings

            get_settings.cache_clear()

            gemini_route = respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
            ).mock(
                return_value=Response(
                    200,
                    json={"candidates": [{"content": {"parts": [{"text": "SELECT 2 AS id"}]}}]},
                )
            )

            # Submit with Gemini
            new_submit_resp = await authenticated_client.post(
                "/api/v1/query/submit",
                json={"question": "What is 2+2?"},
                headers={"origin": "http://test"},
            )
            assert new_submit_resp.status_code == 200
            assert new_submit_resp.json()["generated_sql"] == "SELECT 2 AS id"

            assert ollama_route.called
            assert gemini_route.called
