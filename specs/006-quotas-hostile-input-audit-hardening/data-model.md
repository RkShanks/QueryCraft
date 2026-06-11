# Data Model — Phase 6: Quotas, Hostile Input Detection, Audit Hardening

**Created**: 2026-06-07
**Phase**: 6
**Migration**: `008_phase6_quotas_detection_audit_hardening.py`

---

## New Tables

### `role_quotas`

Stores per-role quota configuration (FR-147, FR-148).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, default `gen_random_uuid()` | Primary key |
| `role_id` | `UUID` | FK → `roles.id` ON DELETE CASCADE, UNIQUE | One quota config per role |
| `daily_query_limit` | `INTEGER` | NULLABLE | Daily query submissions allowed. NULL = uncapped |
| `daily_execution_limit` | `INTEGER` | NULLABLE | Daily SQL executions allowed. NULL = uncapped |
| `daily_export_limit` | `INTEGER` | NULLABLE | Daily audit exports allowed. NULL = uncapped |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Last update timestamp |

**Indexes**: Unique on `role_id` (one quota config per role).

**Relationships**: `role_quotas.role_id` → `roles.id` (CASCADE delete).

**Notes**: All limit columns are nullable. NULL means uncapped (backward compatible with pre-Phase 6 behavior, FR-147). Phase 6 is role-level only (FR-148, Q1 clarification). No `user_id` column.

---

### `detection_threshold_config`

Stores admin-configurable detection thresholds (FR-162).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, default `gen_random_uuid()` | Primary key |
| `block_confidence` | `FLOAT` | NOT NULL, default `0.8` | Confidence score above which input is blocked |
| `flag_confidence` | `FLOAT` | NOT NULL, default `0.5` | Confidence score above which input is flagged (but allowed) |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Last update timestamp |
| `updated_by` | `UUID` | FK → `users.id` ON DELETE SET NULL | Admin who last changed thresholds |

**Notes**: Singleton row (only one active config). Application-layer enforcement ensures at most one row exists. `block_confidence` must be > `flag_confidence`.

---

## Modified Tables

### `audit_log_entries` — No Schema Changes

The existing `audit_log_entries` table schema is sufficient for Phase 6. New audit event types (quota, hostile input, search, export, purge) use the existing columns:

- `action_type`: New enum values added to `AuditActionType` (see below)
- `context`: JSONB carries event-specific metadata (detection category, confidence, redacted input summary, export metadata, etc.)
- `resource_type` / `resource_id`: Used to link events to their target resources

**No migration changes needed for this table.**

---

### `roles` — No Schema Changes

Quota configuration is stored in the separate `role_quotas` table (FK relationship). No changes to the `roles` table itself.

---

## New Enum Values

### `AuditActionType` Extensions

```python
# Quota events
QUOTA_CONFIG_CHANGE = "quota.config.change"     # Admin creates/updates/deletes quota config
QUOTA_EXCEEDED = "quota.exceeded"               # User request rejected due to quota
QUOTA_WARNING = "quota.warning"                 # Usage approaching limit (future use)

# Hostile input events
HOSTILE_INPUT_BLOCKED = "hostile.input.blocked"  # Input blocked by detection pipeline
HOSTILE_INPUT_FLAGGED = "hostile.input.flagged"  # Input flagged but allowed through
DETECTION_CONFIG_CHANGE = "detection.config.change"  # Admin changes detection thresholds

# Audit search/export events
AUDIT_SEARCH = "audit.search"                   # Admin performed audit log search
AUDIT_EXPORT = "audit.export"                   # Admin exported audit log entries

# Retention purge events
AUDIT_PURGE = "audit.purge"                     # Retention purge executed (purge-gap marker)
```

### `Permission` Extensions

```python
ADMIN_QUOTAS_MANAGE = "admin.quotas.manage"         # Configure role quotas
ADMIN_SECURITY_MANAGE = "admin.security.manage"     # Configure detection thresholds
```

---

## Redis Key Schemas

### Quota Counters

```
Key:    quota:{user_id}:{dimension}:{YYYY-MM-DD}
Value:  integer (atomic INCR)
TTL:    auto-expire at next midnight UTC (max 86400 seconds)
```

Dimensions: `queries`, `executions`, `exports`.

Example: `quota:550e8400-e29b-41d4-a716-446655440000:queries:2026-06-07` → `42`

### Quota Configuration Cache

```
Key:    quota_config:{role_id}
Value:  JSON string of RoleQuotaConfig
TTL:    60 seconds
```

---

## Entity Lifecycle

### Quota Configuration

```
Created → Active → Updated → Active → Deleted (role deleted via CASCADE)
```

No soft-delete. Deleting a role cascades to its quota config.

### Detection Threshold Config

```
Created (singleton) → Updated (by admin) → Updated ...
```

Never deleted. Singleton row. Application initializes with defaults on first access if row missing.

### Purge-Gap Marker

```
Inserted (during purge, before deletion) → Immutable (audit log immutability guard)
```

Purge-gap markers are regular `audit_log_entries` rows with `action_type = "audit.purge"`. They are immutable like all audit entries. The marker is inserted via `AuditService.log()` and chains normally into the hash sequence.

**Marker `context` JSONB fields**:
- `purged_from_seq`: First sequence number in the purged range
- `purged_to_seq`: Last sequence number in the purged range
- `purged_count`: Number of entries deleted
- `retention_months`: Retention period used for cutoff calculation
- `first_surviving_seq`: Sequence number of the first data entry that will remain after deletion
- `first_surviving_prev_hash`: The `prev_hash` value of that first surviving entry (which will reference its now-deleted predecessor)
- `last_retained_hash`: `row_hash` of the last retained entry before the purged range (or `"GENESIS"` if purging from the start)
- `last_retained_seq`: Sequence number of the last retained entry before the purged range (or `0` if purging from the start)

No existing audit entries are updated or rewritten. The marker is a forward-looking evidence record, not a retroactive chain fix.

