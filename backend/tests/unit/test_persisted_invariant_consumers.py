"""Fail-closed consumers for persisted resource and provider invariants."""

from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import QuotaUnavailableError
from app.db.models.role_quota import RoleQuota
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
