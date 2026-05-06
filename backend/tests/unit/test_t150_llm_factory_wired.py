"""T-150 regression test — Query router must use LLMProviderFactory.

Currently `_get_query_service` hardcodes `llm=StubLLM()`. After the fix,
it must call `LLMProviderFactory.from_config(get_settings())` so real
adapters can be resolved.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def app_client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_submit_uses_llm_provider_factory(app_client, monkeypatch):
    """The router must call LLMProviderFactory.from_config instead of hardcoding StubLLM."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")

    from app.core.config import get_settings

    get_settings.cache_clear()

    mock_llm = AsyncMock()
    mock_llm.generate_sql.return_value = "SELECT 1 AS id"

    with patch("app.api.v1.query.LLMProviderFactory") as mock_factory:
        mock_factory.from_config.return_value = mock_llm
        # Also mock the evaluator and executor so we don't need source DB
        with patch("app.api.v1.query.Evaluator") as mock_eval_cls, \
             patch("app.api.v1.query.SourceDBExecutor") as mock_exec_cls:
            mock_eval = AsyncMock()
            mock_eval.evaluate.return_value = MagicMock(passed=True, violations=[])
            mock_eval_cls.return_value = mock_eval
            mock_exec = AsyncMock()
            mock_exec.execute.return_value = ([{"name": "id", "type": "integer"}], [[1]])
            mock_exec_cls.return_value = mock_exec

            response = await app_client.post(
                "/api/v1/query/submit",
                json={"question": "Show me something"},
                headers={"origin": "http://test"},
            )

    mock_factory.from_config.assert_called_once()
    # The resolved LLM should have been used for generation
    mock_llm.generate_sql.assert_awaited_once()


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
