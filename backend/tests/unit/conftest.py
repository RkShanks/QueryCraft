"""Unit-test conftest: shared fixtures for the tests/unit/ suite.

T-845 fix: ``HostileInputDetector.detect`` is now called inside
``QueryService.submit_question`` before the quota check. Existing
QueryService unit tests use a mocked DB session where
``DetectionConfigRepository.get()`` returns a ``MagicMock`` row, causing
``float >= MagicMock`` TypeErrors in the threshold comparison.

The fix is an autouse fixture that stubs ``HostileInputDetector.detect``
to always return an "allowed" ``DetectionOutcome`` for unit tests that
are not exercising detection logic themselves.

The conftest opts out by test module name for the files that exercise
real detector, rule, and registry behaviour.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# Detection test files that need the REAL HostileInputDetector.detect.
# These tests control the outcome themselves via patch.object inside
# the test body, which takes precedence — but we must not apply the
# outer autouse patch for files that test raw rule/detector behaviour.
_DETECTION_TEST_MODULES = {
    "test_hostile_detector",
    "test_detection_registry",
    "test_rule_prompt_injection",
    "test_rule_sql_injection",
    "test_rule_rbac_bypass",
    "test_rule_schema_exposure",
    "test_rule_destructive_sql",
    "test_detection_package_registration",
}


@pytest.fixture(autouse=True)
def _stub_hostile_detector_as_allowed(request: pytest.FixtureRequest):
    """Stub HostileInputDetector.detect → "allowed" for non-detection unit tests.

    Skips the stub for detection-specific test modules (``_DETECTION_TEST_MODULES``)
    so the real detector, rule, and registry logic is exercised there.

    For every other test, this prevents the detection threshold comparison
    (``float >= MagicMock``) from failing in QueryService unit tests that
    supply a mocked DB session.

    Detection-specific tests that want to control the outcome can also call
    ``patch.object(HostileInputDetector, "detect", ...)`` inside their own
    test scope, which takes precedence over this outer fixture anyway.
    """
    module_name = request.module.__name__.split(".")[-1]
    if module_name in _DETECTION_TEST_MODULES:
        # Real detector — do not stub.
        yield
        return

    from app.services.detection.detector import DetectionOutcome

    _allowed = DetectionOutcome(outcome="allowed", results=[], max_confidence=0.0)

    with patch(
        "app.services.detection.detector.HostileInputDetector.detect",
        new=AsyncMock(return_value=_allowed),
    ):
        yield
