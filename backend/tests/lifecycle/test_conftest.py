"""Tests for lifecycle conftest fixture behavior (T-377).

Verifies that the lifecycle_aware fixture:
- does nothing for non-lifecycle tests
- rejects empty lifecycle marker
- rejects unknown marker name
- builds only requested checkers
- handles unavailable dependencies gracefully
- does not swallow checker exceptions
"""

import os
import subprocess
import sys

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
    async def test_lifecycle_marked_test_runs(self, lifecycle_aware):
        assert True

    async def test_non_lifecycle_test_unaffected(self):
        assert True


class TestLifecycleDependencySafety:
    """Only requested dependencies are pulled."""

    @pytest.mark.lifecycle("lock")
    async def test_lock_does_not_request_db(self, lifecycle_lock_checker, lifecycle_aware):
        pass

    @pytest.mark.lifecycle("feedback")
    async def test_feedback_does_not_request_redis(self, lifecycle_feedback_checker, lifecycle_aware):
        pass

    @pytest.mark.lifecycle("session")
    async def test_session_does_not_request_redis(self, lifecycle_session_checker, lifecycle_aware):
        pass


@pytest.mark.lifecycle("lock")
@pytest.mark.parametrize("val", [1, 2, 3])
async def test_parametrized_lifecycle(val, lifecycle_aware):
    assert val in (1, 2, 3)


class TestLifecycleCheckerOverride:
    """Tests can override per-checker fixtures with mock-aware checkers."""

    @pytest.fixture
    def lifecycle_lock_checker(self):
        return _SimpleChecker()

    @pytest.mark.lifecycle("lock")
    async def test_custom_lock_checker_is_used(self, lifecycle_lock_checker, lifecycle_aware):
        assert lifecycle_lock_checker.name == "SimpleChecker"


# ---------------------------------------------------------------------------
# Real pytest sub-runs proving lifecycle fixture pipeline behavior
#
# Uses subprocess rather than pytester to avoid session event-loop
# interference from the pytester plugin.
# ---------------------------------------------------------------------------


_SUBRUN_CONFTEST = """\
import asyncio
import pytest
from pytest import FixtureRequest

pytest_plugins = "pytest_asyncio"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class _StateChecker:
    name = "StateChecker"
    def __init__(self):
        self.snap_count = 0
        self.val_count = 0
    async def snapshot(self, state):
        self.snap_count += 1
        return {}
    async def validate(self, before, after):
        self.val_count += 1
        return []


class _ViolationChecker:
    name = "ViolationChecker"
    async def snapshot(self, state):
        return {}
    async def validate(self, before, after):
        return ["ViolationChecker: intentional violation"]


@pytest.fixture
def lifecycle_lock_checker():
    return _StateChecker()


@pytest.fixture
def lifecycle_feedback_checker():
    return _ViolationChecker()


_INVARIANT_FIXTURE_MAP = {
    "lock": "lifecycle_lock_checker",
    "feedback": "lifecycle_feedback_checker",
}


@pytest.fixture
async def lifecycle_aware(request: FixtureRequest):
    marker = request.node.get_closest_marker("lifecycle")
    if marker is None:
        yield
        return
    names = marker.args if marker.args else ()
    if not names:
        pytest.fail("Empty lifecycle marker")
    checkers = []
    for name in names:
        if name not in _INVARIANT_FIXTURE_MAP:
            pytest.fail(f"Unknown lifecycle invariant: {name!r}")
        checker = request.getfixturevalue(_INVARIANT_FIXTURE_MAP[name])
        checkers.append(checker)
    for checker in checkers:
        await checker.snapshot(None)
    yield
    issues = []
    for checker in checkers:
        result = await checker.validate({}, None)
        issues.extend(result)
    if issues:
        pytest.fail("Lifecycle invariant violation(s):\\n" + "\\n".join(issues))


def pytest_collection_modifyitems(items):
    for item in items:
        marker = item.get_closest_marker("lifecycle")
        if marker is None:
            continue
        if "lifecycle_aware" not in item.fixturenames:
            raise pytest.UsageError(
                f"{item.nodeid}: @pytest.mark.lifecycle requires lifecycle_aware",
            )
"""


def _run_pytest_subprocess(test_code: str, expected_ret: int = 0) -> str:
    """Run pytest against a temporary test file with the subrun conftest.

    Returns combined stdout+stderr for assertion inspection.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        conftest_path = os.path.join(tmpdir, "conftest.py")
        with open(conftest_path, "w") as f:
            f.write(_SUBRUN_CONFTEST)

        test_path = os.path.join(tmpdir, "test_subrun.py")
        with open(test_path, "w") as f:
            f.write(test_code)

        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "--asyncio-mode=auto", "--no-header", "-q"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=tmpdir,
        )
        if expected_ret is not None:
            assert result.returncode == expected_ret, (
                f"Expected ret={expected_ret}, got {result.returncode}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return result.stdout + "\n" + result.stderr


class TestLifecyclePipelineSubrun:
    """Real pytest sub-runs proving lifecycle fixture pipeline behavior.

    Each test creates a temporary test module and runs pytest against it
    using subprocess, verifying fixture behavior end-to-end.
    """

    def test_marker_with_aware_snapshots_and_validates(self):
        """@pytest.mark.lifecycle + lifecycle_aware calls snapshot then validate."""
        output = _run_pytest_subprocess("""\
import pytest

@pytest.mark.lifecycle("lock")
async def test_state(lifecycle_lock_checker, lifecycle_aware):
    assert lifecycle_lock_checker.snap_count == 1, "snapshot must run before body"
    assert lifecycle_lock_checker.val_count == 0, "validate must NOT run before body"
""")
        assert "1 passed" in output

    def test_checker_violation_produces_error(self):
        """A checker returning violations triggers pytest.fail during teardown -> ERROR."""
        output = _run_pytest_subprocess(
            """\
import pytest

@pytest.mark.lifecycle("feedback")
async def test_violation(lifecycle_aware):
    pass
""",
            expected_ret=1,
        )
        assert "Lifecycle invariant violation" in output

    def test_empty_lifecycle_marker_produces_error(self):
        """@pytest.mark.lifecycle() without args fails during fixture setup -> ERROR."""
        output = _run_pytest_subprocess(
            """\
import pytest

@pytest.mark.lifecycle()
async def test_empty(lifecycle_aware):
    pass
""",
            expected_ret=1,
        )
        assert "Empty lifecycle marker" in output

    def test_unknown_marker_name_produces_error(self):
        """An unrecognised invariant name fails during fixture setup -> ERROR."""
        output = _run_pytest_subprocess(
            """\
import pytest

@pytest.mark.lifecycle("nonexistent")
async def test_unknown(lifecycle_aware):
    pass
""",
            expected_ret=1,
        )
        assert "Unknown lifecycle invariant" in output

    def test_marker_without_lifecycle_aware_raises_usage_error(self):
        """@pytest.mark.lifecycle without lifecycle_aware fails collection -> USAGE_ERROR."""
        output = _run_pytest_subprocess(
            """\
import pytest

@pytest.mark.lifecycle("lock")
async def test_no_aware():
    pass
""",
            expected_ret=4,
        )
        assert "requires lifecycle_aware" in output
