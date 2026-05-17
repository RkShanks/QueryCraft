# Gemini Phase 2/Wave 10 Audit Findings

## Merge recommendation for PR #61
- Merge now / block / conditional: Conditional
- Reason: PR #61 successfully fixes the stale session issue for `submit_question` and `get_me`, but leaves `accept_query` and `regenerate_query` vulnerable to the exact same 500 Foreign Key error since they rely on `user_id` without verifying it against the database. It should be merged, but immediately followed up with the fixes below.

## Critical bugs

- Title: Stale Redis session causes 500 Foreign Key Violation in `accept_query` and `regenerate_query`
- Files/lines: `backend/src/app/services/query_service.py` (`accept_query` and `regenerate_query` methods)
- Real-world trigger: A user is deleted from the `users` table while their Redis session is active. They click "Accept" or "Regenerate" on an existing query result.
- Reproduction steps: 
  1. Login to a session. 
  2. Ask a question to get a result. 
  3. Delete the user from the DB directly (e.g. via admin cleanup). 
  4. Click "Regenerate" or "Accept".
- Actual behavior: The service calls `repo.create` with the deleted `user_uuid`, causing Postgres to throw an `accepted_queries_user_id_fkey` constraint violation, resulting in a 500 Internal Server Error.
- Expected behavior: The service should verify `user_uuid` exists in the DB before inserting, and if missing, clear the Redis session/attempt and return 401 Unauthorized (mirroring the PR #61 fix for `submit_question`).
- Fix recommendation: Add `result = await self._db_session.execute(select(User).where(User.id == user_uuid))` checks to both methods before inserting rows. If missing, delete the active attempt and raise 401.
- Test recommendation: Add `test_accept_query_stale_user_raises_401` and `test_regenerate_query_stale_user_raises_401` unit tests mocking `db_session.execute` to return None for the user.

- Title: `regenerate_query` and `accept_query` silently release unacquired processing locks, breaking session concurrency
- Files/lines: `backend/src/app/services/query_service.py` (line 345 in `accept_query` and line 559 in `regenerate_query`)
- Real-world trigger: A user has multiple tabs open. Tab A submits a new question (acquiring `http_session_id` lock). Tab B simultaneously clicks "Regenerate" on an older active attempt.
- Reproduction steps: 
  1. Initiate a slow `submit_question` in Tab A. 
  2. Immediately trigger `regenerate_query` or `accept_query` in Tab B.
- Actual behavior: Both `regenerate_query` and `accept_query` execute `await self._release_lock(http_session_id)` at the end of their execution, despite NEVER acquiring it. This forcefully deletes the lock key, leaving Tab A's in-progress query unprotected from further concurrent submissions.
- Expected behavior: Methods that don't acquire the coarse processing lock must not release it. Concurrency protection relies on the lock staying alive for the full duration of `submit_question`.
- Fix recommendation: Remove `await self._release_lock(http_session_id)` from `accept_query` and from the `finally` block of `regenerate_query`. They use `active_attempt_id` validation or granular lock keys (`accept:{attempt_id}`), so they shouldn't interfere with the coarse lock.
- Test recommendation: Write an integration or unit test where `submit_question` is mocked to sleep, `regenerate_query` is executed, and then a second `submit_question` is fired. Ensure the second submit gets a 409 Conflict instead of bypassing the lock.

## High bugs

- Title: Unintended duplicate chat history from auto-saving both original and regenerated queries
- Files/lines: `backend/src/app/services/query_service.py`
- Real-world trigger: User submits a query, it succeeds and auto-saves. User immediately clicks "Regenerate".
- Reproduction steps: Submit query -> Regenerate -> Refresh page.
- Actual behavior: `submit_question` auto-saves the original query to `accepted_queries`. `regenerate_query` generates a new query and ALSO auto-saves it to `accepted_queries` without deleting the old one. Both appear in the history.
- Expected behavior: If regenerate is meant to replace the prior bot response, the old row in `accepted_queries` should be deleted when the new one is auto-saved.
- Fix recommendation: In `regenerate_query`, check if the prior attempt was already saved in DB and delete/replace it.
- Test recommendation: Assert total row count for the session is 1 after regenerate.

## Medium bugs

- Title: Useless idempotency check on newly generated UUIDs in `regenerate_query`
- Files/lines: `backend/src/app/services/query_service.py`
- Real-world trigger: None (silent logic flaw).
- Reproduction steps: N/A.
- Actual behavior: The code generates `new_attempt_id = str(uuid.uuid4())` and immediately does `existing = await self._repo.get_by_attempt_id(new_attempt_id, user_uuid)`. This will always be `None`.
- Expected behavior: Idempotency checks should operate on client-provided IDs, not locally generated UUIDs.
- Fix recommendation: Remove the redundant database lookup.
- Test recommendation: None.

## Low/cosmetic
- Evaluator failures during regeneration silently stop the auto-retry loop and return a RefinePrompt instead of attempting the LLM again.
- Hardcoded `ttl=300` in `submit_question` lock could outlive the actual executor timeout if LLM hangs before executor timeout applies.

## Coverage gaps that could hide future Docker/manual bugs
- Gap: Total bypass of SQLAlchemy engine and database constraints in service tests.
- Why current tests miss it: `test_query_service_submit.py` and others mock `db_session.execute` to blindly return MagicMocks based on naive string matching (e.g. `if "FROM users" in stmt_str:`). This means Foreign Key violations, Null Constraint violations, and DB-level Type errors are completely invisible to the test suite. The bug fixed in PR #61 was missed because of this over-mocking.
- Test to add: Implement a real `pytest.mark.integration` test suite using an ephemeral PostgreSQL container (e.g., via Testcontainers) or in-memory SQLite to run `QueryService` methods against a real schema with foreign keys enforced.

## Paste-ready DS fix prompt

```text
Please implement fixes for the Gemini Wave 10.4 audit findings on a new branch `phase-2/wave-10.4-audit-fixes`.

1. In `QueryService.accept_query` and `QueryService.regenerate_query` (backend/src/app/services/query_service.py), add the same user existence check that PR #61 added to `submit_question`. Before calling `self._repo.create()`, verify the user exists in `self._db_session`. If they don't, delete the active Redis session/attempt and raise a 401 Unauthorized HTTP exception.
2. CRITICAL CONCURRENCY FIX: Remove `await self._release_lock(http_session_id)` from `accept_query` (around line 345) and from the `finally` block of `regenerate_query` (around line 559). Neither method acquires the `http_session_id` processing lock (they use `active_attempt` checks or specific lock keys), so releasing it prematurely breaks concurrency protection for `submit_question`.
3. Add unit tests for both fixes: `test_accept_query_stale_user_raises_401` and `test_regenerate_query_stale_user_raises_401` in the appropriate test files.
```
