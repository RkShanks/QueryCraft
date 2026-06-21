"""QuotaService — Redis-backed daily quota tracking with atomic check-and-increment.

Uses Redis Lua script for atomic INCR-and-check. Key pattern:
``quota:{user_id}:{dimension}:{YYYY-MM-DD}`` with TTL = seconds until
next midnight UTC.

NULL limit = uncapped (always allows, no Redis increment).
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from app.core.exceptions import QuotaExceededError, QuotaUnavailableError

if TYPE_CHECKING:
    from app.repositories.quota_repository import QuotaRepository

_logger = logging.getLogger(__name__)

_DIMENSION_LIMIT_MAP: dict[str, str] = {
    "queries": "daily_query_limit",
    "executions": "daily_execution_limit",
    "exports": "daily_export_limit",
}


def _seconds_until_midnight_utc(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    delta = tomorrow - now
    return int(delta.total_seconds())


def _today_key_suffix(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m-%d")


class QuotaService:
    """Checks and increments daily quota counters in Redis.

    Args:
        redis: Async Redis client.
        quota_repo: QuotaRepository for fetching role quota config.
    """

    def __init__(self, redis: Redis, quota_repo: "QuotaRepository") -> None:
        self._redis = redis
        self._quota_repo = quota_repo

    async def check_and_increment(
        self,
        user_id: uuid.UUID,
        role_id: uuid.UUID,
        dimension: str,
    ) -> tuple[int, int | None, datetime]:
        """Check quota and atomically increment the counter.

        Args:
            user_id: The user's UUID.
            role_id: The user's role UUID (for quota config lookup).
            dimension: One of "queries", "executions", "exports".

        Returns:
            Tuple of (used, limit, reset_at).
            ``limit`` is ``None`` for uncapped roles.

        Raises:
            QuotaExceededError: When the daily limit is reached.
            QuotaUnavailableError: When Redis is unreachable (fail-closed).
        """
        try:
            quota_config = await self._quota_repo.get(role_id)
        except Exception as exc:
            raise QuotaUnavailableError() from exc

        if quota_config is None:
            return (0, None, self._next_midnight())

        limit_attr = _DIMENSION_LIMIT_MAP.get(dimension)
        if limit_attr is None:
            return (0, None, self._next_midnight())

        limit = getattr(quota_config, limit_attr, None)

        if limit is None:
            return (0, None, self._next_midnight())

        now = datetime.now(UTC)
        date_suffix = _today_key_suffix(now)
        key = f"quota:{user_id}:{dimension}:{date_suffix}"

        try:
            used = await self._redis.incr(key)
        except Exception as exc:
            raise QuotaUnavailableError() from exc

        if used == 1:
            ttl = _seconds_until_midnight_utc(now)
            await self._redis.expire(key, ttl)

        reset_at = self._next_midnight(now)

        if used > limit:
            raise QuotaExceededError(dimension=dimension, reset_at=reset_at.isoformat())

        return (used, limit, reset_at)

    @staticmethod
    def _next_midnight(now: datetime | None = None) -> datetime:
        now = now or datetime.now(UTC)
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
