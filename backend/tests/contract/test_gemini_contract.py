"""T-370..T-374: Real-LLM contract tests against simulated provider wire formats."""

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
    route = respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent").mock(
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


@respx.mock
@pytest.mark.asyncio
async def test_gemini_contract_429_rate_limit(adapter: GeminiAdapter):
    """T-371: 429 rate limit — clear error, no crash."""
    respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent").mock(
        return_value=Response(
            429,
            json={
                "error": {
                    "code": 429,
                    "message": "Resource has been exhausted (e.g. check quota).",
                    "status": "RESOURCE_EXHAUSTED",
                }
            },
        )
    )

    with pytest.raises(LLMUnavailable) as exc:
        await adapter.generate("Test prompt")

    assert exc.value.provider == "gemini"


@respx.mock
@pytest.mark.asyncio
async def test_gemini_contract_5xx_server_error(adapter: GeminiAdapter):
    """T-372: 5xx server error — clear service-unavailable error."""
    respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent").mock(
        return_value=Response(
            500,
            json={
                "error": {
                    "code": 500,
                    "message": "Internal error encountered.",
                    "status": "INTERNAL",
                }
            },
        )
    )

    with pytest.raises(LLMUnavailable) as exc:
        await adapter.generate("Test prompt")

    assert exc.value.provider == "gemini"


@respx.mock
@pytest.mark.asyncio
async def test_gemini_contract_malformed_response(adapter: GeminiAdapter):
    """T-373: Malformed response: invalid JSON / missing candidates — graceful handling."""
    # Test missing candidates
    respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent").mock(
        return_value=Response(200, json={"unexpected_format": True})
    )

    with pytest.raises(LLMUnavailable) as exc:
        await adapter.generate("Test prompt")

    assert exc.value.provider == "gemini"
    assert "Malformed response" in str(exc.value)

    # Test invalid JSON
    respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent").mock(
        return_value=Response(200, text="Not JSON format")
    )

    with pytest.raises(LLMUnavailable) as exc:
        await adapter.generate("Test prompt")

    assert exc.value.provider == "gemini"
    assert "Malformed response" in str(exc.value)


@respx.mock
@pytest.mark.asyncio
async def test_gemini_contract_schema_context_too_long(adapter: GeminiAdapter):
    """T-374: Contract test schema-context-too-long — token-limit error surfaced."""
    respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent").mock(
        return_value=Response(
            400,
            json={
                "error": {
                    "code": 400,
                    "message": "Request payload size exceeds the limit: 10485760 bytes.",
                    "status": "INVALID_ARGUMENT",
                }
            },
        )
    )

    with pytest.raises(SchemaTokenLimitExceeded) as exc:
        await adapter.generate("Test prompt")

    assert exc.value.message_key == "error.schemaTokenLimit"
