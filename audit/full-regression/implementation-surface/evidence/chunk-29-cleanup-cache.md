# CHUNK-29 cleanup and corrupted-cache recovery

Status: **Resolved on tested product head `47c5662db951de70c2d2c7c2fd9aeb8010ef682c`** for `IS-GAP-021` / `BE-GAP-021` in [#342](https://github.com/RkShanks/QueryCraft/pull/342), from authoritative main `f96e6747154129ace3da95c34efaf80ee8f6ffa1`.

This evidence is value-safe. It retains only categories, counts, statuses, constant classifications, SHAs, and cleanup results. It contains no injected value, exception message, dependency URL, credential, provider configuration, session data, Redis detail, identifier from a test record, ciphertext, question, SQL, evaluator detail, or source result.

## TDD commits

| Slice | RED | GREEN | REFACTOR |
| --- | --- | --- | --- |
| Shutdown cleanup | `86ffd0f`, `873f5a7`, `1312dd4`, `73a06fd` | `b11daea`, `87f58f7` | `a5f6b82` |
| Session corruption | `c335582` | `fabda26` | `92e8eaf` |
| Attempt corruption | `f5f36dc` | `976cdad` | `62246e5` |

The session RED run reproduced 20 failures with 17 passes, plus three real-Redis failures. The attempt RED run reproduced 44 failures with 15 passes and two skips. Compatibility fixtures were aligned on `bbe1ef7`; the ownership documentation boundary was reconciled on `47c5662db951de70c2d2c7c2fd9aeb8010ef682c`.

## Shutdown failure matrix

Every single top-level failure position passed independently: `source_connector`, `llm_adapters`, `session_middleware`, `shared_redis`, and `database_engine`. Each case attempted all five top-level closer categories exactly once, recorded readiness as already shutting down, surfaced one `ApplicationShutdownError`, emitted `application_shutdown_failed`, and emitted no `application_shutdown` success event.

The cached-adapter matrix covered first, middle, last, and simultaneous first+last failure across three adapters. All three adapters received one attempt in every case; failures were retained for a later pass and successful entries were removed. The middleware matrix attempted three instances with first and last failing while the middle succeeded. The combined top-level case attempted seven concrete closers and retained four constant failure entries: one source, two middleware, and one database category. Repeated cleanup passed for source, adapter, and middleware owned state. Cancellation was propagated and was not converted into ordinary aggregate success.

## Session corruption matrix

The complete session-record consumer inventory contains two readers: `SessionMiddleware` and `AuthService.get_me`. Both use the shared strict `SessionRecord` boundary; local and SSO producers remain compatible.

The middleware matrix passed 18 valid-JSON semantic categories: missing user identity; invalid and noncanonical user UUID; wrong username type; wrong permissions container; invalid nested permission; wrong role, role-ID, and role-name types; wrong provider type; unknown provider; wrong created timestamp type; null activity timestamp; session-index owner mismatch; unknown field; and list, scalar, and null documents. `/auth/me` independently covered null user identity, invalid nested permission, and unknown-field corruption.

All corrupt authentication state remained unauthenticated and returned constant sanitized HTTP 503 `service_unavailable` behavior. `SessionRecordInvalid` remained internal. Owned corruption used atomic compare-delete and reconciled the session, reverse owner, user index, and empty sequence. Redis connection, timeout, and command failures were classified as dependency failures and never triggered corruption cleanup. One stale-cleanup race preserved the valid replacement, and a later valid record recovered without restart.

## Attempt corruption matrix

The attempt field matrix passed 16 categories: invalid/noncanonical/key-mismatched attempt UUID; invalid/noncanonical user UUID; invalid chat-session UUID; invalid source-context UUID; unknown state; zero, float, and string attempt numbers; wrong question, SQL, provider, created-timestamp, and expiry-timestamp shapes. Eleven required-field omissions were covered for attempt ID, user ID, source context, state, attempt number, question, SQL, evaluator result, provider, created timestamp, and expiry timestamp.

Authenticated-encryption compatibility covered seven categories: legacy plaintext, authentication-tag failure, wrong key, unsupported version, wrong purpose, malformed ciphertext, and malformed document. The evaluator matrix covered seven categories: missing fields, wrong passed type, a true passed value, wrong violations container, missing violation fields, invalid nested violation value, and unknown violation field. Wrong-session and wrong-user callers were rejected before decryption and before cleanup; unowned invalid documents were not deleted.

Owned corruption used atomic compare-delete. One stale-cleanup race preserved a valid replacement, and a later valid attempt recovered without restart. The public classification stayed HTTP 422 `attempt_invalid`; `AttemptContextInvalid` stayed internal. Corrupt retry state produced zero fallback-source calls, provider calls, source executions, history writes, success audits, or automatic retries.

## Gates

- Changed-path focus: 192 passed, 11 deselected.
- Foundation-compatibility rerun: 114 passed, eight skipped.
- Final real-Redis session/attempt matrix: 25 passed, 41 deselected.
- Session deletion, attempt privacy, and submit compatibility integration: 34 passed.
- Application log-redaction selection: 14 passed, eight skipped, one deselected.
- XP-013 selection: 52 unit passed, 24 deselected; 10 real-Redis hardening passed; one disposable outage/recovery test passed.
- Backend unit foundation: 2,390 passed, 366 skipped, 49 deselected, one existing warning, zero failures.
- Ruff check passed; Ruff format checked 466 files; `git diff --check` passed.
- Test Guard and Clean Code Guard passed. JSON and Docs Guard are finalized with this evidence/ledger commit.

## Cleanup and accounting

The disposable Redis, platform PostgreSQL, and source PostgreSQL containers were removed; zero CHUNK-29 runtime containers remain. The disposable worktree is intentionally retained only until merge, then removed during delivery cleanup.

All 23 protected files retain their starting hashes and statuses: 14 modified tracked PNGs, seven historical screenshots, and two trace archives. None is staged, and `git add -A` was not used. Draft PR #336 remains open/draft and unchanged at head `c8737db94dd97916b4bbe3e3ee882321db4c9757`.

Accounting is **Resolved 42, Pending 0, Partial 2, Needs Decision 3, Total 47**. No pending implementation gaps remain. CHUNK-30 and CHUNK-31 remain decision-blocked. T-905 and freeze work were not started.
