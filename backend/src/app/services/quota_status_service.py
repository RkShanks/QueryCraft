"""Bounded Redis aggregation for administrative quota status."""

import uuid
from dataclasses import dataclass

from redis.asyncio import Redis

from app.db.models.role_quota import RoleQuota
from app.repositories.quota_repository import QuotaRepository

_DIMENSION_LIMITS = (
    ("queries", "daily_query_limit"),
    ("executions", "daily_execution_limit"),
    ("exports", "daily_export_limit"),
)
_REDIS_BATCH_LIMIT = 500


class InvalidQuotaCounterError(ValueError):
    """A stored quota counter is not a canonical non-negative integer."""


@dataclass(frozen=True)
class _CounterTarget:
    key: str
    role_id: uuid.UUID
    dimension: str


class QuotaStatusAggregator:
    """Aggregate one role page with bounded database and Redis work."""

    def __init__(self, repository: QuotaRepository, redis: Redis, date_suffix: str) -> None:
        self._repository = repository
        self._redis = redis
        self._date_suffix = date_suffix

    async def usage_by_role(self, quotas: list[RoleQuota]) -> dict[uuid.UUID, dict[str, int]]:
        usage = {quota.role_id: {dimension: 0 for dimension, _field in _DIMENSION_LIMITS} for quota in quotas}
        limited = {
            quota.role_id: tuple(
                dimension for dimension, field in _DIMENSION_LIMITS if getattr(quota, field) is not None
            )
            for quota in quotas
        }
        limited = {role_id: dimensions for role_id, dimensions in limited.items() if dimensions}
        if not limited:
            return usage
        async for users in self._repository.user_id_batches(set(limited)):
            await self._add_user_batch(usage, limited, users)
        return usage

    async def _add_user_batch(
        self,
        usage: dict[uuid.UUID, dict[str, int]],
        limited: dict[uuid.UUID, tuple[str, ...]],
        users: list[tuple[uuid.UUID, uuid.UUID]],
    ) -> None:
        targets = [
            _CounterTarget(
                key=f"quota:{user_id}:{dimension}:{self._date_suffix}",
                role_id=role_id,
                dimension=dimension,
            )
            for role_id, user_id in users
            for dimension in limited[role_id]
        ]
        for start in range(0, len(targets), _REDIS_BATCH_LIMIT):
            await self._add_counter_batch(usage, targets[start : start + _REDIS_BATCH_LIMIT])

    async def _add_counter_batch(
        self,
        usage: dict[uuid.UUID, dict[str, int]],
        targets: list[_CounterTarget],
    ) -> None:
        values = await self._redis.mget([target.key for target in targets])
        if len(values) != len(targets):
            raise InvalidQuotaCounterError
        for target, raw_value in zip(targets, values, strict=True):
            usage[target.role_id][target.dimension] += _counter_value(raw_value)


def _counter_value(raw_value: str | bytes | None) -> int:
    if raw_value is None:
        return 0
    try:
        text_value = raw_value.decode("ascii") if isinstance(raw_value, bytes) else raw_value
    except UnicodeDecodeError:
        raise InvalidQuotaCounterError from None
    if (
        not isinstance(text_value, str)
        or not text_value.isascii()
        or not text_value.isdigit()
        or (len(text_value) > 1 and text_value.startswith("0"))
    ):
        raise InvalidQuotaCounterError
    try:
        return int(text_value)
    except ValueError:
        raise InvalidQuotaCounterError from None
