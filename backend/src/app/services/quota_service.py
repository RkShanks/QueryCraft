"""QuotaService — Redis-backed daily quota tracking with atomic check-and-increment.

Uses Redis Lua script for atomic INCR-and-check. Key pattern:
``quota:{user_id}:{dimension}:{YYYY-MM-DD}`` with TTL = seconds until
next midnight UTC.

NULL limit = uncapped (always allows, no Redis increment).
"""

import json
import logging
import math
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import QuotaExceededError, QuotaUnavailableError

if TYPE_CHECKING:
    from app.db.models.role_quota import RoleQuota
    from app.repositories.quota_repository import QuotaRepository

_logger = logging.getLogger(__name__)

_DIMENSION_LIMIT_MAP: dict[str, str] = {
    "queries": "daily_query_limit",
    "executions": "daily_execution_limit",
    "exports": "daily_export_limit",
}
_CONFIG_CACHE_TTL_SECONDS = 60
_CONFIG_CACHE_FIELDS = frozenset((*_DIMENSION_LIMIT_MAP.values(), "revision"))
_CONFIG_CACHE_RETRIES = 3

_BEGIN_CONFIG_TRANSITION_SCRIPT = """
local existing = redis.call('GET', KEYS[3])
if existing then
    return {0, existing}
end

local revision = redis.call('INCR', KEYS[2])
local marker = ARGV[1] .. ':' .. tostring(revision)
redis.call('SET', KEYS[3], marker)
redis.call('DEL', KEYS[1])
return {1, marker}
"""

_PUBLISH_CONFIG_TRANSITION_SCRIPT = """
if redis.call('GET', KEYS[3]) ~= ARGV[1] then
    return 0
end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
redis.call('DEL', KEYS[3])
return 1
"""

_CHECK_SCRIPT = """
if redis.call('GET', KEYS[2]) then
    return redis.error_reply('quota configuration transition pending')
end

local limit = tonumber(ARGV[1])
local requested_ttl = tonumber(ARGV[2])
if not limit or limit < 0 or not requested_ttl or requested_ttl < 1 or requested_ttl > 86400 then
    return redis.error_reply('invalid quota arguments')
end

local current_value = redis.call('GET', KEYS[1])
local current = 0
if current_value then
    current = tonumber(current_value)
    if not current or current < 0 then
        return redis.error_reply('invalid quota counter')
    end
    if redis.call('TTL', KEYS[1]) < 0 then
        redis.call('EXPIRE', KEYS[1], requested_ttl)
    end
end

if current >= limit then
    return {0, current, limit}
end

local used = redis.call('INCR', KEYS[1])
if not current_value then
    redis.call('EXPIRE', KEYS[1], requested_ttl)
end
return {1, used, limit}
"""


def _seconds_until_midnight_utc(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    delta = tomorrow - now
    return math.ceil(delta.total_seconds())


def _today_key_suffix(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m-%d")


def _config_cache_keys(role_id: uuid.UUID) -> tuple[str, str, str]:
    return (
        f"quota_config:{role_id}",
        f"quota_config_revision:{role_id}",
        f"quota_config_transition:{role_id}",
    )


def _parse_check_result(response: object, expected_limit: int) -> tuple[bool, int]:
    if not isinstance(response, (list, tuple)) or len(response) != 3:
        raise ValueError("invalid quota script response shape")
    allowed, used, returned_limit = response
    if allowed not in (0, 1) or isinstance(allowed, bool):
        raise ValueError("invalid quota script decision")
    if isinstance(used, bool) or not isinstance(used, int) or used < 0:
        raise ValueError("invalid quota script usage")
    if isinstance(returned_limit, bool) or not isinstance(returned_limit, int) or returned_limit != expected_limit:
        raise ValueError("invalid quota script limit")
    return allowed == 1, used


@dataclass(frozen=True)
class _QuotaLimits:
    daily_query_limit: int | None
    daily_execution_limit: int | None
    daily_export_limit: int | None

    @classmethod
    def from_record(cls, quota_config: "RoleQuota | None") -> "_QuotaLimits":
        if quota_config is None:
            return cls(None, None, None)
        return cls(
            quota_config.daily_query_limit,
            quota_config.daily_execution_limit,
            quota_config.daily_export_limit,
        )

    def serialize(self, revision: int) -> str:
        cache_payload = {**asdict(self), "revision": revision}
        return json.dumps(cache_payload, separators=(",", ":"), sort_keys=True)

    @classmethod
    def deserialize(cls, payload: str) -> tuple["_QuotaLimits", int]:
        decoded = json.loads(payload)
        if not isinstance(decoded, dict) or set(decoded) != _CONFIG_CACHE_FIELDS:
            raise ValueError("invalid quota cache shape")
        limits = tuple(decoded[field] for field in _DIMENSION_LIMIT_MAP.values())
        for limit in limits:
            if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
                raise ValueError("invalid quota cache limit")
        revision = decoded["revision"]
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise ValueError("invalid quota cache revision")
        return cls(*limits), revision


@dataclass(frozen=True)
class QuotaConfigTransition:
    role_id: uuid.UUID
    token: str
    revision: int
    created: bool

    @property
    def redis_value(self) -> str:
        return f"{self.token}:{self.revision}"

    @classmethod
    def from_redis(
        cls,
        role_id: uuid.UUID,
        marker: str,
        *,
        created: bool,
    ) -> "QuotaConfigTransition":
        token, separator, raw_revision = marker.rpartition(":")
        if not separator or not token:
            raise ValueError("invalid quota transition marker")
        revision = int(raw_revision)
        if revision < 1:
            raise ValueError("invalid quota transition revision")
        return cls(role_id, token, revision, created)


class QuotaService:
    """Checks and increments daily quota counters in Redis.

    Args:
        redis: Async Redis client.
        quota_repo: QuotaRepository for fetching role quota config.
    """

    def __init__(self, redis: Redis, quota_repo: "QuotaRepository") -> None:
        self._redis = redis
        self._quota_repo = quota_repo
        self._check_script = redis.register_script(_CHECK_SCRIPT)

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
        limit_attr = _DIMENSION_LIMIT_MAP.get(dimension)
        if limit_attr is None:
            return (0, None, self._next_midnight())

        quota_limits = await self._quota_limits(role_id)
        limit = getattr(quota_limits, limit_attr)

        if limit is None:
            await self._assert_config_available(role_id)
            return (0, None, self._next_midnight())

        now = datetime.now(UTC)
        date_suffix = _today_key_suffix(now)
        key = f"quota:{user_id}:{dimension}:{date_suffix}"
        ttl = _seconds_until_midnight_utc(now)
        reset_at = self._next_midnight(now)

        try:
            response = await self._check_script(
                keys=[key, _config_cache_keys(role_id)[2]],
                args=[str(limit), str(ttl)],
                client=self._redis,
            )
            allowed, used = _parse_check_result(response, limit)
        except (RedisError, OSError, TypeError, ValueError) as exc:
            raise QuotaUnavailableError() from exc

        if not allowed:
            raise QuotaExceededError(dimension=dimension, reset_at=reset_at.isoformat())

        return (used, limit, reset_at)

    async def _quota_limits(self, role_id: uuid.UUID) -> _QuotaLimits:
        try:
            for _attempt in range(_CONFIG_CACHE_RETRIES):
                revision = await self._cache_revision(role_id)
                cached_limits = await self._stable_cached_limits(role_id, revision)
                if cached_limits is not None:
                    return cached_limits
                repository_limits = await self._cache_repository_limits(
                    role_id,
                    revision,
                )
                if repository_limits is not None:
                    return repository_limits
        except (RedisError, SQLAlchemyError, OSError, TypeError, ValueError) as exc:
            raise QuotaUnavailableError() from exc
        raise QuotaUnavailableError()

    async def _stable_cached_limits(
        self,
        role_id: uuid.UUID,
        expected_revision: int,
    ) -> _QuotaLimits | None:
        cache_key, _revision_key, _transition_key = _config_cache_keys(role_id)
        cached_payload = await self._redis.get(cache_key)
        if cached_payload is None:
            return None
        quota_limits, cached_revision = _QuotaLimits.deserialize(cached_payload)
        if cached_revision != expected_revision:
            return None
        if await self._cache_revision(role_id) != expected_revision:
            return None
        return quota_limits

    async def _cache_repository_limits(
        self,
        role_id: uuid.UUID,
        expected_revision: int,
    ) -> _QuotaLimits | None:
        cache_key, _revision_key, _transition_key = _config_cache_keys(role_id)
        quota_limits = _QuotaLimits.from_record(await self._quota_repo.get(role_id))
        await self._redis.set(
            cache_key,
            quota_limits.serialize(expected_revision),
            ex=_CONFIG_CACHE_TTL_SECONDS,
        )
        if await self._cache_revision(role_id) != expected_revision:
            return None
        return quota_limits

    async def _cache_revision(self, role_id: uuid.UUID) -> int:
        _cache_key, revision_key, transition_key = _config_cache_keys(role_id)
        if await self._redis.get(transition_key) is not None:
            raise ValueError("quota configuration transition pending")
        revision = int(await self._redis.get(revision_key) or 0)
        if revision < 0:
            raise ValueError("invalid quota cache revision")
        return revision

    async def _assert_config_available(self, role_id: uuid.UUID) -> None:
        _cache_key, _revision_key, transition_key = _config_cache_keys(role_id)
        try:
            if await self._redis.get(transition_key) is not None:
                raise QuotaUnavailableError()
        except (RedisError, OSError, TypeError, ValueError) as exc:
            raise QuotaUnavailableError() from exc

    @staticmethod
    async def begin_config_transition(
        redis: Redis,
        role_id: uuid.UUID,
    ) -> QuotaConfigTransition:
        cache_key, revision_key, transition_key = _config_cache_keys(role_id)
        token = uuid.uuid4().hex
        try:
            response = await redis.eval(
                _BEGIN_CONFIG_TRANSITION_SCRIPT,
                3,
                cache_key,
                revision_key,
                transition_key,
                token,
            )
            if not isinstance(response, (list, tuple)) or len(response) != 2:
                raise ValueError("invalid quota transition response")
            created, marker = response
            if created not in (0, 1) or isinstance(created, bool) or not isinstance(marker, str):
                raise ValueError("invalid quota transition response")
            return QuotaConfigTransition.from_redis(
                role_id,
                marker,
                created=created == 1,
            )
        except (RedisError, OSError, TypeError, ValueError) as exc:
            raise QuotaUnavailableError() from exc

    @staticmethod
    async def publish_config_transition(
        redis: Redis,
        transition: QuotaConfigTransition,
        quota_config: "RoleQuota | None",
    ) -> bool:
        cache_key, revision_key, transition_key = _config_cache_keys(transition.role_id)
        quota_limits = _QuotaLimits.from_record(quota_config)
        try:
            published = await redis.eval(
                _PUBLISH_CONFIG_TRANSITION_SCRIPT,
                3,
                cache_key,
                revision_key,
                transition_key,
                transition.redis_value,
                quota_limits.serialize(transition.revision),
                str(_CONFIG_CACHE_TTL_SECONDS),
            )
            if published not in (0, 1) or isinstance(published, bool):
                raise ValueError("invalid quota publication response")
            return published == 1
        except (RedisError, OSError, TypeError, ValueError) as exc:
            raise QuotaUnavailableError() from exc

    @staticmethod
    async def refresh_config_cache(
        redis: Redis,
        role_id: uuid.UUID,
        quota_config: "RoleQuota | None",
    ) -> None:
        transition = await QuotaService.begin_config_transition(redis, role_id)
        if not transition.created:
            raise QuotaUnavailableError()
        if not await QuotaService.publish_config_transition(redis, transition, quota_config):
            raise QuotaUnavailableError()

    @staticmethod
    def _next_midnight(now: datetime | None = None) -> datetime:
        now = now or datetime.now(UTC)
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
