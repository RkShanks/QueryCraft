# Opus Phase 2 / Wave 10 Audit Findings

**Auditor**: Opus (Claude 4.6)
**Date**: 2026-05-14
**Repo**: RkShanks/QueryCraft
**Base commit**: `49269fa` (main, post PR #60 merge)
**PR under review**: #61 (`bf060c7` on `phase-2/wave-10.4-auth-session-user-integrity`)

---

## Executive Recommendation

| Question | Answer |
|---|---|
| **Merge PR #61 now?** | **Conditional** — merge after addressing C-01 and H-01 below |
| **Block manual testing?** | No — PR #61 fixes the primary stale-user crash. Remaining issues are edge-case severity |
| **Top 3 risks** | 1. Regenerate path has no stale-user guard (C-01) 2. Session middleware trusts Redis session data without DB validation for all protected endpoints except `/auth/me` and `/query/submit` (H-01) 3. Sidebar undo-delete actually deletes on timer expiry without rollback capability (H-03) |

---

## Critical Findings

### C-01: `regenerate_query` path has no stale-user guard — FK violation on auto-save

- **Severity**: Critical
- **Affected files/lines**: [query_service.py:526–552](file:///home/avril/QueryCraft/backend/src/app/services/query_service.py#L526-L552)
- **Why this can happen in real Docker/manual use**: PR #61 added user-existence checks to `submit_question` (line 103) and `POST /sessions` (sessions.py:46), but **did not add the same check to `regenerate_query`**. The regenerate path resolves `user_uuid` from `prior.user_id` (line 528) and directly calls `self._repo.create(user_id=user_uuid, ...)` at line 539. If the user was deleted from Postgres after the original submit but before a regenerate, this INSERT violates the `accepted_queries.user_id → users.id` FK constraint, causing a 500 `ForeignKeyViolationError`.
- **Reproduction steps**:
  1. Sign in as admin, submit a question (creates accepted_query + ephemeral attempt)
  2. In a separate psql session: `DELETE FROM users WHERE username = 'admin';`
  3. In the browser, click "Regenerate" on the result
  4. Backend crashes with `asyncpg.exceptions.ForeignKeyViolationError`
- **Expected vs actual**:
  - Expected: 401 Unauthorized, stale session cleaned up
  - Actual: 500 Internal Server Error (unhandled FK violation)
- **Minimal fix**: Add the same user-existence guard at the top of `regenerate_query`, before the auto-save block:
  ```python
  # After line 527: user_uuid = uuid.UUID(prior.user_id) if prior.user_id else None
  if user_uuid is not None:
      result_check = await self._db_session.execute(select(User).where(User.id == user_uuid))
      if result_check.scalar_one_or_none() is None:
          raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                              detail={"error": "unauthorized", "message_key": "error.unauthorized"})
  ```
- **Test to add**: `test_regenerate_stale_user_raises_401` — mock `prior.user_id` to a UUID not in the users table, assert 401 not FK violation.

---

### C-02: `accept_query` path has no stale-user guard — FK violation on double-save

- **Severity**: Critical
- **Affected files/lines**: [query_service.py:318–341](file:///home/avril/QueryCraft/backend/src/app/services/query_service.py#L318-L341)
- **Why this can happen in real Docker/manual use**: The `accept_query` method extracts `user_uuid = uuid.UUID(user_id)` at line 318 and then calls `self._repo.create(user_id=user_uuid, ...)` at line 331 if no existing row was found. The `user_id` comes from `session["user_id"]` (via `query.py:141`), which is the **Redis session data**. PR #61 protects `submit_question` and `get_me`, but `accept_query` trusts the Redis session without verifying the user exists in DB. If the user was deleted between submit and accept, this path also crashes with FK violation.
- **Reproduction steps**:
  1. Submit a question (auto-saved, so the idempotency check catches it). But if Redis `attempt:{id}` expired (15 min TTL) and the user re-tries accept from a cached UI, the `get_by_attempt_id` returns None, and the create path is taken.
  2. More realistically: the auto-save at submit time is the normal path now, but `accept_query` still has a code path that creates a new row. If a race condition or Redis failure causes the idempotency check to miss, this FK path is reachable.
- **Expected vs actual**:
  - Expected: 401 Unauthorized
  - Actual: 500 FK violation
- **Minimal fix**: Add user-existence check at the top of `accept_query`, mirroring `submit_question`.
- **Test to add**: `test_accept_stale_user_raises_401`

---

## High Findings

### H-01: Session middleware trusts Redis session data for ALL protected endpoints — no DB validation

- **Severity**: High
- **Affected files/lines**: [security.py:58–96](file:///home/avril/QueryCraft/backend/src/app/core/security.py#L58-L96)
- **Why this can happen in real Docker/manual use**: The `SessionMiddleware.__call__` reads the session cookie, loads session data from Redis, validates the idle timeout, and attaches `request.state.session` with the Redis-stored `user_id`. It **never** checks that `user_id` exists in Postgres. PR #61 added point guards in `get_me` and `submit_question`, but **every other endpoint** — `GET /sessions`, `GET /sessions/:id`, `DELETE /sessions/:id`, `GET /history`, `GET /history/:id`, `DELETE /history/:id`, `PATCH /feedback/:id` — all trust `request.state.session["user_id"]` from Redis without DB validation. If the user is deleted from Postgres, these endpoints will:
  - `GET /sessions`, `GET /history`: Return empty lists (no crash, but misleading — user thinks they have no data when they're actually unauthorized)
  - `DELETE /sessions/:id`: Return 404 (session belongs to deleted user, but the error is wrong — should be 401)
  - `PATCH /feedback/:id`: Return 404 (wrong error)
  - `GET /sessions/:id`: Return 404 (wrong error)
- **Expected behavior**: All these endpoints should return 401 when the user no longer exists in DB, and the stale Redis session should be cleaned up.
- **Minimal fix**: Either:
  - (A) **Move the DB validation into the session middleware** — after loading Redis session, check user exists. This is the cleanest fix (single enforcement point). Add `import select; from app.db.models.user import User` and a DB session to the middleware.
  - (B) Create a shared `require_valid_session` dependency that all protected routes use, which validates the user exists. This avoids adding DB access to the ASGI middleware layer.
- **Test to add**: Integration test that sets up a stale Redis session and verifies each protected endpoint returns 401.

### H-02: `regenerate_query` does NOT acquire the processing lock — concurrent regenerate can corrupt state

- **Severity**: High
- **Affected files/lines**: [query_service.py:376–559](file:///home/avril/QueryCraft/backend/src/app/services/query_service.py#L376-L559)
- **Why this can happen**: `submit_question` acquires the processing lock at line 93, and `regenerate_query` releases it at line 559. But `regenerate_query` **never acquires** the lock — it only checks `active_attempt_id` (line 402). If a user double-clicks "Regenerate" before the first regenerate completes, two concurrent regenerates can run in parallel because neither acquires the lock. Both will read the same `prior` attempt, both will delete it (line 411), and the second `get_attempt` will raise `AttemptNotFound` (unhandled in the try block — it propagates as a 500 or is caught by the `finally` which calls `release_lock`).
- **Expected vs actual**:
  - Expected: Second regenerate returns 409 (concurrent)
  - Actual: Race condition — second call gets `AttemptNotFound` or creates duplicate auto-saved rows
- **Minimal fix**: Add `if not await self._acquire_lock(http_session_id, ttl=300):` at the top of `regenerate_query`, matching `submit_question`.
- **Test to add**: `test_concurrent_regenerate_returns_409`

### H-03: Sidebar undo-delete fires real DELETE after timer but no rollback if API fails

- **Severity**: High
- **Affected files/lines**: [UndoToast.tsx:49–54](file:///home/avril/QueryCraft/frontend/src/components/sidebar/UndoToast.tsx#L49-L54), [Sidebar.tsx:68–88](file:///home/avril/QueryCraft/frontend/src/components/sidebar/Sidebar.tsx#L68-L88)
- **Why this can happen**: When a user clicks delete on a session:
  1. The session is immediately hidden from the sidebar (optimistic removal via `deletingSessionIds`)
  2. A 5-second undo timer starts
  3. After 5 seconds, `deleteMutationRef.current.mutate(item.sessionId)` is called
  4. The toast is removed via `onExpiredRef.current()` **synchronously before the mutation completes**
  5. If the DELETE API call fails (network error, stale session, etc.), **the session is permanently gone from the UI** because the toast is already removed and there's no error recovery
  6. The session still exists on the server, but the user can't see it or undo
- **Additionally**: In React Strict Mode (development), effects run twice. The `useEffect` in `UndoToast` uses `expiredRef.current` to gate the mutation, which correctly prevents double-fire. However, the cleanup function clears timers from the first effect run, meaning the second effect run creates new timers with a fresh `startTime`. This means in StrictMode, the undo timer effectively resets, giving the user ~10 seconds instead of 5. Not a crash, but a UX inconsistency.
- **Expected behavior**: On mutation failure, re-add the session to the visible list. Show an error toast.
- **Minimal fix**: Use `mutateAsync` instead of `mutate` and handle the rejection:
  ```typescript
  deleteMutationRef.current.mutateAsync(item.sessionId).catch(() => {
    // Restore session visibility — call onUndo to re-add
  });
  ```
- **Test to add**: Test that verifies session reappears in sidebar when DELETE API returns 500.

### H-04: `accept_query` creates a SECOND DB session to read `database_connections` — transaction isolation violation

- **Severity**: High
- **Affected files/lines**: [query.py:131–137](file:///home/avril/QueryCraft/backend/src/app/api/v1/query.py#L131-L137)
- **Why this matters**: The `accept_query` route handler opens a **second** `AsyncSession` via `get_async_session_factory()` (line 133–134) just to read the `database_connections` table. This second session is completely independent of the request's DB session used by `QueryService`. This means:
  1. The `database_connections` read is outside the request transaction
  2. The second session is never committed or closed via `async with` properly — it relies on the `async with factory() as db:` context manager, which is correct, but it's still a wasteful extra connection
  3. The `QueryService.submit_question` already reads `database_connections` via `_get_database_connection_id()` using the same session — this is duplicated logic
- **Expected behavior**: Use the injected `db` session from the dependency, or better yet, let `QueryService.accept_query` read the connection ID internally (it already has `_get_database_connection_id`).
- **Minimal fix**: Remove the second session and pass the `database_connection_id` from the service layer, or use the already-injected `db` session.

### H-05: `accepted_queries.user_id` FK has NO `ondelete` action — user deletion orphans rows

- **Severity**: High
- **Affected files/lines**: [accepted_query.py:23](file:///home/avril/QueryCraft/backend/src/app/db/models/accepted_query.py#L23)
- **Why this matters**: The `accepted_queries.user_id` FK constraint lacks `ondelete="CASCADE"` (compare with `sessions.user_id` which HAS `ondelete="CASCADE"` at session.py:24). If an admin user is deleted from Postgres:
  - `sessions` rows cascade-delete ✓
  - `accepted_queries` rows with a `session_id` cascade-delete via the session ✓
  - But `accepted_queries` rows with `session_id=NULL` (possible from Phase 1 legacy data, or if a direct accept was done without a session) will **block the user deletion** with a FK constraint error, OR orphan the rows if the FK is set to SET NULL (which it isn't — it's the default RESTRICT)
- **This means**: `DELETE FROM users WHERE id = :id` will fail with `ForeignKeyViolationError` if there are any `accepted_queries` with `session_id=NULL` for that user. The PR #61 scenario (manually deleting a user) would actually be blocked by this FK in production.
- **Minimal fix**: Add `ondelete="CASCADE"` to the `user_id` FK on `accepted_queries`. This requires a migration.
- **Test to add**: Integration test that deletes a user and verifies all their data cascades.

---

## Medium Findings

### M-01: Admin settings PATCH uses `CAST(:val AS jsonb)` — integer values stored as JSON strings

- **Severity**: Medium
- **Affected files/lines**: [admin.py:115–138](file:///home/avril/QueryCraft/backend/src/app/api/v1/admin.py#L115-L138)
- **Why this matters**: The admin PATCH handler does `CAST(:cap AS jsonb)` where `:cap` is `str(req.llm_context_cap)`. This stores the value as a JSON number (e.g., `3`), which is correct. However, the `_get_llm_context_cap` and `_get_max_regenerate_attempts` methods in `QueryService` do `int(row[0])` where `row[0]` is the JSONB value. JSONB integers are returned as Python `int` by asyncpg, and `int(3)` works. But if someone manually sets the value via SQL to a string like `"3"` (valid JSONB), `int("3")` also works. The risk is low but the round-trip is fragile.
- **Additionally**: The two INSERT statements in the PATCH handler are not atomic beyond the final `db.commit()`. If the second INSERT fails, the first is still committed because `db.commit()` is called only once at the end. However, if the second `execute` raises, the commit is never reached and the transaction rolls back — so this is actually safe by accident. The comment about "partial corruption" in the user's audit scope is not a real risk here.
- **Minimal fix**: Consider wrapping in an explicit `BEGIN`/`COMMIT` (unnecessary — autocommit is off by default in SQLAlchemy async sessions). No action needed.

### M-02: `QueryResult.session_id` is not set on first submit when lazy session creation happens

- **Severity**: Medium
- **Affected files/lines**: [query_service.py:227–238](file:///home/avril/QueryCraft/backend/src/app/services/query_service.py#L227-L238)
- **Why this matters**: In `submit_question`, when `chat_session_id` is `None` (first submit, lazy session creation), a new session is created and `chat_session_id` is updated to the new session's ID (line 116). The `QueryResult` is built at line 227 with `session_id=chat_session_id`, so `session_id` IS correctly set. This is actually fine. However, the frontend relies on `queryResult.session_id` to update the active session (useQuerySubmit.ts:117). If the backend ever returns `session_id=None` (e.g., due to a race condition or error), the frontend would not switch to the new session. This is a theoretical concern, not a current bug.

### M-03: `regenerate_query` auto-save resolves `session_uuid` via prior attempt's saved query — chain breaks if original was deleted

- **Severity**: Medium
- **Affected files/lines**: [query_service.py:528–534](file:///home/avril/QueryCraft/backend/src/app/services/query_service.py#L528-L534)
- **Why this matters**: The regenerate auto-save resolves `session_uuid` by looking up the prior attempt's saved query: `prior_saved = await self._repo.get_by_attempt_id(prior.attempt_id, user_uuid)`. If the user deleted the original accepted_query from the workspace (via the delete button), `prior_saved` will be `None`, and `session_uuid` will be `None`. The regenerated result will be saved as an orphan `accepted_query` with no `session_id`. It won't appear in the session's conversation history.
- **Reproduction**: Submit → delete the result from workspace → click regenerate → new result is saved but not associated with the session.
- **Expected**: Regenerated result should inherit the session from the ephemeral attempt context, not the DB.
- **Minimal fix**: Store `session_id` in the `EphemeralAttempt` model so the regenerate path can resolve it without a DB lookup.

### M-04: `handleDelete` in WorkspacePage optimistically removes but silently swallows API errors

- **Severity**: Medium
- **Affected files/lines**: [WorkspacePage.tsx:104–117](file:///home/avril/QueryCraft/frontend/src/pages/WorkspacePage.tsx#L104-L117)
- **Why this matters**: The `handleDelete` function adds the ID to `deletedSavedIds`, removes from `localTurns`, then calls the API. If the API fails, the `catch` block is empty — the turn is permanently removed from the UI but still exists on the server. On next session reload, it will reappear (confusing the user).
- **Minimal fix**: In the catch block, remove the ID from `deletedSavedIds` and re-add the turn to `localTurns`.

### M-05: No `staleTime` or `refetchOnMount` for session detail — reopened session may show stale data

- **Severity**: Medium
- **Affected files/lines**: [useSessions.ts:17–24](file:///home/avril/QueryCraft/frontend/src/hooks/useSessions.ts#L17-L24)
- **Why this matters**: `useSessionDetail` uses TanStack Query defaults (`staleTime: 5 * 60 * 1000` from QueryProvider). If a user submits queries in Session A, switches to Session B, then switches back to Session A within 5 minutes, the session detail will be served from cache and won't show the new queries. The user must wait 5 minutes or manually refresh.
- **Minimal fix**: Set `staleTime: 0` for `useSessionDetail` so it always refetches on mount.

### M-06: Redis volume is NOT persisted in docker-compose — Redis restarts wipe all sessions and attempts

- **Severity**: Medium
- **Affected files/lines**: [docker-compose.dev.yml:47–57](file:///home/avril/QueryCraft/docker-compose.dev.yml#L47-L57)
- **Why this matters**: The Redis service has no volume mount. If the Redis container restarts (or is rebuilt), all sessions, processing locks, and ephemeral attempts are lost. Users will get 401 on all requests because their session cookies reference non-existent Redis keys. The frontend's `handle401` in `QueryProvider.tsx` will redirect to `/sign-in`, so the user experience is graceful. But any in-progress queries will be lost without error messaging.
- **Minimal fix**: Add `volumes: [redis-data:/data]` and the corresponding volume declaration. For dev this is acceptable as-is, but document the behavior.

---

## Low Findings

- **L-01**: `sign_out` route calls `auth_service.get_me(session_id)` to validate session before deleting it (auth.py:52). With PR #61, `get_me` now does a DB query — this adds latency to sign-out. Could just delete the Redis key directly without validation.
- **L-02**: `EphemeralAttempt.session_id` field name collision — it stores the HTTP session ID (Redis cookie), not the chat session UUID. Confusing naming.
- **L-03**: `ResultTable` component renders `result.rows` directly. If `result_rows` contains very large JSON arrays (e.g., 10k rows), this will freeze the UI. No virtualization.
- **L-04**: `useCurrentUser` in `AuthGuard` uses `retry: false`. If `/auth/me` fails due to a transient network error (not 401), the user is redirected to sign-in. Could use `retry: (failureCount, error) => error.status !== 401` for resilience.
- **L-05**: English and Arabic locale files are complete and symmetric — all keys present in both. ✓
- **L-06**: `sidebar.deleteConfirm` key says "Delete session?" but the UndoToast shows it as the undo message, not a confirmation dialog. The UX is an undo-after-delete pattern, which is correct, but the key name is misleading.
- **L-07**: `max_regenerate_attempts` seed in migration 005 says "default 3 = original + 2 regens" in the comment, but the code semantics are `max_regenerate_attempts = 3` meaning 3 regen clicks after original (total 4 attempts). The comment is wrong. The runtime code at query_service.py:417 (`next_attempt_number > max_regens + 1`) correctly implements "3 regens after original".
- **L-08**: `QueryProvider.tsx` creates a module-level `queryClient` singleton. In test environments, this leaks state between tests unless tests pass a custom `client` prop. The test setup likely handles this, but it's a common footgun.

---

## PR #61 Review Specifically

### What it fixes correctly

1. **`AuthService.get_me`** (auth_service.py:67–93): Now validates that `user_id` from Redis session exists in Postgres via `UserRepository.get_by_id`. Deletes stale Redis session on miss. Returns 401. Returns profile from DB row instead of Redis data. ✓
2. **`QueryService.submit_question`** (query_service.py:102–108): Adds user-existence check before lazy session creation. Returns 401 instead of FK violation. ✓
3. **`POST /sessions`** (sessions.py:44–51): Adds user-existence check before session creation. ✓
4. **`UserRepository.get_by_id`** (user_repository.py:22–25): Clean, correct implementation. ✓
5. **Tests**: Both `test_get_me_stale_session_deletes_key_and_raises_401` and `test_submit_stale_user_raises_401` are meaningful and correctly validate the fix. ✓

### What it misses

| Gap | Severity | Reference |
|---|---|---|
| `regenerate_query` has no user-existence check | Critical | C-01 |
| `accept_query` has no user-existence check | Critical | C-02 |
| Session middleware still trusts Redis for all other endpoints | High | H-01 |
| `accepted_queries.user_id` FK lacks `ondelete=CASCADE` | High | H-05 |
| Regenerate chain loses `session_id` if original deleted | Medium | M-03 |

### Tests missing

1. `test_regenerate_stale_user_raises_401` — regenerate path with deleted user
2. `test_accept_stale_user_raises_401` — accept path with deleted user
3. Integration test: delete a user from Postgres while they have active sessions, verify all endpoints return 401
4. Integration test: verify `DELETE FROM users` cascades to `accepted_queries` (currently blocked by missing CASCADE)

### Merge recommendation

**Conditional merge**: PR #61 fixes the primary crash path (`submit_question` and `get_me`) and is a net improvement. However, the `regenerate_query` gap (C-01) is the same class of bug and should be fixed before or immediately after merge. I recommend:

1. Add the user-existence guard to `regenerate_query` and `accept_query` in the same PR
2. Merge the expanded PR
3. Address H-01 (middleware-level validation) and H-05 (FK CASCADE) in a follow-up hardening PR

---

## Suggested Kimi Fix Prompt

If Critical/High findings exist, provide a paste-ready implementation prompt:

```
Implement the following hardening fixes on branch phase-2/wave-10.5-auth-hardening, based on main (post PR #61 merge).

CRITICAL FIXES (must fix):

1. [C-01] query_service.py — regenerate_query: Add user-existence check.
   After line 528 (user_uuid = uuid.UUID(prior.user_id) if prior.user_id else None),
   add:
     if user_uuid is not None:
         result_check = await self._db_session.execute(select(User).where(User.id == user_uuid))
         if result_check.scalar_one_or_none() is None:
             await self._redis.delete(f"active_attempt:{http_session_id}")
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                 detail={"error": "unauthorized", "message_key": "error.unauthorized"})

2. [C-02] query_service.py — accept_query: Add user-existence check.
   After line 318 (user_uuid = uuid.UUID(user_id)), add the same pattern:
     result_check = await self._db_session.execute(select(User).where(User.id == user_uuid))
     if result_check.scalar_one_or_none() is None:
         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail={"error": "unauthorized", "message_key": "error.unauthorized"})

HIGH FIXES (should fix in same PR):

3. [H-02] query_service.py — regenerate_query: Add processing lock acquisition.
   At the top of regenerate_query (after the active_attempt check at line 402),
   add:
     if not await self._acquire_lock(http_session_id, ttl=300):
         raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                             detail={"error": "concurrent", "message_key": "error.concurrent"})

4. [H-05] Create migration 006_add_cascade_to_accepted_queries_user_id.py:
   - Drop the existing FK constraint on accepted_queries.user_id
   - Re-add with ondelete="CASCADE"
   - Update the ORM model in accepted_query.py to include ondelete="CASCADE"

TESTS (all test-first):

5. test_regenerate_stale_user_raises_401 — mock user lookup to return None,
   verify 401 is raised.
6. test_accept_stale_user_raises_401 — same pattern for accept_query.
7. test_concurrent_regenerate_returns_409 — acquire lock before calling
   regenerate, verify 409.

Follow all AGENTS.md Section 11 constraints. One T-ID per commit triple.
Foundation gates must pass before push.
```

---

## Cross-Reference Summary

| Finding | Affects Submit | Affects Accept | Affects Regenerate | Affects Other Endpoints |
|---|---|---|---|---|
| Stale user guard | ✅ Fixed (PR #61) | ❌ Missing (C-02) | ❌ Missing (C-01) | ❌ Missing (H-01) |
| Processing lock | ✅ Has lock | N/A | ❌ Missing (H-02) | N/A |
| FK CASCADE on user_id | — | — | — | ❌ Missing (H-05) |
| Session invalidation | — | — | — | Only `get_me` cleans up |
