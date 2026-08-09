# CHUNK-05 retry quota and audit lifecycle evidence

## Status

| Check | Value |
| --- | --- |
| Implementation | Passed |
| Merge readiness | Backend/frontend CI required before merge |
| Starting main | `ca6069b4430aa947f15cbd53f493f478a9e8b4a1` |
| Tested branch commit | `d4cff9cbb1edb22b8a0bbb78bd4733151293b9c2` |
| Product GREEN commit | `a612fe2a254c16ea1c61e7dddfed6442a25048d5` |
| IS-GAP-005 | Resolved |
| IS-GAP-006 | Resolved |
| Response/UI contract changed | False |
| Browser required | False |
| CHUNK-06 started | False |

## TDD commits

| Stage | Commit | Result |
| --- | --- | --- |
| Query quota RED | `460c0ccf86889d0166f254bbc2f22f52c5eb503b` | 12 failed, 2 passed |
| Query quota GREEN | `45f36299a7255e04596bcf1c9af38afff2a3c334` | Focused retry quota slice passed |
| Audit lifecycle RED | `845abfc6bfdf21b74335ba38acdf6631d363b1a9` | 14 failed, 14 passed |
| Audit lifecycle GREEN | `a612fe2a254c16ea1c61e7dddfed6442a25048d5` | Quota, lifecycle, API, dialect and cancellation proof passed |

The two later test-only commits make legacy handcrafted retry attempts explicitly `EXECUTED`, matching the pre-charge state validation now required by the product path.

## Locked quota accounting

| Boundary | Charge | Denial/unavailable behavior |
| --- | --- | --- |
| Direct regenerate query work | One query unit immediately before each actual provider invocation | Sanitized 429/503; zero provider/source calls |
| Explicit reject query work | `query.reject` first, then the same shared regenerate boundary; reject itself charges nothing | Sanitized 429/503; zero provider/source calls |
| Retry source work | One execution unit after evaluator/current-policy/role/row-filter validation and immediately before each actual adapter/executor invocation | Sanitized 429/503; one provider call and zero source calls |
| Retry limit | No query or execution charge | `RefinePrompt`; no provider/source work |
| Invalid, forged, inactive or wrong-user attempt | No query or execution charge | Sanitized existing attempt error; no downstream work |
| Current deny-all policy | No query or execution charge | `access.denied`; no provider/source work |
| Provider/source failure or timeout | Consumed work is not refunded | No duplicate increment for the same invocation |

The implementation retains the existing quota dimensions, Redis key structure, reset timestamp behavior and response contract. Submit still preserves hostile detection → query quota → provider ordering.

## Real HTTP counter and call proof

Real `/query/regenerate` and `/query/reject` requests used PostgreSQL, Redis, deterministic provider/source spies and the real `QuotaService` Lua counter path.

| Scenario | Query counter delta | Execution counter delta | Provider calls | Source calls | HTTP |
| --- | ---: | ---: | ---: | ---: | ---: |
| Successful regenerate | +1 | +1 | 1 | 1 | 200 |
| Successful explicit reject lifecycle | +1 | +1 | 1 | 1 | 200 |
| Query counter at limit | 0 | 0 | 0 | 0 | 429 |
| Query counter over limit | 0 | 0 | 0 | 0 | 429 |
| Execution counter at limit | +1 | 0 | 1 | 0 | 429 |
| Query quota unavailable | 0 | 0 | 0 | 0 | 503 |
| Execution quota unavailable | +1 | 0 | 1 | 0 | 503 |

The query-denial matrix ran for both direct regenerate and explicit reject. PostgreSQL, MySQL and MSSQL retry routes each proved execution denial after one provider call and before their adapter call.

## Ordered audit lifecycle

All retry lifecycle events use one newly allocated retry attempt ID in standard `resource_type=query_attempt` and `resource_id` fields. Explicit `query.reject` identifies the rejected prior attempt. Context contains only constant classifications and existing safe quota metadata.

| Outcome | Ordered actions (`outcome`) |
| --- | --- |
| Successful regenerate | `query.submit` (success) → `query.validate.pass` (success) → `query.execute` (success) |
| Successful explicit reject | `query.reject` (success) → successful regenerate lifecycle |
| Evaluator rejection | `query.submit` (success) → `query.validate.fail` (failure, `evaluator_rejected`) |
| Byte-equal candidate | `query.submit` (success) → `query.validate.fail` (failure, `duplicate_candidate`) |
| Role authorization denial | `query.submit` (success) → `query.validate.pass` (success) → `access.denied` (denied, `role_authorization`) |
| Row-filter/schema conflict | `query.submit` (success) → `query.validate.pass` (success) → `policy.schema_mismatch` (failure, `policy_schema_conflict`) |
| Direct query quota denial | `quota.exceeded` (blocked) |
| Reject query quota denial | `query.reject` (success) → `quota.exceeded` (blocked) |
| Execution quota denial | `query.submit` (success) → `query.validate.pass` (success) → `quota.exceeded` (blocked) |
| Provider failure | `query.submit` (failure, `provider_failure`) |
| Provider timeout/deadline cancellation | `query.submit` (failure, `timeout`) |
| Source failure | `query.submit` (success) → `query.validate.pass` (success) → `query.execute` (failure, safe existing source classification) |
| Source timeout/deadline cancellation | `query.submit` (success) → `query.validate.pass` (success) → `query.execute` (failure, `timeout`) |
| Masking failure | `query.submit` (success) → `query.validate.pass` (success) → `query.execute` (failure, `result_processing_failed`) |
| Source success followed by persistence failure | `query.submit` (success) → `query.validate.pass` (success) → `query.execute` (success); request history rollback remains authoritative |
| Audit-write failure | Request fails closed; pending query/history mutations roll back |
| Retry limit | No regenerate lifecycle; explicit reject retains only its truthful decision event |
| Pre-provider deny-all policy | `access.denied` (denied); explicit reject precedes it |
| Session deletion during provider | Private 404; no late retry lifecycle success |
| Session deletion during source | Earlier submit/validate success remains durable; no late execute event or history result |

Real database assertions searched the appended rows after each HTTP action, verified exact action count/order/outcome/resource identity, and ran `AuditService.verify_chain`. Every checked chain returned verified with no break. Concurrent duplicate reject/regenerate tests proved one winning provider/source invocation, one query/execution increment pair and no duplicated decision/lifecycle events.

## Durability and sanitization

- Retry audit writes use an isolated database transaction, so each truthful stage survives request rollback without committing pending accepted-query/history changes.
- Source and persistence failures preserved the earlier lifecycle rows while the accepted-query row remained byte-for-byte unchanged in the asserted fields.
- Successful execution is audited after masking and before returning. Audit failure rolls back pending history and fails closed.
- Session deletion remains authoritative at provider and source stages; owned operation, attempt, active-attempt and processing-lock state is removed.
- 429, 503, 504, 422 and 502 assertions use the existing sanitized error/message-key contract. No exception, provider, credential, counter, limit, Redis key, prompt, SQL or row value enters audit context or error bodies.
- No new `AuditActionType` was added.

## Automated gates

| Gate | Result |
| --- | --- |
| Core retry quota/audit unit slice | 88 passed |
| Retry/router/ownership/deadline/cancellation/dialect focused slice | 157 passed |
| Broad quota/audit/hostile-ordering slice | 275 passed, 11 dependency-gated skips |
| Real HTTP quota/audit/chain proof | 12 passed |
| Retry cancellation and three-dialect execution denial additions | 5 passed |
| Post-fix full unit suite | 2476 passed |
| Required one-time full backend invocation | Reached 899 passed/17 skipped, then stopped on a legacy `PENDING` retry fixture; both discovered legacy fixtures were corrected and their focused/full-unit gates passed |
| Ruff check `src tests` | Passed |
| Ruff format check `src tests` | 422 files formatted |
| `git diff --check` | Passed |
| Test Guard | Passed |
| Clean Code Guard | Passed |
| Docs Guard | Passed |
| Backend CI | Required before merge |
| Frontend CI | Required before merge |

The one-time full backend command was not duplicated after its fixture-only stop. The PR backend gate is the authoritative complete post-fix full-backend result before merge.

## Cleanup

| Check | Result |
| --- | --- |
| Audit/history/session test rows remaining | 0 |
| Retry attempt/active-attempt/lock/operation/counter keys remaining | 0 |
| Authentication keys created by test clients removed | 2 exact keys removed |
| Live test task/coroutine remaining | 0 |
| Pre-existing PostgreSQL/Redis containers restored to stopped state | Passed |
| Shared/pre-existing volumes deleted | False |
| Temporary proof files retained | False |
| Protected 14 PNGs, seven historical screenshots and traces changed by CHUNK-05 | False |

CHUNK-06 was not started. It is eligible for dispatch only after this PR is merged and the required backend/frontend CI gates are green.
