"""T-077 — AnthropicAdapter unit tests."""

import asyncio

import httpx
import pytest
import respx
from httpx import Response

from app.llm.anthropic_adapter import AnthropicAdapter
from app.llm.exceptions import LLMTimeout, LLMUnavailable


@pytest.fixture
def adapter() -> AnthropicAdapter:
    return AnthropicAdapter(api_key="fake-api-key", model="claude-3-opus-20240229", timeout_s=30)


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
    respx.post("https://api.anthropic.com/v1/messages").mock(return_value=Response(502, text="Bad Gateway"))

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_timeout_raises_llm_timeout(adapter: AnthropicAdapter):
    """Request timeout raises LLMTimeout."""
    respx.post("https://api.anthropic.com/v1/messages").mock(side_effect=httpx.TimeoutException("Request timed out"))

    with pytest.raises(LLMTimeout):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_429_raises_llm_unavailable(adapter: AnthropicAdapter):
    """HTTP 429 rate limit raises LLMUnavailable."""
    respx.post("https://api.anthropic.com/v1/messages").mock(return_value=Response(429, text="Rate limited"))

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_401_raises_typed_llm_unavailable(adapter: AnthropicAdapter):
    """HTTP 4xx auth failure raises typed LLMUnavailable with a sanitized constant message."""
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(
            401,
            json={"type": "error", "error": {"type": "authentication_error", "message": "internal-detail"}},
        )
    )

    with pytest.raises(LLMUnavailable) as excinfo:
        await adapter.generate("prompt")
    assert excinfo.value.provider == "anthropic"
    assert "internal-detail" not in str(excinfo.value)


@respx.mock
async def test_generate_non_json_body_raises_typed_llm_unavailable(adapter: AnthropicAdapter):
    """A 200 response whose body is not JSON raises typed LLMUnavailable, not JSONDecodeError."""
    respx.post("https://api.anthropic.com/v1/messages").mock(return_value=Response(200, text="not-json"))

    with pytest.raises(LLMUnavailable) as excinfo:
        await adapter.generate("prompt")
    assert excinfo.value.provider == "anthropic"


@respx.mock
async def test_generate_missing_content_field_raises_typed_llm_unavailable(adapter: AnthropicAdapter):
    """A structured 200 response without the expected content field raises typed LLMUnavailable."""
    respx.post("https://api.anthropic.com/v1/messages").mock(return_value=Response(200, json={"id": "msg_01"}))

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_empty_content_list_raises_typed_llm_unavailable(adapter: AnthropicAdapter):
    """A structured 200 response with an empty content list raises typed LLMUnavailable."""
    respx.post("https://api.anthropic.com/v1/messages").mock(return_value=Response(200, json={"content": []}))

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")


async def test_generate_cancellation_propagates(adapter: AnthropicAdapter):
    """asyncio cancellation during the provider request propagates instead of being mapped."""

    async def slow_post(*args, **kwargs):
        await asyncio.sleep(60)

    adapter._client.post = slow_post

    task = asyncio.create_task(adapter.generate("prompt"))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.parametrize(
    "raw_body",
    [
        "null",
        "[1, 2]",
        '"scalar-string"',
        '{"content": null}',
        '{"content": 3}',
        '{"content": ["not-a-dict"]}',
    ],
)
@respx.mock
async def test_generate_malformed_container_shapes_raise_typed_llm_unavailable(
    adapter: AnthropicAdapter, raw_body: str
):
    """Malformed but valid-JSON response containers map to typed sanitized failure, never raw TypeError."""
    respx.post("https://api.anthropic.com/v1/messages").mock(return_value=Response(200, text=raw_body))

    with pytest.raises(LLMUnavailable) as excinfo:
        await adapter.generate("prompt")
    assert excinfo.value.provider == "anthropic"
    assert excinfo.value.message_key == "error.llmUnavailable"
    assert str(excinfo.value) == "Malformed response from provider"
    assert "'NoneType'" not in str(excinfo.value)
    assert raw_body not in str(excinfo.value)
