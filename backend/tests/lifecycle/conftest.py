"""Lifecycle-specific conftest — invariant state leak detection (T-377).

Collection-time enforcement:
  Any test decorated with ``@pytest.mark.lifecycle(...)`` MUST also
  request the ``lifecycle_aware`` fixture (or be decorated with
  ``@pytest.mark.usefixtures("lifecycle_aware")``).  Failing that,
  the enforcement hook in ``tests/conftest.py`` raises
  ``pytest.UsageError`` at collection time.

Global fixture definitions (``lifecycle_lock_checker``,
``lifecycle_feedback_checker``, ``lifecycle_session_checker``,
``lifecycle_aware``, and the marker map) live in ``tests/conftest.py``
so they are accessible from any test file under ``tests/``.
This file currently provides no additional fixtures.
"""
