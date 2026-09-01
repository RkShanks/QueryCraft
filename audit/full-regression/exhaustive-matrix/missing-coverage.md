# Missing Coverage and Setup-Dependent Index

Current through synchronized `main` at `0713c14a3e4dc44d4c330347d17aa86f52280d17` and the implementation-surface consolidation.

The final current-head Phase 1–6 and cross-phase runs closed the old execution ledger at the broad requirement-row level. The implementation-surface audit then inspected 456 concrete backend/frontend entrypoints and found narrower product, contract, harness, operational and evidence boundaries that broad Pass rows did not exercise. This file now points to that current handoff; it does not reopen frozen phase specifications or authorize remediation.

## Current reconciliation

| Scope | Exact | Partial | Missing | Intentional N/A | Surfaces |
| --- | ---: | ---: | ---: | ---: | ---: |
| Backend implementation | 206 | 47 | 5 | 6 | 264 |
| Frontend implementation | 32 | 142 | 10 | 8 | 192 |
| **Combined** | **238** | **189** | **15** | **14** | **456** |

The 21 backend and 33 frontend raw candidates reconcile 54/54 into 47 unique consolidated gaps after seven explicit cross-stack merges. See:

- [consolidated-gap-matrix.md](../implementation-surface/consolidated-gap-matrix.md)
- [consolidated-gap-matrix.json](../implementation-surface/consolidated-gap-matrix.json)
- [coverage-summary.md](../implementation-surface/coverage-summary.md)
- [remediation-execution-order.md](../implementation-surface/remediation-execution-order.md)

## Confirmed coverage-only gaps

| Consolidated ID | Evidence boundary still missing | Future evidence |
| --- | --- | --- |
| IS-GAP-015 | Current-head live provider proof covers Gemini, while Anthropic/OpenAI/Ollama remain deterministic/mock-tested. | One approved bounded request per available provider, with no prompt/response/credential retention. |
| IS-GAP-016 | OIDC/SAML protocol logic is covered, but enterprise TLS/network/metadata or JWKS rotation/outage/recovery is not proven against a standards-complete dependency. | Disposable real/standards-complete IdP integration; no tokens/assertions/URLs retained. |
| IS-GAP-046 | Responsive browser evidence samples representative states and includes screenshot-heavy specs without assertions for every critical dynamic state. | Assertion-bearing 1440/768/375 EN/AR matrix using temporary output only. |
| IS-GAP-047 | Privacy evidence covers strong separate API/UI/audit/export/log/storage/accessibility slices, but not one joint same-browser cache/console/network/download flow across hostile/error/download and failed or implicit identity switching. | Boolean/count-only real API/browser channel instrumentation after prerequisite product/contract fixes. |

## Contract and harness prerequisites

| Consolidated ID | Classification | Why it blocks reliable evidence |
| --- | --- | --- |
| IS-GAP-008 | Confirmed Contract/Documentation Drift | Runtime exposes 60 operations; static OpenAPI and generated SDK contain 35. Contract tests exercise only the static set. |
| IS-GAP-042 | Confirmed Test-Harness Gap | Manual fixtures, assertion-light named states, mocked browser APIs and non-isolated screenshot outputs can overstate coverage or mutate protected artifacts. |

## Setup-dependent execution rows

The old setup-dependent list was executed by the accepted final current-head Phase/cross-phase runs for the tested boundaries: three real source databases, isolated Redis/PostgreSQL, deterministic providers, mapped OIDC, one approved live provider call, browser/mobile/RTL and foundation gates all have final evidence. Remaining setup dependence is represented only by the current consolidated rows below.

| Consolidated IDs | Dependency | Isolation requirement |
| --- | --- | --- |
| IS-GAP-001, IS-GAP-002 | PG/MySQL/MSSQL plus platform DB/Redis | Dedicated disposable three-source fixtures and no retained SQL/result values. |
| IS-GAP-003, IS-GAP-004 | Controllable slow/cancellable source and Redis | Cancel all tasks and remove attempts/locks/sessions. |
| IS-GAP-009, IS-GAP-013, IS-GAP-017 | Populated disposable PostgreSQL | Never run downgrade/corruption cases on shared state. |
| IS-GAP-012, IS-GAP-014, IS-GAP-019 | Real disposable Redis plus synthetic high-cardinality platform data | Remove keys/rows and verify bounded cleanup. |
| IS-GAP-015 | Approved provider credentials/service | In-memory credentials, strict call/cost cap, no prompt/response retention. |
| IS-GAP-016 | Disposable standards-complete HTTPS IdP | Remove users, sessions, tokens/assertions and dependency state. |
| IS-GAP-018 | Disposable filesystem/source containers | Verify downloads/checksums/reruns without shared fixtures. |
| IS-GAP-047 | Disposable users/sessions/audit/downloads/browser profile | Destroy every canary-bearing state and retain booleans/counts only. |

## Approved decision handoff

| Consolidated ID | Approved decision | Implementation state |
| --- | --- | --- |
| IS-GAP-010 | Proxy solely owns deployment security headers; backend endpoint-specific cache policy passes through unchanged. | CHUNK-30 implementation pending. |
| IS-GAP-011 | Disable production HTTP documentation; allow explicit development/test exposure; preserve canonical CI generation. | CHUNK-30 implementation pending. |
| IS-GAP-045 | Redirect or retire `/ask` in favor of Workspace. | CHUNK-31 unblocked but not started. |

The decisions were recorded on 2026-09-01 and no implementation row remains decision-blocked. `IS-GAP-015` remains Partial with non-Gemini live smoke deferred until approved credentials/runtime exist; zero external LLM calls were made.

## Deferred scope

| Item | Status |
| --- | --- |
| Phase 6 T-905/freeze | Still prohibited in this consolidation and not started. |
| Product/test remediation | Not started; requires a future explicit implementation dispatch. |
| Protected historical screenshots/traces | Remain user-owned, dirty and unstaged; future evidence must use new temporary paths. |

No consolidated security or data-integrity gap is deferred merely because it is difficult. Broad exhaustive-matrix Pass statuses remain historical requirement evidence, not proof that these concrete implementation boundaries are closed.
