# Research — Phase 3: Multi-Dialect SQL and Multiple Source Databases

**Created**: 2026-05-18
**Status**: Complete (all NEEDS CLARIFICATION resolved in spec.md)

---

## R-001: Fernet vs. AES-GCM Credential Encryption

**Decision**: Migrate from existing AES-256-GCM (`core/encryption.py`) to Fernet symmetric encryption (via `cryptography.fernet.Fernet`) behind a credential-provider abstraction.

**Rationale**: ADR-9 (LOCKED) specifies Fernet. The existing `encryption.py` uses raw AES-GCM with manual IV management. Fernet provides a higher-level API with built-in timestamp, versioning, and key validation. The abstraction layer (`CredentialProvider` protocol) allows Phase 5+ to swap to Vault or AWS KMS without modifying connection services.

**Alternatives Considered**:
- Keep AES-GCM: Lower-level, more error-prone IV management. No timestamp support.
- HashiCorp Vault: External dependency, overkill for single-tenant Phase 3.
- AWS Secrets Manager: Cloud-specific, not self-hosted compatible.

**Migration Path**: Introduce `CredentialProvider` protocol + `FernetCredentialProvider` implementation. Existing `encryption.py` remains for backward compatibility during migration. `DB_CREDENTIAL_KEY` env var is separate from `PLATFORM_ENCRYPTION_KEY` (the latter stays for other AES-GCM uses). Data migration re-encrypts any existing stored passwords.

---

## R-002: Async MySQL Driver — `asyncmy`

**Decision**: Use `asyncmy` for MySQL/MariaDB async connectivity.

**Rationale**: ADR-10 (LOCKED). `asyncmy` is actively maintained, pure-Python, implements the MySQL client protocol directly (no C extension required). Supports parameterized queries natively.

**Alternatives Considered**:
- `aiomysql`: Older, less active maintenance. Based on PyMySQL.
- `mysql-connector-python`: Oracle's official driver. Synchronous only; would require thread-pool executor wrapping.

**Version**: `asyncmy>=0.2.9,<1.0.0` (current latest stable).
**Installation**: `uv add asyncmy` in backend `pyproject.toml`.

---

## R-003: Async MSSQL Driver — `aioodbc`

**Decision**: Use `aioodbc` with `unixODBC` + FreeTDS/ODBC driver for MS SQL Server async connectivity.

**Rationale**: ADR-10 (LOCKED). `aioodbc` wraps `pyodbc` with asyncio support. FreeTDS provides the TDS protocol implementation. This is the standard async MSSQL pattern for Python on Linux.

**Alternatives Considered**:
- `pymssql`: Simpler setup but synchronous; would need `asyncio.to_thread()` wrapping.
- Direct TDS socket: Too low-level, unmaintained libraries.

**Version**: `aioodbc>=0.5.0,<1.0.0`
**System Dependencies** (must be documented in Dockerfile + CI):
```
# Debian/Ubuntu
apt-get install -y unixodbc unixodbc-dev freetds-dev tdsodbc
# OR: Microsoft ODBC Driver 18 for SQL Server
```
**ODBC Configuration**: `/etc/odbcinst.ini` must register FreeTDS or MSSQL ODBC driver.
**Installation**: `uv add aioodbc` in backend `pyproject.toml`.

---

## R-004: `sqlglot` Dialect Parsing for Multi-Dialect Evaluator

**Decision**: Use `sqlglot`'s dialect parameter (`read="mysql"`, `read="tsql"`, `read="postgres"`) for dialect-specific SQL parsing in the evaluator.

**Rationale**: `sqlglot` (already `>=26.0.0` in deps) supports dialect-aware parsing out of the box. The existing `ReadOnlyRule` hardcodes `read="postgres"`. Phase 3 parameterizes this per the selected connection's `database_type`.

**Key Implementation Detail**: When `sqlglot.parse(sql, read=dialect)` raises `ParseError` or returns malformed AST, the evaluator rejects the SQL and triggers regeneration with a dialect correction hint per clarify Q3.

**Dialect Mapping**:
| `database_type` enum | `sqlglot` read dialect |
|---|---|
| `postgresql` | `"postgres"` |
| `mysql` | `"mysql"` |
| `mssql` | `"tsql"` |

---

## R-005: Schema Introspection via `information_schema`

**Decision**: Use `information_schema` views as the primary introspection mechanism for all three dialects.

**Rationale**: ADR-11. `information_schema.tables`, `information_schema.columns`, `information_schema.table_constraints`, and `information_schema.key_column_usage` are standardized across PostgreSQL, MySQL, and SQL Server. Fall back to dialect-specific catalogs only where `information_schema` is insufficient.

**Known Dialect Differences**:
- PostgreSQL: Full `information_schema` support. FK details available via `information_schema.key_column_usage` + `information_schema.referential_constraints`.
- MySQL: `information_schema` available. Some FK metadata requires `information_schema.KEY_COLUMN_USAGE` + `REFERENTIAL_CONSTRAINTS`.
- MSSQL: `INFORMATION_SCHEMA` views available. FK details via `INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS`.

**Introspection Queries**: Will be abstracted per-dialect in a `SchemaIntrospector` strategy pattern. The base query is similar across all three; dialect-specific adjustments are minimal.

---

## R-006: CI Testing Strategy for MySQL/MSSQL Without Real Services

**Decision**: Unit-test dialect/introspection behavior with adapters/fakes in CI. Real-service integration tests are optional/manual.

**Rationale**: ADR-10 (LOCKED). Setting up MySQL and MSSQL containers in CI adds complexity and CI time. The core logic (SQL generation, evaluation, introspection query building) can be tested with mock/fake adapters that return canned metadata.

**Testing Layers**:
1. **Unit tests (CI-mandatory)**: Test `SchemaIntrospector` strategies with fake connection adapters returning predefined metadata. Test dialect evaluator rules with hardcoded SQL strings.
2. **Adapter integration tests (optional, `@pytest.mark.integration`)**: Require real MySQL/MSSQL containers. Run manually or in a separate CI job.
3. **Testcontainers**: For optional integration, use `testcontainers[mysql]` and `testcontainers[mssql]` when available.

---

## R-007: Session-Scoped Database Selection

**Decision**: Store `connection_id` on the session record. Per-session scope, no global default.

**Rationale**: Clarify Q5 (LOCKED). Each new session starts unselected. Single-connection deployments auto-select. Mid-session switch updates the session's `connection_id` but prior query attempts retain their original `connection_id`.

**Data Model Impact**: Add nullable `connection_id` FK to `sessions` table. Nullable because the session starts with no selection; once selected, it is updated. Each `accepted_queries` row already has `database_connection_id` (NOT NULL) — this tracks the per-query connection.

---

## R-008: Legacy Data Migration Strategy

**Decision**: Migrate the Phase 1/2 hardcoded PostgreSQL source as the first `source_database_connections` row. Backfill all existing `accepted_queries` rows with this connection's ID.

**Rationale**: Clarify Q2 (LOCKED). The existing `AcceptedQuery` model already has `database_connection_id` as NOT NULL FK to `database_connections`. Phase 3 renames/extends `database_connections` to `source_database_connections` with new fields (lifecycle state, health status, schema introspection status, etc.).

**Migration Steps**:
1. Alembic migration renames `database_connections` → `source_database_connections`.
2. Add new columns: `database_type` enum, `lifecycle_state`, `health_status`, `last_health_check_at`, `schema_introspection_status`, `schema_last_refreshed_at`.
3. Update existing row(s) with `database_type='postgresql'`, `lifecycle_state='active'`, `health_status='untested'`.
4. Backfill any `accepted_queries` rows lacking a valid `database_connection_id` with the legacy connection ID.
5. Add `connection_id` nullable FK to `sessions` table.
