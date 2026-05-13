"""T-079 — OpenAIAdapter unit tests."""

import httpx
import pytest
import respx
from httpx import Response

from app.llm.exceptions import LLMTimeout, LLMUnavailable
from app.llm.openai_adapter import OpenAIAdapter


@pytest.fixture
def adapter() -> OpenAIAdapter:
    return OpenAIAdapter(api_key="fake-openai-key", model="gpt-4o")


@respx.mock
async def test_generate_success(adapter: OpenAIAdapter):
    """Successful API call returns SQL from choices[0].message.content."""
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-01",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "gpt-4o",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "SELECT 1 AS id"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )
    )

    sql = await adapter.generate("prompt text")
    assert sql == "SELECT 1 AS id"

    request = route.calls.last.request
    assert "Bearer fake-openai-key" in request.headers["Authorization"]
    body = request.content.decode()
    assert "gpt-4o" in body
    assert "prompt text" in body


@respx.mock
async def test_generate_502_raises_llm_unavailable(adapter: OpenAIAdapter):
    """HTTP 502 raises LLMUnavailable."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=Response(502, text="Bad Gateway"))

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_timeout_raises_llm_timeout(adapter: OpenAIAdapter):
    """Request timeout raises LLMTimeout."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("Request timed out")
    )

    with pytest.raises(LLMTimeout):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_429_raises_llm_unavailable(adapter: OpenAIAdapter):
    """HTTP 429 rate limit raises LLMUnavailable."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=Response(429, text="Rate limited"))

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")
