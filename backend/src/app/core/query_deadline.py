"""Monotonic deadline and derived query-lock lifetime."""

import asyncio
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field

_LOCK_CLEANUP_GRACE_SECONDS = 5


class QueryDeadlineExpired(Exception):
    """Raised when no configured query-operation budget remains."""


def _validated_timeout(timeout_seconds: float) -> float:
    timeout = float(timeout_seconds)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("query timeout must be positive and finite")
    return timeout


def query_lock_ttl_seconds(timeout_seconds: float) -> int:
    """Keep the lock five seconds beyond the operation for bounded cleanup."""
    return math.ceil(_validated_timeout(timeout_seconds)) + _LOCK_CLEANUP_GRACE_SECONDS


@dataclass
class QueryDeadline:
    """One monotonic budget shared by every stage of a query operation."""

    expires_at: float
    clock: Callable[[], float] = field(repr=False)
    _timer: asyncio.TimerHandle | None = field(default=None, init=False, repr=False)
    _cancelled_task: bool = field(default=False, init=False, repr=False)

    @classmethod
    def start(
        cls,
        timeout_seconds: float,
        *,
        clock: Callable[[], float] | None = None,
    ) -> "QueryDeadline":
        monotonic_clock = clock or time.monotonic
        return cls(
            expires_at=monotonic_clock() + _validated_timeout(timeout_seconds),
            clock=monotonic_clock,
        )

    def remaining_seconds(self) -> float:
        remaining = self.expires_at - self.clock()
        if remaining <= 0:
            raise QueryDeadlineExpired()
        return remaining

    def ensure_active(self) -> None:
        self.remaining_seconds()

    def arm_current_task(self) -> None:
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("query deadline requires an asyncio task")
        loop = asyncio.get_running_loop()

        def expire_operation() -> None:
            self._cancelled_task = True
            task.cancel()

        self._timer = loop.call_later(self.remaining_seconds(), expire_operation)

    def disarm(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    @property
    def cancelled_current_task(self) -> bool:
        return self._cancelled_task
