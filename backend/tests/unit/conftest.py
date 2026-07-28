"""Unit-test conftest: shared fixtures for the tests/unit/ suite.

T-845 fix: ``HostileInputDetector.detect`` is now called inside
``QueryService.submit_question`` before the quota check. Existing
QueryService unit tests use a mocked DB session that does not contain
a real detection configuration row.

The fix is an autouse fixture that stubs ``HostileInputDetector.detect``
to always return an "allowed" ``DetectionOutcome`` for unit tests that
are not exercising detection logic themselves.

The conftest opts out by test module name for the files that exercise
real detector, rule, and registry behaviour.

Permission-gate denials also write through a dedicated database transaction.
Unit tests for unrelated routers run without PostgreSQL, so the same autouse
isolation pattern stubs that side effect except in the focused denial-audit
contract module.
"""

from __future__ import annotations

from types import SimpleNamespace
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
    "test_detection_config_repo",
    "test_detection_fail_closed",
    "test_no_raw_hostile_payload",
}

_PERMISSION_AUDIT_TEST_MODULES = {
    "test_permission_denial_audit",
}


@pytest.fixture(autouse=True)
def _stub_hostile_detector_as_allowed(request: pytest.FixtureRequest):
    """Stub HostileInputDetector.detect → "allowed" for non-detection unit tests.

        Skips the stub for detection-specific test modules (``_DETECTION_TEST_MODULES``)
        so the real detector, rule, and registry logic is exercised there.

    For every other test, this supplies valid thresholds and prevents the
    detection step from coupling unrelated QueryService tests to detection
    configuration persistence.

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

    with (
        patch(
            "app.services.detection.detector.HostileInputDetector.detect",
            new=AsyncMock(return_value=_allowed),
        ),
        patch(
            "app.services.query_service.DetectionConfigRepository.get_for_detection",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    block_confidence=0.8,
                    flag_confidence=0.5,
                )
            ),
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def _stub_permission_denial_audit(request: pytest.FixtureRequest):
    """Keep unrelated unit tests independent from the platform database."""
    module_name = request.module.__name__.split(".")[-1]
    if module_name in _PERMISSION_AUDIT_TEST_MODULES:
        yield
        return

    with patch(
        "app.api.dependencies.permissions._audit_access_denied",
        new=AsyncMock(),
    ):
        yield
