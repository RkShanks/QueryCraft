"""T-154 regression test — LLM adapters must implement generate_sql.

QueryService calls ``llm.generate_sql(question, schema_context, negative_examples)``.
The real adapters (Anthropic, OpenAI, Gemini, Ollama) only define ``generate(prompt)``,
so swapping StubLLM for a real adapter causes AttributeError.
"""

import pytest

from app.llm.anthropic_adapter import AnthropicAdapter
from app.llm.gemini_adapter import GeminiAdapter
from app.llm.ollama_adapter import OllamaAdapter
from app.llm.openai_adapter import OpenAIAdapter


@pytest.mark.parametrize(
    "adapter_cls, kwargs",
    [
        (AnthropicAdapter, {"api_key": "test"}),
        (OpenAIAdapter, {"api_key": "test"}),
        (GeminiAdapter, {"api_key": "test"}),
        (OllamaAdapter, {"host": "http://localhost:11434"}),
    ],
)
def test_adapter_has_generate_sql(adapter_cls, kwargs):
    """Every real adapter must expose generate_sql with the QueryService signature."""
    adapter = adapter_cls(**kwargs)
    assert hasattr(adapter, "generate_sql")
    import inspect

    sig = inspect.signature(adapter.generate_sql)
    params = list(sig.parameters.keys())
    assert "question" in params
    assert "schema_context" in params
