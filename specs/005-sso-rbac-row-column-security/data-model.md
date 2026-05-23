# Data Model — Phase 5: SSO, RBAC, Row/Column Security

**Created**: 2026-05-24
**Phase**: 5
**Migration**: `007_phase5_sso_rbac_security.py` (single migration, all new tables + user table modifications)

---

## New Tables

### `sso_providers`

SSO IdP configuration. One active provider per protocol type (OIDC or SAML).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `protocol` | `VARCHAR` (enum: `oidc`, `saml`) | NO | — | Protocol type |
| `display_name` | `VARCHAR` | NO | — | Admin-facing label |
| `issuer_url` | `VARCHAR` | YES | — | OIDC issuer URL |
| `client_id` | `VARCHAR` | YES | — | OIDC client ID |
| `encrypted_client_secret` | `VARCHAR` | YES | — | AES-256-GCM encrypted |
| `scopes` | `VARCHAR` | YES | `openid email profile groups` | OIDC scopes |
| `redirect_uri` | `VARCHAR` | YES | — | OIDC callback URL |
| `group_claim_name` | `VARCHAR` | NO | `groups` | Claim/attribute name for group membership |
| `saml_entity_id` | `VARCHAR` | YES | — | SAML SP entity ID |
| `saml_metadata_url` | `VARCHAR` | YES | — | SAML IdP metadata URL |
| `encrypted_saml_metadata_xml` | `TEXT` | YES | — | AES-256-GCM encrypted IdP metadata XML |
| `encrypted_saml_certificate` | `TEXT` | YES | — | AES-256-GCM encrypted IdP signing cert |
| `is_active` | `BOOLEAN` | NO | `true` | Enable/disable provider |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Constraints**: `UNIQUE(protocol)` — one active provider per protocol.

---

### `roles`

Platform roles. Each role defines permissions, allowed schema, row filters, column masks.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `name` | `VARCHAR(100)` | NO | — | Unique role name |
| `description` | `VARCHAR(500)` | YES | — | — |
| `priority` | `INTEGER` | NO | `100` | Lower = higher priority |
| `permissions` | `JSONB` | NO | `[]` | Array of permission strings from fixed set |
| `is_builtin` | `BOOLEAN` | NO | `false` | `true` for built-in admin role |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Constraints**: `UNIQUE(name)`, `UNIQUE(priority)`.

**Permissions fixed set**: `query.submit`, `query.history.view`, `admin.connections.manage`, `admin.roles.manage`, `admin.sso.manage`, `admin.audit.verify`.

---

### `role_connection_policies`

Per-role, per-connection access policy: allowed tables/columns, row filters, column masks.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `role_id` | `UUID` | NO | — | FK → `roles.id` ON DELETE CASCADE |
| `connection_id` | `UUID` | NO | — | FK → `source_database_connections.id` ON DELETE CASCADE |
| `allowed_tables` | `JSONB` | NO | `[]` | Array of `{"table": "t", "columns": ["c1","c2"]}` |
| `row_filters` | `JSONB` | NO | `[]` | Array of `{"table": "t", "filter": "dept = {user.role}"}` |
| `column_masks` | `JSONB` | NO | `[]` | Array of `{"table": "t", "columns": ["salary","ssn"]}` |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Constraints**: `UNIQUE(role_id, connection_id)`.

---

### `sso_group_mappings`

Maps SSO group claim values to platform roles.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `sso_group_value` | `VARCHAR` | NO | — | Group claim value from IdP |
| `role_id` | `UUID` | NO | — | FK → `roles.id` ON DELETE CASCADE |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Constraints**: `UNIQUE(sso_group_value)` — each group maps to exactly one role.

---

### `user_identities`

Links platform users to SSO identities. One user can have one local identity + one SSO identity.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `user_id` | `UUID` | NO | — | FK → `users.id` ON DELETE CASCADE |
| `provider` | `VARCHAR` (enum: `local`, `oidc`, `saml`) | NO | — | Auth provider |
| `subject_id` | `VARCHAR` | NO | — | IdP subject identifier (or username for local) |
| `email` | `VARCHAR` | YES | — | Email from IdP claims |
| `sso_groups` | `JSONB` | YES | `[]` | Raw groups from last login |
| `last_login_at` | `TIMESTAMPTZ` | YES | — | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Constraints**: `UNIQUE(provider, subject_id)`.

---

### `audit_log_entries`

Tamper-evident audit log with chained hashing.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | `BIGSERIAL` | NO | auto | PK, monotonically increasing |
| `sequence_number` | `BIGINT` | NO | — | Explicit sequence for verification |
| `timestamp` | `TIMESTAMPTZ` | NO | `now()` | Event time |
| `actor_id` | `UUID` | YES | — | FK → `users.id` SET NULL (null for system events) |
| `actor_identity` | `VARCHAR` | YES | — | Denormalized: username or SSO subject |
| `action_type` | `VARCHAR` | NO | — | Event category (see below) |
| `resource_type` | `VARCHAR` | YES | — | Affected resource type |
| `resource_id` | `VARCHAR` | YES | — | Affected resource ID (string, not UUID FK) |
| `outcome` | `VARCHAR` | NO | — | `success`, `failure`, `blocked` |
| `context` | `JSONB` | NO | `{}` | Sanitized event details (no secrets) |
| `prev_hash` | `VARCHAR(64)` | NO | — | Hash of previous entry (or `GENESIS`) |
| `row_hash` | `VARCHAR(64)` | NO | — | SHA-256(canonical_payload + prev_hash) |

**Constraints**: `UNIQUE(sequence_number)`. Index on `timestamp`, `action_type`, `actor_id`.

**No UPDATE/DELETE** through application. Append-only enforced by application layer.

**Action types**: `auth.login.success`, `auth.login.failure`, `auth.logout`, `auth.sso.validation`, `query.submit`, `query.validate.pass`, `query.validate.fail`, `query.execute`, `query.accept`, `query.reject`, `role.create`, `role.update`, `role.delete`, `role.mapping.change`, `sso.config.change`, `connection.create`, `connection.update`, `connection.delete`, `admin.config.change`, `access.denied`, `audit.verify`, `policy.schema_mismatch`.

**Retention**: 24 months minimum (Constitution IX). Cleanup via scheduled job (Phase 7+).

---

## Modified Tables

### `users` — Modifications

| Change | Column | Type | Notes |
|--------|--------|------|-------|
| ADD | `role_id` | `UUID` | FK → `roles.id` SET NULL. Null = unmapped (no access). |
| ADD | `is_builtin` | `BOOLEAN` | `true` for Phase 1 admin. Undeletable. |
| ADD | `auth_provider` | `VARCHAR` | `local`, `oidc`, `saml`. Default `local`. |
| MODIFY | `password_hash` | `VARCHAR` | Make nullable. SSO users have no password. |
| MODIFY | `role` | — | **DEPRECATED**. Replaced by `role_id` FK. Migration sets existing admin to built-in admin role. Keep column temporarily for backward compat; remove in Phase 6. |

---

## Redis Session Data — Extended

Existing `session:{session_id}` JSON payload extended:

```json
{
  "user_id": "uuid",
  "username": "string",
  "display_name": "string",
  "role": "string (deprecated, keep for compat)",
  "role_id": "uuid",
  "role_name": "string",
  "permissions": ["query.submit", "query.history.view"],
  "auth_provider": "local|oidc|saml",
  "subject_id": "string",
  "email": "string|null",
  "created_at": 1234567890.0,
  "last_activity": 1234567890.0
}
```

---

## Entity Relationship Diagram

```
users ──< user_identities
  │
  └── role_id ──> roles ──< role_connection_policies ──> source_database_connections
                    │
                    └──< sso_group_mappings

sso_providers (standalone config)

audit_log_entries (standalone, FK to users for actor_id)
```

---

## Migration Notes

1. Single migration file `007_phase5_sso_rbac_security.py`.
2. Creates all new tables.
3. Adds `role_id`, `is_builtin`, `auth_provider` columns to `users`.
4. Makes `password_hash` nullable on `users`.
5. Creates built-in admin role with all permissions, priority=0.
6. Sets existing admin user's `role_id` to built-in admin role, `is_builtin=true`, `auth_provider='local'`.
7. Seeds genesis audit log entry with `prev_hash='GENESIS'`.
8. All operations are idempotent (safe to re-run).
