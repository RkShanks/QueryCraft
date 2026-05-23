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

> **Remediation Note (Backend Review)**: T-532 requires at least one T-SQL dialect-specific marker (e.g. bracket identifiers `[SalesLT].[Customer]` or `TOP` clause instead of `LIMIT`). The observed SQL (`FROM SalesLT.Customer;`) uses schema-qualified dot notation, which is valid T-SQL but is also valid in PostgreSQL and MySQL when schema/catalog prefixes are present. **Gemini follow-up required**: Re-run the MSSQL smoke with the same Arabic prompt and confirm whether the generated SQL contains `TOP` or bracket identifiers. If the LLM output never contains `TOP` or brackets for MSSQL AdventureWorksLT, this gap must be noted as a Phase 4 finding.

## Execution Result
* **State**: `EXECUTED` (passed all evaluator rules).
* **Result Columns**: `['CustomerID', 'NameStyle', 'Title', 'FirstName', 'MiddleName', 'LastName', 'Suffix', 'CompanyName', 'SalesPerson', 'EmailAddress', 'Phone', 'PasswordHash', 'PasswordSalt', 'rowguid', 'ModifiedDate']`
* **Visual Verification**: Screenshot captured at `specs/004-arabic-rtl-verification-polish/evidence/wave-16.3/mssql-arabic-smoke.png`

## Console and Network Logs
* Zero network errors (HTTP 200 OK for query submit).
* No console errors or layout issues.
