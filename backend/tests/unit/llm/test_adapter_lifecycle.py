"""F-001: LLM adapter lifecycle + factory caching tests."""

from dataclasses import dataclass

import pytest

from app.llm.anthropic_adapter import AnthropicAdapter
from app.llm.factory import LLMProviderFactory
from app.llm.gemini_adapter import GeminiAdapter
from app.llm.ollama_adapter import OllamaAdapter
from app.llm.openai_adapter import OpenAIAdapter


class FakeSettings:
    """Minimal settings stand-in for factory tests."""

    def __init__(self, provider="ollama", model="", api_key="", host="http://localhost:11434", timeout=30):
        self.LLM_PROVIDER = provider
        self.LLM_MODEL_NAME = model
        self.LLM_API_KEY_ANTHROPIC = api_key
        self.LLM_API_KEY_OPENAI = api_key
        self.LLM_API_KEY_GEMINI = api_key
        self.LLM_BASE_URL_OLLAMA = host
        self.QUERY_TIMEOUT_SECONDS = timeout


@pytest.mark.parametrize(
    "cls,kwargs",
    [
        (AnthropicAdapter, {"api_key": "test-key", "timeout_s": 30}),
        (OpenAIAdapter, {"api_key": "test-key", "timeout_s": 30}),
        (GeminiAdapter, {"api_key": "test-key", "timeout_s": 30}),
        (OllamaAdapter, {"host": "http://localhost:11434", "timeout_s": 30}),
    ],
)
def test_adapter_has_aclose_method(cls, kwargs):
    adapter = cls(**kwargs)
    assert hasattr(adapter, "aclose")
    assert callable(adapter.aclose)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cls,kwargs",
    [
        (AnthropicAdapter, {"api_key": "test-key", "timeout_s": 30}),
        (OpenAIAdapter, {"api_key": "test-key", "timeout_s": 30}),
        (GeminiAdapter, {"api_key": "test-key", "timeout_s": 30}),
        (OllamaAdapter, {"host": "http://localhost:11434", "timeout_s": 30}),
    ],
)
async def test_adapter_aclose_closes_httpx_client(cls, kwargs, monkeypatch):
    adapter = cls(**kwargs)
    calls = []
    original_aclose = adapter._client.aclose

    async def tracked_aclose():
        calls.append("aclose")
        await original_aclose()

    monkeypatch.setattr(adapter._client, "aclose", tracked_aclose)
    await adapter.aclose()
    assert calls == ["aclose"]


def test_factory_returns_same_instance_for_same_config(monkeypatch):
    LLMProviderFactory.clear_cache()
    settings = FakeSettings(provider="ollama", model="llama3.1")
    first = LLMProviderFactory.from_config(settings)
    second = LLMProviderFactory.from_config(settings)
    assert first is second


def test_factory_new_instance_after_cache_clear(monkeypatch):
    LLMProviderFactory.clear_cache()
    settings = FakeSettings(provider="ollama", model="llama3.1")
    first = LLMProviderFactory.from_config(settings)
    LLMProviderFactory.clear_cache()
    second = LLMProviderFactory.from_config(settings)
    assert first is not second


def test_factory_returns_different_instance_for_different_provider(monkeypatch):
    LLMProviderFactory.clear_cache()
    settings_ollama = FakeSettings(provider="ollama", model="llama3.1")
    settings_openai = FakeSettings(provider="openai", model="gpt-4o", api_key="sk-test")
    ollama = LLMProviderFactory.from_config(settings_ollama)
    openai = LLMProviderFactory.from_config(settings_openai)
    assert ollama is not openai


@pytest.mark.asyncio
async def test_factory_shutdown_all_closes_all_cached_adapters(monkeypatch):
    LLMProviderFactory.clear_cache()
    settings1 = FakeSettings(provider="ollama", model="llama3.1")
    settings2 = FakeSettings(provider="openai", model="gpt-4o", api_key="sk-test")
    adapter1 = LLMProviderFactory.from_config(settings1)
    adapter2 = LLMProviderFactory.from_config(settings2)

    calls = []
    for adapter in (adapter1, adapter2):
        orig = adapter._client.aclose

        async def make_tracked(orig=orig):
            calls.append("aclose")
            await orig()

        monkeypatch.setattr(adapter._client, "aclose", make_tracked)

    await LLMProviderFactory.shutdown_all()
    assert len(calls) == 2
    assert LLMProviderFactory._cache == {}


@dataclass
class _ControllableAdapter:
    should_fail: bool = False
    close_count: int = 0

    async def aclose(self) -> None:
        self.close_count += 1
        if self.should_fail:
            raise RuntimeError("private adapter configuration")


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_indexes", [{0}, {1}, {2}, {0, 2}])
async def test_factory_shutdown_failure_does_not_skip_later_cached_adapters(failed_indexes):
    """IS-GAP-021: every cached adapter gets one close attempt per shutdown pass."""
    adapters = [_ControllableAdapter(index in failed_indexes) for index in range(3)]
    LLMProviderFactory._cache = {f"adapter-{index}": adapter for index, adapter in enumerate(adapters)}

    with pytest.raises(RuntimeError, match="^llm adapter shutdown failed$") as exc_info:
        await LLMProviderFactory.shutdown_all()

    assert type(exc_info.value).__name__ == "LLMShutdownError"
    assert exc_info.value.failure_count == len(failed_indexes)
    assert [adapter.close_count for adapter in adapters] == [1, 1, 1]
    assert list(LLMProviderFactory._cache.values()) == [
        adapter for index, adapter in enumerate(adapters) if index in failed_indexes
    ]

    for adapter in adapters:
        adapter.should_fail = False
    await LLMProviderFactory.shutdown_all()

    assert [adapter.close_count for adapter in adapters] == [
        2 if index in failed_indexes else 1 for index in range(3)
    ]
    assert LLMProviderFactory._cache == {}
