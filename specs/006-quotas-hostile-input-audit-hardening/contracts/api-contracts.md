# API Contracts — Phase 6: Quotas, Hostile Input Detection, Audit Hardening

**Created**: 2026-06-07
**Phase**: 6
**Base path**: `/api/v1`

---

## New Endpoints

### Quota Administration

#### `GET /admin/quotas`

List all role quota configurations.

**Permission**: `admin.quotas.manage`

**Response 200**:
```json
{
  "quotas": [
    {
      "role_id": "uuid",
      "role_name": "analyst",
      "daily_query_limit": 100,
      "daily_execution_limit": 50,
      "daily_export_limit": 5,
      "created_at": "2026-06-07T00:00:00Z",
      "updated_at": "2026-06-07T00:00:00Z"
    }
  ]
}
```

**Notes**: Roles without quota config are omitted (uncapped). NULL limits in DB render as `null` in JSON (meaning uncapped for that dimension).

---

#### `GET /admin/quotas/{role_id}`

Get quota configuration for a specific role.

**Permission**: `admin.quotas.manage`

**Response 200**: Single quota object (same shape as list item).

**Response 404**: Role has no quota configuration (uncapped).

---

#### `PUT /admin/quotas/{role_id}`

Create or update quota configuration for a role.

**Permission**: `admin.quotas.manage`

**Request body**:
```json
{
  "daily_query_limit": 100,
  "daily_execution_limit": 50,
  "daily_export_limit": 5
}
```

All fields nullable. `null` = uncapped for that dimension.

**Response 200**: Updated quota object.

**Audit**: Emits `quota.config.change` with sanitized context (role_id, changed dimensions, no counter values).

---

#### `DELETE /admin/quotas/{role_id}`

Remove quota configuration for a role (returns to uncapped).

**Permission**: `admin.quotas.manage`

**Response 204**: No content.

**Audit**: Emits `quota.config.change` with context `{"action": "removed"}`.

---

#### `GET /admin/quotas/status`

Get current quota consumption status across all roles.

**Permission**: `admin.quotas.manage`

**Response 200**:
```json
{
  "status": [
    {
      "role_id": "uuid",
      "role_name": "analyst",
      "dimensions": {
        "queries": {"limit": 100, "used": 42, "remaining": 58},
        "executions": {"limit": 50, "used": 10, "remaining": 40},
        "exports": {"limit": 5, "used": 0, "remaining": 5}
      },
      "reset_at": "2026-06-08T00:00:00Z"
    }
  ]
}
```

**Notes**: `used` values are aggregated from Redis counters across all users in the role. `limit` is `null` if uncapped. `remaining` is `null` if uncapped.

---

### Detection Administration

#### `GET /admin/detection/config`

Get current hostile input detection thresholds.

**Permission**: `admin.security.manage`

**Response 200**:
```json
{
  "block_confidence": 0.8,
  "flag_confidence": 0.5,
  "updated_at": "2026-06-07T00:00:00Z"
}
```

---

#### `PUT /admin/detection/config`

Update detection thresholds.

**Permission**: `admin.security.manage`

**Request body**:
```json
{
  "block_confidence": 0.85,
  "flag_confidence": 0.6
}
```

**Validation**: `block_confidence` must be > `flag_confidence`. Both must be in range [0.0, 1.0].

**Response 200**: Updated config object.

**Audit**: Emits `detection.config.change`.

---

### Audit Search and Export

#### `GET /admin/audit/entries`

Search and filter audit log entries.

**Permission**: `admin.audit.verify` (reuses existing Phase 5 audit permission — no new audit permission in Phase 6).

**Query parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | `ISO8601` | Filter entries from this timestamp (inclusive) |
| `end_date` | `ISO8601` | Filter entries until this timestamp (inclusive) |
| `action_type` | `string` | Filter by action type (exact match) |
| `actor_identity` | `string` | Filter by actor identity (exact match) |
| `outcome` | `string` | Filter by outcome: `success`, `failure`, `blocked`, `broken` |
| `resource_type` | `string` | Filter by resource type (exact match) |
| `page` | `integer` | Page number (1-indexed, default 1) |
| `page_size` | `integer` | Results per page (default 50, max 100) |

**Response 200**:
```json
{
  "entries": [
    {
      "sequence_number": 1234,
      "timestamp": "2026-06-07T12:00:00Z",
      "actor_identity": "admin@example.com",
      "action_type": "hostile.input.blocked",
      "resource_type": "query",
      "resource_id": null,
      "outcome": "blocked",
      "context": {"category": "prompt_injection", "confidence": 0.92, "summary": "[REDACTED_PATTERN]..."}
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_entries": 1234,
    "total_pages": 25
  }
}
```

**Notes**: Entries outside retention window are never returned (FR-173). Context is always the redacted/sanitized version from `AuditService.log`. No raw hostile payloads.

**Audit**: Emits `audit.search` with sanitized filter summary (no values from results).

---

#### `POST /admin/audit/export`

Export filtered audit entries to CSV or JSON.

**Permission**: `admin.audit.verify` (same permission as search — reuses existing Phase 5 audit permission).

**Request body**:
```json
{
  "format": "csv",
  "start_date": "2026-01-01T00:00:00Z",
  "end_date": "2026-06-07T23:59:59Z",
  "action_type": "hostile.input.blocked",
  "actor_identity": null,
  "outcome": null,
  "resource_type": null
}
```

`format`: `"csv"` or `"json"` (FR-168, Q6 clarification).

**Response 200**: File download with appropriate Content-Type.

- CSV: `text/csv; charset=utf-8` with Content-Disposition attachment header.
- JSON: `application/json` with Content-Disposition attachment header.

**Export metadata** (included in file, FR-169):
- `export_actor`: Identity of the admin who triggered the export.
- `export_timestamp`: ISO8601 timestamp of the export.
- `filter_summary`: Human-readable summary of applied filters.
- `record_count`: Number of entries in the export.
- `checksum`: SHA-256 hash of the data payload for integrity verification.

**Size limit**: Maximum 50,000 records per export (FR-170, Q5 clarification). If the filter matches more, the response is 422 with a message indicating the admin must narrow filters.

**Formula injection prevention**: CSV cell values starting with `=`, `+`, `-`, `@`, `|` are prefixed with tab character (FR-171).

**Audit**: Emits `audit.export` with filter summary and record count (no exported data values).

---

### Audit Retention

#### `GET /admin/audit/retention`

Get retention configuration and last purge status.

**Permission**: `admin.audit.verify` (same permission as search/export — reuses existing Phase 5 audit permission).

**Response 200**:
```json
{
  "retention_months": 24,
  "last_purge_at": "2026-05-01T00:00:00Z",
  "purged_count": 1500
}
```

`retention_months` is read from platform configuration (`Settings.AUDIT_RETENTION_MONTHS`). `last_purge_at` and `purged_count` are derived from the most recent `audit.purge` event in the audit log. `null` if no purge has ever been executed.

**Note**: The platform does not manage or configure the external purge scheduler. This endpoint does not display "next scheduled purge" because the platform has no visibility into external scheduler timing. Operational documentation describes how to configure external schedulers (cron, k8s CronJob, systemd timer) to invoke `purge_expired_entries()`.

---

## Modified Endpoints

### `POST /query/submit`

**Changes**: Before LLM invocation, two new checks run in this order:

1. **Hostile input detection** (FR-156): The `HostileInputDetector` scans the natural language question. If blocked, returns localized safe error. Blocked requests never increment the quota counter. If flagged, logs and proceeds.
2. **Quota check** (FR-151): The `QuotaService` checks the user's daily query counter against their role's limit. If exceeded, returns localized safe error with reset time. Only reached if detection passes.

**New error responses**:

- Hostile input blocked: Localized error with `message_key: "error.hostile_input_blocked"`. No detection details, no echo of input.
- Quota exceeded: Localized error with `message_key: "error.quota_exceeded"` and `reset_at` timestamp. No counter values, no policy IDs.

### `POST /query/{question_id}/execute`

**Changes**: Before SQL execution, quota check for daily execution counter.

**New error response**: Same quota exceeded pattern as above with `message_key: "error.quota_exceeded"`.

### `POST /admin/audit/export`

**Changes**: Before export processing, quota check for daily export counter.

---

## Security Contract

All new endpoints follow the Phase 5 security contract:

1. **No leak**: No internal identifiers, counter values, policy IDs, SQL, prompts, tokens, provider names, database host/port, driver errors, stack traces, SAML XML, OIDC tokens, or raw hostile payloads in any response.
2. **Sanitized errors**: All error responses use constant `message_key` values resolved by i18n. No dynamic interpolation of internal values.
3. **Permission-gated**: All admin endpoints require explicit permission checks via `require_permission()`.
4. **Audit-logged**: All state-changing operations emit audit events with redacted context.
