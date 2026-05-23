# Wave 16.3 Smoke Test — PostgreSQL Pagila

## Verification Details
* **Connection Name**: `PostgreSQL Pagila`
* **Database Type**: `PostgreSQL`
* **Arabic Prompt**: `أظهر لي جميع الممثلين` (Show me all actors)
* **Status**: **PASSED**

## Actions performed
1. Select the `PostgreSQL Pagila` database source from the connection selector.
2. Verify the workspace input area is active.
3. Input the Arabic question `أظهر لي جميع الممثلين` and submit.
4. Verify the system successfully processes the query and displays the SQL response card.

## Observed SQL Output
```sql
SELECT
  actor_id,
  first_name,
  last_name,
  last_update
FROM public.actor;
```

## Dialect-Specific SQL Markers
* Double-quoted identifiers or schema qualification: `public.actor` (PostgreSQL standard schema organization).
* Clean SQL output without markdown markers or execution violations.

## Execution Result
* **State**: `EXECUTED` (passed all evaluator rules including the qualified table-name schema validation check).
* **Result Columns**: `['actor_id', 'first_name', 'last_name', 'last_update']`
* **Visual Verification**: Screenshot captured at `specs/004-arabic-rtl-verification-polish/evidence/wave-16.3/pg-arabic-smoke.png`

## Console and Network Logs
* Zero network errors (HTTP 200 OK for query submit).
* No console errors or layout issues.
