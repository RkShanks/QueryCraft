"""LLM provider factory — selects adapter from application config."""

import os

from app.llm.anthropic_adapter import AnthropicAdapter
from app.llm.exceptions import LLMConfigurationError
from app.llm.gemini_adapter import GeminiAdapter
from app.llm.ollama_adapter import OllamaAdapter
from app.llm.openai_adapter import OpenAIAdapter
from app.llm.provider import LLMProvider
from app.llm.stub import StubLLM


def _api_key_fingerprint(key: str) -> str:
    """Return a short, non-sensitive fingerprint of an API key for cache keys."""
    if not key:
        return ""
    return key[:4] + "..." + key[-4:] if len(key) > 8 else key


class LLMProviderFactory:
    """Builds the appropriate LLM adapter based on ``settings.LLM_PROVIDER``."""

    _cache: dict[str, LLMProvider] = {}

    @classmethod
    def _cache_key(cls, provider: str, model_name: str, api_key: str) -> str:
        return f"{provider}:{model_name}:{_api_key_fingerprint(api_key)}"

    @classmethod
    def from_config(cls, settings) -> LLMProvider:
        """Return an LLMProvider instance matching the configured provider.

        Cached per (provider, model, api_key_fingerprint) so repeated calls
        reuse the same adapter instance and its HTTP connection pool.

        Raises:
            LLMConfigurationError: on unknown provider or missing API key.
        """
        provider_name = (getattr(settings, "LLM_PROVIDER", "ollama") or "ollama").lower()
        model_name = getattr(settings, "LLM_MODEL_NAME", None) or ""

        if provider_name == "stub":
            return StubLLM()

        api_key = ""
        if provider_name == "anthropic":
            api_key = getattr(settings, "LLM_API_KEY_ANTHROPIC", "") or os.getenv("ANTHROPIC_API_KEY", "")
        elif provider_name == "openai":
            api_key = getattr(settings, "LLM_API_KEY_OPENAI", "") or os.getenv("OPENAI_API_KEY", "")
        elif provider_name == "gemini":
            api_key = getattr(settings, "LLM_API_KEY_GEMINI", "") or os.getenv("GOOGLE_API_KEY", "")

        key = cls._cache_key(provider_name, model_name, api_key)
        if key in cls._cache:
            return cls._cache[key]

        if provider_name == "anthropic":
            if not api_key:
                raise LLMConfigurationError("Missing ANTHROPIC_API_KEY")
            adapter = AnthropicAdapter(api_key=api_key, model=model_name or "claude-3-5-sonnet-20241022")
        elif provider_name == "openai":
            if not api_key:
                raise LLMConfigurationError("Missing OPENAI_API_KEY")
            adapter = OpenAIAdapter(api_key=api_key, model=model_name or "gpt-4o")
        elif provider_name == "gemini":
            if not api_key:
                raise LLMConfigurationError("Missing GOOGLE_API_KEY")
            adapter = GeminiAdapter(api_key=api_key, model=model_name or "gemini-1.5-pro")
        elif provider_name == "ollama":
            host = getattr(settings, "LLM_BASE_URL_OLLAMA", "http://localhost:11434")
            adapter = OllamaAdapter(host=host, model=model_name or "llama3.1")
        else:
            raise LLMConfigurationError(f"Unknown LLM provider: {provider_name}")

        cls._cache[key] = adapter
        return adapter

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the adapter cache (useful in tests)."""
        cls._cache.clear()

    @classmethod
    async def shutdown_all(cls) -> None:
        """Close every cached adapter and clear the cache."""
        for adapter in list(cls._cache.values()):
            if hasattr(adapter, "aclose"):
                await adapter.aclose()
        cls._cache.clear()
