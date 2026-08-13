"""Configured readiness deadline contract."""

import math

import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize("configured_deadline", [0, -1, float("inf"), float("nan")])
def test_unbounded_readiness_deadline_fails_configuration(configured_deadline):
    with pytest.raises(ValidationError):
        Settings(READINESS_TIMEOUT_SECONDS=configured_deadline)


def test_readiness_deadline_defaults_to_short_finite_value():
    configured_deadline = Settings().READINESS_TIMEOUT_SECONDS

    assert configured_deadline == 2.0
    assert math.isfinite(configured_deadline)
