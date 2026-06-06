# Wave 6 (US-5 + US-6 + Final Polish) Independent Audit — Gemini Pro 3.1

Audit performed against main HEAD: 320b31f8607b37e6bec742d53b10daae87944215
Audit branch: wave-6-audit-gemini
Auditor: Gemini Pro 3.1 (independent, black-box)
Implementation prompts: NOT shown to auditor.
Opus findings: NOT read (cross-contamination protection).

## Methodology

1. Pulled the latest `main` branch and verified baseline test suites pass successfully.
2. Grounded via specs, constitution, and Wave 6 plans without referencing implementation prompt files.
3. Conducted manual code inspections across backend FastAPI routing (`query.py`, `auth.py`, `admin.py`, `history.py`), LLM adapter implementations, frontend UI components (`HistoryList.tsx`, `HistoryDetail.tsx`, `useDebounce.ts`), E2E testing scripts, and ESLint rule configs.
4. Traced data flows for potential security gaps including IDOR, connection leaks, state management races, XSS, and CSRF weaknesses.

## Findings

### G-001: Severe LLM Adapter Connection Leak on Every Request
- **Severity**: Critical
- **Surface**: `backend/src/app/llm/anthropic_adapter.py:15`, `openai_adapter.py:15`
- **FR / SC / Inv**: Application Stability / Performance
- **Description**: The `LLMProviderFactory.from_config(settings)` instantiates a new LLM adapter (e.g., `AnthropicAdapter` or `OpenAIAdapter`) on every single `/query/submit` request via FastAPI's dependency injection (`_get_query_service`). Each of these adapters instantiates a new `httpx.AsyncClient` but never closes it. This leads to unbounded connection pool and file descriptor leaks, which will cause the service to crash under moderate load in production.
- **Reproduction**: Submit several questions consecutively. Monitor file descriptors for the backend process (e.g. `lsof | grep python | wc -l`), observing them grow monotonically on each request.
- **Suggested fix direction**: Either memoize the adapter instantiation in the factory to reuse a single `httpx.AsyncClient` globally (and ensure it gets shut down in the app lifespan), or strictly call `await client.aclose()` at the end of each generation cycle inside the adapter.
- **Confidence**: High

### G-002: i18n Missing-Key Regex Produces False Negatives
- **Severity**: High
- **Surface**: `frontend/tests/e2e/i18n-audit.spec.ts:19`
- **FR / SC / Inv**: FR-024 (100% of user-facing strings routed through i18n layer)
- **Description**: The Playwright regex `MISSING_KEY_PATTERN` demands at least three dot-separated segments (e.g., `a.b.c`) to flag an untranslated string. However, keys like `history.error` and `history.loading` only have two segments. If these translations are missing, the UI will display the raw keys, but the E2E audit test will silently pass.
- **Reproduction**: Delete `"history.error": "Failed to load history."` from `en.json`, force the frontend to render the error state, and run the E2E audit spec. The test will incorrectly pass.
- **Suggested fix direction**: Update the regex to support two-segment matching (`{1,}` instead of `{2,}`) or explicitly export the dictionary keys during the E2E phase to ensure exact matches against known keys.
- **Confidence**: High

### G-003: RTL Layout E2E Verification is a No-Op
- **Severity**: High
- **Surface**: `frontend/tests/e2e/i18n-audit.spec.ts:48-88`
- **FR / SC / Inv**: FR-025 (No hardcoded directional CSS properties)
- **Description**: The T-186 E2E test verifying RTL layout merely switches `document.documentElement.dir` to `'rtl'` and asserts that a page heading remains visible. It completely fails to inspect computed styles, margins, or padding. Therefore, if a developer mistakenly uses physical properties (e.g., `ml-4` instead of `ms-4`), this E2E test will not catch the layout break.
- **Reproduction**: Intentionally hardcode `ml-10` on an element in the frontend and run the `i18n-audit.spec.ts` test. The test will pass despite the layout defect.
- **Suggested fix direction**: Inject a layout bounding-box check or rely on robust Stylelint guard rails (as implemented in `T-180`) instead of a superficial E2E visibility assertion.
- **Confidence**: High

### G-004: ESLint `no-inline-user-strings` Rule Misses Widespread Patterns
- **Severity**: High
- **Surface**: `frontend/eslint-rules/no-inline-user-strings.cjs`
- **FR / SC / Inv**: SC-009 (No inline string literals exist in user-facing components)
- **Description**: The custom ESLint rule only evaluates `JSXText` and `Literal` nodes within a `JSXAttribute`. It completely ignores strings inside JSX expression containers, template literals, conditional renders (e.g., `{loading ? "Wait" : "Done"}`), and default component props. Hardcoded strings in these constructs will silently bypass the linter.
- **Reproduction**: Insert `<div>{"Hardcoded String"}</div>` into a React component and run `npm run lint`. The linter will not throw an error.
- **Suggested fix direction**: Extend the ESLint rule to visit `TemplateLiteral`, `ConditionalExpression`, and `Literal` nodes inside JSX expression containers to ensure comprehensive coverage.
- **Confidence**: High

### G-005: Empty SQL Fails with Incorrect Violation Identity
- **Severity**: Medium
- **Surface**: `backend/src/app/evaluator/rules/read_only.py:22`
- **FR / SC / Inv**: FR-010 (g) (Empty SQL treated as `empty_sql` violation)
- **Description**: The `ReadOnlyRule` correctly aborts on empty or unparseable SQL, but it returns a generic `False`. The evaluator pipeline maps this to the `read_only` rule failure, thereby emitting the `evaluator.violation.dataModifying` message key ("contains data-modifying statements..."). This actively misleads users and fails the specific mandate of T-252 / FR-010(g) to use an `empty_sql` identity.
- **Reproduction**: Force the LLM to return `""`. Submit the query. The frontend will display the "Write operations are blocked. Try a SELECT" error message instead of an empty SQL specific message.
- **Suggested fix direction**: Refactor the rule pipeline to return structured tuple reasons or distinct rule identities, allowing `ReadOnlyRule` to return an explicit `empty_sql` string that maps to the correct localization key.
- **Confidence**: High

### G-006: E2E Audit Misses Secondary and Modal States
- **Severity**: Medium
- **Surface**: `frontend/tests/e2e/i18n-audit.spec.ts`
- **FR / SC / Inv**: SC-009 (100% of user-facing strings)
- **Description**: The E2E missing-key audit restricts its check to the happy-path default states of `/sign-in`, `/`, and `/history`. It never triggers error toasts, the query detail view, timeout banners, or the evaluator rejection modal. Any missing i18n keys deep within these non-default interactive states are left unverified.
- **Reproduction**: Remove a key specific to the evaluator modal (`query.evaluatorRejection.heading`). The test suite will pass.
- **Suggested fix direction**: Use the mock backend routes in the E2E setup to force the UI into rejected, timed-out, and populated-detail states before running the `assertNoMissingKeys` check.
- **Confidence**: High

### G-007: Admin Endpoint OpenAPI Contract Drift
- **Severity**: Low
- **Surface**: `specs/001-core-text-to-sql/contracts/openapi.yaml:406` vs `backend/src/app/api/v1/admin.py:64`
- **FR / SC / Inv**: Principle XII (API Contract as Single Source of Truth)
- **Description**: In `openapi.yaml`, the security definition for `/admin/refresh-schema` utilizes a logical OR (`- sessionCookie: [] \n - AdminKey: []`). However, the implementation backend strictly requires the `X-Admin-Key` header regardless of whether a valid session exists or not, rendering the OpenAPI spec inaccurate.
- **Reproduction**: Attempt to call `/admin/refresh-schema` with only a valid `session_id` cookie but no `X-Admin-Key`. The backend returns 401/403, contrary to what the OR statement in the YAML suggests.
- **Suggested fix direction**: Update the OpenAPI spec to enforce a logical AND array (`- sessionCookie: [] \n  AdminKey: []`), or drop `sessionCookie` entirely from that endpoint's security array since the backend does not consume it.
- **Confidence**: High

### G-008: Missing `aria-busy` State During Debounce Wait
- **Severity**: Info
- **Surface**: `frontend/src/components/history/HistoryList.tsx:64`
- **FR / SC / Inv**: Accessibility (Polish)
- **Description**: The `HistoryList` applies a 300ms debounce to the filter input to prevent stuttering re-renders. However, it does not set an `aria-busy=true` property on the list container while the user types, meaning screen readers receive no indication that an active background filtering operation is queued or pending.
- **Reproduction**: Type rapidly into the history filter input with a screen reader active. No busy state is announced during the 300ms debounce window.
- **Suggested fix direction**: Expose an `isDebouncing` boolean from the `useDebounce` hook (or derive it by comparing `rawFilter !== filter`) and bind it to `aria-busy` on the table container.
- **Confidence**: Medium

## Summary

| ID | Severity | Surface | Status |
|----|----------|---------|--------|
| G-001 | Critical | `llm/anthropic_adapter.py` | open |
| G-002 | High | `i18n-audit.spec.ts` | open |
| G-003 | High | `i18n-audit.spec.ts` | open |
| G-004 | High | `no-inline-user-strings.cjs` | open |
| G-005 | Medium | `read_only.py` | open |
| G-006 | Medium | `i18n-audit.spec.ts` | open |
| G-007 | Low | `admin.py` vs `openapi.yaml` | open |
| G-008 | Info | `HistoryList.tsx` | open |

Total findings: 8
- Critical: 1
- High: 3
- Medium: 2
- Low: 1
- Info: 1
