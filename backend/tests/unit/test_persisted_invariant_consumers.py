"""Fail-closed consumers for persisted resource and provider invariants."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1 import admin_sso, connections, sso_auth
from app.core.exceptions import QuotaUnavailableError
from app.db.models.sso_provider import SsoProvider
from app.db.models.role_quota import RoleQuota
from app.services.connection_service import ConnectionService
from app.services.quota_service import QuotaService


class _CorruptQuotaRepository:
    def __init__(self, quota: RoleQuota) -> None:
        self._quota = quota

    async def get(self, _role_id: uuid.UUID) -> RoleQuota:
        return self._quota


class _QuotaSideEffectProbe:
    def __init__(self) -> None:
        self.cache_publications = 0
        self.counter_attempts = 0

    def register_script(self, _script):
        async def probe_script(*_args, **_kwargs):
            self.counter_attempts += 1
            return [1, 1, 1]

        return probe_script

    async def get(self, key: str):
        if "transition" in key or key.startswith("quota_config:"):
            return None
        return "0"

    async def set(self, *_args, **_kwargs):
        self.cache_publications += 1


class _CorruptConnectionRepository:
    async def list_user_available(self):
        raise LookupError("persisted source canary")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "quota",
    [
        RoleQuota(role_id=uuid.uuid4(), daily_query_limit=-1),
        RoleQuota(role_id=uuid.uuid4(), daily_execution_limit=-1),
        RoleQuota(role_id=uuid.uuid4(), daily_export_limit=-1),
    ],
    ids=["queries", "executions", "exports"],
)
async def test_corrupt_quota_fails_before_cache_or_counter_side_effects(quota: RoleQuota) -> None:
    side_effects = _QuotaSideEffectProbe()
    service = QuotaService(side_effects, _CorruptQuotaRepository(quota))

    with pytest.raises(QuotaUnavailableError):
        await service.check_and_increment(uuid.uuid4(), quota.role_id, "queries")

    assert side_effects.cache_publications == 0
    assert side_effects.counter_attempts == 0


@pytest.mark.asyncio
async def test_corrupt_source_state_returns_sanitized_unavailable_response(test_env_vars) -> None:
    service = ConnectionService(
        _CorruptConnectionRepository(),
        test_env_vars["DB_CREDENTIAL_KEY"],
    )

    with pytest.raises(HTTPException) as unavailable:
        await connections.list_user_connections(service=service, user_id=str(uuid.uuid4()))

    assert unavailable.value.status_code == 503
    assert unavailable.value.detail == {
        "error": "service_unavailable",
        "message_key": "error.service_unavailable",
    }
    assert "persisted source canary" not in str(unavailable.value.detail)


def _provider_session(provider: SsoProvider):
    provider_rows = MagicMock()
    provider_rows.scalars.return_value.all.return_value = [provider]
    session = MagicMock()
    session.execute = AsyncMock(return_value=provider_rows)
    return session


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "consumer",
    [
        pytest.param(sso_auth.list_providers, id="public-discovery"),
        pytest.param(admin_sso.list_providers, id="admin-list"),
    ],
)
async def test_corrupt_sso_protocol_returns_sanitized_unavailable_response(consumer) -> None:
    session = _provider_session(SsoProvider(protocol="persisted-provider-canary", display_name="Corrupt"))

    with pytest.raises(HTTPException) as unavailable:
        if consumer is admin_sso.list_providers:
            await consumer(_session={}, db=session)
        else:
            await consumer(db=session)

    assert unavailable.value.status_code == 503
    assert unavailable.value.detail == {
        "error": "service_unavailable",
        "message_key": "error.service_unavailable",
    }
    assert "persisted-provider-canary" not in str(unavailable.value.detail)
