"""Lifecycle conftest — per-test invariant state leak detection (T-377).

This conftest provides ``lifecycle_checkers`` and ``lifecycle_aware``
fixtures for lifecycle-specific test files. The same fixtures are also
defined in ``tests/conftest.py`` (global scope) for use by migrated tests
outside ``tests/lifecycle/``.
"""
