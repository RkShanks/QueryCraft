# Wave 5 (US-4) Independent Audit — Opus 4.6

Audit performed against main HEAD: `241cffe`
Audit branch: `wave-5-audit-opus`
Auditor: Opus 4.6 (independent, black-box)
Implementation prompts: NOT shown to auditor.
Gemini findings: NOT read (cross-contamination protection).

## Methodology

1. **Pre-flight**: Fetched `main`, created audit branch, installed all dependencies, and verified all quality gates pass (280 backend unit tests, 105 frontend unit tests, lint, typecheck — all green).
2. **Spec grounding**: Read US-4 acceptance scenarios, FR-020 through FR-023, SC-006/SC-007/SC-009/SC-012, and all six architectural invariants from the constitution.
3. **Backend audit**: Read every line of `history.py` (router), `history_service.py`, `accepted_query_repository.py`, `accepted_query.py` (model), `attempt_store.py`, `query_service.py` (accept/reject/regenerate), `query.py` (router), `unsafe_pattern.py`, `security.py` (session middleware), and the OpenAPI contract. Examined all migration files and schema definitions.
4. **Frontend audit**: Read every line of `useHistory.ts`, `historyApi.ts`, `HistoryList.tsx`, `HistoryDetail.tsx`, `HistoryPage.tsx`, all unit/integration tests, E2E tests, and both locale files (`en.json`, `ar.json`).
5. **Contract audit**: Compared OpenAPI schema definitions against Pydantic models and generated TypeScript types for drift.
6. **Test audit**: Reviewed all test files for coverage gaps, misleading assertions, and mock fidelity.
7. **Cross-cutting**: Checked i18n coverage, RTL/LTR compliance, accessibility attributes, and database indexes.

## Findings

### O-001: Regenerated attempt stored with wrong state — accept after regenerate is broken
- **Severity**: Critical
- **Surface**: `backend/src/app/services/query_service.py:365`
- **FR / SC / Inv**: FR-016, FR-019 (accept after regenerate)
- **Description**: In `regenerate_query()`, after successfully executing SQL against the source DB, the new ephemeral attempt is stored with `state="PENDING"` (line 365). However, `accept_query()` at line 191 requires `state == "EXECUTED"` to proceed. This means any user who regenerates a query and then tries to accept the result will receive a 422 error (`attempt_state_invalid`). The accept-after-regenerate flow is completely broken.
- **Reproduction**: 
  1. Submit a question → receive result (attempt stored as EXECUTED).
  2. Reject the result → triggers `regenerate_query` → new result is displayed.
  3. Click Accept on the regenerated result → 422 `attempt_state_invalid`.
  The bug can also be confirmed by reading lines 358-372 of `query_service.py` where `state="PENDING"` is hardcoded, versus the `submit_question` flow where line 128 correctly sets `state="EXECUTED"`.
- **Suggested fix direction**: Change `state="PENDING"` to `state="EXECUTED"` on line 365 of `query_service.py`, matching the pattern used in `submit_question()`. Add a unit test that regenerates, then accepts, and asserts 201.
- **Confidence**: High

---

### O-002: `limit` query parameter has no upper bound validation — DoS vector
- **Severity**: High
- **Surface**: `backend/src/app/api/v1/history.py:22`
- **FR / SC / Inv**: SC-006 (performance)
- **Description**: The `limit` parameter on `GET /history` is declared as `limit: int = 100` with no upper bound. The OpenAPI contract specifies `maximum: 1000`, but FastAPI does not enforce OpenAPI constraints on query parameters — it only uses the Python type hint. A client can pass `limit=999999999`, causing the repository to execute `SELECT ... LIMIT 1000000000` and attempt to load the entire history into memory. This is both a DoS vector (memory exhaustion) and a performance violation of SC-006's 3-second target.
- **Reproduction**: `curl -b session_cookie '/api/v1/history?limit=99999999'` — the query will attempt to fetch all rows.
- **Suggested fix direction**: Add `Query(le=1000, ge=1)` annotation to the `limit` parameter in the router, matching the OpenAPI constraint. This ensures server-side validation regardless of client behavior.
- **Confidence**: High

---

### O-003: Cursor pagination skips items when multiple queries share the same `accepted_at` timestamp
- **Severity**: High
- **Surface**: `backend/src/app/repositories/accepted_query_repository.py:47-66`
- **FR / SC / Inv**: FR-021 (history list)
- **Description**: The cursor is encoded as an ISO timestamp (`accepted_at.isoformat()`), and pagination uses `WHERE accepted_at < cursor_dt`. The ORDER BY includes `desc(AcceptedQuery.id)` as a tiebreaker, but the cursor filter only uses `accepted_at`. If two queries have the same `accepted_at` timestamp (possible with rapid consecutive accepts or timestamp-truncated databases), the pagination will either skip or duplicate items when crossing a page boundary at that timestamp. The cursor should be a composite of `(accepted_at, id)` to be stable.
- **Reproduction**: Insert two accepted queries with identical `accepted_at` values. Request page 1 with `limit=1`. The cursor will be the shared timestamp. Page 2 with that cursor will filter out BOTH items (since both have `accepted_at == cursor_dt`, and the filter is strict `<`), returning an empty page.
- **Suggested fix direction**: Use a composite cursor encoding both `accepted_at` and `id`, and adjust the WHERE clause to use `(accepted_at, id) < (cursor_at, cursor_id)` keyset pagination.
- **Confidence**: High

---

### O-004: Invalid cursor silently ignored — no error returned for malformed pagination token
- **Severity**: Medium
- **Surface**: `backend/src/app/repositories/accepted_query_repository.py:54-58`
- **FR / SC / Inv**: FR-021
- **Description**: When the `cursor` parameter fails ISO timestamp parsing (`except ValueError: pass`), the cursor filter is silently skipped, causing the query to return the **first** page again instead of returning an error. This is a correctness bug: the client believes it's fetching page N but receives page 1. It also masks client-side bugs that would otherwise surface as errors.
- **Reproduction**: `GET /history?cursor=not-a-timestamp` → returns page 1 instead of an error.
- **Suggested fix direction**: Raise a 400 Bad Request with a descriptive error when the cursor cannot be parsed, rather than silently ignoring it.
- **Confidence**: High

---

### O-005: `query_id` path parameter not validated as UUID — unhandled ValueError on malformed IDs
- **Severity**: Medium
- **Surface**: `backend/src/app/services/history_service.py:39`, `backend/src/app/api/v1/history.py:42`
- **FR / SC / Inv**: FR-023
- **Description**: The `GET /history/{query_id}` endpoint accepts `query_id: str` and passes it to `history_service.get_detail()`, which calls `UUID(query_id)`. If `query_id` is not a valid UUID, `UUID()` raises `ValueError`, which FastAPI catches and returns as an unstructured 500 Internal Server Error. The OpenAPI contract specifies `format: uuid` on this parameter, but FastAPI's `Path()` doesn't validate format. This leaks an internal error trace.
- **Reproduction**: `GET /history/not-a-uuid` → 500 with ValueError traceback (or FastAPI's default 500 response).
- **Suggested fix direction**: Wrap the `UUID(query_id)` call in a try/except ValueError, returning 400 or 404 with a structured error response. Alternatively, change the path parameter type to `uuid.UUID` so FastAPI validates it automatically.
- **Confidence**: High

---

### O-006: Hardcoded `text-left` CSS classes violate FR-025 (RTL directional properties)
- **Severity**: Medium
- **Surface**: `frontend/src/components/history/HistoryList.tsx:77-87`
- **FR / SC / Inv**: FR-025, SC-010, Constitution Principle VI
- **Description**: Four `<th>` elements in the history table use `text-left` class (Tailwind utility for `text-align: left`). FR-025 mandates that all directional CSS use logical equivalents (`inline-start` / `inline-end`). When the UI is switched to Arabic (RTL), table headers will be incorrectly left-aligned instead of right-aligned. SC-010 requires zero instances of hardcoded directional CSS.
- **Reproduction**: Switch locale to Arabic. Open the History view. Table headers will be left-aligned instead of right-aligned.
- **Suggested fix direction**: Replace `text-left` with `text-start` (Tailwind's logical property equivalent) across all four `<th>` elements.
- **Confidence**: High

---

### O-007: 11 of 16 Arabic history i18n keys are untranslated English copies
- **Severity**: Medium
- **Surface**: `frontend/src/locales/ar.json:79-93`
- **FR / SC / Inv**: SC-009 (100% i18n), Constitution Principle VI (Arabic first-class support)
- **Description**: The Arabic locale file contains 11 history-related keys that are verbatim copies of the English values. Affected keys include: `history.empty`, `history.loading`, `history.error`, `history.filter.placeholder`, `history.detail.question`, `history.detail.sql`, `history.detail.acceptedAt`, `history.detail.empty`, `history.detail.schema`, `history.column.schema`, `history.column.sql`. While `history.title`, `history.column.question`, `history.column.acceptedAt`, `history.loadMore`, and `history.loadingMore` are properly translated, the majority of the History UI will display in English when Arabic is selected.
- **Reproduction**: Set the locale to `ar`. Navigate to History page. Most strings will appear in English.
- **Suggested fix direction**: Translate all 11 keys to Arabic. Ensure QA review of translations with a native speaker.
- **Confidence**: High

---

### O-008: E2E mock `mockHistoryList` intercepts detail endpoint requests
- **Severity**: Medium
- **Surface**: `frontend/tests/e2e/helpers/mock-backend.ts:151`, `frontend/tests/e2e/helpers/mock-backend.ts:212`
- **FR / SC / Inv**: Test quality
- **Description**: `mockHistoryList` uses the route pattern `**/history` which matches any URL containing "history", including `/history/some-id`. `mockHistoryDetail` uses `**/history/*`. When both mocks are registered in the same test (as in T-171, line 26-27), the `mockHistoryList` route is registered first and will intercept detail requests too, since Playwright `page.route` matches routes in registration order. The T-171 test passes because the detail mock at line 212 has a pathname check (`/history/[^/]+$`) with `route.fallback()`, but the list mock at line 151 doesn't check the pathname — it fulfills ALL requests matching `**/history`. The detail request gets the list response, but the test assertion (`detail.toContainText('SELECT COUNT(*)')`) happens to match because the detail mock was also set up with `items[0]` which contains that SQL.
- **Reproduction**: Change `mockHistoryDetail` to return different data from the list item (e.g., different SQL). The E2E test would then fail, proving the detail mock isn't actually being hit for the detail request.
- **Suggested fix direction**: Make `mockHistoryList` only match exact `/history` paths (no trailing segments), or use a more specific URL pattern like `**/history?**`.
- **Confidence**: Medium

---

### O-009: `schema` field present in frontend but absent from backend API
- **Severity**: Medium
- **Surface**: `frontend/src/components/history/HistoryList.tsx:5,40,109`, `frontend/src/hooks/useHistory.ts:6,15`
- **FR / SC / Inv**: Contract (Principle XII — API contract is single source of truth)
- **Description**: The frontend `HistoryItem` type extends `AcceptedQuerySummary` with an optional `schema?: string` field. The `HistoryList` component renders a "Schema" column, filters by schema, and `useHistory` passes a `schema` parameter to the API. However, neither the OpenAPI contract, the backend's `AcceptedQuerySummary` Pydantic schema, nor the `accepted_queries` DB table includes a `schema` field. The `listHistory` API function in `historyApi.ts` passes `schema` as a parameter but ignores it (the generated SDK `listHistory` function doesn't accept a `schema` query param). The Schema column always shows `'-'` because `item.schema` is always `undefined`.
- **Reproduction**: Open History view. Every row displays `'-'` in the Schema column, regardless of the database schema used.
- **Suggested fix direction**: Either add `schema` to the backend model/API/OpenAPI contract, or remove the phantom Schema column from the frontend. The spec (FR-021 through FR-023) does not mention a schema field.
- **Confidence**: High

---

### O-010: No debounce on filter input — re-renders on every keystroke
- **Severity**: Low
- **Surface**: `frontend/src/components/history/HistoryList.tsx:66`
- **FR / SC / Inv**: SC-007 (filter returns results within 1 second of user stopping typing)
- **Description**: The filter input calls `setFilter(e.target.value)` on every `onChange` event with no debounce. Each keystroke triggers a state update, re-runs the `useMemo` filter computation, and causes a full re-render of the table. While SC-007 specifies "within 1 second of the user stopping typing," the current implementation filters on every keystroke. For small datasets (Phase 1), this is acceptable, but for 1,000 entries (SC-006's target), the per-keystroke re-render could cause jank. The lack of debounce also means the behavior doesn't match the "stopping typing" semantics described in SC-007.
- **Reproduction**: Type quickly in the filter box with a large dataset. Observe immediate re-renders per keystroke.
- **Suggested fix direction**: Add a 300ms debounce to the filter state update, matching the SC-007 "user stops typing" requirement.
- **Confidence**: Medium

---

### O-011: History table rows not keyboard-accessible — no `tabIndex` or key handlers on `<tr>`
- **Severity**: Medium
- **Surface**: `frontend/src/components/history/HistoryList.tsx:93-111`
- **FR / SC / Inv**: Accessibility (WCAG 2.1 AA)
- **Description**: Table rows are interactive (`onClick={...}`, `cursor-pointer`) but have no `tabIndex`, `role="button"`, or `onKeyDown` handler for Enter/Space activation. Keyboard-only users and screen reader users cannot navigate to or activate history rows. The `<tr>` elements are not focusable via Tab. Only the filter input and Load More button are keyboard-reachable. This is a WCAG 2.1 AA violation (operable).
- **Reproduction**: Use Tab key to navigate the History page. The interactive table rows cannot be focused or activated via keyboard.
- **Suggested fix direction**: Add `tabIndex={0}` and `onKeyDown` handler (activating on Enter/Space) to each `<tr>`. Add `role="button"` or use `role="row"` with `aria-selected` for proper semantics. Consider adding `aria-label` with the question text.
- **Confidence**: High

---

### O-012: `COUNT(*)` executed on every first-page request — N+1 performance concern
- **Severity**: Low
- **Surface**: `backend/src/app/services/history_service.py:31-32`, `backend/src/app/repositories/accepted_query_repository.py:70-75`
- **FR / SC / Inv**: SC-006 (3-second target)
- **Description**: When `cursor is None` (first page request), `list_history` executes a separate `COUNT(*)` query to populate `total`. This results in two queries per first-page load: one `SELECT` and one `COUNT`. While the `idx_accepted_queries_user_id_accepted_at` index covers the main query, the `COUNT(*)` runs a separate `SELECT count(*) FROM accepted_queries WHERE user_id = ?` which does a full index scan. For large tables this becomes expensive. The `total` field is nullable and optional in the contract, so it could be omitted or computed differently.
- **Reproduction**: Observe the SQL log for `GET /history` (no cursor) — two queries are executed.
- **Suggested fix direction**: Consider returning `total` only when explicitly requested (via a query parameter), or compute it from the `limit+1` fetch pattern (if fewer than `limit+1` rows returned, `total = len(items)`). Alternatively, accept the cost for Phase 1 and document as tech debt.
- **Confidence**: Medium

---

### O-013: E2E test T-173 (rejected queries absent from history) uses mock — doesn't test actual backend behavior
- **Severity**: Medium
- **Surface**: `frontend/tests/e2e/history-list-detail.spec.ts:56-69`
- **FR / SC / Inv**: FR-020, SC-012
- **Description**: T-173 claims to verify that "rejected queries do NOT appear in history" (FR-020, SC-012). However, it uses `mockHistoryList` to return a canned list with only one accepted query, then asserts that `DROP TABLE` text is not visible. This test doesn't test any actual backend logic — it only verifies that the mock response doesn't contain rejected queries. The mock could return anything. FR-020 and SC-012 require that rejected queries are never **persisted** to durable storage, which is a backend invariant that this E2E test cannot verify through mocks.
- **Reproduction**: Change the mock to include a rejected query with `DROP TABLE` in the list. T-173 would fail, proving it only tests the mock content, not the actual invariant.
- **Suggested fix direction**: Add a backend integration test that submits a question, rejects it, then queries the `accepted_queries` table directly and asserts zero rows. The E2E test should be marked as "FE-only" and supplemented with a real backend test for SC-012.
- **Confidence**: High

---

### O-014: `HistoryDetail` receives `AcceptedQuerySummary` type but spec expects `AcceptedQueryDetail` fields
- **Severity**: Low
- **Surface**: `frontend/src/components/history/HistoryDetail.tsx:2-4`, `frontend/src/pages/HistoryPage.tsx:11`
- **FR / SC / Inv**: FR-023, Principle XII (API contract)
- **Description**: `HistoryDetail` uses `AcceptedQuerySummary` (which has `id`, `question_text`, `generated_sql`, `accepted_at`) as its type, but the `GET /history/{id}` endpoint returns `AcceptedQueryDetail` (which also includes `llm_provider` and `database_connection_id`). The `useHistoryDetail` hook calls `getHistoryItem` which returns `AcceptedQueryDetail`, but `HistoryPage` passes it to `HistoryDetail` which types it as `AcceptedQuerySummary & { schema?: string }`. The extra fields (`llm_provider`, `database_connection_id`) are fetched but never displayed. While not a functional bug (TypeScript structural typing accepts supertypes), it represents contract/type drift and means the detail view is less informative than the API allows.
- **Reproduction**: Select a history item. The detail view shows question, SQL, schema (always empty), and accepted_at — but not `llm_provider` or `database_connection_id`, which are available from the API.
- **Suggested fix direction**: Update `HistoryDetail` to accept and render the full `AcceptedQueryDetail` type, displaying `llm_provider` and `database_connection_id` (or at least `llm_provider`).
- **Confidence**: High

---

### O-015: `useHistory` hook hardcodes page size of 20, inconsistent with OpenAPI default of 100
- **Severity**: Low
- **Surface**: `frontend/src/hooks/useHistory.ts:14`, `frontend/src/api/historyApi.ts:14`
- **FR / SC / Inv**: Principle XII (API contract)
- **Description**: The `useHistory` hook defaults to `pageSize: 20` and `historyApi.listHistory` defaults to `page_size: 20`. However, the OpenAPI contract specifies a default of 100 for the `limit` parameter. While a smaller page size is valid, the frontend silently overrides the contract default. If the intent was to fetch all history on the first load (as FR-021 says "client-side scrollable list"), 20 items means most users will need to click "Load More" repeatedly. The HistoryPage also doesn't pass `hasMore` or `onLoadMore` to HistoryList, so the load-more button never appears even when there are more pages.
- **Reproduction**: Accept 25 queries. Open History view. Only 20 are shown, with no way to load more (the HistoryPage doesn't wire up pagination props).
- **Suggested fix direction**: Either increase the page size to match the contract default (100) or wire up `hasNextPage` and `fetchNextPage` from `useHistory` to `HistoryList`'s `hasMore` and `onLoadMore` props.
- **Confidence**: High

---

### O-016: `HistoryPage` does not pass `hasMore`/`onLoadMore` props — pagination is silently broken in UI
- **Severity**: High
- **Surface**: `frontend/src/pages/HistoryPage.tsx:23-27`
- **FR / SC / Inv**: FR-021 (list all accepted queries)
- **Description**: `HistoryPage` uses `useHistory()` which returns `hasNextPage` and `fetchNextPage`, but these values are never passed to `HistoryList` as `hasMore` and `onLoadMore` props. `HistoryList` supports pagination (it renders a "Load More" button when `hasMore && onLoadMore` are provided), but since `HistoryPage` doesn't wire them up, the button never appears. Combined with the 20-item page size (O-015), users with more than 20 accepted queries will only ever see the most recent 20, with no indication that more exist. This directly violates FR-021 which says the history view should list "all" accepted queries.
- **Reproduction**: Accept 25+ queries. Open History. Only 20 are visible. No "Load More" button. No scroll. The remaining queries are invisible.
- **Suggested fix direction**: Pass `hasMore={hasNextPage}` and `onLoadMore={fetchNextPage}` from `useHistory()` to the `HistoryList` component props in `HistoryPage.tsx`.
- **Confidence**: High

## Summary

| ID | Severity | Surface | Status |
|----|----------|---------|--------|
| O-001 | Critical | `query_service.py:365` | open |
| O-002 | High | `history.py:22` | open |
| O-003 | High | `accepted_query_repository.py:47-66` | open |
| O-004 | Medium | `accepted_query_repository.py:54-58` | open |
| O-005 | Medium | `history_service.py:39` / `history.py:42` | open |
| O-006 | Medium | `HistoryList.tsx:77-87` | open |
| O-007 | Medium | `ar.json:79-93` | open |
| O-008 | Medium | `mock-backend.ts:151,212` | open |
| O-009 | Medium | `HistoryList.tsx` / `useHistory.ts` | open |
| O-010 | Low | `HistoryList.tsx:66` | open |
| O-011 | Medium | `HistoryList.tsx:93-111` | open |
| O-012 | Low | `history_service.py:31-32` | open |
| O-013 | Medium | `history-list-detail.spec.ts:56-69` | open |
| O-014 | Low | `HistoryDetail.tsx:2-4` | open |
| O-015 | Low | `useHistory.ts:14` / `historyApi.ts:14` | open |
| O-016 | High | `HistoryPage.tsx:23-27` | open |

Total findings: 16
- Critical: 1
- High: 3
- Medium: 8
- Low: 4
- Info: 0
