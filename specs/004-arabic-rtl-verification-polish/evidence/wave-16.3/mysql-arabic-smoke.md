# Wave 16.3 Smoke Test — MySQL Sakila

## Verification Details
* **Connection Name**: `MySQL Sakila`
* **Database Type**: `MySQL`
* **Arabic Prompt**: `أظهر لي جميع الممثلين` (Show me all actors)
* **Status**: **PASSED**

## Actions performed
1. Select the `MySQL Sakila` database source from the connection selector.
2. Verify the workspace input area is active.
3. Input the Arabic question `أظهر لي جميع الممثلين` and submit.
4. Verify the system successfully processes the query and displays the SQL response card.

## Observed SQL Output
```sql
SELECT
  *
FROM actor;
```

## Dialect-Specific SQL Markers
* Standard MySQL syntax without `public.` schemas or PostgreSQL-specific quotes.
* Clean SQL output without markdown markers or execution violations.

* **Gemini Follow-up (Resolved)**:
  * **Dialect-Marker Conclusion**: MySQL generated SQL (`FROM actor;`) used valid unquoted identifiers and executed successfully, but did not demonstrate the backtick identifier marker.
  * **Evaluation**: This is an evidence-gathering limitation against the strict marker wording, not a user-facing runtime failure or application defect. Standard unquoted SQL identifiers are fully valid in MySQL.
  * **Mitigation**: Flagged for the Wave 16.4 final audit as a residual low/medium finding, unless the orchestrator determines that strict compliance with SC-038 requires a dialect-forcing follow-up prompt variant.


## Execution Result
* **State**: `EXECUTED` (passed all evaluator rules).
* **Result Columns**: `['actor_id', 'first_name', 'last_name', 'last_update']`
* **Visual Verification**: Screenshot captured at `specs/004-arabic-rtl-verification-polish/evidence/wave-16.3/mysql-arabic-smoke.png`

## Console and Network Logs
* Zero network errors (HTTP 200 OK for query submit).
* No console errors or layout issues.
