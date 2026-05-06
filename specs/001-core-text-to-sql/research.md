# Research: Core Text-to-SQL Vertical Slice

**Branch**: `001-core-text-to-sql` | **Date**: 2026-05-03  
**Spec**: [spec.md](file:///home/avril/querycraft/specs/001-core-text-to-sql/spec.md)

## R-001: LLM Prompt Structure for Text-to-SQL Generation

**Decision**: Use a structured system prompt with chain-of-thought reasoning, dynamic schema injection, and strict output formatting.

**Rationale**: Research and industry best practices (DIN-SQL, DAIL-SQL papers; production text-to-SQL systems) consistently show that:
1. **Chain-of-thought prompting** dramatically improves SQL accuracy, especially for multi-join and aggregate queries. The LLM should first reason about which tables/joins are needed, then produce the SQL.
2. **Dynamic schema injection** (include only relevant tables rather than the entire schema) reduces token waste and model confusion. However, in Phase 1 with a single database, full schema inclusion is acceptable for schemas under ~200 tables. If the schema exceeds the LLM's context window, the system surfaces a configuration error per the spec's edge case handling.
3. **Strict output format** — SQL must be wrapped in a ```sql code fence — makes extraction deterministic and prevents the model from embedding explanation text inside the SQL.
4. **Negative examples on retry** — when a rejected SQL is provided as negative context, include both the SQL and a brief explanation of why it was rejected (e.g., "user indicated results were incorrect"), so the LLM understands what to change.

**Prompt structure** (conceptual):
```
SYSTEM: You are a PostgreSQL SQL expert. Given a database schema and a user question,
generate a single read-only SELECT statement (or CTE) that answers the question.

RULES:
- Output ONLY valid PostgreSQL SQL
- Use ONLY tables and columns from the provided schema
- Never use INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, CREATE
- Wrap your SQL in ```sql ... ``` markers
- Think step-by-step: first identify relevant tables, then plan joins, then write SQL

SCHEMA:
{schema_context}

{negative_examples_block}

USER QUESTION: {question}
```

**Alternatives considered**:
- Few-shot prompting with static examples: Rejected because static examples become stale as the schema evolves and may mislead the model for dissimilar queries.
- RAG over documentation: Deferred to a later phase. Phase 1 uses direct schema injection.
- Tool-calling / function-calling API: Adds complexity without clear benefit in Phase 1 where the output is always "one SQL string."

---

## R-002: Session Backing Store — Redis vs. Database

**Decision**: Redis 7 for the session store.

**Rationale**:
1. **Sub-millisecond latency**: Session lookups happen on every authenticated request. Redis provides sub-millisecond reads vs. multi-millisecond DB queries.
2. **Native TTL**: Redis natively supports key expiry (8-hour idle timeout per FR-003) without application-level cleanup jobs.
3. **Invalidation simplicity**: `DEL session:{id}` instantly invalidates a session. This is critical for Phase 5 when SSO introduces "logout all sessions" requirements.
4. **Single-region KSA deployment**: A single Redis instance (with optional RDB persistence for crash recovery) is sufficient for Phase 1's single-user scale. Redis Sentinel or Cluster is deferred until multi-user load in Phase 5+.
5. **Operational overhead**: Adding Redis to the stack is minimal — it's already containerized in docker-compose and requires no schema migrations.

**Risk mitigation**: If Redis is temporarily unavailable, authenticated requests fail with a 503 "Service Unavailable" — the user must wait for Redis to recover. This is acceptable for Phase 1's single-user model. The session middleware should catch connection errors and return a clear error rather than crashing.

**Alternatives considered**:
- Database-backed sessions (platform PostgreSQL): Rejected because every authenticated request would add a DB query, TTL cleanup requires a periodic task, and invalidation is slower. Would require a `sessions` table and garbage collection.
- Stateless JWT: Explicitly rejected by the user's technical context. JWTs are harder to invalidate, which conflicts with Phase 5's SSO requirements.

---

## R-003: Source-DB Schema Introspection and Cache Invalidation

**Decision**: Use `information_schema` views for portable, readable introspection. Cache in-memory with a configurable TTL (default: 5 minutes). Support manual refresh via an admin API endpoint.

**Rationale**:
1. **`information_schema` vs. `pg_catalog`**: `information_schema` provides a SQL-standard, human-readable interface sufficient for extracting table names, column names, column types, primary keys, and foreign key relationships — exactly what FR-008 requires. Although `pg_catalog` is faster, the introspection query runs at most once per TTL interval, not per-request.
2. **In-memory cache with TTL**: A 5-minute TTL balances freshness with cost. Schema changes in a production analytics database are infrequent (daily at most). The cache is per-process; since Phase 1 runs a single backend instance, no cross-process invalidation is needed.
3. **Manual refresh endpoint**: An admin API endpoint (`POST /api/v1/admin/refresh-schema`) allows the operator to force a cache refresh after a known schema change, without waiting for TTL expiry.
4. **PostgreSQL `LISTEN/NOTIFY` with `ddl_command_end` event triggers**: This is the gold-standard approach but requires DDL trigger privileges on the customer's source database, which is explicitly a read-only connection (FR-005). Therefore, event-trigger-based invalidation is infeasible in Phase 1 and deferred.

**Schema context payload** (sent to the LLM):
```
Tables:
- orders (id: integer PK, customer_id: integer FK→customers.id, total: numeric, created_at: timestamp)
- customers (id: integer PK, name: text, email: text)
...

Foreign Keys:
- orders.customer_id → customers.id
```

**Alternatives considered**:
- `pg_catalog` direct queries: Faster but PostgreSQL-specific. Since Phase 1 is already PostgreSQL-only and `information_schema` is fast enough at once-per-5-minutes, portability is preferred for when Phase 3 adds MySQL/MSSQL.
- No cache (introspect on every query): Rejected for performance reasons — introspection queries can take 200+ ms on large schemas.
- `LISTEN/NOTIFY` event triggers: Infeasible because the source DB connection is read-only.

---

## R-004: sqlglot PostgreSQL Support — CTEs, Window Functions, JSON Operators

**Decision**: sqlglot is suitable for the Phase 1 evaluator. It parses PostgreSQL CTEs, window functions, and most JSON operators correctly. A targeted test suite will cover PostgreSQL-specific syntax to catch any edge-case false positives.

**Rationale**:
1. **PostgreSQL dialect support**: sqlglot has a dedicated `postgres` dialect that handles CTEs (`WITH ... AS`), window functions (`ROW_NUMBER() OVER (...)`), lateral joins, array operators, and standard JSON operators (`->`, `->>`, `#>`, `#>>`).
2. **Identifier extraction**: `sqlglot.parse(sql, dialect="postgres")` produces an AST from which table and column identifiers can be extracted via `expression.find_all(exp.Table)` and `expression.find_all(exp.Column)`. This is the core mechanism for the evaluator's schema validation (FR-010d, FR-010e).
3. **Unsafe pattern detection**: The AST walk can detect `INSERT`, `UPDATE`, `DELETE`, `DROP`, `TRUNCATE`, `ALTER`, `CREATE` nodes directly, which is more reliable than regex-based keyword scanning (avoids false positives on column names like `update_date`).
4. **Known limitations**: Some highly PostgreSQL-specific syntax (custom operators, PL/pgSQL blocks) may not parse. However, PL/pgSQL blocks would be caught by the multi-statement check (FR-010c) and the read-only check (FR-010a). Custom operators are edge cases that the evaluator can flag for manual review in a later phase.
5. **Mitigation**: The evaluator test suite includes a dedicated test file with 50+ PostgreSQL-specific SQL patterns (CTEs, window functions, JSON operators, array operations, DISTINCT ON, LIMIT/OFFSET) to validate that sqlglot parses them without false positives.

**Alternatives considered**:
- `pglast` (PostgreSQL-specific parser using `libpg_query`): Most accurate for PostgreSQL but adds a C dependency and is not portable to MySQL/MSSQL in Phase 3. sqlglot handles all four dialects.
- Regex-based evaluation: Rejected as fragile and prone to false positives (e.g., `UPDATE` as a column alias).
- No AST parsing (rely solely on the LLM to produce safe SQL): Violates Constitution Principle II and FR-010.

---

## R-005: Best Practices — FastAPI Layered Architecture

**Decision**: Adopt the layered architecture pattern as described in the technical context. This is the established production pattern for FastAPI.

**Rationale**: FastAPI's async-first, dependency-injection-native design maps naturally to a layered architecture where:
- Routers are thin controllers that delegate to injected services
- Services encapsulate business logic and are testable in isolation
- Repositories abstract data access, enabling mock-based unit tests
- Schemas (Pydantic DTOs) are strictly separate from ORM models, preventing wire-format/DB-schema coupling

**Alternatives considered**:
- Strict MVC: Rejected because FastAPI has no server-side "View" layer — the frontend is a separate SPA.
- Domain-driven design (DDD): Overkill for Phase 1's scope. The single bounded context (query generation) doesn't benefit from aggregates, value objects, or domain events yet.

---

## R-006: Best Practices — OpenAPI Contract-First Development

**Decision**: Generate the OpenAPI specification at backend build time from FastAPI's auto-generated schema. Frontend types are generated from this document using `openapi-typescript-codegen`. Contract tests run via `schemathesis`.

**Rationale**: Constitution Principle XII mandates the API contract as the single source of truth. FastAPI auto-generates OpenAPI 3.1 from Pydantic schemas and router definitions, which means the contract is always in sync with the implementation. The generated frontend client eliminates hand-written request/response types, preventing drift.

**Alternatives considered**:
- Manual OpenAPI-first (write YAML, then implement): Adds maintenance overhead and risks spec-code divergence. FastAPI's auto-generation is more reliable.
- GraphQL: Adds complexity without benefit for Phase 1's ~8 endpoints. REST is simpler and better tooled for contract testing.

---

## R-007: CSRF Strategy for SPA + Cookie-Based Session

**Decision**: Enforce `SameSite=Strict` on the session cookie AND validate the `Origin` header on all state-changing requests (POST/PUT/PATCH/DELETE) against a configurable allow-list of frontend origins.

**Rationale**:
1. **SameSite=Strict**: Prevents the browser from sending the session cookie on any cross-origin request, including top-level navigations. This is the strongest SameSite mode and is appropriate because the frontend is a SPA — there are no cross-site navigations that need the cookie.
2. **Origin header validation**: Defense-in-depth. Even if a browser bug bypasses SameSite, the backend rejects any state-changing request whose `Origin` header is missing or not in the configured allow-list (`ALLOWED_ORIGINS` env var, default `["http://localhost:5173"]` for dev). The middleware returns `403 Forbidden` with a structured error.
3. **No CSRF token**: Traditional double-submit CSRF tokens add complexity and are largely redundant when SameSite=Strict is enforced and Origin validation is in place. Deferred unless a future phase requires SameSite=Lax (e.g., for SSO redirect flows in Phase 5).

**Implementation**:
- Session cookie flags: `HttpOnly=True`, `Secure=True` (HTTPS), `SameSite=Strict`, `Path=/api`.
- Middleware in `core/security.py`: on every POST/PUT/PATCH/DELETE request, extract the `Origin` header. If absent or not in `ALLOWED_ORIGINS`, return `403`.
- `ALLOWED_ORIGINS` is a list of strings in the config (pydantic-settings), defaulting to `["http://localhost:5173"]`.

**Alternatives considered**:
- SameSite=Lax + CSRF token: Lax allows the cookie on top-level GET navigations from other sites. Since the SPA has no server-rendered pages, Lax offers no benefit over Strict and requires a compensating CSRF token.
- SameSite=None (for cross-origin API usage): Not applicable — the frontend and backend share the same origin in production (reverse proxy).

---

## R-008: Column-Level Encryption for Source-DB Credentials

**Decision**: Encrypt `database_connections.encrypted_password` with AES-256-GCM using a 32-byte key loaded from the `PLATFORM_ENCRYPTION_KEY` environment variable (base64-encoded). The IV is randomly generated per encryption and stored alongside the ciphertext in the same column (prefixed).

**Rationale**:
1. **Defense-in-depth**: Even if an attacker gains read access to the platform database (via SQL injection in a future phase, a backup leak, or a misconfigured replica), the source-DB password remains encrypted at the application layer. Disk-level encryption alone does not protect against these attack vectors.
2. **AES-256-GCM**: Provides both confidentiality and integrity (authenticated encryption). The 96-bit IV is randomly generated per encryption using `os.urandom(12)`. The ciphertext format in the column is: `base64(iv || ciphertext || tag)`.
3. **Key management**: The encryption key is loaded from `PLATFORM_ENCRYPTION_KEY` (base64-encoded 32 bytes). It is never committed to the repository, never logged, and never exposed via the API. If the env var is missing at startup, the application fails fast with a clear error.
4. **Key rotation**: Deferred to a later phase. Phase 1 uses a single static key. A future phase will add a `key_version` field and a rotation CLI command.

**Implementation**:
- `core/encryption.py`: `encrypt(plaintext: str, key: bytes) -> str` and `decrypt(ciphertext: str, key: bytes) -> str` functions using Python's `cryptography` library (`Fernet` is not used; raw AES-256-GCM via `cryptography.hazmat.primitives.ciphers.aead.AESGCM`).
- `database_connections.encrypted_password` stores the base64-encoded `iv || ciphertext || tag` output.
- Decryption happens only at connection time in `SourceDBConnector`, never in API responses.

**Alternatives considered**:
- Fernet (from `cryptography`): Simpler API but uses AES-128-CBC, not AES-256-GCM. GCM provides authenticated encryption, which is preferred.
- Vault/KMS integration: Ideal for production but adds infrastructure complexity. Deferred to a later phase where a KMS may be available in the KSA deployment.
- Storing passwords in env vars only (no DB column): Would work for Phase 1's single connection, but breaks Phase 3's multi-database support where connections are added dynamically via the admin UI.
