# Research — Phase 6: Quotas, Hostile Input Detection, Audit Hardening

**Created**: 2026-06-07
**Phase**: 6
**Spec**: [spec.md](file:///home/avril/QueryCraft/specs/006-quotas-hostile-input-audit-hardening/spec.md)

---

## R-01: Quota Counter Storage and Atomicity

**Decision**: Use Redis with atomic INCR + TTL for daily quota counters.

**Rationale**: The platform already has Redis 7 for session management. Redis INCR is atomic, single-threaded, and O(1). TTL-based expiry at midnight UTC handles daily reset without a scheduled job. The counter key format `quota:{user_id}:{dimension}:{date_iso}` is self-expiring and partition-friendly.

**Alternatives considered**:
- PostgreSQL row-level counters: Adds write contention on the hot path. Every query submission would require a transactional UPDATE + SELECT. Redis avoids this.
- In-memory counters: Not durable across process restarts. Redis survives FastAPI worker restarts.

**Fail-closed behavior**: If Redis is unreachable, the quota check raises an exception caught at the API boundary, returning a localized "service temporarily unavailable" error. No request proceeds without a successful quota check.

---

## R-02: Quota Configuration Storage

**Decision**: Store quota configurations in PostgreSQL as a `role_quotas` table linked to the existing `roles` table via FK.

**Rationale**: Quota configuration is admin-managed, low-write, and needs transactional consistency with role CRUD. PostgreSQL is the right store. The configuration is cached in Redis with a short TTL (60s) to avoid DB hits on every request.

**Alternatives considered**:
- JSONB column on the `roles` table: Simpler but mixes concerns and makes quota-specific queries harder.
- Separate config service: Over-engineered for single-tenant.

---

## R-03: Hostile Input Detection Architecture

**Decision**: A `HostileInputDetector` service with a registry of `DetectionRule` implementations, each returning a `DetectionResult` with category, confidence, and explanation. The detector runs all rules and aggregates results.

**Rationale**: The modular rule registry pattern (FR-161) allows adding rules without modifying the pipeline. Each rule is independently testable. The aggregator applies threshold logic (block if any rule exceeds block threshold, flag if any exceeds suspicious threshold).

**Alternatives considered**:
- Single monolithic regex scanner: Not modular. Hard to test individual categories.
- LLM-based detection: Explicitly excluded — recursive trust problem (spec §Assumptions).
- Third-party WAF/detection library: Adds external dependency; heuristic rules are domain-specific to text-to-SQL and must cover RBAC bypass and schema exposure patterns unique to QueryCraft.

**Built-in rule categories** (FR-157, Q7 clarification):
1. **Prompt injection**: Patterns like "ignore previous instructions", "system prompt", role-play injection, delimiter abuse.
2. **SQL injection fragments**: SQL keywords in unusual NL positions (`DROP`, `UNION SELECT`, `; DELETE`, `1=1`), backtick/quote abuse.
3. **RBAC/policy bypass**: Attempts to reference tables/columns outside the user's role-filtered schema, "show me all data", "bypass filter".
4. **Schema/secret exposure**: "show tables", "show columns", "database password", "connection string", "show config".
5. **Destructive SQL**: "delete all", "drop table", "truncate", "alter table", "update all rows".

---

## R-04: Safe Audit Representation for Hostile Input

**Decision**: Store a truncated/redacted summary (first 100 chars, with hostile patterns replaced by `[REDACTED_PATTERN]`), plus a SHA-256 hash of the original input for forensic correlation. Never store raw hostile text.

**Rationale**: FR-163/FR-164 require that raw hostile payloads never appear in audit logs. The hash allows correlating multiple attempts from the same payload without storing the payload itself. The truncated summary provides enough context for admin review.

**Alternatives considered**:
- Store nothing about the input: Loses forensic value. Admins can't assess the nature of the attack.
- Store the full input encrypted: Still stores the dangerous payload, even if encrypted. Key compromise exposes it.

---

## R-05: Audit Search Strategy

**Decision**: PostgreSQL-native search with GIN index on `context` JSONB column and B-tree indexes on `action_type`, `actor_identity`, `outcome`, and `timestamp`. Full-text search uses `to_tsvector` over a generated column combining `action_type`, `actor_identity`, and `resource_type`.

**Rationale**: The platform is single-tenant with ~1000 users. Audit log volume is moderate (estimated <1M rows/year). PostgreSQL GIN indexes handle JSONB containment queries efficiently at this scale. External search engines (Elasticsearch) are explicitly out of scope.

**Alternatives considered**:
- Materialized views: Adds maintenance complexity. Direct indexed queries are sufficient at expected volume.
- Elasticsearch: Deferred per spec out-of-scope decision.

---

## R-06: Purge-Gap Chain Integrity

**Decision**: Before purging, insert an `audit.purge` marker via `AuditService.log()` that chains normally into the hash sequence. The marker's `context` records boundary metadata: `purged_from_seq`, `purged_to_seq`, `purged_count`, `retention_months`, `first_surviving_seq`, `first_surviving_prev_hash`, `last_retained_hash`, `last_retained_seq`. After deletion, the first surviving data entry's `prev_hash` still references its original (now-deleted) predecessor — no entries are rewritten. The verifier detects the orphaned `prev_hash` and checks if a retained `audit.purge` marker exists whose `first_surviving_seq` and `first_surviving_prev_hash` match. If they match, the gap is intentional. If no matching marker exists, the break is reported as tampering.

**Rationale**: The existing `before_update`/`before_delete` event listener on `AuditLogEntry` enforces immutability — rewriting `prev_hash` on surviving entries is impossible at the application layer. The marker-based approach provides evidence of intentional purge without violating immutability. The boundary metadata in the marker provides enough information for the verifier to confirm the gap matches the purge event.

**Alternatives considered**:
- Rewrite the first surviving entry's `prev_hash` to the marker's `row_hash`: Violates immutability (`before_update` event listener rejects it). Would require disabling the immutability guard, which is unacceptable.
- Accept broken verification after purge: Loses the value of chain verification entirely.
- Insert marker after deletion: The marker couldn't record `first_surviving_seq`/`first_surviving_prev_hash` reliably if concurrent writes occur between delete and marker insertion. Marker-before-delete in the same transaction is safer.

---

## R-07: Export Integrity and Formula Injection Prevention

**Decision**: CSV exports prefix cell values starting with `=`, `+`, `-`, `@`, `|` with a tab character (`\t`) per OWASP CSV injection prevention guidelines. JSON exports are inherently safe from formula injection. Both formats include a metadata header/wrapper with export actor, timestamp, filter summary, record count, and SHA-256 checksum of the data payload.

**Rationale**: Tab-prefixing is the most widely compatible defense against spreadsheet formula injection. It works across Excel, Google Sheets, and LibreOffice Calc without breaking data parsability.

**Alternatives considered**:
- Single-quote prefix (`'`): Works in Excel but displays the quote in some applications.
- Wrapping all values in double-quotes: Already part of standard CSV quoting, but doesn't prevent formula injection in all spreadsheet applications.

---

## R-08: Admin Notification for Security Events

**Decision**: Phase 6 does not implement a dedicated real-time notification system. Security events (hostile input blocks, quota enforcements) are surfaced through the audit search/filter UI. Admins can filter by `hostile.input.*` and `quota.*` action types.

**Rationale**: The spec defers email/SMS/webhook notifications to Phase 8. The audit search UI (FR-166) with event type filtering provides sufficient admin visibility for v1.

**Alternatives considered**:
- In-app bell notification with badge count: Adds frontend complexity (WebSocket/SSE, notification state management). Deferred.
- Polling dashboard widget: Lower complexity but still adds a new UI component. Deferred to Phase 7 admin dashboard.
