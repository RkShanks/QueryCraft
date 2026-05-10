# Wave 4 (US-3) — Independent Audit by Opus 4.6

Audit performed: 2026-05-10
main HEAD audited: 94db390
Constitution version: v1.1.1
Auditor: Opus 4.6
Methodology: Black-box independent — auditor did not see implementation prompts or other auditors' findings.

## Summary

| Severity | Count | Title list |
|---|---|---|
| Critical | 1 | O-001 |
| High | 5 | O-002, O-003, O-004, O-005, O-006 |
| Medium | 5 | O-007, O-008, O-009, O-010, O-011 |
| Low | 3 | O-012, O-013, O-014 |
| Total | 14 | |
| Hypotheses tested | 50 | |
| Refuted | 28 | |

---

## Findings

### O-001 — Critical — `SELECT FOR UPDATE/SHARE` bypasses ReadOnlyRule (row-level locking)

**Hypothesis**: ReadOnlyRule checks `isinstance(statement, exp.Select)` but `SELECT ... FOR UPDATE` is still parsed as `exp.Select` by sqlglot. The Lock node is a child, not a different statement type.

**Affected files / lines**: `backend/src/app/evaluator/rules/read_only.py:25` — only checks `isinstance(statement, exp.Select)`, never inspects for `exp.Lock` children.

**Reproducer**:
```python
# tmp/probe_01_evaluator_bypass.py — H5, H6
await read_only.evaluate("SELECT * FROM users FOR UPDATE", schema)
# Returns (True, None) — PASSES
```

**Observed**: `SELECT * FROM users FOR UPDATE`, `FOR SHARE`, `FOR UPDATE SKIP LOCKED`, `FOR UPDATE NOWAIT` all pass every evaluator rule.

**Expected**: FR-010a requires "single read-only SELECT". `FOR UPDATE` acquires row-level exclusive locks, blocking concurrent transactions. `FOR SHARE` acquires shared locks. Neither is read-only in PostgreSQL semantics.

**Severity rationale**: Critical — an LLM-generated `SELECT ... FOR UPDATE` against a production source DB would acquire exclusive row locks, potentially causing write starvation or deadlocks on the customer's live database. This directly violates Constitution Principle II (validated before execution) and FR-005 (read-only connection). Defense-in-depth via the read-only DB role would prevent the lock, but the evaluator should catch it first.

**Suggested fix scope**: In `ReadOnlyRule.evaluate()`, after confirming the statement is a `Select`, check `statement.find(exp.Lock)` and reject if present.

---

### O-002 — High — Unsafe function catalog has 15+ gaps (advisory locks, server admin, config mutation)

**Hypothesis**: The `_FORBIDDEN_FUNCTIONS` set in `unsafe_pattern.py` is incomplete relative to FR-010f's catalog and PostgreSQL's admin function surface.

**Affected files / lines**: `backend/src/app/evaluator/rules/unsafe_pattern.py:9-34` — `_FORBIDDEN_FUNCTIONS` set.

**Reproducer**:
```python
# tmp/probe_02_extended.py
# All of these PASS all evaluator rules:
"SELECT pg_advisory_lock(1)"        # blocks indefinitely
"SELECT pg_advisory_unlock(1)"      # releases locks
"SELECT pg_advisory_lock_shared(1)" # shared advisory lock
"SELECT pg_advisory_xact_lock(1)"   # xact-level advisory lock
"SELECT pg_try_advisory_lock(1)"    # non-blocking advisory lock
"SELECT set_config('statement_timeout', '0', false)"  # disables timeout!
"SELECT pg_promote()"               # promotes standby to primary
"SELECT pg_switch_wal()"            # forces WAL segment switch
"SELECT pg_walfile_name('0/0')"     # WAL file name disclosure
"SELECT pg_create_restore_point('x')" # creates named restore point
"SELECT pg_backup_start('x')"      # initiates base backup
"SELECT pg_backup_stop()"          # stops base backup
"SELECT pg_rotate_logfile()"       # rotates server log
"SELECT current_setting('is_superuser')" # role info disclosure
```

**Observed**: All pass. The spec (FR-010f) explicitly lists `pg_advisory_lock` and `pg_advisory_unlock` as required entries. They are missing from the implementation.

**Expected**: FR-010f bullet 1 says "pg_sleep, pg_advisory_lock, pg_advisory_unlock — long-blocking calls". These are spec-mandated.

**Severity rationale**: High — `pg_advisory_lock` can block the connection indefinitely (DoS). `set_config('statement_timeout', '0', false)` disables the query timeout for the current session, defeating FR-012. `pg_promote()` on a standby could promote it to primary.

**Suggested fix scope**: Add all missing functions to `_FORBIDDEN_FUNCTIONS`. Critical additions: `pg_advisory_lock`, `pg_advisory_unlock`, `pg_advisory_lock_shared`, `pg_advisory_xact_lock`, `pg_try_advisory_lock`, `pg_try_advisory_xact_lock`, `set_config`, `current_setting`, `pg_promote`, `pg_switch_wal`, `pg_backup_start`, `pg_backup_stop`.

---

### O-003 — High — `regenerate_query` does not catch `TimeoutError` from `asyncio.wait_for`

**Hypothesis**: `submit_question` catches `(TimeoutError, SourceDBTimeout)` at line 118, but `regenerate_query` only catches `SourceDBTimeout` at line 311.

**Affected files / lines**: `backend/src/app/services/query_service.py:306-315` — the executor timeout handler in `regenerate_query`.

**Reproducer**:
```python
# Code analysis (tmp/probe_03_state_machine.py — Check 1)
# submit_question line 118: except (TimeoutError, SourceDBTimeout)
# regenerate_query line 311: except SourceDBTimeout
# asyncio.wait_for() raises asyncio.TimeoutError (alias of TimeoutError), NOT SourceDBTimeout
```

**Observed**: `asyncio.wait_for(..., timeout=30)` raises `TimeoutError`. The `regenerate_query` handler only catches `SourceDBTimeout`. A timeout during regenerate will propagate as an unhandled exception, returning HTTP 500 instead of 504.

**Expected**: Consistent timeout handling — HTTP 504 with `error.timeout` message key, same as `submit_question`.

**Severity rationale**: High — a query timeout during regeneration returns a raw 500 Internal Server Error to the user instead of a structured 504 timeout response. The lock IS released (finally block exists), but the user experience is broken and the error is misleading. This is also an Inv 1 issue: the evaluator-passed SQL reaches the DB but the error is not properly surfaced.

**Suggested fix scope**: Change line 311 to `except (TimeoutError, SourceDBTimeout) as exc:`.

---

### O-004 — High — `accept_query` has no processing lock — double-accept race condition

**Hypothesis**: `accept_query` reads the attempt from Redis, persists to PostgreSQL, then deletes from Redis — but does not acquire the per-session processing lock.

**Affected files / lines**: `backend/src/app/services/query_service.py:157-195` — `accept_query` method.

**Reproducer**:
```
# Two concurrent POST /query/accept with the same attempt_id:
# T1: reads attempt from Redis → attempt exists
# T2: reads attempt from Redis → attempt still exists (not yet deleted)
# T1: repo.create() → writes row to accepted_queries
# T2: repo.create() → writes DUPLICATE row to accepted_queries
# T1: redis.delete() → deletes attempt
# T2: redis.delete() → no-op (already deleted)
```

**Observed**: No `_acquire_lock` call in `accept_query`. Both `submit_question` and `regenerate_query` acquire the lock.

**Expected**: `accept_query` should either acquire the processing lock or use Redis atomic operations (e.g., `GETDEL`) to ensure single-use.

**Severity rationale**: High — creates duplicate rows in `accepted_queries`, violating data integrity. In practice, the window is small (single user, Phase 1), but this is an architectural defect that will compound in multi-user phases.

**Suggested fix scope**: Either acquire processing lock in `accept_query`, or replace `redis.get()` + `redis.delete()` with an atomic `GETDEL` (Redis 6.2+).

---

### O-005 — High — `accept_query` does not validate attempt state

**Hypothesis**: `accept_query` reads the attempt JSON from Redis but never checks the `state` field before persisting.

**Affected files / lines**: `backend/src/app/services/query_service.py:165-186` — no state check between `json.loads(raw)` and `repo.create()`.

**Reproducer**:
```
# Scenario: submit_question times out → attempt stored with state="TIMEOUT"
# Attempt persists in Redis for 15 minutes (TTL)
# User (or attacker) calls POST /query/accept with that attempt_id
# accept_query reads the TIMEOUT attempt, persists it to accepted_queries
# Result: a never-executed query is permanently stored in history
```

**Observed**: States PENDING, GENERATED, REJECTED, TIMEOUT can all be accepted. Only EXECUTED should be acceptable.

**Expected**: `accept_query` should verify `attempt.state == "EXECUTED"` before persisting. Constitution Principle III: "Only Validated Knowledge Persists."

**Severity rationale**: High — allows persisting unexecuted, evaluator-rejected, or timed-out SQL to the accepted_queries table. This corrupts the history and violates Principle III.

**Suggested fix scope**: Add state validation: `if attempt.get("state") != "EXECUTED": raise HTTPException(400, ...)`.

---

### O-006 — High — UNION / INTERSECT / EXCEPT falsely rejected by ReadOnlyRule

**Hypothesis**: `ReadOnlyRule` checks `isinstance(statement, exp.Select)` but sqlglot parses `UNION` as `exp.Union`, `INTERSECT` as `exp.Intersect`, `EXCEPT` as `exp.Except` — none of which are subclasses of `exp.Select`.

**Affected files / lines**: `backend/src/app/evaluator/rules/read_only.py:25` — `if not isinstance(statement, exp.Select)`.

**Reproducer**:
```python
# tmp/probe_02_extended.py — SET-OP tests
await read_only.evaluate("SELECT id FROM users UNION SELECT id FROM orders", schema)
# Returns (False, "Non-SELECT statement: Union") — REJECTED
```

**Observed**: All set operations (UNION, UNION ALL, INTERSECT, EXCEPT) are rejected as "non-SELECT" even though they are valid read-only queries composed of SELECT statements.

**Expected**: FR-010a says "single read-only SELECT statement or read-only CTE". UNION of two SELECTs is a read-only query and should pass.

**Severity rationale**: High — this is a functional correctness issue. Any LLM-generated query using UNION (very common for analytics) will be rejected, forcing a refine prompt. This significantly degrades the user experience for legitimate queries. Not a security issue, but blocks correct behavior.

**Suggested fix scope**: Extend the isinstance check to `isinstance(statement, (exp.Select, exp.Union, exp.Intersect, exp.Except))`, then recursively validate that each branch is a SELECT.

---

### O-007 — Medium — `accept_query` uses raw `redis.get()` instead of `get_attempt()` — inconsistent ownership validation

**Hypothesis**: `reject_query` and `regenerate_query` use `get_attempt()` from `attempt_store.py` which raises typed exceptions (`AttemptNotFound`, `AttemptOwnershipViolation`). `accept_query` does raw `redis.get()` and manual JSON parsing.

**Affected files / lines**: `backend/src/app/services/query_service.py:165-177` vs `backend/src/app/core/attempt_store.py:51-74`.

**Reproducer**: Code analysis in `tmp/probe_03_state_machine.py — Check 4`.

**Observed**: Two different code paths for ownership validation. The accept path returns generic `attempt_expired` / `attempt_invalid` errors without the typed exception hierarchy.

**Expected**: Consistent use of `get_attempt()` for all attempt operations, ensuring uniform error handling and exception types.

**Severity rationale**: Medium — the manual check IS functionally correct (compares `session_id`), but the inconsistency creates maintenance risk and makes it harder to reason about security properties.

**Suggested fix scope**: Refactor `accept_query` to use `get_attempt()`.

---

### O-008 — Medium — `UnsafePatternRule.add_pattern()` missing — spec deviation from FR-010f

**Hypothesis**: FR-010f states the catalog is "extensible via `UnsafePatternRule.add_pattern()`". The pipeline has `add_rule()` but `UnsafePatternRule` has no `add_pattern()` method.

**Affected files / lines**: `backend/src/app/evaluator/rules/unsafe_pattern.py` — method does not exist. `specs/001-core-text-to-sql/spec.md:190` — references `add_pattern()`.

**Reproducer**: `grep -n "add_pattern" backend/src/app/evaluator/rules/unsafe_pattern.py` returns empty.

**Observed**: No `add_pattern()` method exists. The only way to add patterns is to modify the source code `_FORBIDDEN_FUNCTIONS` set.

**Expected**: A public `add_pattern(pattern: str)` method for runtime extensibility.

**Severity rationale**: Medium — spec deviation. Not exploitable, but the stated extensibility contract is not implemented. Operators cannot add custom unsafe patterns without code changes.

**Suggested fix scope**: Add `add_pattern(self, pattern: str)` that appends to an instance-level copy of `_FORBIDDEN_FUNCTIONS`.

---

### O-009 — Medium — Schema-qualified table access not validated (cross-schema bypass)

**Hypothesis**: `SchemaValidationRule` extracts `table.name` but ignores the schema prefix (e.g., `pg_catalog`, `information_schema`, `foo`). A query like `SELECT * FROM foo.users` resolves `table.name` = `users` which matches the known schema, even though `foo.users` is a different table.

**Affected files / lines**: `backend/src/app/evaluator/rules/schema_validation.py:59-72` — `table.name` ignores schema prefix.

**Reproducer**:
```python
# tmp/probe_01_evaluator_bypass.py — H26
await schema_val.evaluate("SELECT * FROM foo.users", schema)
# Returns (True, None) — PASSES (table.name resolves to "users", matches schema)
```

**Observed**: `SELECT * FROM foo.users` passes schema validation because `table.name` returns `users`, not `foo.users`. The schema prefix `foo` is silently ignored.

**Expected**: If the query specifies a non-`public` schema prefix, and SchemaContext only has `public` tables, the query should be rejected.

**Severity rationale**: Medium — defense-in-depth issue. The read-only DB role limits actual access, but the evaluator gives false confidence. Could allow access to tables in other schemas that the DB role can read (e.g., `pg_catalog.pg_class` if it's not in the forbidden tables list).

**Suggested fix scope**: Check `table.db` (sqlglot's schema attribute) against allowed schemas (default: `public` only). Reject if schema prefix is present and not in the allowed list.

---

### O-010 — Medium — Regenerated `EphemeralAttempt` missing explicit `state` field

**Hypothesis**: When `regenerate_query` creates a new `EphemeralAttempt` (line 337), it does not set `state=` explicitly. The Pydantic model defaults to `"PENDING"`.

**Affected files / lines**: `backend/src/app/services/query_service.py:337-348` — `EphemeralAttempt` constructor call.

**Reproducer**: Code analysis in `tmp/probe_03_state_machine.py — Check 3`.

**Observed**: New attempt after regeneration has `state="PENDING"` in Redis even though it has been executed. Combined with O-005 (no state validation on accept), this is benign but architecturally incorrect.

**Expected**: State should be `"EXECUTED"` to accurately reflect the attempt lifecycle.

**Severity rationale**: Medium — state machine inconsistency. Not directly exploitable (O-005 is the exploitable path), but makes debugging and auditing the attempt lifecycle unreliable.

**Suggested fix scope**: Add `state="EXECUTED"` to the EphemeralAttempt constructor at line 337.

---

### O-011 — Medium — Recursive CTE with UNION falsely rejected

**Hypothesis**: `ReadOnlyRule` validates CTE bodies via `isinstance(cte.this, exp.Select)`. For recursive CTEs, the body is a `UNION ALL` (parsed as `exp.Union`), which fails the Select check.

**Affected files / lines**: `backend/src/app/evaluator/rules/read_only.py:28-30`.

**Reproducer**:
```python
await read_only.evaluate(
    "WITH RECURSIVE t AS (SELECT 1 UNION ALL SELECT * FROM users) SELECT * FROM t",
    schema
)
# Returns (False, "Non-SELECT CTE: Union") — FALSE REJECTION
```

**Observed**: All recursive CTEs are rejected because their body is always a UNION.

**Expected**: Recursive CTEs are valid read-only queries and should pass when their branches are all SELECT statements.

**Severity rationale**: Medium — functional correctness issue. Recursive CTEs are useful for hierarchical queries (org charts, tree structures). Blocking them reduces platform utility.

**Suggested fix scope**: Extend CTE body check to `isinstance(cte.this, (exp.Select, exp.Union))`, then recursively validate branches.

---

### O-012 — Low — `set_config()` can disable query timeout from within SQL

**Hypothesis**: `set_config('statement_timeout', '0', false)` is a PostgreSQL built-in function that changes session-level settings. It passes all evaluator rules.

**Affected files / lines**: `backend/src/app/evaluator/rules/unsafe_pattern.py:9-34` — `set_config` not in forbidden list.

**Reproducer**: `SELECT set_config('statement_timeout', '0', false)` passes all rules.

**Observed**: If an LLM generates this as part of a CTE or subquery preceding the main query, it could disable the statement timeout for the session, defeating FR-012.

**Expected**: `set_config` should be in the forbidden functions list.

**Severity rationale**: Low — in practice, `asyncio.wait_for()` enforces the timeout at the Python level regardless of `statement_timeout`. But if the executor ever changes to rely on PostgreSQL's statement_timeout, this becomes exploitable. Defense-in-depth gap.

**Suggested fix scope**: Add `set_config` and `current_setting` to `_FORBIDDEN_FUNCTIONS`.

---

### O-013 — Low — Server metadata info-disclosure functions not blocked

**Hypothesis**: Functions like `inet_server_addr()`, `inet_server_port()`, `pg_postmaster_start_time()`, `version()` reveal server infrastructure details.

**Affected files / lines**: `backend/src/app/evaluator/rules/unsafe_pattern.py:9-34`.

**Reproducer**: `SELECT inet_server_addr(), inet_server_port(), version()` passes all rules.

**Observed**: Server IP address, port, and PostgreSQL version are disclosed.

**Expected**: While not directly exploitable, this information aids further attacks (fingerprinting, version-specific exploits).

**Severity rationale**: Low — information disclosure only. The read-only DB role limits blast radius. These functions are commonly available to all DB users.

**Suggested fix scope**: Consider adding `inet_server_addr`, `inet_server_port`, `inet_client_addr`, `inet_client_port` to the forbidden list. `version()` is arguably useful and may be left.

---

### O-014 — Low — `accept_query` field name fallback masks data model inconsistency

**Hypothesis**: `accept_query` reads `attempt.get("question_text") or attempt.get("question", "")` and `attempt.get("generated_sql") or attempt.get("sql", "")`. The `EphemeralAttempt` model uses `question` and `sql`, so the `question_text`/`generated_sql` keys will never exist.

**Affected files / lines**: `backend/src/app/services/query_service.py:182-183`.

**Reproducer**: Code analysis in `tmp/probe_03_state_machine.py — Check 5`.

**Observed**: The fallback works correctly in practice, but the dead code (`question_text`, `generated_sql` branches) suggests a naming inconsistency between the Redis attempt model and the DB model.

**Expected**: Direct field access: `attempt.get("question", "")` and `attempt.get("sql", "")`.

**Severity rationale**: Low — functionally correct due to fallback, but the dead code is misleading and maintenance-unfriendly.

**Suggested fix scope**: Remove the dead `question_text`/`generated_sql` branches.

---

## Refuted hypotheses

- HO-01: INSERT RETURNING bypasses ReadOnlyRule — refuted: sqlglot parses as `exp.Insert`, caught.
- HO-02: SELECT INTO bypasses ReadOnlyRule — refuted: sqlglot parses as `exp.Create`, caught.
- HO-03: CREATE TABLE AS bypasses — refuted: caught by ReadOnlyRule.
- HO-04: DO block bypasses — refuted: caught by ReadOnlyRule (`Command` type).
- HO-07: UNION with DML CTE — refuted: CTE body is `Delete`, caught.
- HO-08: Double semicolons `;;` bypass single_statement — refuted: sqlglot parses as 2 statements, caught.
- HO-09: Comment-only trailing `SELECT 1; --` — refuted: parsed as 2 stmts.
- HO-10: EXECUTE in CREATE FUNCTION — refuted: caught by ReadOnlyRule.
- HO-14: pg_catalog.pg_read_file qualified bypass — refuted: `func.this` still returns `pg_read_file`.
- HO-15: pg_catalog.pg_authid — refuted: `table.name` returns `pg_authid`, in forbidden list.
- HO-16: information_schema.tables — refuted: SchemaValidation catches `tables` as unknown.
- HO-17: pg_stat_activity — refuted: SchemaValidation catches as unknown table.
- HO-19: COPY FROM PROGRAM — refuted: caught by ReadOnlyRule + UnsafePatternRule.
- HO-20: PG_SLEEP mixed case — refuted: `func_name.lower()` comparison catches it.
- HO-21: Nested pg_sleep in subquery — refuted: `find_all(exp.Anonymous)` walks recursively.
- HO-22: VALUES statement — refuted: caught by ReadOnlyRule (`Values` type).
- HO-23: TABLE command — refuted: caught by ReadOnlyRule (`Alias` type).
- HO-24: EXPLAIN — refuted: caught by ReadOnlyRule (`Command` type).
- HO-25: EXPLAIN ANALYZE — refuted: caught by ReadOnlyRule (`Command` type).
- HO-29: SET ROLE — refuted: caught by both ReadOnlyRule and UnsafePatternRule.
- HO-30: SAVEPOINT — refuted: caught by ReadOnlyRule.
- HO-31: GRANT — refuted: caught by ReadOnlyRule (`Grant` type).
- HO-37: LISTEN — refuted: caught by UnsafePatternRule (Alias/Column name check).
- HO-38: NOTIFY — refuted: sqlglot fails to parse, `Unable to parse SQL` rejection.
- HO-40: Unicode identifier bypass — refuted: sqlglot normalizes identifiers correctly.
- HO-43: SET statement_timeout — refuted: caught by both rules.
- HO-44: VACUUM — refuted: caught by ReadOnlyRule.
- HO-49: Comment injection `/* ; DROP */` — refuted: sqlglot strips comments, single statement.

## Methodology notes

- **Tools**: Python 3.12, sqlglot (version installed in backend venv), custom probe scripts in `tmp/`.
- **Time**: ~1 hour of analysis.
- **Sources**: spec.md, plan.md, constitution.md v1.1.1, openapi.yaml, all source files listed in Step 2.
- **Cross-references**: Existing unit tests in `backend/tests/unit/evaluator/` and acceptance tests in `backend/tests/acceptance/` were reviewed to understand current coverage.
- **Probe scripts**: `tmp/probe_01_evaluator_bypass.py` (50 patterns), `tmp/probe_02_extended.py` (30 patterns), `tmp/probe_03_state_machine.py` (10 checks), `tmp/probe_04_sqlglot.py` (type analysis).
- **No source code was modified**. All scratch files are in `tmp/` (gitignored).
- **Cross-contamination**: Did NOT read, checkout, or reference `phase1-us3-findings-gemini` branch at any point.
