"""Unit tests for QueryService factory wiring (PR #155 fix).

Verifies that _get_query_service() and _build_query_service_for_connection()
pass a non-None QuotaService to QueryService.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import Redis as AsyncRedis


@pytest.mark.asyncio
async def test_get_query_service_wires_quota_service():
    from app.api.v1.query import _get_query_service

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    mock_redis = AsyncMock(spec=AsyncRedis)

    async def _script(*args, **kwargs):
        return (1, 1, 10)

    mock_redis.register_script.return_value = _script

    with (
        patch("app.api.v1.query._source_introspector") as mock_intro,
        patch("app.api.v1.query.get_settings") as mock_settings,
        patch("app.api.v1.query.make_role_policy_provider") as mock_rpp,
        patch("app.api.v1.query.LLMProviderFactory.from_config") as mock_llm_factory,
    ):
        mock_intro.introspect = AsyncMock(return_value="mock_schema")
        mock_settings.return_value = MagicMock(
            LLM_PROVIDER="test",
            DB_CREDENTIAL_KEY="test-key",
        )
        mock_rpp.return_value = MagicMock()
        mock_llm_factory.return_value = MagicMock()

        service = await _get_query_service(db=mock_db, redis=mock_redis)

    assert service._quota_service is not None


@pytest.mark.asyncio
async def test_build_query_service_for_connection_wires_quota_service():
    from app.api.v1.query import _build_query_service_for_connection

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    mock_redis = AsyncMock(spec=AsyncRedis)

    async def _script(*args, **kwargs):
        return (1, 1, 10)

    mock_redis.register_script.return_value = _script

    conn_id = str(uuid.uuid4())

    with (
        patch("app.api.v1.query.ConnectionRepository") as mock_conn_repo_cls,
        patch("app.api.v1.query.get_settings") as mock_settings,
        patch("app.api.v1.query.make_role_policy_provider") as mock_rpp,
        patch("app.core.credential_provider.FernetCredentialProvider") as mock_fcp,
        patch("app.api.v1.query.LLMProviderFactory.from_config") as mock_llm_factory,
    ):
        mock_repo_instance = AsyncMock()
        mock_conn_repo_cls.return_value = mock_repo_instance

        from app.db.models.enums import HealthStatus, LifecycleState, SchemaIntrospectionStatus

        mock_repo_instance.get_by_id = AsyncMock(
            return_value=MagicMock(
                lifecycle_state=LifecycleState.ACTIVE,
                health_status=HealthStatus.HEALTHY,
                schema_introspection_status=SchemaIntrospectionStatus.SUCCESS,
                database_type="postgresql",
                host="localhost",
                port=5432,
                database_name="test",
                username="user",
                encrypted_password=b"enc",
                ssl_mode="prefer",
            )
        )
        mock_repo_instance.get_schema_entries = AsyncMock(return_value=[])

        mock_settings.return_value = MagicMock(
            LLM_PROVIDER="test",
            DB_CREDENTIAL_KEY="test-key",
        )
        mock_rpp.return_value = MagicMock()
        mock_fcp.return_value = MagicMock(decrypt=MagicMock(return_value="decrypted"))
        mock_llm_factory.return_value = MagicMock()

        service = await _build_query_service_for_connection(
            connection_id=conn_id,
            db=mock_db,
            redis=mock_redis,
        )

    assert service._quota_service is not None
