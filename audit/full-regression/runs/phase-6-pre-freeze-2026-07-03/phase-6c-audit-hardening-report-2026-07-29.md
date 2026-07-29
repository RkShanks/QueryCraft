# Phase 6C Audit Hardening Current-Head Regression

Run date: 2026-07-29

Scope: Phase 6C audit hardening only. Phase 6D, T-905, final Phase 6 closure and freeze work, and the implementation-surface gap audit were not started.

Starting synchronized main HEAD: `f34f1c8d3e17a2e877fb4d74a425fef0e20f0867`

Tested product HEAD: `991f7e38bdc9dcbf0b0fa5c9c00532652ec69a9c`

Runtime: disposable platform Postgres, source Postgres, Redis, backend, frontend, and session helper; real APIs; Chrome DevTools MCP; headless Chromium; and the documented one-shot external purge invocation.

Evidence PR: [#257](https://github.com/RkShanks/QueryCraft/pull/257)

## Result

| Status | Count |
|---|---:|
| Pass | 11 |
| Fail | 0 |
| Partial | 0 |
| Setup-dependent | 0 |
| Not run | 0 |
| Deferred | 0 |

## Requirement Matrix

| ID | Status | Automated Evidence | Browser/API Evidence | Notes |
|---|---|---|---|---|
| P6-FR-166 | Pass | Search integration, service, validation, retention-window, redaction, permission, and migration-index suites passed. Coverage includes every supported filter independently and combined; empty and Unicode inputs; malformed/reversed dates; control characters; invalid enums; injection-like values; parameterized ORM statements; mandatory retention predicates; and timestamp/sequence descending order. | Real isolated API searches returned the expected 0, 1, 100, 101, and 50,000 record sets. Combined and Arabic/Unicode filters were exact, expired rows were absent, injection-like text was treated as data, malformed values returned sanitized 422 responses, equal timestamps retained deterministic sequence order, and sensitive-value absence checks passed. | Search always intersects requested dates with the calendar-month cutoff and applies defense-in-depth redaction before serialization. |
| P6-FR-167 | Pass | Pagination tests passed for empty, first, middle, last, and beyond-last pages; page sizes 1 and 100; all illegal boundaries and overflow; equal timestamps; snapshot count/max-sequence consistency; and concurrent append behavior. | The 50,000-row live result produced 500 pages with exact first, middle, last, and empty page 501 metadata. Repeated equal-timestamp traversal had no duplicates or omissions. Zero, negative, malformed, over-100, and overflow values returned 422. | Offset pagination is stable within one count/upper-sequence snapshot. Inserts after that snapshot do not expand the request; separate later page requests can observe a newer snapshot, as documented. |
| P6-FR-168 | Pass | CSV/JSON endpoint, quota, permission, limit, empty/single/boundary, checksum, redaction, and hardening suites passed. Coverage includes 0, 1, 100, 101, 50,000, and 50,001 rows plus 422/429/503/403 denial behavior. | Real API exports at 0, 1, 100, 101, and 50,000 rows returned exact counts, safe filenames, and correct media/disposition headers. The 50,001-row request returned 422; exhausted quota returned 429; unavailable quota returned 503; restricted access returned 403. Denied UI exports created zero object URLs, so no partial file was offered. Arabic/Unicode, delimiters, quotes, line breaks, and nested context remained parseable. | Limit, quota, availability, and permission checks complete before a downloadable response is created. |
| P6-FR-169 | Pass | Export metadata tests verify actor, UTC timestamp, sanitized filter summary, record count, format, and checksum for zero-row and maximum-size exports. Independent checksum tests cover exact CSV data bytes and canonical JSON records. | Independent live recomputation matched CSV and JSON checksums at small and 50,000-row boundaries. Metadata counts matched parsed rows; expected metadata fields were present; row values and sensitive filter content were absent. | Checksums cover emitted records, excluding the metadata wrapper/line. Evidence retains only boolean absence results, never probe values. |
| P6-FR-170 | Pass | Shared recursive redaction suites cover nested dictionaries/lists, key case variants, safe-looking keys, authorization material, credential shapes, database connection material, hosts, stack traces, hostile content, federation material, and bounded encoded representations. Search and both export formats use the same defense pass. | Value-safe live scans of search, CSV, and JSON were negative at 50,000 rows while required redaction markers were present. No probe value was written to evidence, screenshots, or logs. | Defense-in-depth redaction is applied to every serialized entry field and compliance metadata, not only context keys. |
| P6-FR-171 | Pass | CSV hardening tests cover all documented leading formula operators after spaces, tabs, line breaks, BOM/control prefixes, and in entry and metadata cells. Tests also parse the emitted CSV and preserve legitimate Arabic/Unicode. | Five live formula-shaped entry cases were conservatively tab-prefixed, the 101-row export parsed to the exact row count, and Arabic/Unicode survived. | The documented conservative prefixing contract was preserved; it was not narrowed to trim-only or first-character-only detection. |
| P6-FR-172 | Pass | Search/export self-audit suites verify one bounded event per operation, allowlisted metadata, recursion suppression, repeated calls, and sanitized failure paths. Context contains only sanitized filters, count, and export format where applicable. | Repeated real searches grew self-audit events linearly by one per request. Live search/export event inspection found no returned row, resource value, sensitive filter content, or exported data. | Internal self-audit writes do not recursively audit themselves. Failure responses remain sanitized and bounded. |
| P6-FR-173 | Pass | Calendar-month tests cover month ends, leap years, timezone-aware dates, exactly-at and just-before cutoff, older requested ranges, and matching search/export/purge semantics. | Three live expired rows were absent from search/export and did not affect counts or checksums. The documented purge removed exactly those three; the retained chain remained verified. | Cutoffs use UTC calendar-month subtraction, not a fixed number of days. |
| P6-FR-174 | Pass | Runner, packaging, retention, purge, transaction rollback, and failure-exit suites passed. Cron, Kubernetes, and systemd examples were source-checked with docs-guard; the backend image contains the runner. | The exact documented one-shot command succeeded against isolated Postgres, then a repeated invocation completed as a no-op. It emitted only the purged count, used deterministic success/failure exits, and exposed no next-run timing. | Scheduling remains external. No permanent scheduler was installed and the application makes no scheduling claim. |
| P6-FR-175 | Pass | Normal, purge-gap, all-purged, marker-only, exact-cutoff, repeated-purge, append-after-purge, multi-marker, rollback, tamper, fake/missing/later marker, concurrency, immutability, exact-break, and bounded-verification suites passed. Verification uses a documented 500-row keyset batch, an upper sequence snapshot, and no complete-log `.all()`. A 1,001-row regression observed three capped batches; tampering and purge markers cross batch boundaries without losing exact `entries_checked` or `first_break_at`. | A valid live chain exceeding 50,000 rows verified before and after purging three expired rows, with no break and an exact purge marker. Concurrent work remained bounded by the upper snapshot and transaction lock. | C6-M02 is resolved, not deferred. Purge marker validity includes its own hash, predecessor link, removed range/count, and retained boundary; incoherent markers cannot hide tampering. |
| P6-FR-176 | Pass | Retention API/client and Admin Audit suites cover never-purged/post-purge data, exact fields, parsing, loading, empty, malformed, unavailable, forbidden, locale, accessibility, and responsive layout. | The real panel showed 24 months, the purge timestamp, and purged count 3. Mocked loading/empty/malformed/503/403 states were localized. EN/LTR and AR/RTL passed at 1440px, 768px, and 375px with no raw keys or horizontal clipping; restricted real APIs returned 403. | Narrow results render as labeled cards while desktop retains the table. The panel exposes no scheduler implementation or next-run field. |

## Regression Fixes

- [PR #249](https://github.com/RkShanks/QueryCraft/pull/249) — **C6-M02 / Mid availability and performance**: replaced complete retained-log materialization with bounded 500-row keyset verification and a fixed upper boundary.
- [PR #250](https://github.com/RkShanks/QueryCraft/pull/250) — **Search/pagination security and correctness**: added canonical validation, deterministic snapshot ordering, calendar retention, and shared serialized redaction.
- [PR #251](https://github.com/RkShanks/QueryCraft/pull/251) — **Export security**: closed recursive redaction, encoded-value, formula-prefix, and emitted-byte checksum gaps.
- [PR #252](https://github.com/RkShanks/QueryCraft/pull/252) — **Operational invocation**: shipped and packaged the previously missing one-shot external purge runner and corrected its operational examples.
- [PR #253](https://github.com/RkShanks/QueryCraft/pull/253) — **Chain integrity**: rejected malformed or tampered purge markers that could otherwise bridge an incoherent retained gap.
- [PR #254](https://github.com/RkShanks/QueryCraft/pull/254) — **Migration correctness**: preserved Phase 5 audit indexes when migration 009 is downgraded to 008.
- [PR #255](https://github.com/RkShanks/QueryCraft/pull/255) — **Frontend fail-closed parsing**: rejected empty/malformed retention responses and completed localized panel states.
- [PR #256](https://github.com/RkShanks/QueryCraft/pull/256) — **Responsive UI**: fixed result/action clipping at 768px and 375px with accessible EN/AR layouts.

Every confirmed defect was reproduced before its fix, received a RED-before-GREEN regression, passed both `backend-test` and `frontend-test`, was squash-merged, and had its branch deleted.

## Automated Validation

| Gate | Result |
|---|---|
| Discovered audit search/export/redaction/purge/verify/retention, quota-export, permission, and migration suites | Passed within focused slices and the full backend gate |
| Focused search/export/redaction slice | 704 passed; 2 skipped |
| Focused purge/verify slice | 48 passed |
| Affected audit/quota/retention slice | 812 passed; 12 skipped |
| Relevant migration unit suite | 19 passed |
| Isolated Postgres migration cycle | 008 → 009 → 008 passed; inherited action, actor, and timestamp indexes remained |
| Full backend pytest on tested product HEAD | 2,684 passed; 17 skipped; 4 non-failing warnings; 35 subtests passed |
| Ruff check | Pass |
| Ruff format check | Pass; 405 files already formatted |
| Admin Audit page, audit API client, locale, and RTL tests | Passed within full Vitest |
| Full Vitest on tested product HEAD | 65 files passed; 802 tests passed |
| ESLint | Pass |
| TypeScript typecheck | Pass |
| Production build | Pass; existing non-failing chunk-size warning |
| CSS lint | Pass |
| Live responsive Playwright/Chromium | 6 locale/viewport combinations passed plus loading/error/permission states |
| Fix PR CI | `backend-test` and `frontend-test` passed for PRs #249 through #256 |
| `rtk git diff --check` | Pass |

The four backend warnings were non-failing existing AsyncMock/FastAPI test warnings. No gate was weakened or excluded to obtain closure.

## Browser and API Verification

- Chrome DevTools MCP exercised the real isolated Admin Audit page and API. Headless Chromium covered EN/LTR and AR/RTL at 1440px, 768px, and 375px; all six captures have no raw locale keys, document overflow, or clipped audit fields/actions.
- Search returned exact empty, single, 100, 101, and 50,000 boundaries; all invalid inputs returned sanitized 422 responses. Stable equal-timestamp order and first/middle/last/beyond-last metadata passed.
- CSV and JSON returned exact boundaries through 50,000 rows with independently verified checksums, safe filenames, correct headers, parseable Unicode, and negative sensitive-value scans. The 50,001, quota, quota-unavailable, and permission denials created no download object.
- Search/export self-audit metadata stayed allowlisted and grew linearly without recursive logging.
- The retention panel passed never-purged and post-purge contracts plus loading, empty, malformed, unavailable, and forbidden states.
- The exact external scheduler invocation purged three expired rows, then completed a repeated no-op. Verification remained valid across the resulting purge marker.

## Isolation, Leakage, and Cleanup

- All destructive, large-chain, purge, cutoff, redaction, quota-failure, and concurrency checks used disposable Phase 6C Postgres, source Postgres, Redis, backend, frontend, and session-helper services. The normal development audit database was never tampered with or purged.
- Evidence contains no credential, cookie, session identifier, raw audit row, sensitive filter value, exported row value, hostile probe value, stack detail, or federation material. Value-safe scans retained only boolean absence results, public statuses, counts, and contract field names.
- The isolated application, frontend, helper, Chrome page, three containers, network, three volumes, migration database, and temporary scripts were removed. No permanent scheduler, helper, export file, or isolated session remains.
- Normal development images were rebuilt from the tested product HEAD, migrations were applied, and the normal backend OpenAPI endpoint and frontend root each returned HTTP 200 afterward.
- Pre-existing dirty Phase 5 PNGs and historical Phase 1/2 screenshots/traces were not staged, edited, deleted, or reverted. Only the six fresh Phase 6C responsive screenshots accompany this evidence.

Phase 6C is complete at 11/11 Pass. Phase 6D is unblocked but was not started.
