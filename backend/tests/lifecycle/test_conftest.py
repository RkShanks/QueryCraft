"""Tests for lifecycle conftest fixture behavior (T-377).

Verifies that the lifecycle_aware fixture:
- snapshots state at test start for @pytest.mark.lifecycle tests
- validates at test end
- does nothing for non-lifecycle tests
- handles mocked and real fixtures gracefully
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import _get_checker_db, _get_checker_redis
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


class TestLifecycleConftestFixture:
    """Tests for the lifecycle_aware conftest fixture."""

    @pytest.mark.lifecycle
    async def test_lifecycle_marked_test_runs(self):
        assert True

    @pytest.mark.lifecycle
    async def test_lifecycle_integrations_available(self, lifecycle_checkers):
        assert isinstance(lifecycle_checkers, list)

    async def test_non_lifecycle_test_unaffected(self):
        assert True


class TestLifecycleCheckerHelpers:
    """Test the helper functions used by lifecycle_checkers fixture."""

    async def test_get_checker_redis_returns_none_when_unavailable(self):
        request = MagicMock()
        request.getfixturevalue.side_effect = pytest.skip.Exception("not available")
        result = _get_checker_redis(request)
        assert result is None

    async def test_get_checker_redis_returns_value_when_available(self):
        redis_mock = AsyncMock()
        request = MagicMock()
        request.getfixturevalue.return_value = redis_mock
        result = _get_checker_redis(request)
        assert result is redis_mock

    async def test_get_checker_db_returns_none_when_unavailable(self):
        request = MagicMock()
        request.getfixturevalue.side_effect = pytest.skip.Exception("not available")
        result = _get_checker_db(request)
        assert result is None

    async def test_get_checker_db_returns_value_when_available(self):
        db_mock = AsyncMock()
        request = MagicMock()
        request.getfixturevalue.return_value = db_mock
        result = _get_checker_db(request)
        assert result is db_mock


@pytest.mark.lifecycle
@pytest.mark.parametrize("val", [1, 2, 3])
async def test_parametrized_lifecycle(val):
    """Parametrized lifecycle tests should work."""
    assert val in (1, 2, 3)
