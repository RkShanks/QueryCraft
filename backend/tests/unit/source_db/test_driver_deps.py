"""T-418: Verify multi-dialect driver dependencies are importable."""

import pytest


def test_asyncmy_importable() -> None:
    """asyncmy must be importable for MySQL adapter."""
    import asyncmy  # noqa: F401


def test_aioodbc_package_installed() -> None:
    """aioodbc Python package must be installed (ODBC system libs documented separately)."""
    import importlib.metadata

    dist = importlib.metadata.distribution("aioodbc")
    assert dist is not None
