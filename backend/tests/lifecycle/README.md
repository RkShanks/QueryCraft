# Lifecycle Invariant Test Framework (FR-048, SC-017)

Detects cross-test state leaks in the backend test suite by observing system
state (Redis keys, database rows) before and after each test.

## Quick start

Add `@pytest.mark.lifecycle` to any test to opt in:

```python
@pytest.mark.lifecycle
async def test_my_feature(db_session, redis_client):
    ...
```

That's it. The `lifecycle_aware` autouse fixture (defined in
`tests/conftest.py`) takes a snapshot before the test body runs and validates
after. No imports needed — the fixture is global.

## Built-in invariants (3 examples)

| Invariant | File | What it detects |
|---|---|---|
| `LockInvariant` | `invariants.py` | Leftover `processing_lock:*` Redis keys |
| `FeedbackStateInvariant` | `invariants.py` | Unexpected `accepted_queries` feedback/saved mutations |
| `SessionTouchInvariant` | `invariants.py` | Unexpected `sessions.last_activity_at` changes |

### LockInvariant

Snapshots all Redis keys matching `processing_lock:*` before the test.
After the test, any new matching keys are flagged as leaks.

**Dependency**: `redis_client` fixture (skipped if Redis unavailable).

### FeedbackStateInvariant

Snapshots all `accepted_queries` feedback and saved columns before the test.
After the test, detects:
- New rows that appeared unexpectedly
- Existing rows whose feedback/saved values changed

Use `allowed_query_ids` to whitelist expected mutations:

```python
from tests.lifecycle.invariants import FeedbackStateInvariant

invariant = FeedbackStateInvariant(db_session, allowed_query_ids={my_row_id})
```

**Dependency**: `db_session` fixture (skipped if PostgreSQL unavailable).

### SessionTouchInvariant

Snapshots all `sessions.last_activity_at` timestamps before the test.
After the test, detects:
- New sessions that appeared unexpectedly
- Existing sessions whose `last_activity_at` changed (unexpected touch)

Use `allowed_session_ids` to whitelist expected touches:

```python
from tests.lifecycle.invariants import SessionTouchInvariant

invariant = SessionTouchInvariant(db_session, allowed_session_ids={my_session_id})
```

**Dependency**: `db_session` fixture (skipped if PostgreSQL unavailable).

## How to add a new invariant

1. Create a class in `tests/lifecycle/invariants.py` that inherits from
   `InvariantChecker`.
2. Set a descriptive `name` class attribute.
3. Implement `async def snapshot(self, state) -> dict` — capture relevant
   pre-test state as a plain dict.
4. Implement `async def validate(self, before, after) -> list[str]` —
   compare snapshot with live state and return violation messages.
5. Register the checker in the `lifecycle_checkers` fixture in
   `tests/conftest.py`. Use `_get_checker_redis` / `_get_checker_db`
   helpers to gracefully handle unavailable services.

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
                           lifecycle_checkers fixture
```

The root `tests/conftest.py` provides two fixtures:

- **`lifecycle_checkers`** — builds a list of `InvariantChecker` instances,
  skipping those whose dependencies (Redis, DB) are unavailable. The
  `@pytest.mark.lifecycle` autouse fixture uses this list.

- **`lifecycle_aware`** (autouse) — checks for the `lifecycle` marker on
  each test. If present, snapshots before and validates after. If absent,
  it is a no-op with negligible overhead.

## When to opt in

Add `@pytest.mark.lifecycle` to tests that:

- Use real Redis (`redis_client` fixture) — the LockInvariant detects
  leftover processing locks.
- Mutate the database (`db_session` fixture) — the FeedbackStateInvariant
  and SessionTouchInvariant detect unintended row changes.
- Are prone to fixture-side effects — lifecycle invariants catch state
  leaks that traditional assertions miss.

Do NOT add `@pytest.mark.lifecycle` to:

- Purely mocked tests with no real Redis or DB interaction (no benefit).
- Tests in the `tests/lifecycle/` directory itself (they test the framework).
