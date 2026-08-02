"""T-150 regression test — scoped query factory must use LLMProviderFactory.

The connection-scoped factory must call
`LLMProviderFactory.from_config(get_settings())` so real adapters can be
resolved without an unscoped fallback service.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_connection_scoped_service_calls_llm_factory(monkeypatch):
    """The connection-scoped service resolves its LLM through the factory."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")

    from app.core.config import get_settings

    get_settings.cache_clear()

    mock_llm = AsyncMock()
    mock_llm.generate_sql.return_value = "SELECT 1 AS id"

    from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus

    connection = MagicMock(
        id="00000000-0000-0000-0000-000000000001",
        database_type=DatabaseType.POSTGRESQL,
        database_name="test_db",
        host="localhost",
        port=5432,
        username="query_user",
        encrypted_password=b"encrypted",
        ssl_mode="prefer",
        lifecycle_state=LifecycleState.ACTIVE,
        health_status=HealthStatus.HEALTHY,
        schema_introspection_status=SchemaIntrospectionStatus.SUCCESS,
    )
    connection_repo = MagicMock()
    connection_repo.get_by_id = AsyncMock(return_value=connection)
    connection_repo.get_schema_entries = AsyncMock(return_value=[])

    with (
        patch("app.api.v1.query.LLMProviderFactory") as mock_factory,
        patch("app.api.v1.query.ConnectionRepository", return_value=connection_repo),
        patch("app.core.credential_provider.FernetCredentialProvider"),
    ):
        mock_factory.from_config.return_value = mock_llm
        from app.api.v1.query import _build_query_service_for_connection

        service = await _build_query_service_for_connection(
            connection_id=connection.id,
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

    from app.llm.anthropic_adapter import AnthropicAdapter
    from app.llm.factory import LLMProviderFactory

    settings = get_settings()
    llm = LLMProviderFactory.from_config(settings)
    assert isinstance(llm, AnthropicAdapter)
