"""T-083 — OllamaAdapter unit tests."""

import asyncio

import httpx
import pytest
import respx
from httpx import Response

from app.llm.exceptions import LLMTimeout, LLMUnavailable
from app.llm.ollama_adapter import OllamaAdapter


@pytest.fixture
def adapter() -> OllamaAdapter:
    return OllamaAdapter(host="http://localhost:11434", model="llama3.1", timeout_s=30)


@respx.mock
async def test_generate_success(adapter: OllamaAdapter):
    """Successful API call returns SQL from response field."""
    route = respx.post("http://localhost:11434/api/generate").mock(
        return_value=Response(
            200,
            json={
                "model": "llama3.1",
                "created_at": "2024-01-01T00:00:00Z",
                "response": "SELECT 1 AS id",
                "done": True,
            },
        )
    )

    sql = await adapter.generate("prompt text")
    assert sql == "SELECT 1 AS id"

    request = route.calls.last.request
    body = request.content.decode()
    assert "llama3.1" in body
    assert "prompt text" in body
    assert '"stream":false' in body


@respx.mock
async def test_generate_502_raises_llm_unavailable(adapter: OllamaAdapter):
    """HTTP 502 raises LLMUnavailable."""
    respx.post("http://localhost:11434/api/generate").mock(return_value=Response(502, text="Bad Gateway"))

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_timeout_raises_llm_timeout(adapter: OllamaAdapter):
    """Request timeout raises LLMTimeout."""
    respx.post("http://localhost:11434/api/generate").mock(side_effect=httpx.TimeoutException("Request timed out"))

    with pytest.raises(LLMTimeout):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_429_raises_llm_unavailable(adapter: OllamaAdapter):
    """HTTP 429 rate limit raises LLMUnavailable."""
    respx.post("http://localhost:11434/api/generate").mock(return_value=Response(429, text="Rate limited"))

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_401_raises_typed_llm_unavailable(adapter: OllamaAdapter):
    """HTTP 4xx failure raises typed LLMUnavailable with a sanitized constant message."""
    respx.post("http://localhost:11434/api/generate").mock(
        return_value=Response(401, json={"error": "internal-detail"})
    )

    with pytest.raises(LLMUnavailable) as excinfo:
        await adapter.generate("prompt")
    assert excinfo.value.provider == "ollama"
    assert "internal-detail" not in str(excinfo.value)


@respx.mock
async def test_generate_non_json_body_raises_typed_llm_unavailable(adapter: OllamaAdapter):
    """A 200 response whose body is not JSON raises typed LLMUnavailable, not JSONDecodeError."""
    respx.post("http://localhost:11434/api/generate").mock(return_value=Response(200, text="not-json"))

    with pytest.raises(LLMUnavailable) as excinfo:
        await adapter.generate("prompt")
    assert excinfo.value.provider == "ollama"


@respx.mock
async def test_generate_missing_response_field_raises_typed_llm_unavailable(adapter: OllamaAdapter):
    """A structured 200 response without the response field raises typed LLMUnavailable."""
    respx.post("http://localhost:11434/api/generate").mock(return_value=Response(200, json={"done": True}))

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_null_response_field_raises_typed_llm_unavailable(adapter: OllamaAdapter):
    """A structured 200 response with a null response field raises typed LLMUnavailable."""
    respx.post("http://localhost:11434/api/generate").mock(return_value=Response(200, json={"response": None, "done": True}))

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")


async def test_generate_cancellation_propagates(adapter: OllamaAdapter):
    """asyncio cancellation during the provider request propagates instead of being mapped."""

    async def slow_post(*args, **kwargs):
        await asyncio.sleep(60)

    adapter._client.post = slow_post

    task = asyncio.create_task(adapter.generate("prompt"))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_host_trailing_slash_normalized():
    """A configured host with a trailing slash is normalized once."""
    adapter = OllamaAdapter(host="http://localhost:11434/", model="llama3.1", timeout_s=30)
    assert adapter._host == "http://localhost:11434"
