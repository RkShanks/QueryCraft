"""IS-GAP-004 configured query deadline contracts."""

import inspect
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.llm.anthropic_adapter import AnthropicAdapter
from app.llm.factory import LLMProviderFactory
from app.llm.gemini_adapter import GeminiAdapter
from app.llm.ollama_adapter import OllamaAdapter
from app.llm.openai_adapter import OpenAIAdapter


@pytest.mark.parametrize("configured_timeout", [0, -1, 1.5, float("inf"), float("nan")])
def test_invalid_query_timeout_fails_configuration(configured_timeout: object) -> None:
    with pytest.raises(ValidationError):
        Settings(QUERY_TIMEOUT_SECONDS=configured_timeout)


def test_deadline_reports_only_unconsumed_monotonic_budget() -> None:
    from app.core.query_deadline import QueryDeadline

    clock = SimpleNamespace(now=100.0)
    deadline = QueryDeadline.start(10, clock=lambda: clock.now)

    clock.now = 106.25

    assert deadline.remaining_seconds() == pytest.approx(3.75)


def test_processing_lock_ttl_adds_fixed_cleanup_grace() -> None:
    from app.core.query_deadline import query_lock_ttl_seconds

    assert query_lock_ttl_seconds(7) == 12


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("adapter_type", "adapter_kwargs"),
    [
        (AnthropicAdapter, {"api_key": "test-key"}),
        (OpenAIAdapter, {"api_key": "test-key"}),
        (GeminiAdapter, {"api_key": "test-key"}),
        (OllamaAdapter, {"host": "http://localhost:11434"}),
    ],
)
async def test_provider_adapters_require_configured_timeout_without_hidden_default(
    adapter_type,
    adapter_kwargs,
) -> None:
    timeout_parameter = inspect.signature(adapter_type).parameters["timeout_s"]
    assert timeout_parameter.default is inspect.Parameter.empty

    adapter = adapter_type(**adapter_kwargs, timeout_s=45)
    try:
        assert adapter._timeout_s == 45
        assert adapter._client.timeout.read == 45
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_provider_factory_timeout_cache_tracks_configuration() -> None:
    LLMProviderFactory.clear_cache()
    settings = SimpleNamespace(
        LLM_PROVIDER="ollama",
        LLM_MODEL_NAME="llama3.1",
        LLM_BASE_URL_OLLAMA="http://localhost:11434",
        QUERY_TIMEOUT_SECONDS=45,
    )

    first = LLMProviderFactory.from_config(settings)
    settings.QUERY_TIMEOUT_SECONDS = 60
    second = LLMProviderFactory.from_config(settings)

    try:
        assert first is not second
        assert first._timeout_s == 45
        assert second._timeout_s == 60
    finally:
        await LLMProviderFactory.shutdown_all()
