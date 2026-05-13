"""Tests for InvariantChecker base class and built-in invariants (T-376)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.lifecycle.invariants import (
    FeedbackStateInvariant,
    InvariantChecker,
    LockInvariant,
    SessionTouchInvariant,
)


def _mock_session_scalars(rows: list) -> AsyncMock:
    """Configure an AsyncMock db_session so execute -> scalars -> all returns rows."""
    db = AsyncMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = rows
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    db.execute.return_value = execute_result
    return db


class TestInvariantCheckerInterface:
    """InvariantChecker must expose snapshot and validate async methods."""

    async def test_snapshot_and_validate_defined(self):
        class ConcreteChecker(InvariantChecker):
            async def snapshot(self, state):
                return {"snapped": True}

            async def validate(self, before, after):
                return []

        checker = ConcreteChecker()
        state = await checker.snapshot(None)
        assert state == {"snapped": True}
        issues = await checker.validate(state, state)
        assert issues == []

    async def test_name_property(self):
        class NamedChecker(InvariantChecker):
            name = "my_custom_checker"

            async def snapshot(self, state):
                return {}

            async def validate(self, before, after):
                return []

        checker = NamedChecker()
        assert checker.name == "my_custom_checker"


class TestLockInvariant:
    """LockInvariant detects leftover Redis processing_lock keys."""

    async def test_snapshot_captures_lock_keys(self):
        redis = AsyncMock()
        redis.keys.return_value = ["processing_lock:sess-1", "processing_lock:sess-2"]
        invariant = LockInvariant(redis)
        state = await invariant.snapshot(None)
        assert "processing_lock:sess-1" in state
        assert "processing_lock:sess-2" in state
        assert len(state) == 2

    async def test_validate_no_leaks(self):
        redis = AsyncMock()
        redis.keys.return_value = ["processing_lock:sess-1"]
        invariant = LockInvariant(redis)
        before = {"processing_lock:sess-1": True}
        issues = await invariant.validate(before, None)
        assert issues == []

    async def test_validate_detects_new_lock_key(self):
        redis = AsyncMock()
        redis.keys.return_value = ["processing_lock:sess-1", "processing_lock:sess-2"]
        invariant = LockInvariant(redis)
        before = {"processing_lock:sess-1": True}
        issues = await invariant.validate(before, None)
        assert len(issues) == 1
        assert "processing_lock:sess-2" in issues[0]
        assert "LockInvariant" in issues[0]

    async def test_validate_ignores_expected_keys_removed(self):
        redis = AsyncMock()
        redis.keys.return_value = []
        invariant = LockInvariant(redis)
        before = {"processing_lock:sess-1": True}
        issues = await invariant.validate(before, None)
        assert issues == []

    async def test_snapshot_returns_dict_when_redis_fails(self):
        redis = AsyncMock()
        redis.keys.side_effect = Exception("Redis down")
        invariant = LockInvariant(redis)
        state = await invariant.snapshot(None)
        assert state == {}

    async def test_validate_handles_empty_before(self):
        redis = AsyncMock()
        redis.keys.return_value = ["processing_lock:sess-1"]
        invariant = LockInvariant(redis)
        issues = await invariant.validate({}, None)
        assert len(issues) == 1


class TestFeedbackStateInvariant:
    """FeedbackStateInvariant detects unexpected feedback mutations."""

    @pytest.fixture
    def mock_db_session(self, request):
        return _mock_session_scalars(request.param if hasattr(request, "param") else [])

    async def test_snapshot_captures_feedback_state(self):
        rows = [
            MagicMock(id=uuid.uuid4(), feedback=1, saved=True),
            MagicMock(id=uuid.uuid4(), feedback=-1, saved=False),
        ]
        db = _mock_session_scalars(rows)
        invariant = FeedbackStateInvariant(db)
        state = await invariant.snapshot(None)
        assert len(state) == 2

    async def test_validate_detects_new_row(self):
        after_rows = [
            MagicMock(id=uuid.uuid4(), feedback=1, saved=True),
        ]
        db = _mock_session_scalars(after_rows)
        invariant = FeedbackStateInvariant(db)
        before = {}
        issues = await invariant.validate(before, None)
        assert len(issues) == 1
        assert "FeedbackStateInvariant" in issues[0]
        assert "new" in issues[0].lower()

    async def test_validate_detects_mutated_row(self):
        row_id = uuid.uuid4()
        after_rows = [
            MagicMock(id=row_id, feedback=-1, saved=False),
        ]
        db = _mock_session_scalars(after_rows)
        invariant = FeedbackStateInvariant(db)
        before = {str(row_id): {"feedback": 1, "saved": True}}
        issues = await invariant.validate(before, None)
        assert len(issues) == 1
        assert "FeedbackStateInvariant" in issues[0]

    async def test_validate_allows_expected_changes(self):
        row_id = uuid.uuid4()
        after_rows = [
            MagicMock(id=row_id, feedback=1, saved=True),
        ]
        db = _mock_session_scalars(after_rows)
        invariant = FeedbackStateInvariant(db, allowed_query_ids={row_id})
        before = {}
        issues = await invariant.validate(before, None)
        assert issues == []

    async def test_validate_snapshot_tuple_pass(self):
        row_id = uuid.uuid4()
        after_rows = [
            MagicMock(id=row_id, feedback=1, saved=True),
        ]
        db = _mock_session_scalars(after_rows)
        invariant = FeedbackStateInvariant(db, allowed_query_ids={row_id})
        before = {str(row_id): {"feedback": 1, "saved": True}}
        issues = await invariant.validate(before, None)
        assert issues == []


class TestSessionTouchInvariant:
    """SessionTouchInvariant detects unexpected session activity updates."""

    @pytest.fixture
    def mock_db_session(self, request):
        return _mock_session_scalars(request.param if hasattr(request, "param") else [])

    async def test_snapshot_captures_last_activity(self):
        now = datetime.now(timezone.utc)
        rows = [MagicMock(id=uuid.uuid4(), last_activity_at=now)]
        db = _mock_session_scalars(rows)
        invariant = SessionTouchInvariant(db)
        state = await invariant.snapshot(None)
        assert len(state) == 1

    async def test_validate_detects_updated_activity(self):
        session_id = uuid.uuid4()
        new_time = datetime(2025, 6, 1, tzinfo=timezone.utc)
        old_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        rows = [MagicMock(id=session_id, last_activity_at=new_time)]
        db = _mock_session_scalars(rows)
        invariant = SessionTouchInvariant(db)
        before = {str(session_id): old_time.isoformat()}
        issues = await invariant.validate(before, None)
        assert len(issues) == 1
        assert "SessionTouchInvariant" in issues[0]

    async def test_validate_allows_expected_touches(self):
        session_id = uuid.uuid4()
        new_time = datetime(2025, 6, 1, tzinfo=timezone.utc)
        rows = [MagicMock(id=session_id, last_activity_at=new_time)]
        db = _mock_session_scalars(rows)
        invariant = SessionTouchInvariant(db, allowed_session_ids={session_id})
        before = {}
        issues = await invariant.validate(before, None)
        assert issues == []

    async def test_validate_detects_new_session(self):
        session_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        rows = [MagicMock(id=session_id, last_activity_at=now)]
        db = _mock_session_scalars(rows)
        invariant = SessionTouchInvariant(db)
        before = {}
        issues = await invariant.validate(before, None)
        assert len(issues) == 1
        assert "new" in issues[0].lower()

    async def test_validate_no_changes(self):
        session_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        rows = [MagicMock(id=session_id, last_activity_at=now)]
        db = _mock_session_scalars(rows)
        invariant = SessionTouchInvariant(db)
        before = {str(session_id): now.isoformat()}
        issues = await invariant.validate(before, None)
        assert issues == []
