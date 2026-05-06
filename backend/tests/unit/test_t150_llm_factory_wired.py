"""T-150 regression test — Query router must use LLMProviderFactory.

Currently `_get_query_service` hardcodes `llm=StubLLM()`. After the fix,
it must call `LLMProviderFactory.from_config(get_settings())` so real
adapters can be resolved.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_query_service_calls_llm_factory(monkeypatch):
    """`_get_query_service` must call LLMProviderFactory.from_config instead of hardcoding StubLLM."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")

    from app.core.config import get_settings

    get_settings.cache_clear()

    mock_llm = AsyncMock()
    mock_llm.generate_sql.return_value = "SELECT 1 AS id"

    with patch("app.api.v1.query.LLMProviderFactory") as mock_factory:
        mock_factory.from_config.return_value = mock_llm
        with patch("app.api.v1.query._source_introspector.introspect", new_callable=AsyncMock) as mock_intro:
            mock_intro.return_value = None

            from app.api.v1.query import _get_query_service

            service = await _get_query_service(
                db=MagicMock(),
                redis=MagicMock(),
            )

    mock_factory.from_config.assert_called_once()
    assert service._llm is mock_llm


@pytest.mark.asyncio
async def test_factory_resolves_anthropic_adapter(monkeypatch):
    """LLM_PROVIDER=anthropic must resolve AnthropicAdapter via the factory."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_API_KEY_ANTHROPIC", "sk-test-key")

    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.llm.factory import LLMProviderFactory
    from app.llm.anthropic_adapter import AnthropicAdapter

    settings = get_settings()
    llm = LLMProviderFactory.from_config(settings)
    assert isinstance(llm, AnthropicAdapter)
