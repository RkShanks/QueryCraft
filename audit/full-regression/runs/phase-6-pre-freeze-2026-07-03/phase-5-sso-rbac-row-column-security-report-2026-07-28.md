# Phase 5 Current-Head SSO, RBAC, Row/Column Security Regression

Run date: 2026-07-28

Scope: Phase 5B2 completion only; prior Phase 5A and Phase 5B1 handoffs were accepted inputs

Starting synchronized main HEAD: `cd98d13cf1d1a210599ccaff19436fd4b9995217`

Tested product HEAD: `db5688aaee2dd8e65719908520f3b2765398d6ce`

Runtime: isolated QueryCraft platform PostgreSQL, Redis, backend, frontend, and in-memory mock IdP

## Result

| Status | Count |
|---|---:|
| Pass | 32 |
| Fail | 0 |
| Partial | 0 |
| Setup-dependent | 0 |
| Not run | 0 |
| Deferred | 0 |

## Requirement Matrix

| ID | Status | Automated Evidence | Browser/API Evidence | Notes |
|---|---|---|---|---|
| P5-FR-115 | Pass | Accepted Phase 5A handoff (15/15); starting HEAD includes the isolated IdP harness and SSO fixes from PRs #215-#220. | Validated prior handoff; not repeated during B2. | OIDC configuration and masking remain accepted. |
| P5-FR-116 | Pass | Accepted Phase 5A handoff; SAML harness and validation fixes are in PRs #215-#219. | Validated prior handoff; not repeated during B2. | SAML metadata/certificate masking remains accepted. |
| P5-FR-117 | Pass | Accepted Phase 5A handoff; isolated OIDC browser harness is in PR #215. | Validated prior handoff; not repeated during B2. | OIDC sign-in remains accepted. |
| P5-FR-118 | Pass | Accepted Phase 5A handoff; SAML redirect/assertion fixes are in PRs #216-#219. | Validated prior handoff; not repeated during B2. | SAML sign-in remains accepted. |
| P5-FR-119 | Pass | Accepted Phase 5A handoff; callback and collision hardening are in PRs #215-#220. | Validated prior handoff; not repeated during B2. | Callback validation remains accepted. |
| P5-FR-120 | Pass | Accepted Phase 5A handoff and focused local-login restriction coverage. | Validated prior handoff; not repeated during B2. | Local admin-only login remains accepted. |
| P5-FR-121 | Pass | Accepted Phase 5A handoff and sign-in provider component coverage. | Validated prior handoff; not repeated during B2. | Provider discovery remains accepted. |
| P5-FR-122 | Pass | Accepted Phase 5A handoff and role endpoint/policy-editor coverage. | Validated prior handoff; not repeated during B2. | Role creation and policy editing remain accepted. |
| P5-FR-123 | Pass | Accepted Phase 5A handoff and role update/query-policy coverage. | Validated prior handoff; not repeated during B2. | Next-query policy enforcement remains accepted. |
| P5-FR-124 | Pass | Accepted Phase 5A handoff and role deletion/unmapped-user coverage. | Validated prior handoff; not repeated during B2. | Role deletion behavior remains accepted. |
| P5-FR-125 | Pass | Accepted Phase 5A handoff and group-mapping uniqueness coverage. | Validated prior handoff; not repeated during B2. | Group mapping remains accepted. |
| P5-FR-126 | Pass | Accepted Phase 5A handoff and unmapped-user denial coverage. | Validated prior handoff; not repeated during B2. | Unmapped denial remains accepted. |
| P5-FR-127 | Pass | Accepted Phase 5A handoff and full permission-gate matrix. | Validated prior handoff; not repeated during B2. | UI/API permission enforcement remains accepted. |
| P5-FR-145 | Pass | Accepted Phase 5A handoff and role-priority resolution coverage. | Validated prior handoff; not repeated during B2. | Lowest numeric priority remains accepted. |
| P5-FR-146 | Pass | Accepted Phase 5A handoff and built-in admin lockout-prevention coverage. | Validated prior handoff; not repeated during B2. | Built-in local-admin safety net remains accepted. |
| P5-FR-128 | Pass | Accepted Phase 5B1 handoff (9/9); current focused schema-filtering coverage passed. | Validated prior handoff; not repeated during B2. | Restricted schema context remains accepted. |
| P5-FR-129 | Pass | Accepted Phase 5B1 handoff; current query-policy coverage passed. | Validated prior handoff; not repeated during B2. | Provider prompt filtering remains accepted. |
| P5-FR-130 | Pass | Accepted Phase 5B1 handoff; current evaluator authorization coverage passed. | Validated prior handoff; not repeated during B2. | Pre-execution blocking remains accepted. |
| P5-FR-131 | Pass | Accepted Phase 5B1 handoff; row-filter fixes are in PRs #223 and #224. | Validated prior handoff; not repeated during B2. | PostgreSQL/MySQL/MSSQL enforcement remains accepted. |
| P5-FR-132 | Pass | Accepted Phase 5B1 handoff; masking fixes are in PRs #221, #222, and #225. | Validated prior handoff; not repeated during B2. | Cross-dialect result masking remains accepted. |
| P5-FR-133 | Pass | Accepted Phase 5B1 handoff and masked-indicator component coverage. | Validated prior handoff; not repeated during B2. | Localized masked indicators remain accepted. |
| P5-FR-134 | Pass | Accepted Phase 5B1 handoff and history-scoping coverage. | Validated prior handoff; not repeated during B2. | User-scoped history remains accepted. |
| P5-FR-135 | Pass | Accepted Phase 5B1 handoff and rerun revalidation coverage. | Validated prior handoff; not repeated during B2. | Current-policy rerun checks remain accepted. |
| P5-FR-136 | Pass | Accepted Phase 5B1 handoff and policy-test API/UI coverage. | Validated prior handoff; not repeated during B2. | Policy preview remains accepted. |
| P5-FR-137 | Pass | 418 focused frontend tests passed; final full Vitest passed 64 files/778 tests; locale parity, ESLint, typecheck, build, and CSS lint passed. | Chrome DevTools sweep covered EN/AR sign-in, SSO, roles, mappings, policy editor, audit, masked indicators, and localized authorization/session errors with no raw UI translation key or Arabic English fallback. | Session/error follow-ups are in PRs #228, #230-#232. |
| P5-FR-138 | Pass | Logical-CSS/RTL audits, CSS lint, full frontend gates, and responsive regression coverage passed. | Desktop plus 375px/768px live checks passed 18/18 across EN/AR Phase 5 surfaces; technical SQL/code/data identifiers remained LTR. | RTL identifier and mobile reachability fixes are in PRs #229 and #233. |
| P5-FR-139 | Pass | Authentication/session sanitization, SSO error, collision, permission, and locale suites passed. | EN/AR invalid OIDC/SAML callback, unmapped role, collision, expired/invalid session, unauthenticated, and forbidden paths were exercised; no raw IdP error, UUID, host, token, credential, assertion, stack trace, SQL, constraint name, or raw translation key appeared. | Relevant fixes are in PRs #226, #228, and #230-#232. |
| P5-FR-140 | Pass | Focused audit suite passed 518 tests with one expected skip; shared permission-gate regression passed for Phase 5 and Phase 6 helpers; backend CI passed. | Isolated runtime contained login success/failure, SSO success/failure, provider change, role change, mapping change, policy change, query allowed/blocked, accept, history/rerun, unauthorized-admin denial, audit search/export/verify, and logout events. | Required failed actions were present with sanitized contexts; durability/coverage fixes are in PRs #226, #227, #234-#237. |
| P5-FR-141 | Pass | Chain, immutability, purge-gap, and concurrent sequence tests passed; PR #235 adds the PostgreSQL concurrency regression. | Valid chains verified; mutation/deletion routes returned 404; purge-gap, marker-only, and append-after-purge verified; isolated tamper reported the exact first break; final restricted-denial writes also preserved a valid chain. | Normal development audit data was never tampered with. |
| P5-FR-142 | Pass | Current Phase 6 search/export/purge/retention suite passed 30 tests with one expected skip; focused audit suite passed. | Runtime reported 24 months, null pre-purge marker/count, a two-entry purge, latest purge marker/count, retention-window search, valid chain across purge, marker-only validity, and retained 24-month configuration. | Current superseding retention contract was used. |
| P5-FR-143 | Pass | Comprehensive audit, SSO, hostile-input, export, and permission-denial redaction suites passed. | Representative search plus CSV/JSON exports had integrity metadata and no generated probe values, certificate, token form, DB URL/host, hostile raw payload, assertion, stack trace, or sensitive filter value; final denial contexts contained only reason, method, and static required permission. | Sensitive probe values were not stored as evidence. |
| P5-FR-144 | Pass | Audit permission, Phase 6 permission, and shared-gate suites passed; backend/frontend CI were green after PRs #236 and #237. | Real admin sessions received 200 for verify/status/search/export/retention. Restricted SSO and legacy lowercase `admin` sessions received sanitized 403 responses and no audit navigation/data; final product HEAD durably recorded five restricted audit API denials. | Role-name shortcuts did not bypass fixed permissions. |

## Automated Validation

| Gate | Result |
|---|---|
| Initial focused Phase 5 backend selection (32 discovered files) | 679 passed; 3 existing warnings |
| Current Phase 6 audit search/export/purge selection | 30 passed; 1 expected skip |
| Focused audit/immutability/chain/retention/redaction/history/query selection | 518 passed; 1 expected skip |
| Full backend unit suite after sequence fix | 2,236 passed; 6 existing warnings |
| Full backend unit suite after generic permission-denial fix | 2,241 passed; 6 existing warnings |
| Exact final backend CI pytest command | 2,230 passed; 13 deselected; 6 existing warnings |
| Final shared Phase 5/6 gate, sanitization, retention, and audit permission selection | 36 passed |
| Ruff check | Pass |
| Ruff format check | Pass; 392 files already formatted |
| Focused Phase 5 frontend selection | 418 passed |
| Final full Vitest | 64 files passed; 778 tests passed |
| ESLint | Pass |
| TypeScript typecheck | Pass |
| Production build | Pass; existing chunk-size warning only |
| CSS lint and logical-CSS/RTL audits | Pass |
| Live responsive browser assertions | 18/18 passed |
| PR CI | `backend-test` and `frontend-test` green for every merged fix PR |

The final full-gate commands were:

| Command | Result |
|---|---|
| `cd backend && rtk uv run pytest tests/unit -q -m "not integration"` | 2,230 passed; 13 deselected; 6 existing warnings |
| `cd backend && rtk uv run ruff check src tests` | Pass |
| `cd backend && rtk uv run ruff format --check src tests` | Pass; 392 files already formatted |
| `cd frontend && rtk npm test -- --run` | 64 files passed; 778 tests passed |
| `cd frontend && rtk npm run lint` | Pass |
| `cd frontend && rtk npm run typecheck` | Pass |
| `cd frontend && rtk npm run build` | Pass; existing chunk-size warning only |
| `cd frontend && rtk npm run lint:css` | Pass |

Focused selections were assembled from the current test tree, not copied from the stale matrix command examples.

## Browser and API Scenarios

- Chrome DevTools MCP drove real isolated frontend sessions and real backend APIs.
- English and Arabic Phase 5 pages were checked at desktop, 375px, and 768px widths.
- OIDC success used the in-memory isolated IdP; invalid OIDC/SAML, unmapped, collision, and session-expiry paths remained localized and sanitized.
- A real SSO admin session received HTTP 200 for audit verify, status, search, retention, JSON export, and CSV export.
- Restricted SSO and legacy lowercase `admin` sessions had no audit navigation and received sanitized 403 responses.
- On final product HEAD, a restricted SSO session repeated verify, status, search, retention, and export denials; all five responses had only `error` and `message_key`.

## Audit Integrity and Redaction

- Pre-purge representative run: 35 entries with all required login success/failure, SSO success/failure, provider/role/mapping/policy change, allowed/blocked query, history/rerun, unauthorized-admin denial, and audit-administration categories present.
- Application mutation and deletion routes returned 404.
- Two expired entries were purged; API verification remained valid and the retention endpoint reported the latest purge and matching count.
- Marker-only verification succeeded, and a new append after marker-only purge also verified.
- One retained isolated entry was modified directly in the isolated platform database; verification returned `verified=false` and reported the exact first broken sequence.
- Final product-head permission-denial run persisted at least five attributed `access.denied` entries with the exact sanitized context shape and a valid chain.
- Search and export scans found no generated passwords/provider secrets, tokens, assertions, certificates, database credentials/hosts, raw hostile payloads, stack traces, or sensitive filter values.

## Merged Regression Fixes

- [PR #226](https://github.com/RkShanks/QueryCraft/pull/226) — durable local login audit events.
- [PR #227](https://github.com/RkShanks/QueryCraft/pull/227) — durable blocked hostile-input event.
- [PR #228](https://github.com/RkShanks/QueryCraft/pull/228) — localized expired-session redirect.
- [PR #229](https://github.com/RkShanks/QueryCraft/pull/229) — LTR isolation for technical RTL identifiers.
- [PR #230](https://github.com/RkShanks/QueryCraft/pull/230) — generated-client 401 session handling.
- [PR #231](https://github.com/RkShanks/QueryCraft/pull/231) — explicit SSO sign-in errors.
- [PR #232](https://github.com/RkShanks/QueryCraft/pull/232) — protected-route session-expiry race.
- [PR #233](https://github.com/RkShanks/QueryCraft/pull/233) — reachable mobile sidebar controls.
- [PR #234](https://github.com/RkShanks/QueryCraft/pull/234) — history and rerun audit events.
- [PR #235](https://github.com/RkShanks/QueryCraft/pull/235) — serialized concurrent audit sequence allocation.
- [PR #236](https://github.com/RkShanks/QueryCraft/pull/236) — durable generic permission-denial audit events.
- [PR #237](https://github.com/RkShanks/QueryCraft/pull/237) — shared audited Phase 6 permission gate.

## Cleanup and Closure

- Removed all isolated containers, networks, volumes, mock IdPs, images, helper files, generated sessions, and the tampered isolated database.
- Normal frontend and backend returned HTTP 200 after cleanup.
- No fresh screenshot was required; existing dirty Phase 5 PNGs and historical Phase 1/2 screenshots/traces were not staged or modified by this report.
- Phase 5 is complete at 32/32 Pass. Phase 6 is unblocked, but Phase 6 work was not started in this run.
