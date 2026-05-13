# Lifecycle Invariant Test Framework (FR-048, SC-017)

Detects cross-test state leaks in the backend test suite by observing system
state (Redis keys, database rows) before and after each test.

## Quick start

Add `@pytest.mark.lifecycle("lock")` to any test that uses a Redis client:

```python
@pytest.mark.lifecycle("lock")
async def test_my_feature(redis_client):
    ...
```

Only the invariants you name are activated. The `lifecycle_aware` autouse
fixture (defined in `tests/conftest.py`) takes a snapshot before the test
body runs and validates after.

### Available invariants

| Marker arg | Invariant | Dependency |
|---|---|---|
| `"lock"` | `LockInvariant` — leftover `processing_lock:*` keys | `redis_client` |
| `"feedback"` | `FeedbackStateInvariant` — unexpected `accepted_queries` mutations | `db_session` |
| `"session"` | `SessionTouchInvariant` — unexpected `sessions.last_activity_at` changes | `db_session` |

Multiple invariants can be combined:

```python
@pytest.mark.lifecycle("lock", "session")
async def test_with_both(redis_client, db_session):
    ...
```

### Tests using mocks

Tests that mock Redis can still opt into the lock invariant by providing a
`lifecycle_lock_checker` fixture override:

```python
class TestMyFeature:
    @pytest.fixture
    def lifecycle_lock_checker(self, mock_redis):
        from tests.lifecycle.invariants import LockInvariant
        return LockInvariant(mock_redis)

    @pytest.mark.lifecycle("lock")
    async def test_my_feature(self, ...):
        ...
```

The same override pattern works for `lifecycle_feedback_checker` and
`lifecycle_session_checker`.

## Built-in invariants (3 examples)

| Invariant | File | What it detects |
|---|---|---|
| `LockInvariant` | `invariants.py` | Leftover `processing_lock:*` Redis keys |
| `FeedbackStateInvariant` | `invariants.py` | Unexpected `accepted_queries` feedback/saved mutations |
| `SessionTouchInvariant` | `invariants.py` | Unexpected `sessions.last_activity_at` changes |

### LockInvariant

Snapshots all keys matching `processing_lock:*` before the test.
After the test, any new keys are flagged as leaks.

### FeedbackStateInvariant

Snapshots all `accepted_queries` feedback and saved columns before the test.
After the test, detects:
- New rows that appeared unexpectedly
- Existing rows whose values changed

Use `allowed_query_ids` to whitelist expected mutations:

```python
invariant = FeedbackStateInvariant(db_session, allowed_query_ids={my_row_id})
```

### SessionTouchInvariant

Snapshots all `sessions.last_activity_at` timestamps before the test.
After the test, detects:
- New sessions that appeared unexpectedly
- Existing sessions whose timestamp changed

Use `allowed_session_ids` to whitelist expected touches:

```python
invariant = SessionTouchInvariant(db_session, allowed_session_ids={my_session_id})
```

## How to add a new invariant

1. Create a class in `tests/lifecycle/invariants.py` inheriting from
   `InvariantChecker`.
2. Set a descriptive `name` class attribute.
3. Implement `async def snapshot(self, state) -> dict`.
4. Implement `async def validate(self, before, after) -> list[str]`.
5. Add a per-checker fixture in `tests/conftest.py` following the
   `lifecycle_<name>_checker` naming convention.
6. Register the marker name → fixture name pair in
   `_INVARIANT_FIXTURE_MAP` in `tests/conftest.py`.

## Framework architecture

```
tests/lifecycle/
  __init__.py              Package marker
  invariants.py            InvariantChecker base + 3 built-in invariants
  conftest.py              Lifecycle-specific conftest
  README.md                This file
  test_invariants.py       Unit tests for invariants
  test_conftest.py         Tests for lifecycle fixture wiring
  test_invariant_detection.py  Validation: leaks detected, clean tests pass

tests/conftest.py          (root) lifecycle_aware autouse fixture +
                           per-checker fixtures (lifecycle_lock_checker,
                           lifecycle_feedback_checker,
                           lifecycle_session_checker)
```

## When to opt in

Add `@pytest.mark.lifecycle(...)` to tests that:

- Use real Redis (`redis_client` fixture) — use `"lock"` to detect leftover
  processing locks.
- Mutate the database (`db_session` fixture) — use `"feedback"` and/or
  `"session"` to detect unintended row changes.
- Mock Redis but want lock invariant — override `lifecycle_lock_checker`
  fixture.

Do NOT add lifecycle markers to:

- Tests in the `tests/lifecycle/` directory itself (they test the framework).

## Exception behavior

If a checker's `snapshot()` or `validate()` method raises an exception, the
exception propagates through `lifecycle_aware` and fails the test with the
checker name and phase. Exceptions are NOT silently swallowed.

If the dependency fixture (`redis_client` / `db_session`) is unavailable,
the checker is silently skipped via `pytest.skip.Exception` handling.
