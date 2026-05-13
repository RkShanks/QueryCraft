"""Invariant registry for lifecycle test state leak detection (T-376).

Provides:
- InvariantChecker: abstract base class
- LockInvariant: detects leftover Redis processing_lock keys
- FeedbackStateInvariant: detects unexpected accepted_query feedback mutations
- SessionTouchInvariant: detects unexpected session last_activity_at updates
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.accepted_query import AcceptedQuery
from app.db.models.session import Session


class HasRowId(Protocol):
    id: Any


class HasFeedback(Protocol):
    id: Any
    feedback: int | None
    saved: bool


class HasTouch(Protocol):
    id: Any
    last_activity_at: datetime


class InvariantChecker(ABC):
    """Base class for lifecycle invariants.

    Subclasses implement snapshot() to capture pre-test state and
    validate() to detect leaks between before and after.
    """

    name: str = ""

    @abstractmethod
    async def snapshot(self, state: Any) -> dict[str, Any]:
        """Capture relevant pre-test state. Returns a serializable dict."""
        ...

    @abstractmethod
    async def validate(self, before: dict[str, Any], after: Any) -> list[str]:
        """Compare before/after state. Return list of violation messages."""
        ...


_LOCK_PREFIX = "processing_lock:"


class LockInvariant(InvariantChecker):
    """Detects leftover Redis processing_lock keys after a test.

    Snapshots all Redis keys matching ``processing_lock:*`` before the test.
    After the test, any new matching keys are flagged as leaks.
    """

    name = "LockInvariant"

    def __init__(self, redis: Redis):
        self._redis = redis

    async def snapshot(self, state: Any) -> dict[str, bool]:
        try:
            keys = await self._redis.keys(f"{_LOCK_PREFIX}*")
            return {key: True for key in keys if isinstance(key, str)}
        except Exception:
            return {}

    async def validate(self, before: dict[str, bool], after: Any) -> list[str]:
        try:
            current_keys = await self._redis.keys(f"{_LOCK_PREFIX}*")
            current = {k for k in current_keys if isinstance(k, str)}
        except Exception:
            return []

        before_keys = set(before.keys())
        new_keys = current - before_keys
        return [
            f"{self.name}: unexpected processing_lock key leaked: {key}" for key in sorted(new_keys)
        ]


class FeedbackStateInvariant(InvariantChecker):
    """Detects unexpected mutations to accepted_queries feedback/saved state.

    Allows specific query IDs to be listed as allowed for expected mutations
    (e.g. the test's own feedback update).
    """

    name = "FeedbackStateInvariant"

    def __init__(
        self,
        db_session: AsyncSession,
        allowed_query_ids: set[Any] | None = None,
    ):
        self._db_session = db_session
        self._allowed_ids = {str(qid) for qid in (allowed_query_ids or set())}

    async def snapshot(self, state: Any) -> dict[str, dict[str, Any]]:
        result = await self._db_session.execute(select(AcceptedQuery))
        rows: Sequence[HasFeedback] = result.scalars().all()
        return {
            str(row.id): {"feedback": row.feedback, "saved": row.saved}
            for row in rows
        }

    async def validate(self, before: dict[str, dict[str, Any]], after: Any) -> list[str]:
        result = await self._db_session.execute(select(AcceptedQuery))
        rows: Sequence[HasFeedback] = result.scalars().all()
        after_state = {
            str(row.id): {"feedback": row.feedback, "saved": row.saved}
            for row in rows
        }

        issues: list[str] = []
        for row_id, after_val in after_state.items():
            if row_id in self._allowed_ids:
                continue
            if row_id not in before:
                issues.append(
                    f"{self.name}: new accepted_query row appeared: {row_id} "
                    f"(feedback={after_val['feedback']})"
                )
            elif before[row_id] != after_val:
                issues.append(
                    f"{self.name}: accepted_query {row_id} mutated: "
                    f"before={before[row_id]} after={after_val}"
                )
        return issues


class SessionTouchInvariant(InvariantChecker):
    """Detects unexpected session last_activity_at updates.

    Allows specific session IDs to be listed as allowed for expected
    touches (e.g. the test's own session update).
    """

    name = "SessionTouchInvariant"

    def __init__(
        self,
        db_session: AsyncSession,
        allowed_session_ids: set[Any] | None = None,
    ):
        self._db_session = db_session
        self._allowed_ids = {str(sid) for sid in (allowed_session_ids or set())}

    async def snapshot(self, state: Any) -> dict[str, str]:
        result = await self._db_session.execute(select(Session))
        rows: Sequence[HasTouch] = result.scalars().all()
        return {str(row.id): row.last_activity_at.isoformat() for row in rows}

    async def validate(self, before: dict[str, str], after: Any) -> list[str]:
        result = await self._db_session.execute(select(Session))
        rows: Sequence[HasTouch] = result.scalars().all()
        after_state = {str(row.id): row.last_activity_at.isoformat() for row in rows}

        issues: list[str] = []
        for row_id, after_val in after_state.items():
            if row_id in self._allowed_ids:
                continue
            if row_id not in before:
                issues.append(
                    f"{self.name}: new session row appeared: {row_id} (last_activity_at={after_val})"
                )
            elif before[row_id] != after_val:
                issues.append(
                    f"{self.name}: session {row_id} last_activity_at changed: "
                    f"before={before[row_id]} after={after_val}"
                )
        return issues
