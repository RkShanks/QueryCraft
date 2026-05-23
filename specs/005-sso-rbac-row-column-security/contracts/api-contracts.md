# API Contracts — Phase 5: SSO, RBAC, Row/Column Security

**Created**: 2026-05-24
**Phase**: 5

All endpoints under `/api/v1/`. Errors use existing `ErrorResponse` / `ValidationErrorResponse` schemas with `message_key` for i18n.

---

## SSO Authentication Endpoints

### `GET /auth/sso/providers`
**Permission**: Public (unauthenticated)
**Purpose**: List configured SSO providers for sign-in page display.

**Response 200**:
```json
{
  "providers": [
    {
      "protocol": "oidc",
      "display_name": "Corporate SSO",
      "login_url": "/api/v1/auth/sso/oidc/login"
    },
    {
      "protocol": "saml",
      "display_name": "SAML Provider",
      "login_url": "/api/v1/auth/sso/saml/login"
    }
  ]
}
```

---

### `GET /auth/sso/oidc/login`
**Permission**: Public
**Purpose**: Initiate OIDC authorization code flow. Redirects to IdP.

**Response 302**: Redirect to IdP authorization endpoint with `state`, `nonce` stored in Redis.

---

### `GET /auth/sso/oidc/callback`
**Permission**: Public
**Purpose**: Process OIDC callback. Validates ID token, resolves role, creates session.

**Query params**: `code`, `state`
**Response 302**: Redirect to `/` on success with session cookie set.
**Error 302**: Redirect to `/sign-in?error=sso_no_role` (or `sso_validation_failed`, `sso_provider_unavailable`). Error codes mapped to i18n keys on frontend.

---

### `GET /auth/sso/saml/login`
**Permission**: Public
**Purpose**: Initiate SAML AuthnRequest. Redirects to IdP.

**Response 302**: Redirect to SAML IdP with AuthnRequest.

---

### `POST /auth/sso/saml/callback` (ACS)
**Permission**: Public
**Purpose**: Process SAML assertion callback.

**Body**: Form-encoded `SAMLResponse`, `RelayState`
**Response 302**: Redirect to `/` on success.
**Error 302**: Redirect to `/sign-in?error=<code>`.

---

### `POST /auth/sign-in` (existing, modified)
**Permission**: Public
**Purpose**: Local password login — **admin only** in Phase 5.

**Modification**: If user's `auth_provider != 'local'`, reject with 401. If user has no admin permissions, reject with 401. Generic error message, no account existence leak.

---

### `GET /auth/me` (existing, extended)
**Response 200** — Extended `UserProfile`:
```json
{
  "id": "uuid",
  "username": "string",
  "display_name": "string",
  "role": "string (deprecated)",
  "role_id": "uuid",
  "role_name": "string",
  "permissions": ["query.submit", "query.history.view"],
  "auth_provider": "local|oidc|saml"
}
```

---

## SSO Admin Configuration Endpoints

### `GET /admin/sso/providers`
**Permission**: `admin.sso.manage`
**Response 200**:
```json
{
  "providers": [
    {
      "id": "uuid",
      "protocol": "oidc",
      "display_name": "Corporate SSO",
      "issuer_url": "https://idp.example.com",
      "client_id": "app-client-id",
      "client_secret_masked": "●●●●●●●●",
      "scopes": "openid email profile groups",
      "redirect_uri": "https://app.example.com/api/v1/auth/sso/oidc/callback",
      "group_claim_name": "groups",
      "is_active": true,
      "created_at": "iso8601",
      "updated_at": "iso8601"
    }
  ]
}
```

### `POST /admin/sso/providers`
**Permission**: `admin.sso.manage`
**Body**:
```json
{
  "protocol": "oidc|saml",
  "display_name": "string",
  "issuer_url": "string (oidc)",
  "client_id": "string (oidc)",
  "client_secret": "string (oidc, write-only)",
  "scopes": "string (oidc)",
  "redirect_uri": "string (oidc)",
  "group_claim_name": "string",
  "saml_entity_id": "string (saml)",
  "saml_metadata_url": "string (saml)",
  "saml_metadata_xml": "string (saml, write-only)",
  "saml_certificate": "string (saml, write-only)"
}
```
**Response 201**: Created provider (secrets masked).
**Error 409**: Provider for this protocol already exists.
**Error 422**: Validation errors (invalid issuer, unreachable metadata URL).

### `PUT /admin/sso/providers/{provider_id}`
**Permission**: `admin.sso.manage`
**Body**: Same as POST (partial update).
**Response 200**: Updated provider (secrets masked).

### `DELETE /admin/sso/providers/{provider_id}`
**Permission**: `admin.sso.manage`
**Response 204**: Deleted.

---

## Role Management Endpoints

### `GET /admin/roles`
**Permission**: `admin.roles.manage`
**Response 200**:
```json
{
  "roles": [
    {
      "id": "uuid",
      "name": "Analyst",
      "description": "Read-only analyst role",
      "priority": 10,
      "permissions": ["query.submit", "query.history.view"],
      "is_builtin": false,
      "group_mappings": [
        {"id": "uuid", "sso_group_value": "analysts"}
      ],
      "connection_policy_count": 2,
      "created_at": "iso8601",
      "updated_at": "iso8601"
    }
  ]
}
```

### `GET /admin/roles/{role_id}`
**Permission**: `admin.roles.manage`
**Response 200**: Full role detail including `connection_policies`.
```json
{
  "id": "uuid",
  "name": "Analyst",
  "description": "string",
  "priority": 10,
  "permissions": ["query.submit", "query.history.view"],
  "is_builtin": false,
  "group_mappings": [...],
  "connection_policies": [
    {
      "id": "uuid",
      "connection_id": "uuid",
      "connection_display_name": "Production PG",
      "allowed_tables": [
        {"table": "orders", "columns": ["id", "customer_id", "total"]}
      ],
      "row_filters": [
        {"table": "orders", "filter": "region = {user.role}"}
      ],
      "column_masks": [
        {"table": "customers", "columns": ["email", "phone"]}
      ]
    }
  ],
  "created_at": "iso8601",
  "updated_at": "iso8601"
}
```

### `POST /admin/roles`
**Permission**: `admin.roles.manage`
**Body**:
```json
{
  "name": "string",
  "description": "string",
  "priority": 10,
  "permissions": ["query.submit", "query.history.view"],
  "group_mappings": ["analysts", "data-team"],
  "connection_policies": [
    {
      "connection_id": "uuid",
      "allowed_tables": [...],
      "row_filters": [...],
      "column_masks": [...]
    }
  ]
}
```
**Response 201**: Created role.
**Error 409**: Duplicate name, duplicate priority, or duplicate group mapping.
**Error 422**: Validation errors (invalid filter SQL, nonexistent columns, invalid permissions).

### `PUT /admin/roles/{role_id}`
**Permission**: `admin.roles.manage`
**Body**: Same as POST.
**Response 200**: Updated role.
**Error 403**: Cannot modify built-in admin role's core properties.

### `DELETE /admin/roles/{role_id}`
**Permission**: `admin.roles.manage`
**Response 204**: Deleted.
**Error 403**: Cannot delete built-in admin role.

---

### `POST /admin/roles/{role_id}/test-policy`
**Permission**: `admin.roles.manage`
**Purpose**: Dry-run a sample question against role policy (FR-136).
**Body**:
```json
{
  "question": "Show me all customers",
  "connection_id": "uuid"
}
```
**Response 200**:
```json
{
  "accessible_tables": ["customers"],
  "accessible_columns": {"customers": ["id", "name"]},
  "blocked_tables": ["orders"],
  "applicable_row_filters": [{"table": "customers", "filter": "region = 'US'"}],
  "masked_columns": {"customers": ["email"]},
  "would_be_allowed": true
}
```

---

## SSO Group Mapping Endpoints

### `GET /admin/sso/group-mappings`
**Permission**: `admin.roles.manage`
**Response 200**:
```json
{
  "mappings": [
    {
      "id": "uuid",
      "sso_group_value": "analysts",
      "role_id": "uuid",
      "role_name": "Analyst",
      "created_at": "iso8601"
    }
  ]
}
```

### `POST /admin/sso/group-mappings`
**Permission**: `admin.roles.manage`
**Body**: `{"sso_group_value": "string", "role_id": "uuid"}`
**Response 201**: Created.
**Error 409**: Duplicate group value.

### `DELETE /admin/sso/group-mappings/{mapping_id}`
**Permission**: `admin.roles.manage`
**Response 204**: Deleted.

---

## Audit Log Endpoints

### `POST /admin/audit/verify`
**Permission**: `admin.audit.verify`
**Purpose**: Trigger chain integrity verification.
**Response 200**:
```json
{
  "verified": true,
  "entries_checked": 15234,
  "first_break_at": null,
  "verified_at": "iso8601"
}
```
**Response 200** (broken chain):
```json
{
  "verified": false,
  "entries_checked": 15234,
  "first_break_at": 8291,
  "verified_at": "iso8601"
}
```

### `GET /admin/audit/status`
**Permission**: `admin.audit.verify`
**Purpose**: Return last verification result and entry count.
**Response 200**:
```json
{
  "total_entries": 15234,
  "last_verification": {
    "verified": true,
    "verified_at": "iso8601",
    "entries_checked": 15234
  }
}
```

---

## Modified Existing Endpoints

### `POST /query/submit` (modified)
**New behavior**:
1. Check `query.submit` permission. 403 if missing.
2. Filter schema context by role's `allowed_tables`/`allowed_columns` for connection.
3. After execution, apply column masking on result rows.
4. Apply row filter injection via `sqlglot` AST before execution.
5. Emit `query.submit` + `query.execute` audit log entries.

### `GET /history` / `GET /history/{query_id}` (modified)
**New behavior**:
1. Check `query.history.view` permission. 403 if missing.
2. Filter by `user_id = current_user.id`. No cross-user visibility.

### `POST /query/accept` / `POST /query/reject` / `POST /query/regenerate` (modified)
**New behavior**: Emit audit log entries for accept/reject.

### All `/admin/*` endpoints (modified)
**New behavior**: Check relevant admin permission. 403 if missing. Emit audit log entries.

---

## Error Code Additions

| Error Code | i18n Key | Context |
|-----------|----------|---------|
| `sso_no_role` | `error.ssoNoRole` | User SSO groups don't map to any role |
| `sso_validation_failed` | `error.ssoValidationFailed` | Token/assertion validation failed |
| `sso_provider_unavailable` | `error.ssoProviderUnavailable` | IdP unreachable |
| `sso_not_configured` | `error.ssoNotConfigured` | No SSO provider configured |
| `forbidden` | `error.forbidden` | Missing required permission |
| `local_login_admin_only` | `error.localLoginAdminOnly` | Non-admin attempted local login |
| `role_not_found` | `error.roleNotFound` | Referenced role doesn't exist |
| `duplicate_group_mapping` | `error.duplicateGroupMapping` | SSO group already mapped |
| `column_masked` | `query.columnMasked` | Column value was masked |
| `query_blocked_policy` | `error.queryBlockedPolicy` | Query references disallowed schema |
| `filter_validation_failed` | `error.filterValidationFailed` | Row filter SQL invalid |
| `policy_schema_conflict` | `error.policySchemaConflict` | Row filter references column removed by schema drift; query blocked (fail-closed) |
| `audit_chain_broken` | `error.auditChainBroken` | Audit chain verification failed |
| `builtin_role_protected` | `error.builtinRoleProtected` | Cannot delete/modify built-in role |
