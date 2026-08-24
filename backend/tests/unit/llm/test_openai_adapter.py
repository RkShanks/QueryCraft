"""T-079 — OpenAIAdapter unit tests."""

import asyncio

import httpx
import pytest
import respx
from httpx import Response

from app.llm.exceptions import LLMTimeout, LLMUnavailable
from app.llm.openai_adapter import OpenAIAdapter


@pytest.fixture
def adapter() -> OpenAIAdapter:
    return OpenAIAdapter(api_key="fake-openai-key", model="gpt-4o", timeout_s=30)


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


@respx.mock
async def test_generate_401_raises_typed_llm_unavailable(adapter: OpenAIAdapter):
    """HTTP 4xx auth failure raises typed LLMUnavailable with a sanitized constant message."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(401, json={"error": {"message": "internal-detail"}})
    )

    with pytest.raises(LLMUnavailable) as excinfo:
        await adapter.generate("prompt")
    assert excinfo.value.provider == "openai"
    assert "internal-detail" not in str(excinfo.value)


@respx.mock
async def test_generate_non_json_body_raises_typed_llm_unavailable(adapter: OpenAIAdapter):
    """A 200 response whose body is not JSON raises typed LLMUnavailable, not JSONDecodeError."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=Response(200, text="not-json"))

    with pytest.raises(LLMUnavailable) as excinfo:
        await adapter.generate("prompt")
    assert excinfo.value.provider == "openai"


@respx.mock
async def test_generate_missing_choices_field_raises_typed_llm_unavailable(adapter: OpenAIAdapter):
    """A structured 200 response without the expected choices field raises typed LLMUnavailable."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=Response(200, json={"id": "chatcmpl-01"}))

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_null_content_raises_typed_llm_unavailable(adapter: OpenAIAdapter):
    """A structured 200 response with null message content raises typed LLMUnavailable."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(200, json={"choices": [{"index": 0, "message": {"role": "assistant", "content": None}}]})
    )

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")


async def test_generate_cancellation_propagates(adapter: OpenAIAdapter):
    """asyncio cancellation during the provider request propagates instead of being mapped."""

    async def slow_post(*args, **kwargs):
        await asyncio.sleep(60)

    adapter._client.post = slow_post

    task = asyncio.create_task(adapter.generate("prompt"))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
