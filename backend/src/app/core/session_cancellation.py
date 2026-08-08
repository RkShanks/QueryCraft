"""Cross-worker chat-session cancellation and owned query-state cleanup."""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable
from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from redis.asyncio import Redis

from app.core.exceptions import SessionInvalidated

_STATE_TTL_SECONDS = 15 * 60
_local_stage_tasks: dict[tuple[str, str], set[asyncio.Task]] = defaultdict(set)
_local_stage_guard = Lock()

_COMPARE_DELETE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
end
return 0
"""

_DISCARD_ATTEMPT_SCRIPT = """
if redis.call("SISMEMBER", KEYS[1], ARGV[1]) == 0 then
    return 0
end
redis.call("SREM", KEYS[1], ARGV[1])
redis.call("DEL", "attempt:" .. ARGV[2])
if redis.call("GET", "active_attempt:" .. ARGV[3]) == ARGV[2] then
    redis.call("DEL", "active_attempt:" .. ARGV[3])
end
if redis.call("SCARD", KEYS[1]) == 0 then
    redis.call("DEL", KEYS[1])
end
return 1
"""

_TRACK_ATTEMPT_SCRIPT = """
redis.call("SADD", KEYS[1], ARGV[1])
redis.call("EXPIRE", KEYS[1], ARGV[2])
return 1
"""

_CLEAN_CANCELLED_STATE_SCRIPT = """
if redis.call("GET", KEYS[1]) ~= ARGV[1] then
    return 0
end

local function fields(raw)
    local parts = {}
    for part in string.gmatch(raw, "([^|]+)") do
        table.insert(parts, part)
    end
    return parts
end

local operation = redis.call("GET", KEYS[2])
if operation then
    local op = fields(operation)
    if op[1] == ARGV[2] then
        if redis.call("GET", "processing_lock:" .. op[2]) == op[4] then
            redis.call("DEL", "processing_lock:" .. op[2])
        end
        if redis.call("GET", "active_attempt:" .. op[2]) == op[3] then
            redis.call("DEL", "active_attempt:" .. op[2])
        end
        redis.call("DEL", "attempt:" .. op[3])
        redis.call("DEL", KEYS[2])
    end
end

local tracked_attempts = redis.call("SMEMBERS", KEYS[3])
for _, tracked in ipairs(tracked_attempts) do
    local state = fields(tracked)
    if state[1] == ARGV[2] then
        if redis.call("GET", "active_attempt:" .. state[2]) == state[3] then
            redis.call("DEL", "active_attempt:" .. state[2])
        end
        redis.call("DEL", "attempt:" .. state[3])
        redis.call("SREM", KEYS[3], tracked)
    end
end
if redis.call("SCARD", KEYS[3]) == 0 then
    redis.call("DEL", KEYS[3])
end
return 1
"""


@dataclass(frozen=True)
class CancellationMarker:
    session_id: str
    user_id: str
    token: str

    @property
    def redis_value(self) -> str:
        return f"{self.user_id}:{self.token}"


@dataclass(frozen=True)
class QueryOperation:
    session_id: str
    user_id: str
    http_session_id: str
    attempt_id: str
    lock_owner: str
    token: str

    @property
    def redis_value(self) -> str:
        return "|".join((self.user_id, self.http_session_id, self.attempt_id, self.lock_owner, self.token))


@dataclass(frozen=True)
class TrackedAttempt:
    session_id: str
    user_id: str
    http_session_id: str
    attempt_id: str

    @property
    def redis_value(self) -> str:
        return "|".join((self.user_id, self.http_session_id, self.attempt_id))


def _cancellation_key(session_id: str) -> str:
    return f"session_cancelled:{session_id}"


def _operation_key(session_id: str) -> str:
    return f"session_operation:{session_id}"


def _attempt_state_key(session_id: str) -> str:
    return f"session_attempts:{session_id}"


async def mark_session_cancelling(session_id: str, user_id: str, redis: Redis) -> CancellationMarker | None:
    marker = CancellationMarker(session_id, user_id, str(uuid4()))
    created = await redis.set(
        _cancellation_key(session_id),
        marker.redis_value,
        nx=True,
        ex=_STATE_TTL_SECONDS,
    )
    return marker if created else None


async def clear_cancellation_if_owned(marker: CancellationMarker, redis: Redis) -> bool:
    deleted = await redis.eval(
        _COMPARE_DELETE_SCRIPT,
        1,
        _cancellation_key(marker.session_id),
        marker.redis_value,
    )
    return deleted == 1


async def ensure_session_active(session_id: str, redis: Redis) -> None:
    if await redis.get(_cancellation_key(session_id)) is not None:
        raise SessionInvalidated()


async def register_query_operation(operation: QueryOperation, redis: Redis) -> bool:
    created = await redis.set(
        _operation_key(operation.session_id),
        operation.redis_value,
        nx=True,
        ex=_STATE_TTL_SECONDS,
    )
    return bool(created)


async def clear_query_operation_if_owned(operation: QueryOperation, redis: Redis) -> bool:
    deleted = await redis.eval(
        _COMPARE_DELETE_SCRIPT,
        1,
        _operation_key(operation.session_id),
        operation.redis_value,
    )
    return deleted == 1


async def track_session_attempt(attempt: TrackedAttempt, redis: Redis) -> None:
    await redis.eval(
        _TRACK_ATTEMPT_SCRIPT,
        1,
        _attempt_state_key(attempt.session_id),
        attempt.redis_value,
        _STATE_TTL_SECONDS,
    )


async def discard_session_attempt_if_owned(
    attempt: TrackedAttempt,
    redis: Redis,
) -> bool:
    deleted = await redis.eval(
        _DISCARD_ATTEMPT_SCRIPT,
        1,
        _attempt_state_key(attempt.session_id),
        attempt.redis_value,
        attempt.attempt_id,
        attempt.http_session_id,
    )
    return deleted == 1


async def cleanup_cancelled_session_state(
    marker: CancellationMarker,
    redis: Redis,
) -> bool:
    cleaned = await redis.eval(
        _CLEAN_CANCELLED_STATE_SCRIPT,
        3,
        _cancellation_key(marker.session_id),
        _operation_key(marker.session_id),
        _attempt_state_key(marker.session_id),
        marker.redis_value,
        marker.user_id,
    )
    return cleaned == 1


async def run_cancellable_session_stage[StageResult](
    session_id: str,
    user_id: str,
    stage: Awaitable[StageResult],
) -> StageResult:
    task = asyncio.create_task(stage)
    task_key = (session_id, user_id)
    with _local_stage_guard:
        _local_stage_tasks[task_key].add(task)
    try:
        return await task
    finally:
        with _local_stage_guard:
            tasks = _local_stage_tasks.get(task_key)
            if tasks is not None:
                tasks.discard(task)
                if not tasks:
                    _local_stage_tasks.pop(task_key, None)


def cancel_local_session_work(session_id: str, user_id: str) -> int:
    with _local_stage_guard:
        tasks = tuple(_local_stage_tasks.get((session_id, user_id), ()))
    for task in tasks:
        task.cancel()
    return len(tasks)
