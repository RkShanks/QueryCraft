# Implementation Plan — Phase 6: Quotas, Hostile Input Detection, Audit Hardening

**Created**: 2026-06-07
**Phase**: 6
**Spec**: [spec.md](file:///home/avril/QueryCraft/specs/006-quotas-hostile-input-audit-hardening/spec.md)
**Research**: [research.md](file:///home/avril/QueryCraft/specs/006-quotas-hostile-input-audit-hardening/research.md)
**Data Model**: [data-model.md](file:///home/avril/QueryCraft/specs/006-quotas-hostile-input-audit-hardening/data-model.md)
**API Contracts**: [api-contracts.md](file:///home/avril/QueryCraft/specs/006-quotas-hostile-input-audit-hardening/contracts/api-contracts.md)

---

## Technical Context

| Item | Value |
|------|-------|
| Backend | FastAPI, Python 3.12, SQLAlchemy 2, Alembic, asyncpg |
| Frontend | React 19, Tailwind v4, Vite, TanStack Query, react-i18next, lucide-react |
| i18n | `frontend/src/locales/{en,ar}.json` — 100% parity at Phase 5 close |
| RTL | `dir="rtl"` on root; logical CSS properties only |
| Source DBs | PostgreSQL, MySQL, MSSQL (Phase 3) |
| LLM | Gemini (default), provider-agnostic interface |
| Auth | SSO (OIDC/SAML) + local admin, Redis sessions, HttpOnly cookies |
| RBAC | Role-based with group-to-role priority mapping, fixed permission set |
| Audit | Tamper-evident chained SHA-256, 24-month retention, immutability guard |
| Encryption | AES-256-GCM via `app.core.encryption` |
| SQL parsing | `sqlglot>=26.0.0` |
| Evaluator | Rule-based pipeline with read-only, schema validation, role authorization |
| Phase 5 closure | FROZEN on `main` (6ecbcd8). 0 Critical/High/Mid. 3 Low deferred. |
| Next migration | `008_phase6_quotas_detection_audit_hardening.py` |
| Task ID range | T-779+ (Phase 5 ended at T-778) |
| FR range | FR-147 – FR-180 (34 requirements) |
| SC range | SC-063 – SC-077 (15 success criteria) |

## Constitution Check

| Principle | Phase 6 Status | Notes |
|-----------|---------------|-------|
| I — Security | ✅ Extended | Hostile input detection extends security surface |
| II — Query Validation | ✅ Extended | Hostile input check runs before evaluator |
| III — Validated Knowledge | ✅ Preserved | No changes to accepted query storage |
| IV — Hostile Input | ✅ **ACTIVATED** | Prompt/SQL injection detection, blocking, audit logging (FR-156–FR-165) |
| V — LLM-Agnostic | ✅ Preserved | Quota tracking is provider-agnostic |
| VI — Language ↔ Dialect | ✅ Preserved | Detection supports English and Arabic |
| VII — Role Auth | ✅ Preserved | Existing SSO/RBAC unchanged |
| VIII — Brokered DB Access | ✅ Preserved | Existing row/column security unchanged |
| IX — Audit | ✅ **COMPLETED** | Search, export, retention purge-gap handling (FR-166–FR-176) |
| X — Quotas | ✅ **ACTIVATED** | Daily quotas enforced at system boundary, fail-closed (FR-147–FR-155) |
| XI — Modularity | ✅ Extended | Detection pipeline is modular rule registry |
| XII — API Contract | ✅ Extended | New endpoints documented in api-contracts.md |

**§11 Phased Rollout**: Principles IV and X triggered at Phase 6 (§11 phased commitment table). This plan activates both. All 12 principles will be active after Phase 6.

## Locked Decisions

### ADR-22 — Quota Storage and Enforcement Architecture

- **Counter storage**: Redis INCR with TTL-based daily reset at midnight UTC.
- **Config storage**: PostgreSQL `role_quotas` table with Redis cache (60s TTL).
- **Atomicity**: Single Redis INCR is atomic. Check-and-increment in a single Lua script or pipeline to prevent TOCTOU.
- **Fail-closed**: If Redis is unreachable, `QuotaService.check_and_increment()` raises `QuotaUnavailableError`. API boundary catches and returns localized safe error.
- **Reset**: Key format `quota:{user_id}:{dimension}:{YYYY-MM-DD}` with TTL = seconds until next midnight UTC. Daily-only, fixed interval (Q4 clarification).
- **Dimensions**: 3 — `queries`, `executions`, `exports` (Q8 clarification).
- **Scope**: Role-level only, no per-user overrides (Q1 clarification).

### ADR-23 — Hostile Input Detection Pipeline

- **Architecture**: `HostileInputDetector` service with `DetectionRule` protocol. Rules registered via `RuleRegistry`. Detector runs all rules, aggregates `DetectionResult` list.
- **Built-in rules**: All 5 categories ship at launch (Q7 clarification): prompt injection, SQL injection fragments, RBAC/policy bypass, schema/secret exposure, destructive SQL.
- **Confidence**: Each rule returns `(category, confidence: float, explanation: str)`. Block if max confidence ≥ `block_confidence` threshold. Flag if max confidence ≥ `flag_confidence` threshold. Allow otherwise.
- **Thresholds**: Admin-configurable via `detection_threshold_config` table. Defaults: block=0.8, flag=0.5.
- **Pipeline order**: In `POST /query/submit`, hostile input detection runs FIRST, then query quota check, then LLM invocation (FR-151, FR-156). Hostile input that is blocked never increments the quota counter. Execution and export quota checks remain at their own respective boundaries.
- **Integration**: Does NOT replace Phase 5 evaluator authorization (runs after LLM returns SQL).
- **Language support**: Rules handle both English and Arabic patterns (FR-160).

### ADR-24 — Safe Audit Representation for Hostile Input

- **Redaction**: First 100 characters of input, with hostile patterns replaced by `[REDACTED_PATTERN]`.
- **Hash**: SHA-256 of the full original input stored as `input_hash` in audit context. Allows forensic correlation without storing the payload.
- **Never stored**: Raw hostile text never appears in `context` JSONB. The redacted summary is the maximum stored representation.
- **Classification metadata**: `category`, `confidence`, `rules_triggered` (rule names only, no pattern details), `outcome` (blocked/flagged).

### ADR-25 — Audit Search Strategy

- **Indexes**: GIN on `context`, B-tree on `action_type`, `actor_identity`, `outcome`, `timestamp`.
- **Search fields**: `action_type`, `actor_identity`, `outcome`, `resource_type`, `timestamp` range. Keyword search over `action_type + actor_identity + resource_type`.
- **Retention enforcement**: All queries include `WHERE timestamp >= retention_cutoff` to ensure FR-173.
- **Pagination**: Keyset or offset-based (offset for v1 simplicity), default 50 per page, max 100.

### ADR-26 — Purge-Gap Chain Integrity

- **Purge-gap marker**: Before deleting entries, insert an `audit.purge` event via `AuditService.log()` (which chains it into the hash sequence normally). The marker's `context` JSONB records: `{purged_from_seq, purged_to_seq, purged_count, retention_months, first_surviving_seq, first_surviving_prev_hash, last_retained_hash, last_retained_seq}`. The marker is an immutable, chained audit entry — no existing entries are rewritten.
- **Verification update**: `verify_chain()` walks the retained entries. When the first surviving data entry's `prev_hash` doesn't match the previous retained entry's `row_hash` (because the predecessor was deleted), the verifier checks if a retained `audit.purge` marker exists whose `first_surviving_seq` matches and whose `first_surviving_prev_hash` matches the orphaned `prev_hash`. If the marker confirms the gap boundary, the gap is treated as intentional. If no matching marker exists, the break is reported as tampering.
- **Immutability preserved**: No audit entries are updated or rewritten. The purge-gap marker is a forward-looking evidence record, not a retroactive chain fix. Existing entries retain their original `prev_hash` values.
- **External scheduler**: The purge method `AuditService.purge_expired_entries()` is extended to insert the purge-gap marker BEFORE deleting entries (same transaction). Phase 6 documents safe invocation via external scheduler (cron/k8s CronJob). The platform does not manage or configure the external scheduler.

### ADR-27 — Export Integrity and Formula Injection Prevention

- **CSV formula injection**: Tab-prefix (`\t`) for cells starting with `=`, `+`, `-`, `@`, `|`.
- **Compliance metadata**: Both CSV and JSON include: `export_actor`, `export_timestamp`, `filter_summary`, `record_count`, `checksum` (SHA-256 of data payload).
- **Size limit**: 50,000 records per export (Q5 clarification). 422 if exceeded.
- **Redaction (defense-in-depth)**: Exports apply the central audit redaction/sanitization pass again before serialization, even though the stored `context` from `AuditService.log` is already redacted. This defense-in-depth layer ensures that if any stored context unexpectedly contains sensitive values (e.g., due to a bug in a caller that bypasses redaction), the export pipeline catches it. Tests must verify export redaction independently of storage-time redaction.
- **Processing order**: Redaction → formula injection prevention → checksum computation → metadata wrapper.

---

## Wave Structure

### Wave 18.0 — Foundation

**Scope**: Contracts, migrations, permissions, shared schemas/types, audit event taxonomy, test fixtures.

**FR coverage**: FR-177 (permissions), partial FR-147 (data model), partial FR-155 (audit event types).

**SC coverage**: Partial SC-074, SC-075 (foundation gates).

**Deliverables**:
- Migration `008_phase6_quotas_detection_audit_hardening.py` — `role_quotas`, `detection_threshold_config` tables
- `AuditActionType` enum extensions (quota, hostile input, audit search/export, purge events)
- `Permission` enum extensions (`admin.quotas.manage`, `admin.security.manage`). Note: audit search/export/retention status reuse existing `admin.audit.verify` permission — no new audit permission in Phase 6.
- Pydantic schemas for quota config, detection config, audit search/export request/response
- Shared test fixtures: factory functions for quota configs, detection rules, audit entries
- Built-in admin role updated with new permissions
- Backend foundation gates pass

**Dependencies**: None (first wave).

---

### Wave 18.1 — Quotas

**Scope**: Quota configuration CRUD, Redis counter service, fail-closed enforcement, admin quota UI, i18n/RTL, quota audit events.

**FR coverage**: FR-147, FR-148, FR-149, FR-150, FR-151, FR-152, FR-153, FR-154, FR-155, FR-178 (quota i18n), FR-179 (quota RTL), FR-180 (quota error messages).

**SC coverage**: SC-063, SC-064 (quota errors), SC-071, SC-072 (quota i18n), SC-073 (quota RTL), SC-074, SC-075.

**Backend deliverables**:
- `QuotaService` — Redis counter check-and-increment, config cache, fail-closed
- `QuotaConfig` repository — CRUD for `role_quotas` table
- Quota admin router (`/admin/quotas/*`) — list, get, put, delete, status
- Quota enforcement middleware integration in `/query/submit`, `/query/{id}/execute`
- Quota audit event emission (config changes, exceeded)
- Error responses with localized `message_key` and `reset_at`

**Frontend deliverables**:
- Admin quota configuration page (AdminQuotasPage)
- Quota status dashboard component
- Quota exceeded error display in query submission flow
- i18n keys for en/ar: quota config labels, error messages, status indicators
- RTL layout verification

**Dependencies**: Wave 18.0 (migration, schemas, permissions).

---

### Wave 18.2 — Hostile Input Detection

**Scope**: Detection pipeline, 5 built-in rule categories, threshold config, pre-generation integration, safe errors, redacted audit events, admin threshold config UI.

**FR coverage**: FR-156, FR-157, FR-158, FR-159, FR-160, FR-161, FR-162, FR-163, FR-164, FR-165, FR-178 (detection i18n), FR-179 (detection RTL), FR-180 (detection error messages).

**SC coverage**: SC-065, SC-066, SC-067, SC-064 (detection errors), SC-072 (detection i18n), SC-073 (detection RTL), SC-074, SC-075.

**Backend deliverables**:
- `HostileInputDetector` service with `DetectionRule` protocol and `RuleRegistry`
- 5 built-in rules: `PromptInjectionRule`, `SqlInjectionRule`, `RbacBypassRule`, `SchemaExposureRule`, `DestructiveSqlRule`
- Each rule with English and Arabic pattern support
- `DetectionThresholdConfig` repository — singleton CRUD
- Detection admin router (`/admin/detection/config`) — get, put
- Integration into `POST /query/submit` — detection runs before LLM invocation
- Safe audit event emission with redacted input representation (ADR-24)
- Error responses with localized `message_key`, no detection details

**Frontend deliverables**:
- Admin detection threshold configuration (in security settings)
- Hostile input blocked error display in query submission flow
- i18n keys for en/ar: detection config labels, blocked error messages
- RTL layout verification

**Dependencies**: Wave 18.0 (migration, schemas, permissions). Wave 18.1 (quota service exists for post-detection quota check integration). Detection runs before quota in the pipeline, but the detection service itself can be built in parallel with quota service.

---

### Wave 18.3 — Audit Search/Export/Retention

**Scope**: Audit search filters, pagination, CSV/JSON export, 50k limit, formula injection prevention, export integrity metadata, permission gates, purge-gap verification, external scheduler docs.

**FR coverage**: FR-166, FR-167, FR-168, FR-169, FR-170, FR-171, FR-172, FR-173, FR-174, FR-175, FR-176, FR-178 (audit i18n), FR-179 (audit RTL).

**SC coverage**: SC-068, SC-069, SC-070, SC-072 (audit i18n), SC-073 (audit RTL), SC-074, SC-075, SC-077.

**Backend deliverables**:
- `AuditSearchService` — query builder with filter parameters, pagination, retention enforcement
- Audit search router (`GET /admin/audit/entries`) — paginated, filtered
- `AuditExportService` — CSV and JSON serializers with formula injection prevention, compliance metadata, checksum
- Audit export router (`POST /admin/audit/export`) — file download with 50k limit
- Audit retention status router (`GET /admin/audit/retention`) — last purge timestamp and retention config from app settings + last `audit.purge` event. The platform does not know or display external scheduler timing.
- `AuditService.purge_expired_entries()` updated to insert purge-gap marker (with boundary metadata) before deletion
- `AuditService.verify_chain()` updated to recognize purge-gap markers and match boundary metadata against orphaned `prev_hash` values
- Quota enforcement for export endpoint (daily export counter)
- Search/export actions audit-logged

**Frontend deliverables**:
- Admin audit search page (replaces/extends AdminAuditPage) with date range, action type, actor, outcome filters
- Paginated results table
- Export controls (CSV/JSON buttons)
- Retention status display (last purge time, retention period from config — no external scheduler timing)
- i18n keys for en/ar: filter labels, table headers, export buttons, retention info
- RTL layout verification

**Dependencies**: Wave 18.0 (migration, schemas), Wave 18.1 (export quota enforcement), Wave 18.2 (hostile input events to search/view).

---

### Wave 18.4 — Verification/Polish/Closeout

**Scope**: Cross-cutting verification, security regression, Arabic/RTL browser smoke, full browser smoke, independent audit, documentation.

**SC coverage**: SC-074, SC-075, SC-076, SC-072, SC-073 (final verification).

**Deliverables**:
- Security regression tests across all new surfaces
- Cross-dialect verification (quota enforcement with PG/MySQL/MSSQL source DBs)
- Full browser smoke (English + Arabic, desktop + mobile viewport)
- Independent security audit (0 Critical/High required for freeze)
- External purge scheduler operational documentation
- Consolidation report
- Wave-final-snapshot
- AGENTS.md Phase 6 status update to FROZEN

**Dependencies**: Waves 18.0–18.3 all complete.

---

## FR/SC Traceability Matrix

### Functional Requirements → Waves

| FR | Description | Wave |
|----|-------------|------|
| FR-147 | Quota config per role (3 dimensions) | 18.0 (model) + 18.1 (CRUD/UI) |
| FR-148 | Role-level only, no per-user overrides | 18.1 |
| FR-149 | Quota consumption status view | 18.1 |
| FR-150 | Config changes take effect immediately | 18.1 |
| FR-151 | Quota enforcement before downstream work | 18.1 |
| FR-152 | Localized rejection on quota exceeded | 18.1 |
| FR-153 | Fail-closed when tracking unavailable | 18.1 |
| FR-154 | Daily reset at midnight UTC, fixed | 18.1 |
| FR-155 | Quota events audit-logged | 18.1 |
| FR-156 | Hostile input detection pipeline | 18.2 |
| FR-157 | Heuristic rules, 5 built-in categories | 18.2 |
| FR-158 | Sanitized error on block | 18.2 |
| FR-159 | Detection extends evaluator, not replaces | 18.2 |
| FR-160 | English + Arabic detection | 18.2 |
| FR-161 | Modular rule registry | 18.2 |
| FR-162 | Admin-configurable thresholds | 18.2 |
| FR-163 | Redacted audit events for detection | 18.2 |
| FR-164 | No raw hostile text in audit | 18.2 |
| FR-165 | No auto-suspension; admin manual review | 18.2 |
| FR-166 | Audit search/filter | 18.3 |
| FR-167 | Paginated search results | 18.3 |
| FR-168 | CSV/JSON export, redacted | 18.3 |
| FR-169 | Export compliance metadata | 18.3 |
| FR-170 | Export size limit 50k, permission-gated | 18.3 |
| FR-171 | Formula injection prevention | 18.3 |
| FR-172 | Search/export actions audit-logged | 18.3 |
| FR-173 | Retention window enforced in search | 18.3 |
| FR-174 | External purge scheduler + docs | 18.3 |
| FR-175 | Purge-gap marker | 18.3 |
| FR-176 | Purge status admin view | 18.3 |
| FR-177 | Permission extensions | 18.0 |
| FR-178 | En/Ar i18n parity | 18.1 + 18.2 + 18.3 |
| FR-179 | RTL layout | 18.1 + 18.2 + 18.3 |
| FR-180 | Localized sanitized error messages | 18.1 + 18.2 |

### Success Criteria → Waves

| SC | Description | Wave |
|----|-------------|------|
| SC-063 | Quota-exceeded blocks before downstream | 18.1 |
| SC-064 | Localized safe denial messages | 18.1 + 18.2 |
| SC-065 | Hostile prompts blocked | 18.2 |
| SC-066 | 95% normal prompt pass-through | 18.2 |
| SC-067 | Redacted audit events for blocks | 18.2 |
| SC-068 | Audit search/export permission-gated | 18.3 |
| SC-069 | Export redaction + formula injection checks | 18.3 |
| SC-070 | Retention window enforced in search | 18.3 |
| SC-071 | Fail-closed on Redis unavailable | 18.1 |
| SC-072 | En/Ar i18n parity | 18.1 + 18.2 + 18.3 + 18.4 |
| SC-073 | RTL smoke pass | 18.1 + 18.2 + 18.3 + 18.4 |
| SC-074 | Frontend gates pass | 18.0 + 18.1 + 18.2 + 18.3 |
| SC-075 | Backend gates pass | 18.0 + 18.1 + 18.2 + 18.3 |
| SC-076 | 0 Critical/High audit findings | 18.4 |
| SC-077 | Purge-gap chain verification | 18.3 |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Hostile input false positives block legitimate queries | Medium | High | Configurable thresholds (ADR-23). Regression suite with ≥95% pass-through requirement (SC-066). Flag-only mode below block threshold. |
| Redis unavailability during quota checks | Low | High | Fail-closed design (ADR-22). Localized "service unavailable" error. Redis health check at startup. |
| Audit search performance degrades at scale | Low | Medium | GIN + B-tree indexes (ADR-25). 50k export limit. Single-tenant volume is ~1M rows/year max. |
| Formula injection bypasses tab-prefix defense | Low | Medium | OWASP-recommended approach. Automated test suite validates all prefix patterns. JSON export as alternative. |
| Arabic hostile patterns not adequately covered | Medium | Medium | Dedicated Arabic pattern set in each rule. Arabic-specific test suite. Threshold tuning available. |
| Purge-gap marker breaks existing chain verification | Low | High | Backward-compatible: marker is a normal audit entry. `verify_chain` update is additive. Extensive unit tests. |
| Scope creep from Phase 5 deferred items | Low | Low | SMOKE-002/SMOKE-003 explicitly out of scope unless pulled in. Monitored in orchestration log. |

---

## Implementation Handoff Notes

### Backend Implementer

- **Start with Wave 18.0**: Migration, enum extensions, schemas, test fixtures. All subsequent waves depend on this.
- **QuotaService** (Wave 18.1): Use Redis Lua script for atomic check-and-increment to prevent TOCTOU races. The key pattern and TTL calculation are specified in data-model.md.
- **HostileInputDetector** (Wave 18.2): Follow the `DetectionRule` protocol pattern. Each rule is a separate module in `app/services/detection/rules/`. The detector aggregates results — it does not short-circuit on first match (all rules run).
- **AuditService updates** (Wave 18.3): The `purge_expired_entries()` method must insert the purge-gap marker BEFORE deleting entries (same transaction). The marker's `context` must record boundary metadata (`purged_from_seq`, `purged_to_seq`, `first_surviving_seq`, `first_surviving_prev_hash`, `last_retained_hash`, `last_retained_seq`, `purged_count`). The `verify_chain()` method must recognize gaps and match marker metadata against the orphaned `prev_hash`. No existing audit entries are rewritten.
- **Sanitization invariant**: NO endpoint may expose internal counters, policy IDs, provider names, detection rule names/patterns, raw hostile text, database host/port, driver errors, stack traces, or OIDC/SAML tokens in any response or audit context. This is verified by security tests.

### Frontend Implementer

- **AdminQuotasPage** (Wave 18.1): New admin page at `/admin/quotas`. Follow the AdminRolesPage pattern for CRUD form + table layout. Permission guard: `admin.quotas.manage`.
- **Detection config** (Wave 18.2): Add to existing settings or create a security config section. Simple threshold sliders/inputs. Permission guard: `admin.security.manage`.
- **Audit search/export permission** (Wave 18.3): Reuse existing `admin.audit.verify` permission for search, export, and retention status endpoints. No new audit permission in Phase 6.
- **AdminAuditPage enhancement** (Wave 18.3): The existing AdminAuditPage (verify + status) must be extended with search filters, paginated results table, and export buttons. This is the largest frontend surface in Phase 6.
- **i18n**: Add all new keys to both `en.json` and `ar.json` in every wave. Zero English fallback tolerance.
- **RTL**: All CSS must use logical properties. No `left`/`right`/`text-align: left`. Verified by `lint:css`.

---

## Test Strategy

### Unit Tests (Backend)

- `QuotaService`: check-and-increment, fail-closed, daily reset, config cache
- `HostileInputDetector`: each rule category, English + Arabic, threshold logic, modular registration
- `AuditSearchService`: filter building, pagination, retention enforcement
- `AuditExportService`: CSV/JSON serialization, formula injection, metadata, checksum, 50k limit
- Purge-gap marker insertion and chain verification with gaps

### Integration Tests (Backend)

- Full query submission flow with quota enforcement
- Full query submission flow with hostile input detection
- Audit search/export with real database
- Purge + verify_chain with purge-gap markers

### Frontend Tests

- Component tests for all new admin pages
- i18n key completeness tests
- Error display tests for quota exceeded and hostile input blocked

### Security Tests

- Verify no raw hostile text in any audit entry
- Verify no internal details in any error response
- Verify export redaction independently of storage-time redaction (defense-in-depth: inject unexpected sensitive values into stored context, confirm export strips them)
- Verify formula injection prevention in CSV exports
- Verify permission gates on all new endpoints

### Browser Smoke

- English: all new pages, quota config, quota exceeded flow, hostile input blocked flow, audit search, audit export
- Arabic: same flows, verify RTL layout, verify zero English fallback
- Mobile viewport: verify no clipping on new surfaces (320px, 375px, 768px)

---

## Browser Smoke Plan

| UC | Surface | English | Arabic | Mobile |
|----|---------|---------|--------|--------|
| UC-11 | Admin quota config page | ✓ | ✓ | ✓ |
| UC-12 | Quota exceeded error on query submit | ✓ | ✓ | — |
| UC-13 | Hostile input blocked error on query submit | ✓ | ✓ | — |
| UC-14 | Detection threshold config | ✓ | ✓ | ✓ |
| UC-15 | Audit search with filters | ✓ | ✓ | ✓ |
| UC-16 | Audit export CSV/JSON | ✓ | ✓ | — |
| UC-17 | Audit retention status | ✓ | ✓ | ✓ |
| UC-18 | Quota status dashboard | ✓ | ✓ | ✓ |

---

## Independent Audit Plan

- **Timing**: After Wave 18.3 merge, before 18.4 closeout
- **Scope**: Full-wave audit of FR-147–FR-180 and SC-063–SC-077
- **Auditors**: Gemini + Opus dual-audit (per Phase 5 pattern)
- **Output**: `audit/wave-18/gemini-findings.md` and `audit/wave-18/opus-findings.md`
- **Gate**: 0 Critical, 0 High required for Phase 6 freeze
