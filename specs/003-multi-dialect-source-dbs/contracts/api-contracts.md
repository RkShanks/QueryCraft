# API Contracts — Phase 3: Multi-Dialect SQL and Multiple Source Databases

**Created**: 2026-05-18
**OpenAPI Version**: 3.1.0
**Base Path**: `/api/v1`
**Auth**: Session cookie (`require_admin_user` for admin endpoints, `require_user` for user endpoints)

---

## New Endpoints

### Admin Connection Management

#### `GET /api/v1/admin/connections`

List all source database connections (all lifecycle states visible to admin).

**Auth**: `require_admin_user`

**Response 200**:
```json
{
  "connections": [
    {
      "id": "uuid",
      "display_name": "Production PG",
      "database_type": "postgresql",
      "host": "db.example.com",
      "port": 5432,
      "database_name": "analytics",
      "username": "reader",
      "ssl_mode": "require",
      "lifecycle_state": "active",
      "health_status": "healthy",
      "last_health_check_at": "2026-05-18T12:00:00Z",
      "health_error_category": null,
      "schema_introspection_status": "success",
      "schema_last_refreshed_at": "2026-05-18T12:00:05Z",
      "created_at": "2026-05-18T10:00:00Z",
      "updated_at": "2026-05-18T12:00:05Z"
    }
  ]
}
```

**Note**: `encrypted_password` is NEVER returned. No `password` field in response.

---

#### `POST /api/v1/admin/connections`

Create a new source database connection. On success, auto-triggers health check + schema introspection (FR-093).

**Auth**: `require_admin_user`

**Request**:
```json
{
  "display_name": "Production MySQL",
  "database_type": "mysql",
  "host": "mysql.example.com",
  "port": 3306,
  "database_name": "analytics",
  "username": "reader",
  "password": "s3cret",
  "ssl_mode": "require"
}
```

**Response 201**:
```json
{
  "id": "uuid",
  "display_name": "Production MySQL",
  "database_type": "mysql",
  "host": "mysql.example.com",
  "port": 3306,
  "database_name": "analytics",
  "username": "reader",
  "ssl_mode": "require",
  "lifecycle_state": "active",
  "health_status": "untested",
  "schema_introspection_status": "none",
  "created_at": "2026-05-18T14:00:00Z",
  "updated_at": "2026-05-18T14:00:00Z"
}
```

**Note**: Password is NOT returned. Health check + introspection run asynchronously after response; poll `GET /admin/connections/{id}` for updated status.

**Validation**:
- `database_type` must be one of: `postgresql`, `mysql`, `mssql`
- `display_name` required, max 255 chars
- `host` required, non-empty
- `port` required, 1–65535
- `database_name` required, non-empty
- `username` required, non-empty
- `password` required on create, min 1 char

**Error 422**: Validation failure with `message_key` per field.
**Error 409**: `DB_CREDENTIAL_KEY` not configured → `{"error": "credential_config_error", "message_key": "error.credential_config"}`.

---

#### `PUT /api/v1/admin/connections/{connection_id}`

Update an existing connection. All fields editable. Password is optional (omit to keep existing).

**Auth**: `require_admin_user`

**Request**:
```json
{
  "display_name": "Renamed MySQL",
  "database_type": "mysql",
  "host": "mysql2.example.com",
  "port": 3306,
  "database_name": "analytics_v2",
  "username": "reader2",
  "password": null,
  "ssl_mode": "require"
}
```

`password: null` or field omitted → existing credential retained.

**Response 200**: Updated connection object (same shape as GET, no password).

**Error 404**: Connection not found.
**Error 422**: Validation failure.

---

#### `DELETE /api/v1/admin/connections/{connection_id}`

Hard-delete a connection. Blocked if referenced by query attempts or sessions.

**Auth**: `require_admin_user`

**Response 204**: Deleted successfully.

**Error 404**: Connection not found.
**Error 409**: Connection is referenced → `{"error": "connection_referenced", "message_key": "error.connection_referenced_delete_blocked"}`.

---

#### `POST /api/v1/admin/connections/{connection_id}/disable`

Disable an active connection.

**Auth**: `require_admin_user`

**Response 200**: Updated connection object with `lifecycle_state: "disabled"`.

**Error 404**: Connection not found.
**Error 409**: Already disabled → `{"error": "already_disabled", "message_key": "error.connection_already_disabled"}`.

---

#### `POST /api/v1/admin/connections/{connection_id}/enable`

Re-enable a disabled connection.

**Auth**: `require_admin_user`

**Response 200**: Updated connection object with `lifecycle_state: "active"`.

**Error 404**: Connection not found.
**Error 409**: Already active → `{"error": "already_active", "message_key": "error.connection_already_active"}`.

---

#### `POST /api/v1/admin/connections/{connection_id}/test`

Test a connection's health (lightweight `SELECT 1` or equivalent).

**Auth**: `require_admin_user`

**Response 200**:
```json
{
  "status": "healthy",
  "latency_ms": 12,
  "tested_at": "2026-05-18T14:05:00Z"
}
```

**Response 200 (failure)**:
```json
{
  "status": "unhealthy",
  "error_category": "auth_failed",
  "message_key": "error.connection_auth_failed",
  "tested_at": "2026-05-18T14:05:00Z"
}
```

**Error 404**: Connection not found.

---

#### `POST /api/v1/admin/connections/{connection_id}/refresh-schema`

Trigger schema introspection for a specific connection.

**Auth**: `require_admin_user`

**Response 200**:
```json
{
  "tables_count": 15,
  "columns_count": 87,
  "refreshed_at": "2026-05-18T14:06:00Z"
}
```

**Error 404**: Connection not found.
**Error 502**: Introspection failed → `{"error": "introspection_failed", "message_key": "error.introspection_failed", "detail": "..."}`.

---

#### `GET /api/v1/admin/connections/{connection_id}/schema`

Get the introspected schema summary for a connection.

**Auth**: `require_admin_user`

**Response 200**:
```json
{
  "connection_id": "uuid",
  "tables": [
    {
      "table_name": "users",
      "column_count": 8,
      "columns": [
        {
          "column_name": "id",
          "data_type": "integer",
          "is_primary_key": true,
          "foreign_key": null
        },
        {
          "column_name": "department_id",
          "data_type": "integer",
          "is_primary_key": false,
          "foreign_key": {"table": "departments", "column": "id"}
        }
      ]
    }
  ],
  "introspected_at": "2026-05-18T14:06:00Z"
}
```

**Error 404**: Connection not found or no schema data.

---

### User-Facing Endpoints

#### `GET /api/v1/connections`

List active connections available for the current user (filtered: active + healthy + introspected).

**Auth**: `require_user`

**Response 200**:
```json
{
  "connections": [
    {
      "id": "uuid",
      "display_name": "Production PG",
      "database_type": "postgresql"
    }
  ]
}
```

**Note**: Minimal payload — only what the database selector needs. No host/port/credentials/admin details.

---

### Modified Endpoints

#### `POST /api/v1/query/submit` (MODIFIED)

**New required field**: `connection_id` (UUID)

**Request** (updated):
```json
{
  "question": "Show me all customers",
  "session_id": "uuid",
  "connection_id": "uuid"
}
```

**Validation**:
- `connection_id` required, must reference an active + healthy + introspected connection.
- If connection is disabled → 400 `{"error": "connection_disabled", "message_key": "error.connection_disabled"}`.
- If connection is unhealthy → 400 `{"error": "connection_unhealthy", "message_key": "error.connection_unhealthy"}`.
- If connection has no schema → 400 `{"error": "connection_no_schema", "message_key": "error.connection_no_schema"}`.

**Response**: Existing shape + `connection_id` and `database_type` fields added to the response.

---

#### `POST /api/v1/sessions` (MODIFIED)

**New optional field**: `connection_id` (UUID, nullable)

Sessions can be created without a connection (user selects later).

---

#### `PATCH /api/v1/sessions/{session_id}/connection` (NEW)

Update the session's selected connection.

**Auth**: `require_user`

**Request**:
```json
{
  "connection_id": "uuid"
}
```

**Response 200**: Updated session object.

**Error 404**: Session not found.
**Error 400**: Connection not active/healthy.

---

## Error Message Keys (i18n)

All new error conditions have `message_key` fields for frontend i18n lookup:

| Error Condition | `message_key` | Category |
|---|---|---|
| Connection auth failure | `error.connection_auth_failed` | Connection test |
| Connection network unreachable | `error.connection_network_unreachable` | Connection test |
| Connection database not found | `error.connection_db_not_found` | Connection test |
| Connection timeout | `error.connection_timeout` | Connection test |
| Credential config missing | `error.credential_config` | Server config |
| Schema introspection failed | `error.introspection_failed` | Introspection |
| Schema introspection timeout | `error.introspection_timeout` | Introspection |
| Connection disabled | `error.connection_disabled` | Query submission |
| Connection unhealthy | `error.connection_unhealthy` | Query submission |
| Connection no schema | `error.connection_no_schema` | Query submission |
| Connection not found | `error.connection_not_found` | General |
| Delete blocked (referenced) | `error.connection_referenced_delete_blocked` | Admin delete |
| Already disabled | `error.connection_already_disabled` | Admin disable |
| Already active | `error.connection_already_active` | Admin enable |
| Dialect validation failed | `error.dialect_validation_failed` | Evaluator |
| Unsupported dialect | `error.unsupported_dialect` | Evaluator |
| No database available | `error.no_database_available` | User workspace |
| Query execution failed | `error.query_execution_failed` | Query execution |
| Connection unavailable during query | `error.connection_unavailable_query` | Query execution |

---

## OpenAPI / Client Regeneration Points

1. **Wave 11** (backend foundation): After admin connection CRUD + test + disable/enable endpoints are implemented, regenerate `types.gen.ts` via `npm run gen:api`.
2. **Wave 12** (backend dialect/introspection): After `refresh-schema`, `GET schema`, user `GET /connections`, and modified `POST /query/submit` (with `connection_id`), regenerate `types.gen.ts`.
3. **Wave 13** (frontend admin UI): Frontend consumes regenerated client. No further API changes expected.
4. **Wave 14** (frontend workspace): Frontend consumes `PATCH /sessions/{id}/connection` and `GET /connections`. Final regeneration if any API tweaks.
