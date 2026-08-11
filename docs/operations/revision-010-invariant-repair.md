# Revision 010 persisted-invariant repair

Use this runbook only when revision 010 refuses to migrate because persisted rows violate its security or resource invariants. The refusal is deliberate: revision 010 does not delete, select, normalize, or overwrite existing rows.

## Safety rules

- Stop application writes before diagnosis and keep them stopped through the migration retry.
- Take a restorable database backup before changing any row. Record the backup identifier and complete the organization's restore verification procedure.
- Keep persisted values, SQL parameters, connection strings, and host details out of tickets, logs, and migration evidence.
- Treat every nonzero category as an owner decision. Do not infer a replacement value from API defaults or neighboring rows.
- If the detection table has more than one row, stop until the owner identifies the authoritative row and explicitly approves the disposition of every other row. Never select the newest row automatically.

## 1. Confirm the refusal

From the repository's `backend` directory, record the current revision and attempt the migration:

```console
uv run alembic current
uv run alembic upgrade head
```

The expected refusal text is constant and contains no row values:

```text
Revision 010 preflight refused: persisted invariant repair is required before retry.
```

After refusal, `uv run alembic current` must still report revision `009`. Do not proceed if the version or any schema object changed; preserve the database and escalate for investigation.

## 2. Diagnose categories and counts read-only

Connect through the organization's approved PostgreSQL administration path. Run this query in a read-only transaction. It returns category labels and counts only.

```sql
BEGIN;
SET TRANSACTION READ ONLY;

SELECT 'role_quota_daily_query_negative' AS category, count(*) AS affected_count
FROM role_quotas WHERE daily_query_limit < 0
UNION ALL
SELECT 'role_quota_daily_execution_negative', count(*)
FROM role_quotas WHERE daily_execution_limit < 0
UNION ALL
SELECT 'role_quota_daily_export_negative', count(*)
FROM role_quotas WHERE daily_export_limit < 0
UNION ALL
SELECT 'detection_threshold_invalid', count(*)
FROM detection_threshold_config
WHERE block_confidence IS NULL
   OR flag_confidence IS NULL
   OR NOT (0 <= flag_confidence
           AND flag_confidence < block_confidence
           AND block_confidence <= 1)
UNION ALL
SELECT 'detection_threshold_surplus_rows', greatest(count(*) - 1, 0)
FROM detection_threshold_config
UNION ALL
SELECT 'source_database_type_invalid', count(*)
FROM source_database_connections
WHERE database_type IS NULL
   OR database_type NOT IN ('postgresql', 'mysql', 'mssql')
UNION ALL
SELECT 'source_lifecycle_state_invalid', count(*)
FROM source_database_connections
WHERE lifecycle_state IS NULL
   OR lifecycle_state NOT IN ('active', 'disabled')
UNION ALL
SELECT 'source_health_status_invalid', count(*)
FROM source_database_connections
WHERE health_status IS NULL
   OR health_status NOT IN ('untested', 'healthy', 'unhealthy')
UNION ALL
SELECT 'source_schema_status_invalid', count(*)
FROM source_database_connections
WHERE schema_introspection_status IS NULL
   OR schema_introspection_status NOT IN ('none', 'success', 'failed', 'stale')
UNION ALL
SELECT 'user_auth_provider_invalid', count(*)
FROM users
WHERE auth_provider IS NULL OR auth_provider NOT IN ('local', 'oidc', 'saml')
UNION ALL
SELECT 'sso_protocol_invalid', count(*)
FROM sso_providers
WHERE protocol IS NULL OR protocol NOT IN ('oidc', 'saml')
ORDER BY category;

ROLLBACK;
```

Record only the category/count result. An empty detection table is valid and is not reported as corruption; revision 010 will insert one canonical default row.

## 3. Obtain and execute an explicit repair decision

For each nonzero category, the owning team must provide a row-specific remediation decision through the secure change-control channel. The decision must identify the intended valid state and why it is authoritative. Do not place those values or identifiers in general logs or this runbook.

Execute only the approved statements in one operator-controlled transaction:

```sql
BEGIN;
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;

-- Execute the owner-approved, row-specific remediation statements here.
-- Do not use an automatic delete, a bulk default, or a newest-row rule.

-- Re-run the complete category/count query from section 2 before committing.

COMMIT;
```

If any category remains nonzero, if concurrent writes occur, or if the approved decision is incomplete, roll back. For duplicate detection rows, absence of an explicit authoritative-row decision is a hard stop.

## 4. Verify and retry

Run the section 2 diagnosis again in a fresh read-only transaction. Continue only when every count is zero. Then retry and verify the migration:

```console
uv run alembic upgrade head
uv run alembic current
```

The current revision must be `010`. Run the category/count diagnosis once more; all counts must remain zero. Restart application writes only after the normal deployment health checks pass.

If revision 010 refuses again, do not bypass the preflight. Repeat diagnosis, obtain a new owner decision for any nonzero category, and preserve the failed-attempt evidence as categories, counts, and booleans only.
