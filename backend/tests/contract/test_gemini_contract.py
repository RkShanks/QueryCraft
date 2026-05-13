"""T-370..T-374: Real-LLM contract tests against simulated provider wire formats."""

import httpx
import pytest
import respx
from httpx import Response

from app.core.exceptions import SchemaTokenLimitExceeded
from app.llm.exceptions import LLMUnavailable
from app.llm.gemini_adapter import GeminiAdapter


@pytest.fixture
def adapter() -> GeminiAdapter:
    return GeminiAdapter(api_key="fake-contract-key", model="gemini-1.5-pro")


@respx.mock
@pytest.mark.asyncio
async def test_gemini_contract_happy_path(adapter: GeminiAdapter):
    """T-370: Happy path — 200 with valid Gemini JSON, SQL extracted correctly."""
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
    ).mock(
        return_value=Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "SELECT * FROM users;"}],
                            "role": "model",
                        },
                        "finishReason": "STOP",
                        "index": 0,
                    }
                ],
            },
        )
    )

    sql = await adapter.generate("Test prompt")
    assert sql == "SELECT * FROM users;"

    # Verify wire format request
    request = route.calls.last.request
    assert request.headers.get("x-goog-api-key") == "fake-contract-key"
    
    # Ensure api key is not in query string
    assert "key=" not in str(request.url)

    body = request.content.decode()
    assert "Test prompt" in body
    assert "contents" in body
