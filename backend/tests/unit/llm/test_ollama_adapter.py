"""T-083 — OllamaAdapter unit tests."""

import httpx
import pytest
import respx
from httpx import Response

from app.llm.exceptions import LLMTimeout, LLMUnavailable
from app.llm.ollama_adapter import OllamaAdapter


@pytest.fixture
def adapter() -> OllamaAdapter:
    return OllamaAdapter(host="http://localhost:11434", model="llama3.1")


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
