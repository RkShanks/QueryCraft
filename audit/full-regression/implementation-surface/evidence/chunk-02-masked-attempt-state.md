# CHUNK-02 masked-attempt-state evidence

Status: **Resolved**  
Gap: `IS-GAP-002`  
Starting main: `6682520e92174ac696c31d6989c36a6fb677b605`  
Tested product main: `76f317b6894ffb4300133d51ad4e201ecb022d96`  
Fix PR: [#299](https://github.com/RkShanks/QueryCraft/pull/299)

## Outcome

Raw source rows no longer cross the Redis attempt-state boundary. Production-reader tracing found no production flow that reads `executor_result`; the only production references were the attempt field and submit/regenerate writes. The field and both writes were removed instead of retaining a masked duplicate.

Submit now keeps the source result request-local, applies column masks, and only then writes an `EXECUTED` metadata-only attempt. Regenerate follows the same invariant. Attempt state retains the existing retry/source/ownership metadata but no rows, columns, row count, result payload, credentials, row-filter identity values, policy definitions, source hosts, schema context, complete provider prompt, or audit payload.

Responses and accepted-query history still contain the final masked result. Accept, regenerate, ownership, byte-equal/refine, and CHUNK-01 source continuity remain functional. No frontend product change was required.

CHUNK-02 changed no behavior assigned to `IS-GAP-003` through `IS-GAP-006` or `IS-GAP-047`.

## TDD and automated gates

| Check | Result |
| --- | --- |
| RED commit | `c92c786dd4bcb98956eba3cc62356d2a59173e2d` |
| RED unit result | 10 failed; 17 passed before implementation |
| RED public API result | All 12 dialect/projection Redis assertions reproduced raw pre-mask retention; the leakage guard also failed |
| GREEN commit | `50e1decf21b1791ada7d1835fbfed272082c313e` |
| REFACTOR commit | Not needed; GREEN removed obsolete state and serialization code |
| Focused attempt/submit/regenerate/policy | 67 passed |
| Public source-continuity/API matrix | 42 passed |
| Broader masking/history/audit/security | 160 passed; 2 skipped |
| Full backend suite | 2,810 passed; 17 skipped; 35 subtests passed |
| Ruff check and format | Passed; 414 files already formatted |
| Focused frontend masked-result sentinels | 2 files; 27 tests passed |
| Diff validation | Passed |
| Fix CI | `backend-test` and `frontend-test` passed |

The RED tests use runtime-generated, redacted sensitive sentinels and never include their values in assertion output. Test Guard was applied to changed tests and Clean Code Guard to production changes before the fix PR merged.

Automated failure coverage proves that a masking exception leaves only pre-execution metadata, Redis serialization failures do not echo result values to logs or errors, source failures/timeouts store no result payload, malformed mask shapes fail closed, and exotic/empty/large results do not expand Redis attempt state. Covered values include zero rows, null, decimal, date/time, binary-like, Unicode/Arabic, nested values, and a 2,000-row result.

## Merged-main isolated proof

The proof ran against the tested product main SHA with a dedicated disposable platform PostgreSQL, Redis, backend runtime, and PostgreSQL/MySQL/MSSQL source services. The backend used the real production adapters and public API wiring.

| Source | Direct | Alias | Nested projection | Row filter + mask | API masked | History masked | Redis raw-free |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| PostgreSQL | Pass | Pass | Pass | Pass | Yes | Yes | Yes |
| MySQL | Pass | Pass | Pass | Pass | Yes | Yes | Yes |
| MSSQL | Pass | Pass | Pass | Pass | Yes | Yes | Yes |

The proof covered 12 dialect/projection-policy cases, 15 masked API results, 15 masked history results, three accept paths, three regenerate paths, and three session-selector source-continuity paths. Sixteen serialized attempt payloads and 15 Redis channels were checked. Every stored attempt had the exact metadata-only schema and no `executor_result` key.

Old, regenerated, unauthorized-row, and row-filter identity value categories were absent from Redis attempt state. Regenerate retained the submit-time connection while the visible chat-session selection pointed at another source. The prior attempt was removed after successful regeneration; the successor retained only required metadata.

## Failure and leakage results

- A structurally malformed mask failed closed after source execution without returning or storing the source value.
- A real unreachable-source failure returned a sanitized response and left no result payload in Redis.
- Wrong-session ownership failed with the constant invalid-attempt response before retry work.
- A byte-equal regenerate reached the refine terminal path without storing a result payload.
- Redis JSON, API bodies, accepted history, audit rows, audit search/export, and backend logs were raw-value free.
- The focused browser result displayed the mask token. DOM text, browser storage, accessibility text, network bodies, and console text were raw-value free.
- No screenshot, trace, browser profile, response body, prompt, statement, row, cookie, token, credential, host, or canary was retained.

## Cleanup and handoff

- Removed the disposable proof backend, platform PostgreSQL, Redis, three source services, network, tmpfs data, helper files, and bytecode.
- Restored source-service running/stopped state to preflight.
- Confirmed the normal backend and frontend each returned HTTP 200 after cleanup.
- Confirmed the protected dirty baseline remained limited to the original 14 tracked images, seven historical screenshots, and historical traces.

`IS-GAP-002` is resolved on tested product main. `CHUNK-03` is unblocked; no CHUNK-03 work was started.
