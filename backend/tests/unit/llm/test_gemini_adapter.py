"""T-081 — GeminiAdapter unit tests."""

import httpx
import pytest
import respx
from httpx import Response

from app.llm.exceptions import LLMTimeout, LLMUnavailable
from app.llm.gemini_adapter import GeminiAdapter


@pytest.fixture
def adapter() -> GeminiAdapter:
    return GeminiAdapter(api_key="fake-gemini-key", model="gemini-1.5-pro")


@respx.mock
async def test_generate_success(adapter: GeminiAdapter):
    """Successful API call returns SQL from candidates[0].content.parts[0].text."""
    route = respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent").mock(
        return_value=Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "SELECT 1 AS id"}],
                            "role": "model",
                        },
                        "finishReason": "STOP",
                        "index": 0,
                    }
                ],
            },
        )
    )

    sql = await adapter.generate("prompt text")
    assert sql == "SELECT 1 AS id"

    request = route.calls.last.request
    assert request.headers.get("x-goog-api-key") == "fake-gemini-key"
    assert "key=" not in str(request.url)
    body = request.content.decode()
    assert "prompt text" in body


@respx.mock
async def test_generate_502_raises_llm_unavailable(adapter: GeminiAdapter):
    """HTTP 502 raises LLMUnavailable."""
    respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent").mock(
        return_value=Response(502, text="Bad Gateway")
    )

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_timeout_raises_llm_timeout(adapter: GeminiAdapter):
    """Request timeout raises LLMTimeout."""
    respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent").mock(
        side_effect=httpx.TimeoutException("Request timed out")
    )

    with pytest.raises(LLMTimeout):
        await adapter.generate("prompt")


@respx.mock
async def test_generate_429_raises_llm_unavailable(adapter: GeminiAdapter):
    """HTTP 429 rate limit raises LLMUnavailable."""
    respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent").mock(
        return_value=Response(429, text="Rate limited")
    )

    with pytest.raises(LLMUnavailable):
        await adapter.generate("prompt")


def _fake_response(text: str) -> Response:
    return Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


@respx.mock
async def test_generate_sql_mysql_strips_public_schema(adapter: GeminiAdapter):
    """MySQL dialect strips public. schema prefix from generated SQL."""
    respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent").mock(
        return_value=_fake_response("SELECT * FROM public.actor")
    )

    sql = await adapter.generate_sql("question", "schema", target_dialect="mysql")
    assert "public." not in sql
    assert "actor" in sql


@respx.mock
async def test_generate_sql_tsql_strips_public_schema(adapter: GeminiAdapter):
    """TSQL dialect strips public. schema prefix from generated SQL."""
    respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent").mock(
        return_value=_fake_response("SELECT * FROM public.Customer")
    )

    sql = await adapter.generate_sql("question", "schema", target_dialect="tsql")
    assert "public." not in sql
    assert "Customer" in sql


@respx.mock
async def test_generate_sql_postgres_preserves_public_schema(adapter: GeminiAdapter):
    """PostgreSQL dialect preserves public. schema prefix."""
    respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent").mock(
        return_value=_fake_response("SELECT * FROM public.actor")
    )

    sql = await adapter.generate_sql("question", "schema", target_dialect="postgres")
    assert "public.actor" in sql


@respx.mock
async def test_generate_sql_does_not_strip_compound_public(adapter: GeminiAdapter):
    """Cleanup must not touch 'public' when it is part of a larger word."""
    respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent").mock(
        return_value=_fake_response("SELECT * FROM mypublic.table")
    )

    sql = await adapter.generate_sql("question", "schema", target_dialect="mysql")
    assert "mypublic.table" in sql
