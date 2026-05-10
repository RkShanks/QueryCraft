# Wave 5 (US-4) Independent Audit — Gemini Pro 3.1

Audit performed against main HEAD: 241cffe
Audit branch: wave-5-audit-gemini
Auditor: Gemini Pro 3.1 (independent, black-box)
Implementation prompts: NOT shown to auditor.

## Methodology

I performed a static analysis and black-box code review of the Wave 5 (US-4) implementation. I verified the test suite passed locally. I cross-referenced the implementation of `HistoryList.tsx`, `HistoryDetail.tsx`, `useHistory.ts`, `history_service.py`, `query_service.py`, `admin.py`, and `openapi.yaml` against the User Stories (US-4), Functional Requirements (FR-020 to FR-030), and Architectural Invariants defined in the specification and constitution. 

## Findings

### G-001: Concurrent Submission Lock Release Bug
- **Severity**: Critical
- **Surface**: `backend/src/app/services/query_service.py:157`
- **FR / SC / Inv**: Invariant 3 (No Concurrent Submissions)
- **Description**: The `submit_question` method releases the per-session `processing_lock` in a `finally` block before returning the result. This means the lock is only held during the initial LLM generation and execution, but NOT while the attempt is waiting for user acceptance or rejection. A user can submit another question while the first one is pending, generating a new attempt and orphaning the first one, violating Invariant 3 which states the lock should be released on accept, reject, regenerate, or attempt expiry.
- **Reproduction**: Submit a question, wait for the result to appear. Instead of clicking Accept/Reject, open another tab with the same session and submit another question. The backend will accept it and process it concurrently.
- **Suggested fix direction**: Do not release the session lock in the `submit_question` `finally` block. Instead, ensure the lock is set with a TTL matching the attempt expiry and is only explicitly deleted in `accept_query`, `reject_query`, and `regenerate_query` (or allowed to expire via Redis TTL).
- **Confidence**: High

### G-002: History Pagination Timestamp Collision Bug
- **Severity**: High
- **Surface**: `backend/src/app/repositories/accepted_query_repository.py:56`
- **FR / SC / Inv**: FR-021 (Cursor-based Pagination)
- **Description**: The `list_by_user` repository method implements cursor pagination using only the `accepted_at` timestamp: `stmt = stmt.where(AcceptedQuery.accepted_at < cursor_dt)`. If a user accepts multiple queries in the exact same millisecond, the pagination will skip queries sharing that timestamp when moving to the next page, as the strict inequality `<` will discard them.
- **Reproduction**: Insert two `AcceptedQuery` records for the same user with the exact same `accepted_at` timestamp. Set the pagination limit to 1 so the first page ends exactly at this timestamp. Request the next page using the returned cursor; the second query will be completely skipped.
- **Suggested fix direction**: Implement deterministic keyset pagination by including the `id` in the cursor and the where clause, i.e., `WHERE (accepted_at, id) < (cursor_dt, cursor_id)`.
- **Confidence**: High

### G-003: Unhandled ValueError on Invalid UUID in History Detail
- **Severity**: Medium
- **Surface**: `backend/src/app/services/history_service.py:39`
- **FR / SC / Inv**: General API Correctness
- **Description**: The `get_history_entry` endpoint accepts `query_id` as a `str` and passes it to `HistoryService.get_detail`, which calls `UUID(query_id)`. If the client passes a non-UUID string, `UUID()` raises a `ValueError`. Because it is not caught, FastAPI responds with a 500 Internal Server Error instead of a 422 Validation Error or 404 Not Found.
- **Reproduction**: Make a GET request to `/api/v1/history/invalid-uuid-string`. The server will return a 500 error.
- **Suggested fix direction**: Change the type annotation in the endpoint router from `query_id: str` to `query_id: UUID` so FastAPI automatically validates and parses it, or wrap the `UUID(query_id)` call in a try-except block and raise a 404 or 422 `HTTPException`.
- **Confidence**: High

### G-004: Missing Session-Lock Check on Accept Query
- **Severity**: Medium
- **Surface**: `backend/src/app/services/query_service.py:166`
- **FR / SC / Inv**: State Machine Enforcement
- **Description**: `accept_query` operates independently of the session lock. While it implements a distributed lock on the `attempt_id`, it does not check or acquire the session lock. Since `submit_question` prematurely releases the session lock (G-001), a race condition could allow a user to accept an orphaned attempt while a new attempt is generating.
- **Reproduction**: Submit question A. Submit question B concurrently (possible due to G-001). Accept question A while B is still processing.
- **Suggested fix direction**: In addition to fixing G-001, `accept_query` should validate that the attempt being accepted is currently the single active attempt for the session.
- **Confidence**: High

### G-005: Interactive History Rows Lack Keyboard Accessibility
- **Severity**: Medium
- **Surface**: `frontend/src/components/history/HistoryList.tsx:93`
- **FR / SC / Inv**: General A11y
- **Description**: The history list table rows are interactive (`onClick={() => onSelect?.(item.id)}`) but they use a generic `<tr>` element without `tabIndex={0}`, `role="button"`, or keyboard event handlers (e.g. `onKeyDown`). This makes the detail view completely inaccessible to keyboard and screen-reader users.
- **Reproduction**: Load the history page, press the Tab key repeatedly. The focus will skip over the table rows entirely.
- **Suggested fix direction**: Add `tabIndex={0}`, an appropriate ARIA role (or wrap cell content in a `<button>`), and handle the `onKeyDown` event for `Enter` and `Space` keys.
- **Confidence**: High

### G-006: Missing X-Admin-Key Enforcement in schema refresh
- **Severity**: Medium
- **Surface**: `backend/src/app/api/v1/admin.py:48`
- **FR / SC / Inv**: Security
- **Description**: The `/admin/refresh-schema` endpoint allows ANY authenticated user (with a valid `sessionCookie`) to trigger an expensive DB introspection. It only falls back to requiring the `X-Admin-Key` header if the user has no session.
- **Reproduction**: Sign in as a regular user, extract the session cookie, and send a POST to `/api/v1/admin/refresh-schema` without the `X-Admin-Key` header. It will succeed.
- **Suggested fix direction**: Remove the session-check fallback and unconditionally require the `X-Admin-Key` (or perform an explicit RBAC check to ensure the session belongs to an admin).
- **Confidence**: High

### G-007: History Filter References Non-Existent schema Field
- **Severity**: Low
- **Surface**: `frontend/src/components/history/HistoryList.tsx:40`
- **FR / SC / Inv**: FR-022 (Free-text filter)
- **Description**: The frontend history filter logic explicitly checks `(item.schema ?? '').toLowerCase().includes(lower)`. However, the `AcceptedQuerySummary` schema generated from OpenAPI does not contain a `schema` field. This is a type mismatch disguised as a feature.
- **Reproduction**: Load the history page with accepted queries. Type a known schema name into the filter box. It will not match unless the schema name is in the question or SQL.
- **Suggested fix direction**: The backend schema should include the schema name or the frontend filtering should remove the reference to `schema` and restrict filtering to `question_text` and `generated_sql`.
- **Confidence**: High

### G-008: Unnecessary COUNT(*) execution on every initial history load
- **Severity**: Low
- **Surface**: `backend/src/app/services/history_service.py:32`
- **FR / SC / Inv**: Performance
- **Description**: The `list_history` service executes `count_by_user` (`SELECT COUNT(*) FROM accepted_queries WHERE user_id = ...`) every time `cursor is None`, which corresponds to the first page of history. As the user accumulates thousands of queries, this operation will become slow.
- **Reproduction**: Load the history page with a user account that has 500,000 accepted queries. Observe the slow response time due to the `COUNT(*)` scan.
- **Suggested fix direction**: Remove the exact count calculation, and instead rely solely on the `next_cursor` to indicate if there are more pages.
- **Confidence**: High

### G-009: Dead Frontend parameter `schema` in historyApi.ts
- **Severity**: Info
- **Surface**: `frontend/src/api/historyApi.ts:10`
- **FR / SC / Inv**: Code smells
- **Description**: The frontend `useHistory` and `historyApi.ts` accept a `schema` parameter, but they don't actually pass it to the generated `sdkListHistory` function, nor does the OpenAPI spec define a `schema` query parameter. It is a completely dead parameter.
- **Reproduction**: Read `historyApi.ts` and observe `params.schema` is defined but unused in the SDK call.
- **Suggested fix direction**: Remove the `schema` parameter from the frontend code.
- **Confidence**: High

## Summary

| ID | Severity | Surface | Status |
|----|----------|---------|--------|
| G-001 | Critical | `backend/src/app/services/query_service.py` | open |
| G-002 | High | `backend/src/app/repositories/accepted_query_repository.py` | open |
| G-003 | Medium | `backend/src/app/services/history_service.py` | open |
| G-004 | Medium | `backend/src/app/services/query_service.py` | open |
| G-005 | Medium | `frontend/src/components/history/HistoryList.tsx` | open |
| G-006 | Medium | `backend/src/app/api/v1/admin.py` | open |
| G-007 | Low | `frontend/src/components/history/HistoryList.tsx` | open |
| G-008 | Low | `backend/src/app/services/history_service.py` | open |
| G-009 | Info | `frontend/src/api/historyApi.ts` | open |

Total findings: 9
- Critical: 1
- High: 1
- Medium: 4
- Low: 2
- Info: 1
