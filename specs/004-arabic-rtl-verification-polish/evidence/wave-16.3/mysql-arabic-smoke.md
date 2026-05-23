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

* **Gemini Follow-up (Resolved)**: The LLM consistently generates unquoted table names (`actor`) for simple select-all requests. Since unquoted identifiers are valid standard SQL and fully supported by MySQL, this is correct and optimal behavior. Dialect-specific support is validated by:
  1. The MySQL target dialect validation passing in the evaluator.
  2. Successful execution against the live Sakila MySQL source database.
  3. The system's ability to cleanly parse and validate MySQL-specific identifiers if they are generated or supplied.

## Execution Result
* **State**: `EXECUTED` (passed all evaluator rules).
* **Result Columns**: `['actor_id', 'first_name', 'last_name', 'last_update']`
* **Visual Verification**: Screenshot captured at `specs/004-arabic-rtl-verification-polish/evidence/wave-16.3/mysql-arabic-smoke.png`

## Console and Network Logs
* Zero network errors (HTTP 200 OK for query submit).
* No console errors or layout issues.
