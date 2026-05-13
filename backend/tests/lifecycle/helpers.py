"""Shared test helpers for lifecycle invariant tests (T-376, T-379 hardening).

Provides:
- FakeRedis: in-memory async Redis fake with set/get/delete/keys
- make_fake_db_session: configurable AsyncSession fake for invariants
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock


class FakeRedis:
    """In-memory fake for ``redis.asyncio.Redis`` geared toward lifecycle tests.

    Tracks string keys in ``self._data``.  The ``keys()`` method implements
    ``processing_lock:*`` matching; other glob patterns fall back to naive
    suffix matching.
    """

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool | None:
        if nx and key in self._data:
            return None
        self._data[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def delete(self, key: str) -> int:
        return 1 if self._data.pop(key, None) is not None else 0

    async def keys(self, pattern: str) -> list[str]:
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in self._data if k.startswith(prefix)]
        return [k for k in self._data if k == pattern]

    async def flushdb(self) -> None:
        self._data.clear()

    async def aclose(self) -> None:
        pass


def make_fake_db_session(rows: list | None = None) -> AsyncMock:
    """Build an ``AsyncMock`` that returns the given ORM rows via execute→scalars→all."""
    rows = rows or []
    db = AsyncMock()

    class ScalarsResult:
        def __init__(self, rows: list) -> None:
            self._rows = rows

        def all(self) -> list:
            return self._rows

    async def execute_mock(_stmt: Any) -> MagicMock:
        return MagicMock(scalars=MagicMock(return_value=ScalarsResult(db._rows)))  # noqa: WPS529

    db._rows = rows  # type: ignore[attr-defined]
    db.execute.side_effect = execute_mock
    return db
