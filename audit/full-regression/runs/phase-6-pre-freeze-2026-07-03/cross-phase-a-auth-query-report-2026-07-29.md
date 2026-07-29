# Cross-Phase A Authentication and Query Regression

Run date: 2026-07-29

Scope: Cross-Phase A only, XP-001 through XP-006. Cross-Phase B, XP-007 and
later rows, the implementation-surface gap audit, independent final audit,
T-905, and freeze work were not started.

Expected and synchronized starting main:
`7ee642f4d5fcbc8e7a4b74a07fa14e701f138569`

Tested product HEAD:
`a3f1253f00ba40bb791086b5f9bdfa7256f9ca39`

Runtime: isolated platform PostgreSQL and Redis, isolated backend and frontend,
two isolated mock identity providers, temporary users, roles, policies,
sessions, connections, audit state, and an in-memory deterministic provider.
The local PostgreSQL, MySQL, and MSSQL source databases were exercised
read-only. Real-provider smoke remains assigned to Cross-Phase C.

## Result

| ID | Status | Automated Evidence | Browser/API Evidence | Notes |
|---|---|---|---|---|
| XP-001 | Pass | Current auth, local-login, SSO, callback, session, and sanitization slice: 229 passed. | Chrome local Admin login/sign-out, mapped OIDC and SAML login, user switching, and expired-session handling passed. API checks rejected non-admin and unknown local users equivalently and failed closed for unmapped identity, replay, expiry, state, nonce, signature, assertion, and cross-provider collision cases. | Normal provider configuration was not changed. Responses and retained evidence omitted enumeration detail, federation material, callbacks, cookies, provider internals, and constraint detail. |
| XP-002 | Pass | Current connection, routing, dialect, schema, and policy slice: 250 passed with one existing non-failing warning. | Real PostgreSQL, MySQL, and MSSQL health, introspection, policy, schema visibility, and masked query flows passed. Chrome proved one-connection auto-selection, required multi-connection selection, per-session persistence, session switching, and the localized no-healthy-connection state. Disabled, unhealthy, deleted, missing, and unauthorized selections stopped before provider work without rerouting. | Temporary connection deletion removed its policy/session/schema state. Query-facing APIs, UI, history, audit, logs, and evidence omitted credentials, driver internals, encrypted fields, and source locations. The privileged Phase 3 admin-management API retained its existing non-secret endpoint metadata contract and returned no credential or encrypted value. |
| XP-003 | Pass | Current history/scoping/rerun slice after fixture isolation: 103 passed and 1 intentionally skipped. Exact service-composition tests proved current-policy rerun denial, later restoration, and masking. | Two isolated SSO clients saw only their own accepted queries and sessions. Cross-user list totals, direct IDs, cursors, session detail, delete, and browser user switching remained scoped; stored results stayed masked. | The current public API has no standalone rerun route, so the locked rerun behavior was exercised at its existing service composition boundary without starting the excluded implementation-surface gap audit. Delete and permanent visibility remained user-scoped. |
| XP-004 | Pass | Current audit search, pagination, retention, export, redaction, checksum, formula-defense, permission, quota, and boundary slice: 543 passed, 1 intentionally skipped, and 2 non-failing warnings. | Using XP-001 through XP-003 events, an Admin searched, filtered, paginated, exported CSV and JSON, read retention, and verified the chain. Restricted clients received sanitized 403 responses. A temporary export limit proved first-use success and second-use 429 denial, then was restored. | Automated exact 50,000/50,001 boundaries avoided a permanent oversized dataset. Independently recomputed checksums matched. Recursive redaction and self-logging checks found no result rows, sensitive filters, identity claims, credentials, or source values. |
| XP-005 | Pass | Shared pipeline/privacy slice: 519 passed. The exact order/failure composition slice added 72 passed cases covering hostile detection, both quotas, policy/schema filtering, evaluation, sanitization, and dependency failures. | Real API composition and deterministic call counters proved all seven locked scenarios: hostile stop, query-quota stop, restricted prompt, evaluator stop, execution-quota stop, exactly-once safe flow, and sanitized fail-closed dependency failures. | Source-derived order is recorded below. It preserves detection before query quota, query quota before generation, filtered schema before provider invocation, evaluation before source execution, and execution quota before adapter execution. |
| XP-006 | Pass | Prompt privacy, policy, connection authorization, evaluator, and three-dialect cases passed within the 519-test shared slice. | Provider-bound context was captured in memory only for restricted PostgreSQL, MySQL, and MSSQL requests. It contained the selected dialect and approved schema identifiers only. A policy edit affected the next request, a connection switch removed prior schema context, and missing, unhealthy, or unauthorized connections prevented invocation. | Durable evidence contains only approved identifiers and boolean absence checks, never a complete prompt, identity/filter values, role internals, credentials, source locations, or result values. |

## Closure

| Status | Count |
|---|---:|
| Pass | 6 |
| Fail | 0 |
| Partial | 0 |
| Setup-dependent | 0 |
| Not run | 0 |
| Deferred | 0 |

## Current Query Call Order

The order was derived from
`backend/src/app/api/v1/query.py` and
`backend/src/app/services/query_service.py` before composing XP-005:

1. Validate the question.
2. Resolve the selected connection and require it to be authorized, active,
   healthy, and introspected.
3. Acquire the session lock and validate the current database user.
4. Load detection configuration and run hostile-input rules.
5. Stop a blocked request after its redacted audit write, before quota,
   session, attempt, provider, evaluator, adapter, or history work.
6. Write the redacted flagged audit event when applicable and continue.
7. Enforce query quota.
8. Create or validate the chat session and attempt, then write the submit
   audit event.
9. Load the current role policy and stop deny-all policy before generation.
10. Load only the caller's conversation history.
11. Filter schema by the current role policy.
12. Invoke the provider once with the selected dialect and filtered schema.
13. Evaluate generated SQL with the base evaluator.
14. Evaluate current role authorization.
15. Bind the row filter.
16. Enforce execution quota.
17. Execute once through the selected adapter.
18. Audit and mask the result.
19. Persist and return only the masked result.

The locked invariants and current source order agree. No product-order change
or deferred matrix wording change was made.

## Authentication and Session Results

- Built-in Admin local login succeeded. Non-admin local login and unknown-user
  login returned the same generic 401 contract.
- Browser OIDC and SAML authorization flows passed through separate isolated
  mock identity providers for mapped users.
- Unmapped identities, replayed and expired callbacks, invalid state, nonce,
  signature, and assertion cases, and a cross-provider identity collision all
  failed closed with localized or generic errors.
- Sign-out invalidated the session; expired and invalid sessions returned to the
  sign-in surface; changing users cleared the prior user's TanStack/session
  data and navigation.

## Connection, History, and Three-Dialect Results

- PostgreSQL, MySQL, and MSSQL each passed real health, introspection,
  restricted-schema, role-policy, dialect, execution, masking, and routing
  checks.
- The approved prompt schema was limited to
  `public.actor(actor_id, first_name)` for PostgreSQL,
  `actor(actor_id, first_name)` for MySQL, and
  `SalesLT.Address(AddressID, AddressLine1)` for MSSQL.
- One usable connection auto-selected. Multiple usable connections required a
  choice and retained it independently per session.
- No disabled, unhealthy, deleted, missing, or unauthorized selection silently
  switched to another source. With no healthy connection, submission was
  disabled with a localized state.
- Two SSO users remained isolated across history list, total, cursor, direct
  detail, session detail, delete, and browser cache transitions. Accepted and
  saved masked data remained masked.

## Audit and Prompt-Privacy Results

- Search, filtering, deterministic pagination, retention, CSV and JSON export,
  chain verification, quota denial, maximum boundary, recursive redaction,
  formula defense, and checksum verification passed.
- Restricted users received sanitized 403 responses and no audit navigation or
  data.
- Prompt capture was memory-only. Boolean checks confirmed absence of hidden
  tables and columns, identity claims, row-filter values, mask definitions,
  permission and role internals, credentials, source locations, and other
  connections.
- A role-policy edit applied on the next request. Switching connections changed
  both dialect and schema without retaining the prior source context.

## Defect Classification and Pull Requests

- [PR #263](https://github.com/RkShanks/QueryCraft/pull/263) — test-harness
  isolation: the integration fixture did not clear Redis or `role_quotas`
  between history tests.
- [PR #264](https://github.com/RkShanks/QueryCraft/pull/264) — Playwright
  test-harness isolation: the history spec left the session-list request
  unmocked, allowing the normal backend's correct 401 to trigger the global
  expired-session redirect.
- [PR #265](https://github.com/RkShanks/QueryCraft/pull/265) — Playwright
  locator defect: a desktop assertion selected the hidden mobile duplicate of
  an Arabic quota label.

All three were reproduced before editing, changed tests or fixtures only,
passed Test Guard, passed both `backend-test` and `frontend-test`, and were
squash-merged with branches deleted. Clean Code Guard found no production-code
diff to review. No product defect was confirmed.

A diagnostic Playwright run against the long-running normal frontend bundle
selected its older served build for two already-fixed mobile checks. A fresh
Vite server from the tested HEAD passed both checks and the full relevant
matrix. This runner target mismatch required no repository change.

## Final Gates

| Gate | Result |
|---|---|
| Full backend pytest | 2,686 passed; 17 skipped; 35 subtests passed; 4 existing non-failing warnings |
| Auth/SSO/session focused backend slice | 229 passed |
| Connection/routing/dialect/policy focused backend slice | 250 passed; 1 non-failing warning |
| History/scoping/rerun focused backend slice | 103 passed; 1 intentionally skipped |
| Audit focused backend slice | 543 passed; 1 intentionally skipped; 2 non-failing warnings |
| Pipeline/detection/quota/policy/evaluator/prompt focused backend slice | 519 passed |
| Exact XP-005 composition slice | 72 passed |
| Focused frontend Vitest slice | 120 passed |
| Ruff check | Pass |
| Ruff format check | 407 files already formatted |
| Full frontend Vitest | 65 files and 804 tests passed |
| ESLint | Pass |
| TypeScript typecheck | Pass |
| Production build | Pass; existing non-failing chunk-size warning only |
| CSS lint | Pass |
| Relevant Playwright on fresh tested source | 32 passed; 3 intentionally skipped |
| Chrome DevTools real browser checks | Pass |
| Fix PR CI | `backend-test` and `frontend-test` passed for PRs #263 through #265 |
| `rtk git diff --check` | Pass after evidence authoring |

## Leakage Controls and Cleanup

- Federation and credential material existed in memory only. Evidence excludes
  cookies, session material, callback content, identity/filter values, full
  prompts, generated SQL, source results, connection secrets, source
  locations, encrypted values, and raw audit rows.
- Value-safe log and response scans found none of the isolated secret markers,
  federation tokens/assertions, source locations, encrypted fields, or
  prohibited prompt fields.
- Temporary sessions, users, roles, policies, connections, schema cache, audit
  state, mock identity providers, helpers, databases, containers, networks,
  volumes, and images were removed. MySQL and MSSQL source containers returned
  to their prior stopped state.
- No isolated Cross-Phase A container, network, or volume remains. The normal
  frontend and backend each returned HTTP 200 after cleanup.
- An initial relevant Playwright discovery sweep invoked legacy specs that
  write to repository evidence paths. It rewrote the already-dirty Phase 5
  audit PNGs and ten tracked Wave 18 PNGs. None of those artifacts was staged,
  deleted, or reverted; they remain excluded local changes. Every subsequent
  screenshot-producing check ran from disposable storage, which was removed.
- Pre-existing historical Phase 1/2 screenshots and traces were not staged,
  edited, deleted, or reverted.

Cross-Phase A is complete at 6/6 Pass. Cross-Phase B is unblocked and was not
started.
