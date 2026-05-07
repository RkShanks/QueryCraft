# Wave 4 (US-3) — Independent Audit by Gemini Pro 3.1

Audit performed: 2026-05-07
main HEAD audited: 94db390
Constitution version: v1.1.1
Auditor: Gemini Pro 3.1
Methodology: Black-box independent — auditor did not see implementation prompts.

## Summary

| Severity | Count | Title list |
|---|---|---|
| Critical | 1 | G-001 (Quoted Identifier Bypass in UnsafePatternRule) |
| High | 4 | G-002 (Invariant 4 bypassed by whitespace), G-003 (Cross-Schema Access), G-004 (ReadOnlyRule Rejects Set Operations), G-005 (CTE Validation Bypass) |
| Medium | 0 | |
| Low | 0 | |
| Total findings | 5 | |
| Hypotheses tested | 20 | |
| Hypotheses refuted (no bug) | 15 | |

## Findings

### G-001 — Critical — Quoted Identifier Bypass in UnsafePatternRule

**Hypothesis**: Does `UnsafePatternRule` properly extract and check the names of functions when they are quoted in the SQL statement?

**Affected files / lines**:
  - `backend/src/app/evaluator/rules/unsafe_pattern.py:86-89`

**Reproducer**:
```sql
-- Minimal SQL reproducer
SELECT "dblink"('dbname=postgres', 'DROP TABLE users;');
```

**Observed**: The query passes the `UnsafePatternRule` because `sqlglot` parses `"dblink"` as an `Identifier` object, not a string. The `isinstance(func_name, str)` check evaluates to `False`, skipping the verification entirely.
**Expected**: Per FR-010(f), `dblink` and other unsafe functions must be rejected regardless of case or quoting.
**Severity rationale**: **Critical**. This enables an attacker to completely bypass the platform's security controls to execute forbidden functions. Since functions like `dblink` or `pg_read_file` can lead to arbitrary code execution, unauthorized data modification (e.g. `DROP TABLE`), and severe data exfiltration, this directly violates the core architectural intent of the evaluator gate.
**Suggested fix scope**: Modify `UnsafePatternRule` to correctly extract the string value from `sqlglot` objects (e.g. `func_name = func.this.this if isinstance(func.this, exp.Identifier) else getattr(func, "this", None)`) or properly handle `Identifier` checks.

### G-002 — High — Invariant 4 bypassed by whitespace differences

**Hypothesis**: Does `QueryService`'s duplicate detection (Invariant 4) strictly prevent duplicate queries, or can it be bypassed by trivial formatting differences like trailing whitespace?

**Affected files / lines**:
  - `backend/src/app/services/query_service.py:273-277`

**Reproducer**:
```python
# Conceptual Reproducer
prior_sql = "SELECT * FROM users;"
new_sql = "SELECT * FROM users; "
assert new_sql == prior_sql  # Fails
```

**Observed**: The service uses exact string equality `new_sql == prior.sql`. If the LLM generates the same logical SQL but includes an extra space, newline, or different casing for keywords, the byte-equal check fails, triggering execution instead of prompting the user to refine.
**Expected**: Per SC-005 and Invariant 4, duplicate statements should trigger a failed regeneration and prompt the user to refine their question to prevent degenerate identical loops.
**Severity rationale**: **High**. The intent of Invariant 4 is to stop an LLM from stubbornly repeating the same flawed logic. An attacker or simply a poorly behaving LLM can easily bypass this safety limit, consuming resources and providing a degraded UX.
**Suggested fix scope**: Either use `sqlglot` to parse and compare structural equality, or at minimum strip leading/trailing whitespace and normalize case before comparison.

### G-003 — High — Cross-Schema Access via SchemaValidationRule

**Hypothesis**: Does `SchemaValidationRule` restrict access to only the `public` (or explicitly configured) schema by verifying the `db` attribute of table identifiers?

**Affected files / lines**:
  - `backend/src/app/evaluator/rules/schema_validation.py:161-170`

**Reproducer**:
```sql
-- Minimal SQL reproducer
SELECT * FROM secret_schema.users;
```

**Observed**: When matching a table name, `SchemaValidationRule._find_table` only checks `table.name`. If a table named `users` exists in the allowed schema context, a query requesting `secret_schema.users` will be validated successfully, ignoring the schema prefix (`table.db`).
**Expected**: Per FR-010(d), SQL referencing tables not present in the connected schema must be rejected. The table resolution must include the schema namespace to prevent access to identically named tables in restricted schemas.
**Severity rationale**: **High**. This allows cross-schema data exposure if tables share the same name as those in the authorized schema context, bypassing logical boundaries and potentially revealing sensitive data.
**Suggested fix scope**: Update `_find_table` to accept and verify the schema prefix (e.g. `table.db`) when searching the `SchemaContext`.

### G-004 — High — ReadOnlyRule Rejects Valid UNION/INTERSECT/EXCEPT Queries

**Hypothesis**: Does `ReadOnlyRule` properly allow complex read-only queries that use set operations like `UNION`?

**Affected files / lines**:
  - `backend/src/app/evaluator/rules/read_only.py:24-26`

**Reproducer**:
```sql
-- Minimal SQL reproducer
SELECT 1 UNION SELECT 2;
```

**Observed**: `sqlglot` parses `UNION`, `INTERSECT`, and `EXCEPT` as distinct AST nodes (e.g. `exp.Union`), not `exp.Select`. The rule's strict `isinstance(statement, exp.Select)` check immediately fails and rejects the query.
**Expected**: Per FR-010(a), a single read-only `SELECT` statement in valid PostgreSQL syntax is permitted. `UNION` constructs are standard and necessary read-only analytical queries.
**Severity rationale**: **High**. This breaks legitimate, highly common use cases for a Text-to-SQL platform. Complex analytical questions will often require set operations.
**Suggested fix scope**: Expand the `isinstance` check in `ReadOnlyRule` to also allow `exp.Union`, `exp.Intersect`, and `exp.Except`, ensuring their children are similarly validated.

### G-005 — High — CTE Column Extraction Bypasses Qualified Column Validation

**Hypothesis**: If a CTE uses `SELECT *` from multiple tables, how does `SchemaValidationRule` validate columns qualified with the CTE's alias in the outer query?

**Affected files / lines**:
  - `backend/src/app/evaluator/rules/schema_validation.py:92-96`
  - `backend/src/app/evaluator/rules/schema_validation.py:146-157`

**Reproducer**:
```sql
-- Minimal SQL reproducer
WITH c AS (SELECT * FROM table1, table2) SELECT c.fake_column FROM c;
```

**Observed**: `SchemaValidationRule._extract_cte_columns` fails to resolve columns when a CTE contains `SELECT *` over multiple tables, returning an empty list `[]`. In `_validate_statement`, if `cte_cols` is empty, it skips validation for qualified columns (`c.fake_column`), allowing arbitrary, invalid columns to pass validation.
**Expected**: Per FR-010(e), columns not present in the referenced tables must be rejected.
**Severity rationale**: **High**. This causes the evaluator to blindly trust non-existent columns, leading to database execution errors down the line and bypassing the semantic validation gate.
**Suggested fix scope**: If column extraction fails or cannot fully resolve a `SELECT *` with multiple tables, either strictly reject the CTE or flag it as unresolvable so that `_validate_statement` strictly rejects unverified column references instead of failing open.

## Refuted hypotheses (negative results — included for completeness)

- H-006: `ReadOnlyRule` bypass via `WITH updated AS (UPDATE ...) SELECT * FROM updated;` — refuted because `sqlglot` parses the inner statement as an `Update`, properly caught by the CTE recursive check in `ReadOnlyRule`.
- H-007: `SchemaValidationRule` fails on nested CTEs (WITH inside WITH) — refuted because `cte.this` recursively triggers CTE discovery, validating nested CTE structures correctly.
- H-008: `UnsafePatternRule` allows executing `pg_catalog.pg_sleep(10)` — refuted because the AST still retains the `Anonymous(this="pg_sleep")` node within the `Dot` expression, successfully trapping the forbidden function if unquoted.
- H-009: PENDING attempt with no terminal state causes a memory leak — refuted because Redis handles TTL expiry automatically within 15 minutes.
- H-010: Rejected attempts can be maliciously accepted later — refuted because `regenerate_query` immediately deletes the attempt from Redis before issuing a new one, and `EvaluatorRejection` never exposes the attempt ID to the client.
- H-011: Evaluator validation can be bypassed by placing an `UPDATE` in a `DO $$ BEGIN ... END $$` block — refuted because `ReadOnlyRule` correctly flags the `DO` block as a non-SELECT statement.
- H-012: Frontend XSS via identifier echo back — refuted because `react-i18next` interpolations automatically escape HTML by default, preventing injection in the RejectionBanner.
- H-013: Concurrent session attempts bypass lock — refuted because `acquire_lock` correctly uses Redis `NX` execution and wraps the operation in a try/finally block for reliable release.
- H-014: `SchemaValidationRule` fails to reject system tables — refuted because any tables not explicitly matched against the `SchemaContext` (like `pg_catalog.pg_class`) are correctly rejected as Unknown tables.
- H-015: Server restart breaks attempt ownership — refuted because attempts are stored with `session_id` mapping. Session cookies handle persistence across backend restarts smoothly (Redis-backed).
- H-016: Admin statements like `GRANT` or `COMMENT ON` allowed — refuted because `ReadOnlyRule` strictly permits `Select` only, dropping administrative directives immediately.
- H-017: Multi-statement comments trick `SingleStatementRule` (`SELECT 1; -- comment; SELECT 2`) — refuted because `sqlglot` parser condenses/ignores comments properly, correctly raising multiple statements.
- H-018: Ephemeral lock leaves system stuck indefinitely on failure — refuted because the mutex has an automatic TTL upper-bound, serving as a backstop.
- H-019: Session authentication can be bypassed for history — refuted because FastAPI request state strictly enforces the dependency and raises a 401 correctly.
- H-020: Modularity boundaries breached by DB credentials — refuted because credentials remain safely brokered on the backend, only passing IDs around the APIs.

## Methodology notes

- Tools used: Custom Python test scripts leveraging `sqlglot` inspection and instantiated `EvaluatorRule` classes.
- Time spent: ~45 minutes.
- Sources consulted: spec.md, plan.md, constitution.md, openapi.yaml, source files in backend and frontend.
- Cross-references: Verified against existing tests. The test suite correctly checked basic variations but missed deep structural parsing quirks with `sqlglot` identifiers, `Union` nodes, and whitespace boundaries in string equality checks.
