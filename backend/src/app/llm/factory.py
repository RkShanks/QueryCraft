"""LLM provider factory — selects adapter from application config."""

import os

from app.llm.anthropic_adapter import AnthropicAdapter
from app.llm.exceptions import LLMConfigurationError
from app.llm.gemini_adapter import GeminiAdapter
from app.llm.ollama_adapter import OllamaAdapter
from app.llm.openai_adapter import OpenAIAdapter
from app.llm.provider import LLMProvider


class LLMProviderFactory:
    """Builds the appropriate LLM adapter based on ``settings.LLM_PROVIDER``."""

    @staticmethod
    def from_config(settings) -> LLMProvider:
        """Return an LLMProvider instance matching the configured provider.

        Raises:
            LLMConfigurationError: on unknown provider or missing API key.
        """
        provider_name = (getattr(settings, "LLM_PROVIDER", "ollama") or "ollama").lower()
        model_name = getattr(settings, "LLM_MODEL_NAME", None)

        if provider_name == "anthropic":
            api_key = getattr(settings, "LLM_API_KEY_ANTHROPIC", "") or os.getenv("ANTHROPIC_API_KEY", "")
            if not api_key:
                raise LLMConfigurationError("Missing ANTHROPIC_API_KEY")
            return AnthropicAdapter(api_key=api_key, model=model_name or "claude-3-5-sonnet-20241022")

        if provider_name == "openai":
            api_key = getattr(settings, "LLM_API_KEY_OPENAI", "") or os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                raise LLMConfigurationError("Missing OPENAI_API_KEY")
            return OpenAIAdapter(api_key=api_key, model=model_name or "gpt-4o")

        if provider_name == "gemini":
            api_key = getattr(settings, "LLM_API_KEY_GEMINI", "") or os.getenv("GOOGLE_API_KEY", "")
            if not api_key:
                raise LLMConfigurationError("Missing GOOGLE_API_KEY")
            return GeminiAdapter(api_key=api_key, model=model_name or "gemini-1.5-pro")

        if provider_name == "ollama":
            host = getattr(settings, "LLM_BASE_URL_OLLAMA", "http://localhost:11434")
            return OllamaAdapter(host=host, model=model_name or "llama3.1")

        raise LLMConfigurationError(f"Unknown LLM provider: {provider_name}")
