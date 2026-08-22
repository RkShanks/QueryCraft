# CHUNK-20 / IS-GAP-032 + IS-GAP-038 — history dataset search and locale runtime

Status: resolved on tested branch `phase-6/wave-19.20-history-locale`, starting from synchronized main `841905cd182140b60ee1594a07baa9bbdc7012b6` (the squash merge of [#317](https://github.com/RkShanks/QueryCraft/pull/317)). The machine-readable [JSON evidence](chunk-20-history-locale.json) records the same contract, commits, browser results, gates, cleanup and ledger counts.

Merge bookkeeping reconciliation carried in this branch: `CHUNK-19` / `IS-GAP-029`+`IS-GAP-030`+`IS-GAP-039` was confirmed merged through [#317](https://github.com/RkShanks/QueryCraft/pull/317) at main `841905cd182140b60ee1594a07baa9bbdc7012b6`; the three tested-branch rows became Resolved without changing historical test evidence.

## API/search contract (IS-GAP-032)

`GET /api/v1/history` gains one optional `search` query parameter; no new endpoint was added and operation parity stays 64 runtime = 64 canonical = 64 generated:

- The value is trimmed before a 200-code-point cap (`StringConstraints(strip_whitespace=True, max_length=200)`); whitespace-only means unfiltered history; over-long input returns the existing sanitized 422 validation envelope with no raw echo.
- Matching is case-insensitive literal substring over the caller's own `question_text` and `generated_sql`: `%`, `_` and `\` are escaped and the pattern is a bound SQLAlchemy parameter (`ILIKE ... ESCAPE '\'`), so `100%_done` matches only literal text.
- User scoping, reverse-chronological `(accepted_at, id)` keyset order and explicit limits are unchanged.
- Cursors became opaque (`encode_cursor`) with namespace binding: unfiltered pages use namespace `accepted_query_history`; filtered pages use `accepted_query_history:<sha256-prefix of normalized search>`, so a cursor minted under one filter is rejected (`400 invalid_cursor`) under another filter or unfiltered, and raw search text never enters any cursor payload. Legacy pre-opaque `accepted_at|id` cursors remain accepted for the unfiltered listing only — compatibility is preserved exactly where it is safe.
- The first page returns the filtered total (`count_by_user(search=...)`); subsequent pages return `total: null` as before — clients never receive an unbounded scan to simulate search.
- Audit context records only `{"operation": "list", "searched": true}` when filtering; raw search text never reaches audit storage.

## Frontend history behavior (IS-GAP-032)

- `useHistory({ search })` sends the trimmed term server-side; the query key includes the normalized search so different filters occupy separate cache entries, stale responses cannot leak across filters, and the filtered first-page total is exposed.
- HistoryPage owns the debounced input (300 ms), keeps Load More explicit and bounded, and reconciles selection by derivation: an active settled search that no longer returns the selected entry suppresses the detail until it matches again (no effect-state syncing).
- Errors stay panel-scoped: list/search failures render inside `history-list-panel`, detail failures inside `history-detail-panel`; valid rows persist through background refresh failures via the CHUNK-17 client-contract states.
- Localized initial, empty, no-match, loading-more, partial and retry states exist for both locales (`history.noMatch` added to en/ar).
- Rows render as a semantic `<ul role="list">` of independent `<button aria-pressed>` elements with native keyboard activation; focusable divs with manual Enter/Space handlers and the fake hidden `columnheader` spans were removed (no table is imitated because no table exists). SQL previews keep `dir="ltr"` inside RTL chrome.

## Locale contract (IS-GAP-038)

- Supported active locales are normalized `en` (LTR) and `ar` (RTL); variants resolve to base language (`ar-EG`/`ar-SA` → ar, `en-US`/`en_GB` → en); unsupported values are ignored safely at every lookup.
- Precedence: explicit `?lng=` → persisted device preference (`querycraft.language`, not identity-sensitive) → navigator languages → html lang attribute → English.
- A query-string choice persists on arrival. A manual change becomes authoritative: it writes the preference immediately, updates `documentElement.lang/dir`, and rewrites a present `?lng=` parameter so a stale value cannot revert the choice on reload. localStorage denial degrades to in-memory switching.
- One normalization helper (`src/i18n/locale.ts`) replaced every production exact `language === "ar"` check (App.tsx, AppShell.tsx, SignInPage.tsx); i18n initialization dropped the language detector in favor of the locked resolver.
- All production date/number rendering routes through `formatDateTime`/`formatNumber` (active app locale, safe fallbacks for invalid values): history list/detail timestamps, admin audit verification/purge/entry times, connection schema refresh times, detection updated-at, quota reset times and quota counters, and the quota-exceeded banner. SQL, code, IDs and user-entered content keep their existing LTR/`dir="auto"` isolation.

## TDD commits

| Stage | Commit |
| --- | --- |
| RED backend search contract | `56020c69353a9a1b3719917f1348982dabdaa089` |
| GREEN backend search contract | `34c81cb8791c5bd4807d4ea6fd90b3d4eabe7d71` |
| Generated client regeneration | `002c3b7191dcc900b53b815cf02598ed403cdd16` |
| RED frontend history gaps | `6d40c14201e2ce3e8e360b5067f445c5282ee4fe` |
| GREEN frontend history behavior | `e5b8d0c0732577435820021f783776eb7eda6176` |
| RED locale gaps | `2082350f9c30b84bff6bd18700778c4284f6fa97` |
| GREEN locale runtime | `341ea033353191be318427451e693a71bebe9aa5` |
| Browser matrix + live proof + fixture hardening | `caa2547b3cd55481eede4a1773c9c8c19a5d00bc` |

RED evidence: the backend slice failed at collection (no `search` parameter, no normalization helpers existed); the frontend history slice failed 9 of 10 new cases against the client-filter/div-row implementation; the locale slice failed all three module imports (no resolver, formatter or switcher existed).

## Browser/live evidence

Disposable Compose project `qc20` (platform PostgreSQL on 5433 with migrations applied, Redis, FastAPI backend on 8000, frontend on 5173). Two disposable users were seeded directly into the platform database with disposable credentials; user A owned 49 accepted-query rows (25 `zebra` matches spanning two pages, four literal `100%_done` rows), user B owned cross-user bait rows. No LLM call and no source-database query were made.

Direct API proof (curl, real HTTP): `search=zebra&limit=20` returned exact filtered total 25 with a cursor whose payload keys are exactly `{i,n,s,v}`, namespace prefixed `accepted_query_history:` and containing no raw needle; page 2 returned the remaining 5; replaying that cursor under `100%_done` and unfiltered both returned `invalid_cursor`; `search=100%25_done` returned exactly the 4 literal rows.

Chromium matrix (mocked routes, fixed clock):

`PLAYWRIGHT_HTML_OUTPUT_DIR=/tmp/opencode/chunk20-report PLAYWRIGHT_OUTPUT_DIR=/tmp/opencode/chunk20-browser npx playwright test chunk_20_history_locale.spec.ts` — 6 passed in 13.8s:

- 1440/768/375 semantic list: real list/button structure, zero columnheaders/focusable divs, aria-pressed selection, keyboard activation, server-side search narrowing to the mocked filtered dataset.
- ar-EG resolves RTL with normalized `lang="ar"`, persists across a param-less reload, manual English switch wins and rewrites the stale `?lng=` to `lng=en`, survives reload, and back/forward keeps direction coherent.
- Fixed-clock formatting at 768px: Arabic chrome renders Arabic-script dates while SQL stays LTR-isolated; English renders Latin script; detail errors surface only inside the detail panel at 375px.

Live spec (real FastAPI HTTP through the running stack, no route mocking):

`CHUNK20_LIVE_USERNAME=<disposable> CHUNK20_LIVE_PASSWORD=<disposable> E2E_BASE_URL=http://localhost:5173 npx playwright test chunk_20_live_history.spec.ts` — 2 passed in 4.3s:

- Server-side dataset search: initial load = exactly one bounded request; debounced `zebra` produced exactly one request carrying `search=zebra`; Load More clicked once produced exactly one cursor page (three requests total — no automatic full-dataset loading); rendered count reached the exact filtered total; user B's bait rows never appeared; literal `100%_done` matched exactly 4 rows.
- Selection reconciliation: selecting a row then filtering it out returned the detail pane to its localized empty state with no extra detail fetch.

Console/page-error streams contained no raw keys, no search-text leakage, no overflow or stale-detail artifacts during the runs.

## Automated gates

- Backend: full unit suite 2,561 passed (`uv run pytest tests/unit -q -m "not integration"`); integration history suite 8 passed plus repository cursor suites on the disposable PostgreSQL stack; Schemathesis history/openapi contract suites passed (`SCHEMATHESIS_RUN=1 pytest tests/contract/test_history_contract.py test_openapi_contract.py`, 64 subtests); Ruff check and format clean; canonical OpenAPI regenerated deterministically; `gen:api:check` parity holds (64=64=64).
- Frontend: focused new/changed suites 52 history tests + 36 locale/toggle/formatting tests green; full Vitest 87 files / 1,232 tests passed; ESLint clean; typecheck clean; production build clean; stylelint clean; harness guard passed with 34 classified specs including both new entries; `git diff --check` clean.

Environment quirks discovered:

1. Playwright's regex route matching tests the full URL, so `/api/v1/history(?:\?.*)?$` never intercepts detail paths `/api/v1/history/{id}`; specs must register distinct detail patterns. Suggested skill location: `.agents/skills/FRONTEND_GEMINI.md` quirks table.
2. Locator-scoped `getByPlaceholderText` does not exist in Playwright (page-level only); role-based locators with the localized aria-label are the equivalent.
3. jsdom's ICU renders Arabic dates with Arabic script but Western digits; digit-shape assertions must accept CLDR variance while asserting the script.
4. Unmocked workspace endpoints leak through the Vite dev proxy to a real backend; a single 401 triggers global session-expiry redirection, so mocked-shell specs must mock every mounted fetch (query limits included).
5. Node's `tsc -b` build compiles test sources and caught generated-SDK callback nullability (`params?`) that `tsc --noEmit` reported only after build ordering — same class as the CHUNK-19 quirk.
6. The on-demand Schemathesis admin suite (`test_admin_contract[POST /api/v1/admin/refresh-schema]`) can fail against a shared seeded stack independent of this diff (reproduced after removing all seeded rows); CI does not run SCHEMATHESIS suites, and the history contract suites pass.

Cleanup removed the disposable Compose project's seeded users/rows/connections from the platform database, all temporary Playwright HTML/browser output under `/tmp/opencode`, and `frontend/test-results`. The protected baseline remains exactly 14 modified tracked PNGs, seven historical untracked screenshots and existing trace archives; none was staged, regenerated, restored or deleted (`git add -A` was never used).

Both gaps are Resolved on this branch pending this PR's CI and squash merge. Ledger totals after CHUNK-20 are 30 Resolved, 0 Resolved on tested branch, 14 Pending and 3 Needs Decision out of 47.
