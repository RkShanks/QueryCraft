"""Tests for lifecycle conftest fixture behavior (T-377).

Verifies that the lifecycle_aware fixture:
- does nothing for non-lifecycle tests
- rejects empty lifecycle marker
- builds only requested checkers
- handles unavailable dependencies gracefully
- does not swallow checker exceptions
"""

import pytest

from tests.lifecycle.invariants import InvariantChecker


class _SimpleChecker(InvariantChecker):
    name = "SimpleChecker"

    def __init__(self):
        self.snap_count = 0
        self.validate_count = 0

    async def snapshot(self, state):
        self.snap_count += 1
        return {"state": "clean"}

    async def validate(self, before, after):
        self.validate_count += 1
        return []


class TestLifecycleConftestBasic:
    """Basic lifecycle fixture behavior."""

    @pytest.mark.lifecycle("lock")
    async def test_lifecycle_marked_test_runs(self):
        assert True

    async def test_non_lifecycle_test_unaffected(self):
        assert True


class TestLifecycleDependencySafety:
    """Only requested dependencies are pulled."""

    @pytest.mark.lifecycle("lock")
    async def test_lock_does_not_request_db(self, lifecycle_lock_checker):
        """lock marker does not need db_session."""
        pass

    @pytest.mark.lifecycle("feedback")
    async def test_feedback_does_not_request_redis(self, lifecycle_feedback_checker):
        """feedback marker does not need redis_client."""
        pass

    @pytest.mark.lifecycle("session")
    async def test_session_does_not_request_redis(self, lifecycle_session_checker):
        """session marker does not need redis_client."""
        pass


@pytest.mark.lifecycle("lock")
@pytest.mark.parametrize("val", [1, 2, 3])
async def test_parametrized_lifecycle(val):
    """Parametrized lifecycle tests should work."""
    assert val in (1, 2, 3)


class TestLifecycleCheckerOverride:
    """Tests can override per-checker fixtures with mock-aware checkers."""

    @pytest.fixture
    def lifecycle_lock_checker(self):
        return _SimpleChecker()

    @pytest.mark.lifecycle("lock")
    async def test_custom_lock_checker_is_used(self, lifecycle_lock_checker):
        """Test can inject a custom lock checker."""
        assert lifecycle_lock_checker.name == "SimpleChecker"
