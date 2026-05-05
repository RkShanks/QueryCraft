"""T-085 — LLM factory selection tests."""

import pytest

from app.llm.anthropic_adapter import AnthropicAdapter
from app.llm.exceptions import LLMConfigurationError
from app.llm.factory import LLMProviderFactory
from app.llm.gemini_adapter import GeminiAdapter
from app.llm.ollama_adapter import OllamaAdapter
from app.llm.openai_adapter import OpenAIAdapter


@pytest.fixture
def factory() -> LLMProviderFactory:
    return LLMProviderFactory()


def test_selects_anthropic(factory, monkeypatch):
    """Factory returns AnthropicAdapter when provider == 'anthropic'."""
    monkeypatch.setenv("LLM_API_KEY_ANTHROPIC", "fake-anthropic-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(settings, "LLM_MODEL_NAME", "claude-3-opus")

    provider = factory.from_config(settings)
    assert isinstance(provider, AnthropicAdapter)


def test_selects_openai(factory, monkeypatch):
    """Factory returns OpenAIAdapter when provider == 'openai'."""
    monkeypatch.setenv("LLM_API_KEY_OPENAI", "fake-openai-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "LLM_MODEL_NAME", "gpt-4o")

    provider = factory.from_config(settings)
    assert isinstance(provider, OpenAIAdapter)


def test_selects_gemini(factory, monkeypatch):
    """Factory returns GeminiAdapter when provider == 'gemini'."""
    monkeypatch.setenv("LLM_API_KEY_GEMINI", "fake-gemini-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "LLM_MODEL_NAME", "gemini-1.5-pro")

    provider = factory.from_config(settings)
    assert isinstance(provider, GeminiAdapter)


def test_selects_ollama(factory, monkeypatch):
    """Factory returns OllamaAdapter when provider == 'ollama'."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "LLM_BASE_URL_OLLAMA", "http://ollama:11434")
    monkeypatch.setattr(settings, "LLM_MODEL_NAME", "llama3.1")

    provider = factory.from_config(settings)
    assert isinstance(provider, OllamaAdapter)


def test_unknown_provider_raises(factory, monkeypatch):
    """Unknown provider raises LLMConfigurationError."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_PROVIDER", "unknown")

    with pytest.raises(LLMConfigurationError):
        factory.from_config(settings)


def test_missing_api_key_raises(factory, monkeypatch):
    """Missing env var for selected provider raises LLMConfigurationError."""
    monkeypatch.setenv("LLM_API_KEY_ANTHROPIC", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")

    with pytest.raises(LLMConfigurationError):
        factory.from_config(settings)
