"""T-712 follow-up regression test.

`_get_query_service` and `_build_query_service_for_connection` must wire
`make_role_policy_provider(db)` so production requests enforce role/connection
policy. The policy_provider_factory hook is an AsyncMock return_value that
the test asserts is passed through to `QueryService(role_policy_provider=...)`.

Without this wiring the production query flow would skip policy enforcement
entirely (only test-injected providers in `tests/unit/test_query_flow_policy.py`
would exercise it), creating a security gap.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_query_service_passes_role_policy_provider(monkeypatch):
    """`_get_query_service` must call `make_role_policy_provider(db)` and pass result to QueryService."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")

    from app.core.config import get_settings

    get_settings.cache_clear()

    mock_provider = AsyncMock(return_value=None)
    mock_db = MagicMock()

    with patch("app.api.v1.query.make_role_policy_provider", return_value=mock_provider) as mock_factory:
        with patch("app.api.v1.query.LLMProviderFactory") as mock_llm_factory:
            mock_llm = AsyncMock()
            mock_llm.generate_sql.return_value = "SELECT 1 AS id"
            mock_llm_factory.from_config.return_value = mock_llm
            with patch("app.api.v1.query._source_introspector.introspect", new_callable=AsyncMock) as mock_intro:
                mock_intro.return_value = None

                from app.api.v1.query import _get_query_service

                service = await _get_query_service(
                    db=mock_db,
                    redis=MagicMock(),
                )

    mock_factory.assert_called_once_with(mock_db)
    assert service._role_policy_provider is mock_provider


@pytest.mark.asyncio
async def test_build_query_service_for_connection_passes_role_policy_provider(monkeypatch):
    """`_build_query_service_for_connection` must call `make_role_policy_provider(db)`."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")

    from app.core.config import get_settings

    get_settings.cache_clear()

    mock_provider = AsyncMock(return_value=None)
    mock_db = MagicMock()

    fake_connection = MagicMock()
    fake_connection.id = "00000000-0000-0000-0000-000000000001"
    fake_connection.dialect = "postgres"
    fake_connection.database_name = "test_db"
    fake_connection.is_enabled = True
    fake_connection.is_healthy = True
    fake_connection.is_introspected = True

    from app.db.models.enums import (
        DatabaseType,
        HealthStatus,
        LifecycleState,
        SchemaIntrospectionStatus,
    )

    fake_connection = MagicMock()
    fake_connection.id = "00000000-0000-0000-0000-000000000001"
    fake_connection.database_type = DatabaseType.POSTGRESQL
    fake_connection.database_name = "test_db"
    fake_connection.host = "localhost"
    fake_connection.port = 5432
    fake_connection.username = "u"
    fake_connection.encrypted_password = b"x"
    fake_connection.ssl_mode = "prefer"
    fake_connection.lifecycle_state = LifecycleState.ACTIVE
    fake_connection.health_status = HealthStatus.HEALTHY
    fake_connection.schema_introspection_status = SchemaIntrospectionStatus.SUCCESS

    fake_conn_repo = MagicMock()
    fake_conn_repo.get_by_id = AsyncMock(return_value=fake_connection)
    fake_conn_repo.get_schema_entries = AsyncMock(return_value=[])

    with patch("app.api.v1.query.make_role_policy_provider", return_value=mock_provider) as mock_factory:
        with patch("app.api.v1.query.LLMProviderFactory") as mock_llm_factory:
            mock_llm = AsyncMock()
            mock_llm.generate_sql.return_value = "SELECT 1 AS id"
            mock_llm_factory.from_config.return_value = mock_llm
            with patch("app.api.v1.query.ConnectionRepository", return_value=fake_conn_repo):
                with patch("app.api.v1.query._source_introspector.introspect", new_callable=AsyncMock) as mock_intro:
                    mock_intro.return_value = None

                    from app.api.v1.query import _build_query_service_for_connection

                    service = await _build_query_service_for_connection(
                        connection_id="00000000-0000-0000-0000-000000000001",
                        db=mock_db,
                        redis=MagicMock(),
                    )

    mock_factory.assert_called_once_with(mock_db)
    assert service._role_policy_provider is mock_provider
