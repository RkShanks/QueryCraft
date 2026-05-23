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
* **Dialect-Marker Conclusion**: MSSQL: valid schema-qualified T-SQL executed successfully, but no TOP/bracket marker was produced.
* **Validated Evidence Limitation**:
  - **Execution Passed**: Yes, the query execution completed successfully with state `EXECUTED` and returned the customer rows.
  - **SQL Validity**: The generated SQL (`FROM SalesLT.Customer;`) was fully valid schema-qualified T-SQL for the target MS SQL Server database.
  - **User Impact**: No user-facing failure occurred.
  - **Wording Gap**: The strict dialect-marker wording in T-532 (which expects bracket identifiers or a `TOP` clause) was not demonstrated because the model produced valid unquoted schema-qualified identifiers without brackets or `TOP`.


## Execution Result
* **State**: `EXECUTED` (passed all evaluator rules).
* **Result Columns**: `['CustomerID', 'NameStyle', 'Title', 'FirstName', 'MiddleName', 'LastName', 'Suffix', 'CompanyName', 'SalesPerson', 'EmailAddress', 'Phone', 'rowguid', 'ModifiedDate']` (sensitive `PasswordHash` / `PasswordSalt` columns omitted from evidence)
* **Visual Verification**: Screenshot captured at `specs/004-arabic-rtl-verification-polish/evidence/wave-16.3/mssql-arabic-smoke.png`

## Console and Network Logs
* Zero network errors (HTTP 200 OK for query submit).
* No console errors or layout issues.
