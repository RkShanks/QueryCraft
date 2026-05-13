"""Validation: intentionally introduced leaks are detected, clean tests pass.

Uses fake/in-memory stores so tests are deterministic and don't pollute
the real test DB/Redis.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.lifecycle.invariants import (
    FeedbackStateInvariant,
    LockInvariant,
    SessionTouchInvariant,
)

# ---------------------------------------------------------------------------
# LockInvariant validation
# ---------------------------------------------------------------------------


class TestLockInvariantDetection:
    """LockInvariant: leak detection and clean-pass validation."""

    @pytest.fixture
    def fake_redis(self):
        """In-memory Redis mock that tracks keys."""
        r = AsyncMock()
        r._keys: set[str] = set()

        async def keys_mock(pattern: str) -> list[str]:
            return [k for k in r._keys if pattern.rstrip("*") in k]

        async def set_mock(key: str, value: str, **kwargs):
            r._keys.add(key)

        async def delete_mock(key: str):
            r._keys.discard(key)

        r.keys.side_effect = keys_mock
        r.set.side_effect = set_mock
        r.delete.side_effect = delete_mock
        return r

    async def test_clean_no_leaks_passes(self, fake_redis):
        """A clean test with no lock keys should pass."""
        invariant = LockInvariant(fake_redis)
        before = await invariant.snapshot(None)
        issues = await invariant.validate(before, None)
        assert issues == []

    async def test_leaked_key_detected(self, fake_redis):
        """Lock left behind after test is detected."""
        invariant = LockInvariant(fake_redis)
        before = await invariant.snapshot(None)
        fake_redis._keys.add("processing_lock:leaked-session")
        issues = await invariant.validate(before, None)
        assert len(issues) == 1
        assert "processing_lock:leaked-session" in issues[0]
        assert "LockInvariant" in issues[0]

    async def test_multiple_leaks_all_reported(self, fake_redis):
        """Multiple leaked keys are all reported."""
        invariant = LockInvariant(fake_redis)
        before = await invariant.snapshot(None)
        fake_redis._keys.update({"processing_lock:a", "processing_lock:b", "processing_lock:c"})
        issues = await invariant.validate(before, None)
        assert len(issues) == 3

    async def test_pre_existing_keys_not_flagged(self, fake_redis):
        """Keys that existed before the test are not flagged."""
        fake_redis._keys.add("processing_lock:pre-existing")
        invariant = LockInvariant(fake_redis)
        before = await invariant.snapshot(None)
        # Validate even with same keys present
        issues = await invariant.validate(before, None)
        assert issues == []

    async def test_leak_and_cleanup_detected(self, fake_redis):
        """Leaked keys cleaned up by test are not flagged."""
        fake_redis._keys.add("processing_lock:sess-1")
        invariant = LockInvariant(fake_redis)
        before = await invariant.snapshot(None)
        fake_redis._keys.discard("processing_lock:sess-1")
        fake_redis._keys.add("processing_lock:sess-2")
        issues = await invariant.validate(before, None)
        assert len(issues) == 1
        assert "sess-2" in issues[0]
        assert "sess-1" not in issues[0]


# ---------------------------------------------------------------------------
# FeedbackStateInvariant validation
# ---------------------------------------------------------------------------


def _make_feedback_row(
    row_id: uuid.UUID | None = None,
    feedback: int | None = 0,
    saved: bool = False,
):
    row = MagicMock()
    row.id = row_id or uuid.uuid4()
    row.feedback = feedback
    row.saved = saved
    return row


class TestFeedbackStateInvariantDetection:
    """FeedbackStateInvariant: leak detection and clean-pass validation."""

    @pytest.fixture
    def fake_db(self):
        """In-memory DB mock that tracks accepted_query rows."""
        db = AsyncMock()
        db._rows: list = []

        class ScalarsResult:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        async def execute_mock(stmt):
            return MagicMock(scalars=MagicMock(return_value=ScalarsResult(db._rows)))

        db.execute.side_effect = execute_mock
        return db

    async def test_clean_no_changes_passes(self, fake_db):
        """No feedback changes should pass validation."""
        row_id = uuid.uuid4()
        fake_db._rows.append(_make_feedback_row(row_id, feedback=1, saved=True))
        invariant = FeedbackStateInvariant(fake_db)
        before = await invariant.snapshot(None)
        issues = await invariant.validate(before, None)
        assert issues == []

    async def test_new_unexpected_row_detected(self, fake_db):
        """New row appearing after snapshot is detected."""
        invariant = FeedbackStateInvariant(fake_db)
        before = await invariant.snapshot(None)
        fake_db._rows.append(_make_feedback_row(feedback=1, saved=True))
        issues = await invariant.validate(before, None)
        assert len(issues) == 1
        assert "new" in issues[0].lower()

    async def test_mutated_row_detected(self, fake_db):
        """Feedback change in existing row is detected."""
        row_id = uuid.uuid4()
        fake_db._rows.append(_make_feedback_row(row_id, feedback=0, saved=False))
        invariant = FeedbackStateInvariant(fake_db)
        before = await invariant.snapshot(None)
        fake_db._rows.clear()
        fake_db._rows.append(_make_feedback_row(row_id, feedback=1, saved=True))
        issues = await invariant.validate(before, None)
        assert len(issues) == 1
        assert "mutated" in issues[0].lower()

    async def test_allowed_mutation_not_flagged(self, fake_db):
        """Mutation in allowed row is not flagged."""
        row_id = uuid.uuid4()
        invariant = FeedbackStateInvariant(fake_db, allowed_query_ids={row_id})
        before = await invariant.snapshot(None)
        fake_db._rows.append(_make_feedback_row(row_id, feedback=1, saved=True))
        issues = await invariant.validate(before, None)
        assert issues == []


# ---------------------------------------------------------------------------
# SessionTouchInvariant validation
# ---------------------------------------------------------------------------


def _make_session_row(
    session_id: uuid.UUID | None = None,
    last_activity_at: datetime | None = None,
):
    row = MagicMock()
    row.id = session_id or uuid.uuid4()
    row.last_activity_at = last_activity_at or datetime.now(UTC)
    return row


class TestSessionTouchInvariantDetection:
    """SessionTouchInvariant: leak detection and clean-pass validation."""

    @pytest.fixture
    def fake_db(self):
        db = AsyncMock()
        db._rows: list = []

        class ScalarsResult:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        async def execute_mock(stmt):
            return MagicMock(scalars=MagicMock(return_value=ScalarsResult(db._rows)))

        db.execute.side_effect = execute_mock
        return db

    async def test_clean_no_changes_passes(self, fake_db):
        """No session changes should pass validation."""
        now = datetime.now(UTC)
        session_id = uuid.uuid4()
        fake_db._rows.append(_make_session_row(session_id, now))
        invariant = SessionTouchInvariant(fake_db)
        before = await invariant.snapshot(None)
        issues = await invariant.validate(before, None)
        assert issues == []

    async def test_new_unexpected_session_detected(self, fake_db):
        """New session appearing after snapshot is detected."""
        invariant = SessionTouchInvariant(fake_db)
        before = await invariant.snapshot(None)
        fake_db._rows.append(_make_session_row())
        issues = await invariant.validate(before, None)
        assert len(issues) == 1
        assert "new" in issues[0].lower()

    async def test_updated_timestamp_detected(self, fake_db):
        """Timestamp change in existing session is detected."""
        session_id = uuid.uuid4()
        old_time = datetime(2025, 1, 1, tzinfo=UTC)
        new_time = datetime(2026, 6, 1, tzinfo=UTC)
        fake_db._rows.append(_make_session_row(session_id, old_time))
        invariant = SessionTouchInvariant(fake_db)
        before = await invariant.snapshot(None)
        fake_db._rows.clear()
        fake_db._rows.append(_make_session_row(session_id, new_time))
        issues = await invariant.validate(before, None)
        assert len(issues) == 1
        assert "changed" in issues[0].lower()

    async def test_allowed_touch_not_flagged(self, fake_db):
        """Touch in allowed session is not flagged."""
        session_id = uuid.uuid4()
        invariant = SessionTouchInvariant(fake_db, allowed_session_ids={session_id})
        before = await invariant.snapshot(None)
        fake_db._rows.append(_make_session_row(session_id))
        issues = await invariant.validate(before, None)
        assert issues == []


# ---------------------------------------------------------------------------
# LockInvariant: regression — leak detection with FakeRedis (mock
# QueryService style, per T-379 audit hardening)
# ---------------------------------------------------------------------------


class TestLockInvariantMockQueryServiceStyle:
    """Regression: LockInvariant detects leaks via FakeRedis, the same
    implementation used by mock-based QueryService lifecycle tests."""

    async def test_leaked_key_in_mock_query_service_style(self):
        """Prove leak detection works with FakeRedis (mock QueryService style).

        This replicates the pattern used by test_query_service_submit.py
        and test_query_service_reject.py where lifecycle_lock_checker
        wraps a FakeRedis instance.
        """
        from tests.lifecycle.helpers import FakeRedis

        redis = FakeRedis()
        invariant = LockInvariant(redis)

        before = await invariant.snapshot(None)

        # Simulate QueryService acquiring a processing lock
        await redis.set("processing_lock:http-sess-1", "1", nx=True, ex=300)

        # Intentionally NOT releasing — this is the leak the checker should catch
        issues = await invariant.validate(before, None)
        assert len(issues) == 1
        assert "processing_lock:http-sess-1" in issues[0]
        assert "LockInvariant" in issues[0]

    async def test_clean_lock_no_leak_regression(self):
        """Prove that a properly released lock is not flagged."""
        from tests.lifecycle.helpers import FakeRedis

        redis = FakeRedis()
        invariant = LockInvariant(redis)

        before = await invariant.snapshot(None)

        # Simulate QueryService acquiring and releasing a lock
        await redis.set("processing_lock:http-sess-1", "1", nx=True, ex=300)
        await redis.delete("processing_lock:http-sess-1")

        issues = await invariant.validate(before, None)
        assert issues == []


# ---------------------------------------------------------------------------
# Cross-invariant: multiple checkers work together
# ---------------------------------------------------------------------------


class TestCombinedDetection:
    """Multiple invariants can be used together without interference."""

    async def test_lock_and_session_together(self):
        """Lock and session invariants can both be active."""
        redis = AsyncMock()
        redis.keys.return_value = []
        lock = LockInvariant(redis)

        db = AsyncMock()
        db._rows: list = []
        scalars_result = MagicMock()
        scalars_result.all.return_value = db._rows
        db.execute.return_value = MagicMock(scalars=MagicMock(return_value=scalars_result))
        session_touch = SessionTouchInvariant(db)

        lock_before = await lock.snapshot(None)
        session_before = await session_touch.snapshot(None)

        lock_issues = await lock.validate(lock_before, None)
        session_issues = await session_touch.validate(session_before, None)

        assert lock_issues == []
        assert session_issues == []
