# Research — Phase 5: SSO, RBAC, Row/Column Security

**Created**: 2026-05-24
**Phase**: 5

---

## R-001: OIDC Library Selection

**Decision**: Use **Authlib** (`authlib>=1.3.0`) for OIDC client implementation.

**Rationale**: Authlib is industry-standard, well-maintained, standards-compliant OIDC client. Integrates natively with Starlette/FastAPI. Handles authorization code flow, ID token validation (issuer, audience, signature, expiry, nonce), JWKS key rotation. Already compatible with project's `httpx` dependency.

**Alternatives considered**:
- `python-jose` + manual flow: More code, less maintained, no integrated flow handling.
- Auth0/WorkOS SDK: SaaS dependency inappropriate for single-tenant on-prem KSA deployment.
- `oauthlib`: Lower level, lacks OIDC-specific helpers.

---

## R-002: SAML Library Selection

**Decision**: Use **python3-saml** (`python3-saml>=1.16.0`) with strict XML signature validation and assertion replay cache.

**Rationale**: Despite maintenance concerns, python3-saml remains the only viable pure-Python SAML SP library. For single-tenant on-prem deployment (not SaaS), it provides adequate control. Mitigations: pin version, wrap in thin abstraction layer for future swap, enforce strict validation checks (signature required, audience match, assertion expiry, replay detection via Redis TTL cache).

**Alternatives considered**:
- SSOReady/WorkOS: SaaS dependency, unacceptable for on-prem KSA deployment.
- `pysaml2`: Heavier, more complex, less documentation, but more actively maintained. If `python3-saml` becomes unmaintainable, `pysaml2` is fallback.
- Manual XML parsing: Too error-prone for SAML's XML security requirements.

**Mitigations for python3-saml**:
1. Wrap behind `SamlProvider` abstraction; swap to `pysaml2` later if needed.
2. Pin exact version in `pyproject.toml`.
3. XML signature validation MUST be enforced (never disabled even in dev).
4. Assertion replay protection via Redis-backed ID cache (TTL = assertion validity window).

---

## R-003: Chained Hash Audit Log Strategy

**Decision**: Application-layer SHA-256 chained hashing with PostgreSQL append-only table.

**Rationale**: Application-layer hashing gives full control over serialization, avoids DB trigger complexity, works with existing SQLAlchemy/Alembic setup. SHA-256 is sufficient for tamper-evidence in single-tenant deployment.

**Implementation pattern**:
1. Each entry: `sequence_number` (monotonic), `payload` (canonical JSON), `prev_hash`, `row_hash = SHA-256(canonical_payload + prev_hash)`.
2. Genesis entry: `prev_hash = "GENESIS"`, `row_hash = SHA-256(payload + "GENESIS")`.
3. Canonical JSON: sorted keys, no whitespace, ISO 8601 UTC timestamps with microsecond precision.
4. Write serialization: single async writer with `SELECT ... FOR UPDATE` on last entry to prevent race conditions.
5. Verification: walk chain from genesis, recompute each hash, report first break.

**Alternatives considered**:
- PostgreSQL trigger: Adds DB CPU overhead, harder to test, couples hashing to DB.
- Merkle tree: Overkill for sequential log; chained hash is simpler and sufficient.
- External anchoring (S3/blockchain): Deferred; single-tenant deployment doesn't warrant external trust anchor in Phase 5.

---

## R-004: Row Filter Enforcement Strategy

**Decision**: Application-layer SQL `WHERE` clause appending via `sqlglot` AST manipulation, cross-dialect.

**Rationale**: Project already depends on `sqlglot>=26.0.0` for SQL parsing. Using AST manipulation (not string concatenation) prevents SQL injection in filter fragments. `sqlglot` supports PostgreSQL, MySQL, T-SQL dialects natively, enabling cross-dialect enforcement from single filter definition.

**Implementation pattern**:
1. Admin authors raw SQL WHERE fragments per role per connection (e.g., `department = {user.role}`).
2. At save time: parse fragment with `sqlglot.parse()`, validate:
   - All referenced columns exist in connection schema. **Reject save if any column is absent** (fail-closed).
   - No subqueries (`SELECT` inside fragment).
   - No function calls beyond safe allowlist (`LOWER`, `UPPER`, `TRIM`, `COALESCE`).
   - No `UNION`, `JOIN`, `INSERT`, `UPDATE`, `DELETE`.
   - No comments (`--`, `/*`).
3. At query time: parse generated SQL with `sqlglot`, inject filter into `WHERE` clause via AST `AND` conjunction. Resolve `{user.*}` placeholders to parameterized bind values (not string interpolation).
4. At query time (schema drift guard): if a required filter references a column no longer present in the connection schema, **block the query before execution** with a localized sanitized policy error. Emit `policy.schema_mismatch` audit event. Never execute without a required row filter.
5. Dialect transpilation: `sqlglot.transpile()` handles identifier quoting per dialect.

**Alternatives considered**:
- Database-native RLS (PostgreSQL `CREATE POLICY`): Only works for PostgreSQL, not MySQL/MSSQL.
- String concatenation: SQL injection risk.
- ORM-level filtering: Doesn't work because SQL is LLM-generated, not ORM-generated.

---

## R-005: Column Masking Strategy

**Decision**: Post-query result-set masking at application layer before data reaches frontend.

**Rationale**: Consistent with spec assumption. Masking at result level (not DB level) works identically across all three dialects. Masking is display-level only — SQL computation (GROUP BY, ORDER BY, JOIN) uses real values. Only output values are replaced with `***`.

**Implementation pattern**:
1. After query execution, before response serialization, check column names against role's masked column set for current connection.
2. Replace values in masked columns with `"***"` placeholder.
3. Add `masked: true` flag to `ColumnMeta` for affected columns.
4. Frontend renders localized "column was masked" indicator.

**Alternatives considered**:
- Database-level dynamic data masking: PostgreSQL has no native DDM; MSSQL has it but MySQL doesn't. Cross-dialect inconsistency.
- SQL rewrite (SELECT replacement): Would break GROUP BY/ORDER BY semantics.

---

## R-006: Secret Storage and Redaction

**Decision**: Reuse existing AES-256-GCM encryption (`app.core.encryption`) for SSO secrets (client secret, SAML certificates). Redaction via never-return pattern.

**Rationale**: Existing `encrypt()`/`decrypt()` using `PLATFORM_ENCRYPTION_KEY` already proven for DB credentials. SSO secrets follow same pattern. API never returns decrypted secrets; GET responses return masked placeholder (`"●●●●●●●●"`). Admin can only set (POST/PUT), never read back.

---

## R-007: Session Model Extension

**Decision**: Extend existing Redis session with `provider`, `subject_id`, `role_id`, `permissions` fields. Session TTL unchanged (8h idle timeout). Add concurrent session limit per user (configurable, default: 5).

**Rationale**: Existing `SessionMiddleware` + Redis session store is proven. Adding SSO-specific claims to session data is non-breaking. Concurrent session limit prevents session accumulation.

**Implementation pattern**:
1. SSO login: after token/assertion validation, look up user identity in DB (create if first login), resolve role via group mapping, store enriched session in Redis.
2. Local admin login: existing flow, role = built-in admin.
3. Session data structure adds: `provider` (local/oidc/saml), `subject_id`, `role_id`, `role_name`, `permissions` (list of permission strings).

---

## R-008: LLM Schema Filtering

**Decision**: Filter `SchemaContext` before it reaches LLM prompt builder. Only role-allowed tables/columns included.

**Rationale**: Constitution I + FR-128/FR-129 mandate LLM never receives unauthorized schema. Filtering at schema context construction (before prompt) is cleanest integration point. Existing `SchemaContext` model (`evaluator/schema_context.py`) already has `tables` with `columns` — filtering is a straightforward list comprehension.

**Implementation pattern**:
1. Load full `ConnectionSchemaEntry` rows for connection.
2. Filter to role-allowed tables and columns.
3. Build `SchemaContext` from filtered entries only.
4. Pass filtered context to LLM.

---

## R-009: Cross-Dialect Row Filter Application

**Decision**: Store filters as dialect-agnostic SQL fragments. Use `sqlglot` to parse and transpile per dialect at query time.

**Rationale**: Admin writes filter once. Platform transpiles to PG/MySQL/T-SQL automatically. `sqlglot` handles identifier quoting (`"col"` vs `` `col` `` vs `[col]`) and dialect-specific syntax.

**Edge cases**:
- Filter references column absent at save time: **reject save** with localized validation error. Admin must fix fragment.
- Filter references column that was dropped after save (schema drift): **block query before execution** with localized policy error. Emit `policy.schema_mismatch` audit event. Never execute without required filter (fail-closed).
- Filter uses `{user.email}` placeholder: resolved to parameterized value, never interpolated as string.
