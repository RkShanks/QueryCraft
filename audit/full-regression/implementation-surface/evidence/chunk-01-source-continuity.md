# CHUNK-01 selected-source continuity evidence

Status: **Resolved**  
Gap: `IS-GAP-001`  
Tested product main: `3522440f0bbf3c837aafe62edaf2e9d89d4717fb`  
Fix PR: [#297](https://github.com/RkShanks/QueryCraft/pull/297)

## Outcome

The source selected at submit time is now immutable, server-owned attempt context. Public accept, reject, and regenerate decisions rebuild their query service from that stored connection, re-evaluate current authorization and policy, and fail closed instead of using a default source. No frontend product change was required because decision requests remain attempt-based.

CHUNK-01 changed no behavior assigned to `IS-GAP-002` through `IS-GAP-006`.

## TDD and automated gates

| Check | Result |
| --- | --- |
| RED commit | `028e0d878663ceb0730018d89024dfd792368fed` |
| RED result | Required continuity, ownership, revocation, and client-authority regressions failed before implementation |
| GREEN commit | `a4690c4de27db767bc0fdeda4fc9517981f3cad2` |
| REFACTOR commit | Not needed |
| Full backend suite | 2,791 passed; 17 skipped; 35 subtests passed |
| Ruff check and format | Passed |
| Full Vitest | 65 files; 839 tests passed |
| ESLint, typecheck, build, CSS lint | Passed |
| Diff validation | Passed |
| Fix CI | `backend-test` and `frontend-test` passed |

Test Guard was applied to changed tests and Clean Code Guard to production changes before the fix PR merged.

## Merged-main isolated proof

The proof ran against the tested main SHA through real HTTP with a dedicated disposable platform PostgreSQL and Redis. PostgreSQL, MySQL, and MSSQL source fixtures were independently confirmed read-only before use.

| Source | Accept | Reject | Regenerate | Selector switch isolated | Source label retained |
| --- | ---: | ---: | ---: | ---: | ---: |
| PostgreSQL fixture | 201 | 200 | 200 | Yes | Yes |
| MySQL fixture | 201 | 200 | 200 | Yes | Yes |
| MSSQL fixture | 201 | 200 | 200 | Yes | Yes |

All nine decision flows retained the submit-time source, dialect, schema, current policy, and adapter boundary. Regenerated attempts retained the original source. Accepted persistence used the original source. A selector change affected only later submissions.

## Fail-closed and isolation results

- Current policy revocation after submit failed closed on regenerate for all three sources: three of three returned sanitized 422 responses before new provider or source work.
- Deleted, disabled, and unauthorized original connections failed closed in the public accept integration matrix.
- Missing, malformed, forged-source, forged-user, wrong-user, and wrong-session attempt context failed before retry work.
- Concurrent selector update and retry could not redirect the attempt; a later submission used the later selector.
- Byte-equal reject/regenerate terminal paths retained the persisted source label.
- Sanitized attempt errors exposed none of the prohibited identifier, host, credential, dialect-internal, schema, statement, row, policy-value, or stack-trace categories.

## Focused browser proof

A current-main Chromium flow submitted on the PostgreSQL fixture, switched the visible session selector to the MySQL fixture, and invoked the visible Regenerate control. The request returned 200, the response card retained the PostgreSQL label, the selector remained on MySQL, and the decision body contained only `attempt_id`.

No screenshot, trace, browser profile, response body, prompt, statement, or source value was retained.

## Cleanup

- Removed the dedicated proof backend, platform PostgreSQL, Redis, network, image, tmpfs data, and temporary harness files.
- Restored the MySQL and MSSQL source fixtures to their preflight stopped state; the PostgreSQL fixture remained in its preflight running state.
- Confirmed the normal backend and frontend each returned HTTP 200 after cleanup.
- Confirmed the protected dirty baseline remained limited to the original 14 tracked images, seven historical screenshots, and historical traces.

`IS-GAP-001` is resolved on tested main. Its dependency is satisfied, so `CHUNK-02` is unblocked; no CHUNK-02 work was started.
