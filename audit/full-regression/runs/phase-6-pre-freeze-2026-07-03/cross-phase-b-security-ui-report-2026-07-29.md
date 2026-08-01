# Cross-Phase B Security and UI Regression

Run start: 2026-07-29  
Completed: 2026-08-01

Scope: Cross-Phase B only, XP-007 through XP-012. Cross-Phase C, XP-013 and
later rows, the implementation-surface gap audit, independent final audit,
T-905, and freeze work were not started.

Expected and synchronized starting main:
`7c7c103670375f762fa25f26688f2f466a044d72`

Tested product HEAD:
`9e8975b70fa949f91959b58757ab5ca385d83485`

Runtime: isolated platform PostgreSQL and Redis, isolated backend and frontend,
temporary users, roles, permissions, policies, connections, sessions,
providers, and audit state, plus an in-memory deterministic provider. The local
PostgreSQL, MySQL, and MSSQL source databases were exercised read-only. The two
test files that intentionally create or alter source objects ran only against
disposable real-engine clones. Real-provider smoke remains assigned to
Cross-Phase C.

## Result

| ID | Status | Automated Evidence | Browser/API Evidence | Notes |
|---|---|---|---|---|
| XP-007 | Pass | Full backend coverage passed. The final source-clone gate added 15/15 read-only and cross-dialect policy cases. Focused execution-failure coverage passed 18 service cases, 63 adjacent query/rerun/source cases, and 2 migrated ASGI cases. | Real adapters accepted 24 valid read classes across PostgreSQL, MySQL, and MSSQL and rejected 24 mutation, external-access, obfuscation, multi-statement, and authorization classes before execution. Final-head API checks executed a safe PostgreSQL read, rejected unsafe SQL without a success audit, and persisted exactly one sanitized failure audit after a live 502 rollback. | Real source schemas and table counts were unchanged. Application credentials remained read-only. CTEs, nested queries, aggregates, joins, windows, aliases, pagination, row filters, and masks passed. Rejections never produced history/result success claims. |
| XP-008 | Pass | Six explicit locale/logical-CSS files passed 325 checks; full Vitest passed 65 files and 838 tests; the relevant Chromium suite passed 73 with one intentional real-provider skip. | An authenticated 54-surface sweep covered nine routes in EN/AR at 1440, 375, and 768 pixels. It checked 2,262 controls with zero raw keys, Arabic fallback, unnamed/clipped controls, overflow, console errors, or failed requests. Final-head Chrome revalidated EN LTR and AR RTL, reload persistence, focus, accessible names, and zero fallback/key leakage. | SQL, code, hashes, identifiers, timestamps, filenames, database identifiers, connection values, thresholds, and numeric settings remained LTR where required. |
| XP-009 | Pass | Full Vitest and the 73-pass Chromium slice covered the mobile shell, role actions, connection forms, policy/security direction, quotas, history, and responsive regressions. | The 375/768 authenticated sweep covered roles, mappings, policy controls, connection and SSO forms, quota/detection/audit controls, filters, export/retention, dialogs, banners, toasts, pagination, and sidebar close/reopen. No page overflow, overlap, clipped action, off-screen control, or unauthorized background call occurred. | Internal table/scroll containers retained reachable actions. Keyboard focus was visible. Physical-direction CSS audits passed. |
| XP-010 | Pass | Isolated tamper/retention harnesses verified a 625-entry pre-purge chain and 626-entry post-purge chain, exact first-break reporting, snapshot-bounded concurrency, large-chain batching, purge rollback safety, and ORM/API update/delete denial. Full backend pytest passed all current audit tests. | Fifteen representative action classes were generated across authentication, role/mapping/policy, SSO, connection, query, quota, detection, history, export, denial, rejection, and logout paths. Final-head API chain verification passed after allowed, rejected, and failed query events. | Missing, fake, mismatched, reordered, duplicated, or later purge markers could not conceal the first break. Search/export respected retention and redaction. All tamper and purge mutation occurred only in isolated platform databases. |
| XP-011 | Pass | Source inventory found 38 current admin route/method combinations: 37 permission-gated routes plus one legacy-key route. The complete matrix passed unauthenticated, unrelated-permission, spoofed-claim, revoked-permission, legacy-role-name, exact-permission, and built-in Admin protection cases. | The authenticated UI sweep covered all current admin navigation and direct routes. Six unauthorized direct routes redirected or denied with zero unauthorized background requests. Final-head API checks returned sanitized 401 for unauthenticated admin access and intended success for the built-in Admin. | Connections, settings, SSO, roles, mappings, policy preview, quotas, detection, audit search/export/retention/verify/status were included. No full implementation-surface gap audit was started. |
| XP-012 | Pass | Full backend/frontend gates and focused storage, recursive redaction, logging, export, schema, SSO, and connection tests passed. Canonical OpenAPI marks connection and SSO secrets write-only and omits endpoint/credential fields from response schemas. | Final-head API checks confirmed connection list/read/update responses, user connection responses, public SSO responses, localized errors, and audit search contained no secret fields or values. HttpOnly session handling and masked secret-preserving edits passed. The 54-surface browser sweep found no redisplayed secret or browser-storage leak. | Value-safe probes covered nested structures, safe-looking keys, case variants, encoded and formula-shaped values, credentials, tokens, cookies, headers, identity claims, filters, stack traces, and hostile payloads. No actual probe value appears in evidence. |

## Closure

| Status | Count |
|---|---:|
| Pass | 6 |
| Fail | 0 |
| Partial | 0 |
| Setup-dependent | 0 |
| Not run | 0 |
| Deferred | 0 |

## Three-Dialect Read-Only Results

- PostgreSQL, MySQL, and MSSQL each passed real-adapter SELECT, CTE, nested,
  aggregate, join, window, alias, dialect-pagination, masked, and row-filtered
  reads.
- INSERT, UPDATE, DELETE, MERGE, CREATE, ALTER, DROP, TRUNCATE,
  GRANT/REVOKE, procedure invocation, writable CTE and SELECT INTO forms,
  COPY/LOAD/OUTFILE/BULK/OPENROWSET-style access, multi-statements,
  comment-obfuscated writes, and unauthorized alias/CTE/nested projections
  stopped before adapter execution.
- The source-side roles remained read-only as defense in depth. Pre/post schema
  and table-count snapshots matched, and the final live failure response was
  localized and sanitized.
- The final durable-failure regression proved request rollback occurs before a
  sanitized failure audit is appended and committed. If audit persistence
  itself fails, the error propagates and no commit occurs.

## Locale, RTL, and Responsive Results

- The authenticated browser matrix covered workspace/query, history/detail,
  settings, connections, roles, mappings, policy editor/preview, quotas,
  detection, audit, export, retention, dialogs, banners, toasts, and
  loading/empty/error states in EN and AR at desktop, 375px, and 768px.
- Root and body direction switched LTR/RTL correctly. Final-head Chrome proved
  Arabic direction survived reload. No raw translation key or English fallback
  remained in the Arabic surface.
- Mobile security actions remained reachable, including role actions,
  group-mapping controls, multi-column masks, connection and SSO forms,
  quota/detection/audit controls, retention/export, sidebar controls, and long
  localized labels.
- Focus order, visible focus, accessible names/statuses, internal scrolling,
  and technical-value LTR isolation passed.

The exhaustive authenticated UI sweep ran on
`db41b45a87a69f506cdea5da00650a2213d9f5de`. The only product changes between
that commit and the tested product HEAD were backend query-audit logic, backend
tests, and the canonical OpenAPI document; the frontend tree was identical.
Chrome DevTools and the 73-pass Playwright slice then revalidated the final
frontend bundle built from the tested product HEAD.

## Audit, Permission, and Redaction Results

- Representative actions included SSO validation, role update, mapping change,
  SSO configuration change, connection update, query execution, quota
  configuration and denial, detection configuration and hostile blocking,
  history view, audit export, access denial, query rejection, and logout.
- Valid chains verified before and after retention purge. Context tampering,
  missing rows, reordered sequences, duplicate sequences, and invalid markers
  reported the exact first break. Concurrent append/verify/purge stayed bounded
  to the captured snapshot; batching remained bounded.
- Application and ORM paths could not update or delete audit rows. Failed purge
  transactions could not leave deletion without a durable valid marker.
- All 37 permission-gated admin routes denied unauthenticated, unrelated,
  legacy-name, and spoofed callers and accepted the exact permission. Revocation
  took effect on the next request. The legacy API-key route retained only its
  intended valid-key behavior.
- Secrets were accepted on write and never redisplayed. Masked edits preserved
  existing connection and OIDC secrets. Boolean/value-safe checks found no
  secret probe in API/UI/browser storage, application logs, history, audit
  search, CSV/JSON export, accessibility text, or committed evidence.

## Defect Classification and Pull Requests

Each defect was reproduced before editing, fixed in a focused branch with TDD,
reviewed with Test Guard and Clean Code Guard where applicable, passed both
`backend-test` and `frontend-test`, and was squash-merged with its branch
deleted.

| PR | Classification | Resolution |
|---|---|---|
| [#267](https://github.com/RkShanks/QueryCraft/pull/267) | High product UI/security reachability | Restored the mobile sidebar toggle. |
| [#268](https://github.com/RkShanks/QueryCraft/pull/268) | High read-only evaluator false denial | Allowed valid read-only CTEs without weakening write rejection. |
| [#269](https://github.com/RkShanks/QueryCraft/pull/269) | High accessibility/localization | Added the missing localized prompt accessible name. |
| [#270](https://github.com/RkShanks/QueryCraft/pull/270) | High systematic RTL defect | Isolated technical values with logical bidi handling. |
| [#271](https://github.com/RkShanks/QueryCraft/pull/271) | High frontend credential exposure | Made connection credentials write-only in the UI. |
| [#272](https://github.com/RkShanks/QueryCraft/pull/272) | High backend credential exposure | Removed connection host/username from responses and marked request secrets write-only. |
| [#273](https://github.com/RkShanks/QueryCraft/pull/273) | High audit/redaction defect | Added recursive persisted-audit redaction and formula-value defense. |
| [#274](https://github.com/RkShanks/QueryCraft/pull/274) | High application-log redaction defect | Hardened application and structured-log redaction. |
| [#275](https://github.com/RkShanks/QueryCraft/pull/275) | High responsive navigation defect | Preserved collapsed-sidebar accessible names. |
| [#276](https://github.com/RkShanks/QueryCraft/pull/276) | High mobile authorization-control defect | Kept role table actions reachable at 375px and 768px. |
| [#277](https://github.com/RkShanks/QueryCraft/pull/277) | High RTL form defect | Kept connection technical controls LTR. |
| [#278](https://github.com/RkShanks/QueryCraft/pull/278) | High row-policy enforcement defect | Corrected row-filter physical-scope binding. |
| [#279](https://github.com/RkShanks/QueryCraft/pull/279) | High source-boundary disclosure defect | Sanitized source execution errors across query paths. |
| [#280](https://github.com/RkShanks/QueryCraft/pull/280) | High SSO contract defect | Marked OIDC/SAML secret inputs write-only. |
| [#281](https://github.com/RkShanks/QueryCraft/pull/281) | High RTL settings defect | Isolated numeric settings direction. |
| [#282](https://github.com/RkShanks/QueryCraft/pull/282) | High RTL detection defect | Isolated detection-threshold direction. |
| [#283](https://github.com/RkShanks/QueryCraft/pull/283) | High localization defect | Removed the history-detail English fallback/missing locale action. |
| [#284](https://github.com/RkShanks/QueryCraft/pull/284) | High canonical-contract disclosure defect | Aligned OpenAPI connection responses with the runtime omission contract. |
| [#285](https://github.com/RkShanks/QueryCraft/pull/285) | High audit-durability defect | Persisted sanitized source-failure audits after request rollback across submit, regenerate, and rerun. |

## Final Gates

| Gate | Result |
|---|---|
| Full backend pytest, non-mutating main invocation | 2,736 passed; 15 intentionally skipped; 35 subtests passed; 4 existing non-failing warnings |
| Source-mutating files on disposable real-engine clones | 15 passed |
| XP-007 durable failure focused service/adjacent/ASGI | 18 passed; 63 passed; 2 passed |
| Ruff check | Pass |
| Ruff format check | 412 files already formatted |
| Full frontend Vitest | 65 files and 838 tests passed |
| Locale and logical-CSS focused Vitest | 6 files and 325 tests passed |
| ESLint | Pass |
| TypeScript typecheck | Pass |
| Production build | Pass; existing non-failing chunk-size warning only |
| CSS lint | Pass |
| Relevant Playwright with disposable output | 73 passed; 1 intentional real-provider smoke skip |
| Chrome DevTools final-head checks | Pass |
| Fix PR CI | `backend-test` and `frontend-test` passed for PRs #267 through #285 |
| `rtk git diff --check` | Pass after evidence authoring |

## Leakage Controls and Cleanup

- Evidence contains booleans, counts, categories, commit identifiers, and safe
  route/test metadata only. It excludes cookies, authorization headers,
  credentials, federation material, identity/filter values, hostile input,
  source locations, full prompts, generated SQL, source results, encrypted
  values, raw audit rows, and stack traces.
- All isolated containers, networks, volumes, databases, deterministic/mock
  providers, helper images, sessions, and temporary browser output were
  removed. No Cross-Phase B or XP-007 Docker/temp resource remains.
- MySQL and MSSQL returned to their preflight stopped state. PostgreSQL and the
  normal platform PostgreSQL/Redis/backend/frontend are healthy; normal backend
  and frontend each returned HTTP 200 after cleanup.
- The protected dirty baseline remained present and unstaged: fourteen tracked
  Phase 5/Wave 18 evidence PNGs, seven historical Phase 1/2 screenshots, and
  the pre-existing traces directory. None was staged, edited by this chunk,
  deleted, regenerated, restored, or reverted.

Cross-Phase B is complete at 6/6 Pass. Cross-Phase C is unblocked and was not
started.
