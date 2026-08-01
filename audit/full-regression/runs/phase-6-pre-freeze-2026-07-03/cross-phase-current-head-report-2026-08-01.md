# Final Cross-Phase Current-Head Regression

Run completed: 2026-08-01  
Expected and synchronized starting main:
`4039c0c85370853b302a43794d416003c9356ae4`  
Final tested product HEAD:
`b07a9083b1da796a4e64390463aedb597e8fbd07`

Scope: Cross-Phase C and consolidation of the accepted
[Cross-Phase A](cross-phase-a-auth-query-report-2026-07-29.md) and
[Cross-Phase B](cross-phase-b-security-ui-report-2026-07-29.md) results. The
implementation-surface gap audit, independent final audit, T-905, and freeze
work were not started.

The runtime used isolated platform PostgreSQL, Redis, backend, frontend, and
deterministic dependency boundaries. One approved live provider call used
in-memory credentials only. Real local PostgreSQL, MySQL, and MSSQL sources
were exercised without retaining source values. The two source-mutating test
files ran only against disposable real-engine clones.

## Result

| ID | Status | Accepted evidence | Current-head evidence |
|---|---|---|---|
| XP-001 | Pass | Cross-Phase A authentication matrix. | Local Admin and isolated mapped OIDC authentication passed; non-admin local and restricted-route checks remained fail closed and sanitized. |
| XP-002 | Pass | Cross-Phase A connection/routing matrix. | PostgreSQL, MySQL, and MSSQL selected-session routing, policy visibility, introspection, and expected safe results passed through real APIs and adapters. |
| XP-003 | Pass | Cross-Phase A history/scoping matrix. | Two-user history remained isolated; a current-policy denial stopped provider/execution and added no false success history. |
| XP-004 | Pass | Cross-Phase A audit matrix. | Search, filtered JSON export, retention, and chain verification passed with sanitized evidence. |
| XP-005 | Pass | Cross-Phase A pipeline composition. | Focused current-head ordering proved hostile, quota, policy, evaluator, and dependency failures short-circuit before prohibited downstream work. |
| XP-006 | Pass | Cross-Phase A prompt-privacy matrix. | Memory-only capture retained the selected dialect and approved schema only; identity, restricted schema, secrets, and prior-connection context were absent. |
| XP-007 | Pass | Cross-Phase B read-only matrix. | A representative mutation was rejected before source execution and produced one durable sanitized failure audit with no success history. |
| XP-008 | Pass | Cross-Phase B locale/RTL matrix. | EN/AR desktop and mobile checks, locale parity, logical CSS, direction persistence, accessibility, and overflow sentinels passed. |
| XP-009 | Pass | Cross-Phase B responsive matrix. | The relevant Chromium suite and current Chrome sentinel found no clipped security action or page overflow at the required mobile widths. |
| XP-010 | Pass | Cross-Phase B audit-integrity matrix. | Current-head search/export/retention/verify passed; the final chain verified after allowed, denied, rejected, and failed actions. |
| XP-011 | Pass | Cross-Phase B permission matrix. | Exact-permission success and unrelated, missing, revoked, spoofed, and restricted-route denial checks passed without role-name bypass. |
| XP-012 | Pass | Cross-Phase B credential/redaction matrix. | Value-safe API, UI, audit, export, log, and browser-storage scans found no prohibited credential or sensitive value. |
| XP-013 | Pass | New dependency-composition execution. | Session, lock, quota counter, and quota-config-cache paths passed healthy, unavailable, timeout, malformed, command-error, lock-loss, restart, and no-restart recovery cases. |
| XP-014 | Pass | New provider execution. | One benign live request completed the full pipeline with exactly one external invocation; deterministic 429, 5xx, timeout, malformed, missing-SQL, oversized-context, and cancellation boundaries all failed locally and safely. |
| XP-015 | Pass | New real-source execution. | All three real databases passed health, introspection, policy, routing, dialect execution, expected results, negative cases, cleanup, and unchanged-schema checks. |
| XP-016 | Pass | Governance diff and task-state review. | Phase 6 remained pre-freeze; the prohibited closeout tasks, governance files, frozen Phase 1–5 files, and freeze metadata were not started or mutated. |
| XP-017 | Pass | New focused sentinel sweep. | Authentication, three dialects, isolation/denial, audit, pipeline/privacy, read-only, EN/AR/mobile, permissions/routes, and redaction were refreshed after the accepted security/UI fixes. |
| XP-018 | Pass | New final foundation gates. | Backend, frontend, lint, format, types, build, CSS, locale, Playwright, migrations, service health, evidence validation, leakage scans, and diff checks passed on the final product tree. |

## Totals

| Status | Count |
|---|---:|
| Pass | 18 |
| Fail | 0 |
| Partial | 0 |
| Setup-dependent | 0 |
| Not run | 0 |
| Deferred | 0 |

## Redis dependency composition

| Dependency path | Healthy behavior | Failure and recovery evidence |
|---|---|---|
| Session lookup/authentication | Existing session authenticated and the same session recovered after Redis restart. | Unavailable, timeout, malformed response, and command error returned the sanitized dependency contract. No chat, attempt, history, source execution, export, or false success audit was created. |
| Processing lock | One owner retained exclusive generation/execution. | Lock loss and Redis faults could not permit a second provider or executor call; one request succeeded and the competitor received the intended conflict outcome. |
| Quota counter | Atomic counters enforced query and execution limits without overshoot. | Every Redis failure failed closed before unmetered work. Restart recovered the durable counter state without application restart. |
| Quota configuration cache | Cached configuration refreshed and expired as specified. | Malformed/failed cache commands did not create an allow path; repository-backed recovery did not retain stale configuration. |

The disposable Redis service alone was stopped and restarted. Normal Redis was
never stopped. Focused dependency coverage passed 78 cases, and the final
opt-in Docker outage/recovery row passed independently. Failure/denial audits
remained transactionally durable where required, while failed requests left no
prohibited product side effect.

## Live provider and deterministic failure boundaries

One approved Gemini request traversed authentication, connection/policy,
detection, query quota, filtered prompt construction, provider, evaluator,
execution quota, source adapter, masking, history, and audit. The external
invocation count was exactly one and the expected safe result was returned.

The prompt and credential existed in memory only. Evidence contains no prompt,
API key, provider payload, request header, raw response, generated SQL, or
source value. Boolean capture proved role- and dialect-scoped context and the
absence of disallowed schema and secrets.

Thirty-eight deterministic provider-boundary cases covered rate limiting,
server failure, timeout, malformed payload, missing SQL, oversized context, and
cancellation. Each response was localized/sanitized, stopped before source
execution, and created no false success history or audit.

## Real source databases

| Source | Health and schema | Policy/routing/query result | Restoration |
|---|---|---|---|
| PostgreSQL | Healthy; 30 tables and 172 columns introspected. | Current role visibility and selected-session routing passed; the safe dialect request returned the expected three rows. | Remained healthy; schema and data unchanged. |
| MySQL | Started from stopped; 23 tables and 132 columns introspected. | Current role visibility and selected-session routing passed; the safe dialect request returned the expected three rows. | Returned to the exact stopped preflight state; schema and data unchanged. |
| MSSQL | Started from stopped; 15 tables and 142 columns introspected. | Current role visibility and selected-session routing passed; the safe dialect request returned the expected three rows. | Returned to the exact stopped preflight state; schema and data unchanged. |

Service unavailable, wrong credentials, invalid database/schema,
introspection failure, disabled/deleted connection, and stale selection cases
failed without provider work, source execution, rerouting, or false success.
Errors omitted credentials, driver details, hosts, connection strings, stack
traces, and provider internals. Temporary connections, policies, selected
state, schema cache, and disposable source clones were removed.

## Current-head sentinel

- Local Admin and mapped OIDC browser authentication passed; the mapped user
  saw only exact permitted navigation and APIs.
- Three-dialect selection and safe execution returned the expected bounded
  results. Two users remained isolated across history list/detail/session
  access, and a current-policy denial stopped all prohibited downstream work.
- Audit search found the intended sanitized failure context; filtered JSON
  export, 24-day retention visibility, and verification of the current chain
  passed.
- Prompt capture was memory-only and contained the chosen dialect/approved
  schema, while identity, source location, secret, restricted schema, and
  policy internals were absent.
- A representative non-read query was rejected with no source execution or
  success history and exactly one durable sanitized failure audit.
- The EN/AR desktop and mobile sweep passed direction, localization,
  accessibility, route restriction, exact-permission, credential/redaction,
  and overflow checks. The final Chrome render remained complete with no
  horizontal overflow.

The focused backend sentinel passed 328 tests. The relevant Chromium suite
passed 73 tests with one reviewed provider-placeholder skip. The frontend tree
was unchanged between the browser sentinel and final product HEAD. Later
product changes affected only application/source-pool shutdown; the exact
final backend tree then passed the complete backend partition and its
OpenAPI/lifespan regressions.

## Final foundation gates and skip review

| Gate | Result |
|---|---|
| Complete backend pytest | Non-source-mutating partition: 2,757 passed, 5 reviewed skips, 35 subtests passed, 4 existing non-failing warnings; source-mutating partition on disposable real engines: 15 passed. |
| OpenAPI 3.1 on-demand property sweep | 9 passed; the full exact OpenAPI sweep also passed with 35 subtests after the lifecycle fix. |
| Redis Docker outage/recovery | 1 passed when explicitly enabled. |
| Ruff check / format | Pass; 413 files formatted. |
| Complete frontend Vitest | 65 files and 838 tests passed. |
| ESLint / typecheck / production build | Pass; build retained only the known non-failing chunk-size warning. |
| CSS lint | Pass. |
| Locale parity / logical CSS | 6 files and 329 tests passed. |
| Relevant Playwright | 73 passed, 1 reviewed skip; all output used disposable storage. |
| Migration cycle | Upgrade to `009`, downgrade to `008`, and upgrade back to `009` passed on disposable PostgreSQL. |
| Docker/service health | Isolated services were healthy during execution; normal platform/source health passed after restoration. |
| JSON, ID, totals, matrix consistency | Pass. |
| Value-safe leakage scan | Pass. |
| `rtk git diff --check` | Pass. |

The five aggregate backend skips were reviewed individually: three
Schemathesis modules are deliberately on-demand and passed as a 9-test sweep;
one Docker outage row passed when enabled; one audit pagination test
intentionally skips when its fixture has fewer than two pages, while the same
module passed 17 other rows and current API pagination evidence is accepted.
The one Playwright skip is the historical full-stack provider-switch
placeholder; the required live provider success above replaces it. There were
no unexpected or hidden skips.

## Defects and pull requests

| PR | Classification | Resolution |
|---|---|---|
| [#287](https://github.com/RkShanks/QueryCraft/pull/287) | High product lock-exclusivity defect | Prevented lock loss from permitting concurrent duplicate generation/execution. |
| [#288](https://github.com/RkShanks/QueryCraft/pull/288) | High product dependency-sanitization defect | Made session Redis failure return the sanitized fail-closed contract. |
| [#289](https://github.com/RkShanks/QueryCraft/pull/289) | High product audit-durability defect | Preserved required sanitized failure/denial audits after request rollback. |
| [#290](https://github.com/RkShanks/QueryCraft/pull/290) | Test-fixture compatibility | Corrected evaluator-gate transaction mocks without changing product behavior. |
| [#291](https://github.com/RkShanks/QueryCraft/pull/291) | Contract harness plus product resource lifecycle | Enabled canonical OpenAPI 3.1 sweeps and closed the module-owned source pool at shutdown. |
| [#292](https://github.com/RkShanks/QueryCraft/pull/292) | Product lifecycle/testability regression | Closed foreign-event-loop source pools safely while preserving graceful same-loop shutdown. |

Every defect was reproduced before editing, fixed test-first, reviewed with
Test Guard and Clean Code Guard where applicable, passed both mandatory CI
jobs, squash-merged, and had its branch deleted.

## Governance, artifact handling, and cleanup

- Phase 6 remains pre-freeze. T-905 through T-909 remain unstarted. No final
  snapshot or freeze metadata was created, and no Phase 1–5 frozen governance
  file, `AGENTS.md`, Phase 6 task file, or orchestration log was modified.
- All disposable containers, attached anonymous volumes, network, helper
  images, platform database, sessions, provider boundary, browser output, and
  temporary directories were removed. Normal frontend and backend returned
  HTTP 200. PostgreSQL source remained healthy; MySQL and MSSQL were restored
  to stopped.
- The protected dirty baseline remains present and unstaged: fourteen tracked
  Phase 5/Wave 18 PNGs, seven untracked historical screenshots, and the
  pre-existing traces directory. None was staged, deleted, restored, reverted,
  or regenerated by final evidence authoring.
- Final evidence contains only safe counts, booleans, classifications, route
  categories, and commit/PR identifiers. It excludes credential material,
  cookies, identity claims, source locations or values, raw prompts, provider
  exchanges, generated SQL, raw audit entries, and stack traces.

All 18 cross-phase requirements pass. The implementation-surface gap audit is
unblocked and was not started.
