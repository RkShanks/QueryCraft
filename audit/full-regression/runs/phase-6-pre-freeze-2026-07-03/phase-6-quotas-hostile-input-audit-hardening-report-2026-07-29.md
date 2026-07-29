# Phase 6 Quotas, Hostile Input, and Audit Hardening — Final Regression

Run date: 2026-07-29

Scope: Phase 6D final regression and consolidation only. The cross-phase matrix,
implementation-surface gap audit, independent final audit, T-905, and freeze
work were not started.

Expected synchronized starting main: `46109ec88b872e02b88c1e7fa8804581eca57397`

Tested product HEAD: `957fa7dccb105883e3671a2fa658b9644be3a31c`

Runtime: isolated platform Postgres and Redis, temporary roles and sessions,
temporary source Postgres, real backend APIs, the configured real LLM for one
benign request, headless Chromium, and Chrome DevTools MCP.

## Evidence Basis

- [Phase 6A accepted report](phase-6a-quotas-report-2026-07-28.md) supplies the
  nine quota rows. Those accepted live checks were not repeated or rewritten.
- [Phase 6B accepted report](phase-6b-detection-report-2026-07-28.md) supplies
  the ten detection rows. Those accepted live checks were not repeated or
  rewritten.
- [Phase 6C accepted report](phase-6c-audit-hardening-report-2026-07-29.md)
  supplies the eleven audit-hardening rows. Those accepted live checks were not
  repeated or rewritten.
- [Current-head browser evidence](phase-6-current-head-browser-evidence-2026-07-29.json)
  records the four final rows, the responsive matrix, permission isolation,
  integrated browser/API flow, gates, and cleanup.

## Result

| Status | Count |
|---|---:|
| Pass | 34 |
| Fail | 0 |
| Partial | 0 |
| Setup-dependent | 0 |
| Not run | 0 |
| Deferred | 0 |

## Requirement Matrix

| ID | Status | Evidence |
|---|---|---|
| P6-FR-147 | Pass | Accepted 6A: quota CRUD/status, validation, exact permission, audit sanitization, and uncapped reset passed through real APIs and backend suites. |
| P6-FR-148 | Pass | Accepted 6A: isolated real-Redis atomic counters, dimensions, UTC-day isolation, malformed-state recovery, and non-disclosure passed. |
| P6-FR-149 | Pass | Accepted 6A: EN/AR quota configuration and status UI, localized states, request isolation, and narrow layouts passed. |
| P6-FR-150 | Pass | Accepted 6A: 60-second cache, expiry, immediate revision invalidation, minimal serialization, stale-write protection, and fail-closed behavior passed. |
| P6-FR-151 | Pass | Accepted 6A: query, execution, and export quota ordering stopped downstream work on 429/503 and called it exactly once under limit. |
| P6-FR-152 | Pass | Accepted 6A: quota errors used the constant localized contract and omitted counter, limit, policy, role, SQL, provider, host, and stack details. |
| P6-FR-153 | Pass | Accepted 6A: unavailable, timeout, malformed, script-error, and recovery paths failed closed without downstream side effects. |
| P6-FR-154 | Pass | Accepted 6A: fractional-midnight TTL, positive bounds, missing-expiry repair, valid-expiry preservation, and concurrent rollover passed. |
| P6-FR-155 | Pass | Accepted 6A: durable configuration and denial audit events contained only allowlisted sanitized context. |
| P6-FR-156 | Pass | Accepted 6B: the five-rule detector, aggregation, singleton configuration, corrupt-state handling, and fail-closed ordering passed. |
| P6-FR-157 | Pass | Accepted 6B: all five hostile categories passed clear and weaker-signal English and Arabic coverage. |
| P6-FR-158 | Pass | Accepted 6B: sanitized blocked API/browser states cleared the rejected turn and exposed no detector or input detail. |
| P6-FR-159 | Pass | Accepted 6B: detection ran before quota and LLM; blocked stopped, while allowed/flagged continued through the evaluator contract. |
| P6-FR-160 | Pass | Accepted 6B: whitespace, punctuation, comments, Unicode, bidi, Arabic normalization, mixed-language, benign, and bounded-runtime coverage passed. |
| P6-FR-161 | Pass | Accepted 6B: extensible registry behavior, duplicate rejection, repeat imports, and production-registry integrity passed. |
| P6-FR-162 | Pass | Accepted 6B: exact security permission, threshold validation, singleton updates, safe audit context, EN/AR UI, and mobile controls passed. |
| P6-FR-163 | Pass | Accepted 6B: blocked/flagged audit durability, search/export visibility, and absence of the original rejected value passed. |
| P6-FR-164 | Pass | Accepted 6B: recursive hostile redaction and audit-write fail-closed composition prevented raw payload retention and downstream work. |
| P6-FR-165 | Pass | Accepted 6B: repeated blocks caused no hidden suspension, role/user mutation, lockout, or quota consumption. |
| P6-FR-166 | Pass | Accepted 6C: all search filters, retention intersection, deterministic ordering, validation, parameterization, redaction, and real boundaries passed. |
| P6-FR-167 | Pass | Accepted 6C: pagination bounds, snapshots, concurrent append behavior, equal-timestamp traversal, and 50,000-row metadata passed. |
| P6-FR-168 | Pass | Accepted 6C: CSV/JSON boundaries, safe downloads, 50,001 limit, quota, unavailable, permission, and no-partial-download behavior passed. |
| P6-FR-169 | Pass | Accepted 6C: sanitized compliance metadata and independently recomputed CSV/JSON checksums matched emitted records. |
| P6-FR-170 | Pass | Accepted 6C: shared recursive, value-based redaction protected search, CSV, JSON, and metadata at maximum size. |
| P6-FR-171 | Pass | Accepted 6C: conservative CSV formula-prefix hardening and Arabic/Unicode preservation passed. |
| P6-FR-172 | Pass | Accepted 6C: bounded search/export self-audit, recursion suppression, allowlisted context, and sanitized failures passed. |
| P6-FR-173 | Pass | Accepted 6C: UTC calendar-month retention semantics matched search, export, and purge at cutoff boundaries. |
| P6-FR-174 | Pass | Accepted 6C: the packaged one-shot purge runner succeeded, repeated as a no-op, rolled back on failure, and made no scheduling claim. |
| P6-FR-175 | Pass | Accepted 6C: bounded keyset verification, valid purge gaps, marker integrity, exact break reporting, concurrency, and large-chain behavior passed. |
| P6-FR-176 | Pass | Accepted 6C: retention API/panel contracts and loading, empty, malformed, unavailable, forbidden, accessible, EN/AR responsive states passed. |
| P6-FR-177 | Pass | Current head: built-in Admin seed/upgrade/idempotency, full unauthenticated/insufficient/exact API matrix, three least-privilege administrators, legacy lowercase role, spoof resistance, next-request revocation, routes, and navigation isolation passed. |
| P6-FR-178 | Pass | Current head: complete EN/AR key parity and Phase 6 states passed; dates, numbers, downloads, identifiers, hashes, SQL, accessible names, and live announcements preserved locale and direction contracts. |
| P6-FR-179 | Pass | Current head: 18 EN/AR surface/viewport combinations plus Chrome checks passed without overflow, clipping, overlap, physical-direction CSS, off-screen actions, or invisible keyboard focus. |
| P6-FR-180 | Pass | Current head: browser and API sanitization matrix passed for quota, hostile, detection, audit, export, retention, authorization, malformed input, and relevant dependency failures with fail-closed ordering and no prohibited retained value. |

## Phase 6D Permission Matrix

The built-in Admin contained `admin.quotas.manage`,
`admin.security.manage`, and `admin.audit.verify`. Migration from the earlier
revision upgraded an existing built-in Admin, and a second upgrade was
idempotent.

| Surface | Unauthenticated | Insufficient permission | Exact permission |
|---|---|---|---|
| Quota list, CRUD, and status | Sanitized 401 | Sanitized 403 | Success |
| Detection configuration read/update | Sanitized 401 | Sanitized 403 | Success |
| Audit search, CSV/JSON export, and retention | Sanitized 401 | Sanitized 403 | Success |
| Audit verify and verify status | Sanitized 401 | Sanitized 403 | Success |

The quota-only administrator made no roles, mappings, detection, or audit
requests. The security-only administrator made no quota or audit requests. The
audit-only administrator made no quota or detection requests. Direct navigation
to an unrelated surface was denied before that surface's API call. A legacy
lowercase role name succeeded only when its database role had the exact
permission. Spoofed role, role-name, permission, and role-identifier session
claims did not bypass current database authorization. Removing the database
permission changed the next protected response from success to 403 and the next
profile response exposed no stale permission.

## EN/AR, Accessibility, RTL, and Responsive Results

Locale coverage included quota configuration/status, detection configuration,
the hostile banner, audit search/results/pagination, CSV/JSON controls,
retention, validation, loading, empty, success, unavailable, malformed, and
restricted states. No raw translation key or English fallback appeared in
Arabic. Control labels and live-region announcements were localized.

Chrome DevTools verified Arabic document direction, the localized detection
timestamp, left-to-right isolation for its technical value, numeric threshold
accessible names, visible range/number focus rings, quota action visibility,
audit download/retention controls, and left-to-right spans for technical audit
values.

No-artifact Playwright checked quotas, detection, and audit in English and
Arabic at 1440px, 768px, and 375px. All 18 combinations had the correct
document language/direction, no page overflow, no clipped interactive control,
no untranslated key, no physical-direction class, and visible keyboard focus.
A permanent mobile regression additionally passed for both locales at 375px.

## Sanitized Error Matrix

| Path | Result | Sanitization and ordering |
|---|---|---|
| Query quota exceeded | 429, `error.quota_exceeded` | Browser/API localized; no prohibited quota detail; stopped before LLM and request side effects. |
| Query quota unavailable | 503, `error.service_unavailable` | Failed closed before LLM and source work. |
| Hostile input blocked | 400, `error.hostile_input_blocked` | Browser/API localized; textarea and rejected turn cleared; absent from DOM, history, storage, and audit serialized context; stopped before quota and LLM. |
| Detection configuration/service unavailable | Sanitized unavailable state | Constant localized service message; no rule, confidence, pattern, dependency, or exception detail; stopped before quota. |
| Invalid detection thresholds | 422 | Constant localized validation state; no constraint or internal configuration detail. |
| Malformed JSON or identifier | 422 or 400, including `error.validation.invalidUUID` | Constant localized validation response; no parser, model, database, or identifier internals. |
| Audit filters or pagination invalid | 422 | Constant localized validation response; no query or database detail. |
| Export over record limit | 422, `error.export_limit_exceeded` | No count, file, object URL, or partial download. |
| Export quota exceeded | 429, `error.quota_exceeded` | No counter or configured limit; stopped before export generation. |
| Export quota unavailable | 503, `error.service_unavailable` | Failed closed before export generation. |
| Retention malformed or unavailable | Localized malformed/unavailable state | No raw response, scheduler detail, database detail, or exception text. |
| Unauthenticated or forbidden | 401 `error.unauthorized`; 403 `error.forbidden` | No permission inventory, role data, or spoofed-claim effect. |
| Relevant database, Redis, and LLM failures | Sanitized 4xx/503 contract | Automated failure paths excluded hosts, ports, credentials, provider detail, stack traces, raw exception text, and prohibited downstream side effects. |

## Integrated Current-Head Flow

- An exact-permission administrator opened each Phase 6 page.
- Least-privilege administrators opened only their own surfaces and made zero
  unrelated admin requests.
- A browser-submitted hostile value was blocked before quota and LLM. It was
  cleared from the input and absent from DOM, history state, browser storage,
  and serialized audit context.
- A benign over-quota request returned a sanitized 429 before the LLM.
- A benign under-quota request produced one submit request, reached the real LLM
  path exactly once, returned 200, and completed source execution. No prompt,
  generated SQL, provider identity, or result value was retained in evidence.
- Audit search found the sanitized quota and detection events.
- Current-filter CSV and JSON downloads returned successful responses with the
  correct media and filename contracts.
- Arabic desktop and mobile admin surfaces remained usable.

## Regression Fixes

- [PR #258](https://github.com/RkShanks/QueryCraft/pull/258) — **High,
  authorization**: stopped stale server-side permission snapshots by resolving
  the current database role on every request; added next-request revocation
  regressions.
- [PR #259](https://github.com/RkShanks/QueryCraft/pull/259) — **High,
  accessibility/RTL**: added accessible threshold names and visible keyboard
  focus for detection controls.
- [PR #260](https://github.com/RkShanks/QueryCraft/pull/260) — **High,
  i18n/RTL**: added dedicated localized updated-time text, active-locale date
  formatting, and isolated left-to-right direction for the technical value.
- [PR #261](https://github.com/RkShanks/QueryCraft/pull/261) — **High,
  responsive usability**: prevented 375px quota action clipping and added a
  permanent EN/AR Playwright regression.

Each fix was reproduced and classified before editing, received a
RED-before-GREEN regression, passed the applicable test/clean-code guards and
both required CI jobs, was squash-merged, and had its branch deleted.

## Final Gates

| Gate | Result |
|---|---|
| Full backend pytest | 2,686 passed; 17 skipped; 35 subtests passed; 4 non-failing warnings |
| Current-head permission/detection/audit focused backend slice | 51 passed |
| Current-head sanitization slice, run sequentially | 33 passed |
| Ruff check | Pass |
| Ruff format check | Pass |
| Full frontend Vitest | 65 files and 804 tests passed |
| ESLint | Pass |
| TypeScript typecheck | Pass |
| Production build | Pass; existing non-failing chunk-size warning only |
| CSS lint | Pass |
| Locale parity and i18n audit | Pass |
| Logical-CSS and RTL audit | Pass |
| Permanent Phase 6D Playwright regression | 2 passed |
| Current-head responsive browser matrix | 18 combinations passed |
| Chrome DevTools real-use checks | Pass |
| Fix PR CI | `backend-test` and `frontend-test` passed for PRs #258 through #261 |
| `rtk git diff --check` | Pass |

The two audit-chain failures observed when a database-mutating ordering suite
was accidentally run concurrently with the sanitization slice were runner
interference in a shared test database. The unchanged sanitization slice passed
33/33 immediately when run sequentially.

## Isolation, Leakage, and Cleanup

- Permission, mutation, outage, and integrated checks used an isolated platform
  database and Redis plus temporary roles, sessions, quota configuration, source
  connection, and policy state.
- The integrated flow restored the original quota and removed its sessions,
  policy, connection, and counter state. The isolated containers, network,
  volumes, and temporary scripts were then removed.
- Evidence retains no credentials, cookies, session material, Redis keys,
  database connection material, provider detail, raw hostile value, generated
  SQL, source result, or raw audit row.
- Normal frontend and backend endpoints both returned HTTP 200 after cleanup.
- Pre-existing dirty Phase 5 PNGs and historical Phase 1/2 screenshots and
  traces were not staged, edited, deleted, or reverted. No fresh screenshot was
  necessary for Phase 6D.

Phase 6 exhaustive regression is complete at 34/34 Pass. The cross-phase matrix
is unblocked and was not started.
