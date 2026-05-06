"""T-077 — AnthropicAdapter unit tests."""

import httpx
import pytest
import respx
from httpx import Response

from app.llm.anthropic_adapter import AnthropicAdapter
from app.llm.exceptions import LLMTimeout, LLMUnavailable


@pytest.fixture
def adapter() -> AnthropicAdapter:
    return AnthropicAdapter(api_key="fake-api-key", model="claude-3-opus-20240229")


@respx.mock
async def test_generate_success(adapter: AnthropicAdapter):
    """Successful API call returns the SQL from content[0].text."""
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(
            200,
            json={
                "id": "msg_01",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "SELECT 1 AS id"}],
                "model": "claude-3-opus-20240229",
                "stop_reason": "end_turn",
            },
        )
    )

    sql = await adapter.generate("prompt text")
    assert sql == "SELECT 1 AS id"

    request = route.calls.last.request
    assert request.headers["x-api-key"] == "fake-api-key"
    body = request.content.decode()
    assert "claude-3-opus-20240229" in body
    assert "prompt text" in body


@respx.mock
async def test_generate_502_raises_llm_unavailable(adapter: AnthropicAdapter):
    """HTTP 502 from upstream raises LLMUnavailable."""
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(502, text="Bad Gateway")
    )

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_timeout_raises_llm_timeout(adapter: AnthropicAdapter):
    """Request timeout raises LLMTimeout."""
    respx.post("https://api.anthropic.com/v1/messages").mock(
        side_effect=httpx.TimeoutException("Request timed out")
    )

    with pytest.raises(LLMTimeout):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_429_raises_llm_unavailable(adapter: AnthropicAdapter):
    """HTTP 429 rate limit raises LLMUnavailable."""
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(429, text="Rate limited")
    )

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")
