# Wave 16.3 Smoke Test — MSSQL AdventureWorks

## Verification Details
* **Connection Name**: `MSSQL AdventureWorks`
* **Database Type**: `MS SQL Server`
* **Arabic Prompt**: `أظهر لي جميع العملاء` (Show me all customers)
* **Status**: **PASSED**

## Actions performed
1. Select the `MSSQL AdventureWorks` database source from the connection selector.
2. Verify the workspace input area is active.
3. Input the Arabic question `أظهر لي جميع العملاء` and submit.
4. Verify the system successfully processes the query and displays the SQL response card.

## Observed SQL Output
```sql
SELECT
  *
FROM SalesLT.Customer;
```

## Dialect-Specific SQL Markers
* Standard MSSQL schema-qualified syntax: `SalesLT.Customer` (AdventureWorks SalesLT schema organization).
* Clean SQL output without any `public.` prefix (stripped cleanly by the dialect-aware GeminiAdapter) or markdown markers or execution violations.

## Execution Result
* **State**: `EXECUTED` (passed all evaluator rules).
* **Result Columns**: `['CustomerID', 'NameStyle', 'Title', 'FirstName', 'MiddleName', 'LastName', 'Suffix', 'CompanyName', 'SalesPerson', 'EmailAddress', 'Phone', 'PasswordHash', 'PasswordSalt', 'rowguid', 'ModifiedDate']`
* **Visual Verification**: Screenshot captured at `specs/004-arabic-rtl-verification-polish/evidence/wave-16.3/mssql-arabic-smoke.png`

## Console and Network Logs
* Zero network errors (HTTP 200 OK for query submit).
* No console errors or layout issues.
