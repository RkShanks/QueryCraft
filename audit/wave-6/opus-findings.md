# Wave 6 (US-5 + US-6 + Final Polish) Independent Audit — Opus 4.6

Audit performed against main HEAD: `320b31f8607b37e6bec742d53b10daae87944215`
Audit branch: `wave-6-audit-opus`
Auditor: Opus 4.6 (independent, black-box)
Implementation prompts: NOT shown to auditor.
Gemini findings: NOT read (cross-contamination protection).

## Methodology

1. **Pre-flight**: Checked out main, created `wave-6-audit-opus` branch, installed all dependencies (`uv sync --extra dev`, `npm ci`), and ran baseline gates:
   - Backend: 291 passed, 66 skipped, 62 deselected
   - Frontend: 19 test files, 123 tests passed
   - Lint + typecheck: clean
   - E2E: 36 tests listed across 9 files

2. **Spec grounding**: Read US-5, US-6, FR-009/024/025/026, SC-008/009/010 from `spec.md`. Read all constitutional invariants. Read the wave-6 scope table (not detailed chunk plans).

3. **Code review**: Read all files in the audit scope list:
   - Backend: LLM factory, all 4 adapters, provider protocol, query router, query service, auth service, security middleware, config settings
   - Frontend: `useDebounce` hook, `HistoryList`, `HistoryDetail`, `en.json`, `ar.json`, `index.css`, `eslint.config.js`, custom ESLint rule
   - Tests: All US-5 integration tests, T-179/180/181/182/183 lint/i18n tests, T-184/213/215/226/250/251 backend tests, T-178/185/186 E2E tests, mock-backend helper
   - Specs: `openapi.yaml` (schema definitions, security schemes), `style-guide.md`, `constitution.md`

4. **Automated checks**:
   - Compared `en.json` vs `ar.json` key sets (found 7 missing keys, 36 untranslated)
   - Searched for physical CSS properties, `dangerouslySetInnerHTML`, `SELECT *`, `aria-busy`
   - Traced `LLM_MODEL_NAME` config usage, httpx client lifecycle, Redis connection lifecycle
   - Analyzed the E2E missing-key regex against real key patterns

## Findings

### O-001: LLM adapters create httpx.AsyncClient per request and never close it (resource leak)

- **Severity**: High
- **Surface**: `backend/src/app/llm/factory.py:18`, `backend/src/app/api/v1/query.py:49`
- **FR / SC / Inv**: FR-009, Constitution Principle XI (modularity)
- **Description**: `_get_query_service()` is a FastAPI `Depends` called on **every request**. It calls `LLMProviderFactory.from_config(settings)` which constructs a new adapter instance. Each adapter creates an `httpx.AsyncClient` in its `__init__`. None of the four adapters (`AnthropicAdapter`, `OpenAIAdapter`, `GeminiAdapter`, `OllamaAdapter`) implement `aclose()`, `__aenter__/__aexit__`, or any lifecycle management. The httpx client is never closed, leaking file descriptors and TCP connections on every request. Under sustained load this will exhaust OS file descriptor limits.
- **Reproduction**: Run a load test with 100+ sequential requests and monitor open file descriptors via `lsof -p <pid> | wc -l`.
- **Suggested fix direction**: Either (a) make the adapter a singleton held at module/app scope with proper shutdown cleanup, or (b) use `httpx.AsyncClient` as an async context manager within each `generate()` call. Option (a) is far more efficient.
- **Confidence**: High

### O-002: SessionMiddleware creates a new Redis connection per request and never closes it

- **Severity**: High
- **Surface**: `backend/src/app/core/security.py:43-46,64`
- **FR / SC / Inv**: Performance / resource management
- **Description**: `SessionMiddleware._get_redis()` calls `Redis.from_url()` on every HTTP request, creating a fresh async Redis connection. The connection is never closed (`aclose()`) after use. This leaks Redis connections at the rate of incoming traffic. The middleware has `self._redis = None` in `__init__` but never caches the result from `_get_redis()`.
- **Reproduction**: Monitor Redis `CLIENT LIST` output under sustained traffic; connection count will grow unboundedly.
- **Suggested fix direction**: Initialize the Redis connection once (e.g., in an `on_startup` hook or lazily with caching in `_get_redis`) and share across requests. Add `aclose()` on shutdown.
- **Confidence**: High

### O-003: LLM_MODEL_NAME setting referenced but never declared in Settings

- **Severity**: Medium
- **Surface**: `backend/src/app/llm/factory.py:25`, `backend/src/app/core/config.py` (missing)
- **FR / SC / Inv**: FR-009 (LLM provider configuration), SC-008 (operator effort)
- **Description**: The factory reads `model_name = getattr(settings, "LLM_MODEL_NAME", None)`. However, `LLM_MODEL_NAME` is not declared in the `Settings` class, so pydantic-settings will never populate it from environment variables. The `getattr` silently falls through to `None`, and each adapter falls back to its hardcoded default model. An operator who sets `LLM_MODEL_NAME=gpt-4o-mini` in their `.env` file would have no effect — a silent configuration failure that violates SC-008's intent of easy operator configuration.
- **Reproduction**: Set `LLM_MODEL_NAME=custom-model` in `.env`, start the app, and observe the factory still uses the hardcoded default model.
- **Suggested fix direction**: Add `LLM_MODEL_NAME: str = ""` to the `Settings` class so pydantic-settings will bind it from environment variables.
- **Confidence**: High

### O-004: Arabic (ar.json) has 7 missing keys and 36 untranslated English strings

- **Severity**: Medium
- **Surface**: `frontend/src/locales/ar.json`
- **FR / SC / Inv**: FR-024 (i18n layer), SC-009 (100% strings through i18n), US-6 acceptance scenario 1
- **Description**: `ar.json` is missing 7 keys that exist in `en.json` (`query.accept.success.message`, `query.accept.success.title`, `query.actions.accept`, `query.actions.accepted`, `query.actions.accepting`, `query.actions.regenerate`, `query.actions.reject`). Additionally, 36 keys in `ar.json` contain identical English text (not Arabic translations), including critical UX keys like `history.empty`, `history.loading`, `history.error`, `history.filter.placeholder`, and all `history.detail.*` keys. While the spec says "Only English translations are provided in this phase," the existence of `ar.json` with partial Arabic creates a false sense of readiness and would show mixed English/Arabic text if Arabic locale were activated.
- **Reproduction**: `python3 -c "import json; en=json.load(open('frontend/src/locales/en.json')); ar=json.load(open('frontend/src/locales/ar.json')); print(len(set(en)-set(ar)), 'missing,', sum(1 for k in ar if ar[k]==en.get(k,'') and k in en), 'untranslated')"`
- **Suggested fix direction**: Either (a) complete the Arabic translations for all 36+7 keys, or (b) remove `ar.json` entirely since the spec says "Only English translations are provided in this phase" and add it in Phase 4 (constitution §11 commitment). If keeping ar.json, all keys must be present and translated.
- **Confidence**: High

### O-005: no-inline-user-strings ESLint rule does not catch template literals or conditional expressions

- **Severity**: Medium
- **Surface**: `frontend/eslint-rules/no-inline-user-strings.cjs`
- **FR / SC / Inv**: SC-009 (100% user-facing strings through i18n), FR-024
- **Description**: The custom ESLint rule only handles two AST node types: `JSXText` and `Literal` (when parent is `JSXAttribute`). It does **not** handle: (a) `TemplateLiteral` nodes in JSX attributes (e.g., `` placeholder={`Search ${count} items`} ``), (b) string literals in JSX expression containers (e.g., `<span>{"Hello world"}</span>`), (c) conditional string expressions (e.g., `{isError ? "Error occurred" : t('key')}`), or (d) default prop values with English strings. These patterns would bypass the lint gate entirely. The T-179 regression test only tests inline `<div>Hello</div>` and `placeholder="Search"` — it does not test template literals, conditional renders, or default props.
- **Reproduction**: Create a component with `<input placeholder={\`Search $\{count\}\`} />` and verify ESLint reports zero violations from `local/no-inline-user-strings`.
- **Suggested fix direction**: Add handlers for `TemplateLiteral` (when inside a `JSXExpressionContainer` with a user-facing parent attribute) and for string `Literal` nodes inside `JSXExpressionContainer` elements.
- **Confidence**: High

### O-006: E2E missing-key regex (T-185) requires 3+ dot segments, misses 2-segment keys

- **Severity**: Medium
- **Surface**: `frontend/tests/e2e/i18n-audit.spec.ts:19`
- **FR / SC / Inv**: FR-024 (i18n layer completeness)
- **Description**: The `MISSING_KEY_PATTERN` regex requires at least 3 dot-separated segments: `[a-z][a-zA-Z0-9_]+(?:\.[a-z][a-zA-Z0-9_]+){2,}`. This means that if a 2-segment key (e.g., `error.unauthorized`, `error.concurrent`, `nav.signIn`, `app.title`, `common.close`, `history.loading`) were rendered as raw text due to a missing translation, the regex would **not** detect it. 21 of the 133 keys in `en.json` are 2-segment keys. This creates false negatives — the E2E test would pass even if those keys appear as raw fallback text.
- **Reproduction**: Temporarily remove `error.unauthorized` from en.json, render a 401 error page, and observe the E2E test passes despite the raw key being visible.
- **Suggested fix direction**: Lower the regex threshold to `{1,}` instead of `{2,}`, or use a different detection strategy such as comparing rendered text against the known key set.
- **Confidence**: High

### O-007: T-186 RTL E2E test only checks for JS errors, not actual layout correctness

- **Severity**: Medium
- **Surface**: `frontend/tests/e2e/i18n-audit.spec.ts:47-87`
- **FR / SC / Inv**: FR-025 (no hardcoded directional CSS), SC-010
- **Description**: The T-186 test sets `document.documentElement.dir = 'rtl'` and then only asserts: (a) no JS errors occurred, and (b) a heading is still visible. It does **not** verify that text alignment, padding, margins, or layout actually flipped correctly. A page could have broken RTL layout (overlapping elements, text cut off, wrong alignment) and this test would still pass. FR-025 requires "all directional styling uses logical equivalents" — the T-186 test does not validate this at runtime.
- **Reproduction**: Add `style="margin-left: 20px"` to a component, run T-186, and observe it passes despite the FR-025 violation being rendered.
- **Suggested fix direction**: Add screenshot comparison or computed-style assertions that verify text-align is `start`/`right` (in RTL), padding/margin directions are mirrored, and critical layout elements don't overlap or clip.
- **Confidence**: High

### O-008: Schema context never passed to LLM — generates SQL without database schema

- **Severity**: High
- **Surface**: `backend/src/app/services/query_service.py:78`, `backend/src/app/api/v1/query.py:44`
- **FR / SC / Inv**: US-1 core functionality
- **Description**: In `_get_query_service()`, `schema_context = await _source_introspector.introspect()` retrieves the database schema, but it is only used for the `SchemaValidationRule` evaluator — it is **never** passed to `QueryService`. Inside `QueryService.submit_question()`, the LLM is called with `self._llm.generate_sql(question, "")` — an empty string for `schema_context`. The same is true in `regenerate_query()` (line 298-301). The LLM has no knowledge of the database schema and generates SQL blind. While this is likely a pre-Wave-6 issue (not introduced in Wave 6), it means the LLM provider switching is tested against a fundamentally broken generation pipeline.
- **Reproduction**: Submit a question referencing specific table names and observe the LLM generates SQL without knowledge of actual tables.
- **Suggested fix direction**: Pass `schema_context` into `QueryService.__init__()` and use it in both `submit_question()` and `regenerate_query()` calls to `self._llm.generate_sql()`.
- **Confidence**: High

### O-009: Debounce delay (300ms) is a hardcoded magic number

- **Severity**: Low
- **Surface**: `frontend/src/components/history/HistoryList.tsx:26`
- **FR / SC / Inv**: Code quality (SC-007 debounce)
- **Description**: The debounce delay `300` is hardcoded inline as a numeric literal: `const filter = useDebounce(rawFilter, 300)`. This is a magic number with no named constant, no configuration option, and no documentation of why 300ms was chosen. The E2E test at `frontend/tests/e2e/helpers/mock-backend.ts` and the HistoryPage test also hardcode `300` for their wait assertions, creating brittle coupling.
- **Reproduction**: Search for `300` across the codebase and find 3+ unlinked references.
- **Suggested fix direction**: Extract `300` to a named constant like `FILTER_DEBOUNCE_MS = 300` exported from the hook or a config module. Use that constant in tests as well.
- **Confidence**: High

### O-010: `accept_query` endpoint performs raw SQL query without parameterization comment

- **Severity**: Medium
- **Surface**: `backend/src/app/api/v1/query.py:122-130`
- **FR / SC / Inv**: Constitution Principle V (read-only execution), security
- **Description**: The `accept_query` endpoint contains an inline raw SQL query: `text("SELECT id FROM database_connections LIMIT 1")`. While this specific query has no user-controlled input and is not a SQL injection risk, it: (a) bypasses the ORM's repository pattern used everywhere else, (b) is imported lazily inside the function body (not at module top), and (c) creates an entirely separate database session (`get_async_session_factory()()`) outside the dependency-injected session — potentially causing transaction isolation issues. The comment "Phase 1 has exactly one" suggests this is a shortcut that will scale poorly.
- **Reproduction**: Code review — no runtime reproduction needed.
- **Suggested fix direction**: Move the database_connection lookup to a proper repository method using the injected `db` session, or pass the connection ID via configuration rather than querying at accept time.
- **Confidence**: High

### O-011: T-183 i18n render audit does not cover error states, modals, or toast components

- **Severity**: Medium
- **Surface**: `frontend/tests/unit/i18n-render.test.tsx:72-93`
- **FR / SC / Inv**: FR-024 (100% i18n), SC-009
- **Description**: The T-183 test renders only 3 pages: `SignInPage`, `AskQuestionPage`, and `HistoryPage` in their default (happy-path) state. It does not test: (a) error state renders (network errors, 401 redirects, evaluator rejections), (b) the `EvaluatorRejectionBanner`, `TimeoutBanner`, or `RefinePromptBanner` components, (c) the accept success toast, (d) the empty state for history, or (e) any modal dialogs. Missing keys in these states would not be caught. The `findRawKeys` function also only checks text nodes — it would miss raw keys in `aria-label`, `title`, or `placeholder` attributes.
- **Reproduction**: Add a missing key reference in `TimeoutBanner.tsx` and verify T-183 still passes.
- **Suggested fix direction**: Extend the test to render each error/banner component in isolation with appropriate props, and also inspect element attributes (not just text nodes).
- **Confidence**: High

### O-012: `defaultValue` fallback in t() calls embeds English strings in component source

- **Severity**: Low
- **Surface**: 54+ occurrences across `frontend/src/components/`
- **FR / SC / Inv**: SC-009 (100% i18n), FR-024
- **Description**: Nearly every `t()` call includes a `{ defaultValue: "English text" }` option, e.g., `t('history.loading', { defaultValue: 'Loading history...' })`. While this is a valid i18next feature, it means English fallback text is embedded directly in component source code. If a key is missing from `en.json`, the component would silently render the hardcoded English `defaultValue` instead of showing a missing-key indicator — making translation completeness issues invisible. The `i18n-render.test.tsx` mock throws on missing keys, but this protection only exists in tests, not in production. In production, missing keys silently fall back to `defaultValue`, hiding i18n gaps.
- **Reproduction**: Remove a key from `en.json`, render the page, and observe the English `defaultValue` appears with no warning.
- **Suggested fix direction**: Remove `defaultValue` from all `t()` calls and instead configure i18next with `saveMissing: true` and a missing-key handler that logs warnings or throws in development mode.
- **Confidence**: Medium

### O-013: No `aria-busy` or loading indicator during debounce wait

- **Severity**: Low
- **Surface**: `frontend/src/components/history/HistoryList.tsx:62-72`
- **FR / SC / Inv**: Accessibility (a11y), US-6 RTL-readiness
- **Description**: When a user types in the filter input, the `useDebounce` hook introduces a 300ms delay before the filter actually applies. During this delay, there is no visual or accessible indicator that filtering is pending — no `aria-busy`, no spinner, no visual feedback. Screen reader users would have no way to know that the list will update shortly. The filter input also lacks `role="search"` or `aria-controls` linking it to the filtered table.
- **Reproduction**: Tab to the filter input, type rapidly, and observe no indication that filtering is in progress.
- **Suggested fix direction**: Add `aria-busy={rawFilter !== filter}` to the table or list container, and consider adding a subtle visual indicator (e.g., a small spinner) during the debounce delay.
- **Confidence**: Medium

### O-014: `no-physical-directions` test (T-180) does not check for `left:`, `right:`, `float: left/right`, `border-left`, `border-right`

- **Severity**: Low
- **Surface**: `frontend/tests/lint/no-physical-directions.test.ts:19-26`
- **FR / SC / Inv**: FR-025 (no hardcoded directional CSS), SC-010
- **Description**: The T-180 `PHYSICAL_PATTERNS` array only checks for 6 patterns: `margin-left:`, `margin-right:`, `padding-left:`, `padding-right:`, `text-align: left`, `text-align: right`. It misses: `left:` (position offset), `right:` (position offset), `float: left`, `float: right`, `border-left:`, `border-right:`, `border-left-width:`, etc. FR-025 specifically mentions "`left`, `right`, `margin-left`, `margin-right`, `padding-left`, `padding-right`" — the spec includes raw `left` and `right` as banned properties. Currently, no source files use these patterns, so this is a guard gap rather than an active violation.
- **Reproduction**: Add `left: 10px` to a component's inline style or CSS module and verify the test passes despite the FR-025 violation.
- **Suggested fix direction**: Add regex patterns for `left\s*:`, `right\s*:`, `float\s*:\s*(left|right)`, `border-left`, `border-right` to `PHYSICAL_PATTERNS`.
- **Confidence**: High

### O-015: `no-physical-tailwind` test (T-181) is a no-op when dist/ doesn't exist

- **Severity**: Low
- **Surface**: `frontend/tests/lint/no-physical-tailwind.test.ts:8-17`
- **FR / SC / Inv**: FR-025, SC-010
- **Description**: The T-181 test checks for physical-direction Tailwind utilities in the built CSS bundle (`dist/`). However, if `dist/` does not exist (which is the case in CI when only `npm run test` is run without `npm run build`), the test silently skips with a `console.warn` and reports 0 failures. This means the guard never actually runs in CI unless a build step is explicitly added. The second `it()` block also has an early return when `dist/` is missing, effectively making both test cases no-ops.
- **Reproduction**: Run `npm run test -- --run` without first running `npm run build` and observe both test cases pass without doing any work.
- **Suggested fix direction**: Either (a) make the CI pipeline run `npm run build` before tests, or (b) rewrite the test to scan Tailwind config + source files for physical utility class names directly (like T-180 does for CSS declarations).
- **Confidence**: High

### O-016: T-182 i18n key completeness test has sequential dependency between `it()` blocks

- **Severity**: Low
- **Surface**: `frontend/tests/unit/i18n-key-completeness.test.ts:40-56,58-66`
- **FR / SC / Inv**: Test reliability
- **Description**: The first `it()` block ("extracts t() references from all source files") populates a `Set<string>` variable `referencedKeys` that is then used by the second and third `it()` blocks. If the first test is skipped or if test execution order changes, the subsequent tests would operate on an empty set and silently pass. This violates the principle that each test case should be independent. Additionally, the regex `t\(['"]([a-zA-Z0-9_.]+)['"]/g` would not match keys with hyphens (none exist currently, but the pattern is fragile).
- **Reproduction**: Run only the second `it()` block in isolation and observe it passes trivially (empty `referencedKeys` means no missing keys).
- **Suggested fix direction**: Move the reference extraction logic to a `beforeAll()` hook or a shared fixture so all tests have the populated data regardless of execution order.
- **Confidence**: High

## Summary

| ID | Severity | Surface | Status |
|----|----------|---------|--------|
| O-001 | High | LLM adapter httpx client leak | open |
| O-002 | High | SessionMiddleware Redis connection leak | open |
| O-003 | Medium | LLM_MODEL_NAME config not declared in Settings | open |
| O-004 | Medium | ar.json missing 7 keys + 36 untranslated strings | open |
| O-005 | Medium | ESLint no-inline-strings misses template literals | open |
| O-006 | Medium | E2E missing-key regex has false negatives (2-segment keys) | open |
| O-007 | Medium | T-186 RTL test is effectively a no-op for layout validation | open |
| O-008 | High | Schema context never passed to LLM (empty string) | open |
| O-009 | Low | Debounce 300ms is a magic number | open |
| O-010 | Medium | accept_query uses raw SQL outside repository pattern | open |
| O-011 | Medium | T-183 render audit misses error states and banners | open |
| O-012 | Low | defaultValue in t() embeds English fallbacks in source | open |
| O-013 | Low | No aria-busy during debounce wait | open |
| O-014 | Low | T-180 physical-direction check misses `left:`, `right:`, `float`, `border-left/right` | open |
| O-015 | Low | T-181 physical-tailwind test is a no-op without dist/ | open |
| O-016 | Low | T-182 test has sequential it() block dependency | open |

Total findings: 16
- Critical: 0
- High: 3
- Medium: 6
- Low: 7
- Info: 0
