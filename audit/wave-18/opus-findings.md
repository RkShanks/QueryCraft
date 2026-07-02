# Opus Audit Findings - Wave 18.4 / Phase 6

## 1. Summary Verdict

PASS.

Critical = 0, High = 0. Wave 18.4 freeze is not blocked from the Opus audit perspective.

## 2. Audit Metadata

- Date: 2026-07-03T00:35:40+03:00
- Branch: main
- Target HEAD: 3ab3a8883d1cd44f6e0a7c284b612ec27e6a765a
- Independence: `audit/wave-18/gemini-findings.md` was not opened or used as evidence.
- Missing required artifact: `specs/006-quotas-hostile-input-audit-hardening/plan.md` is absent in this snapshot. `tasks.md` states Phase 6 source artifacts including `plan.md` are not present.
- Files reviewed: `AGENTS.md`; `.agents/ORCHESTRATOR.md`; `specs/006-quotas-hostile-input-audit-hardening/tasks.md`; `specs/006-quotas-hostile-input-audit-hardening/plans/orchestration-log.md`; `audit/wave-18/browser-smoke-wave18.md`; Phase 6 backend migrations/models/schemas/repositories/services/API routes; Phase 6 backend unit/integration tests; Phase 6 frontend API hooks/pages/components/routes/locales/tests; smoke screenshots under `audit/wave-18/*.png`.
- Key source files reviewed: `backend/src/app/services/quota_service.py`, `backend/src/app/services/query_service.py`, `backend/src/app/services/detection/*`, `backend/src/app/api/v1/admin_audit.py`, `backend/src/app/services/audit_search_service.py`, `backend/src/app/services/audit_export_service.py`, `backend/src/app/services/audit_service.py`, `backend/src/app/api/v1/phase6_permissions.py`, `frontend/src/pages/AdminAuditPage.tsx`, `frontend/src/pages/AdminQuotasPage.tsx`, `frontend/src/pages/AdminDetectionPage.tsx`, `frontend/src/auth/permissions.ts`, `frontend/src/components/auth/PermissionGuard.tsx`, `frontend/src/components/sidebar/Sidebar.tsx`.

## 3. FR Verification Table

| FR | Status | Evidence |
|---|---|---|
| FR-147 | PASS | `role_quotas` migration/model/schema/repository/admin API present: `008_phase6...py`, `role_quota.py`, `quota.py`, `quota_repository.py`, `admin_quotas.py`. |
| FR-148 | PASS | `QuotaService.check_and_increment()` maps query/execution/export dimensions and enforces Redis atomic counters in `quota_service.py`. |
| FR-149 | PASS | Admin quota API/UI present and permission gated in `admin_quotas.py`, `AdminQuotasPage.tsx`, `App.tsx`. |
| FR-150 | PASS with Mid note O6-M01 | Quota config changes are immediately read from DB; the planned 60s Redis config cache is absent. |
| FR-151 | PASS | Query quota runs before session/attempt/LLM side effects; execution quota runs before source DB execution in `query_service.py`. |
| FR-152 | PASS | Quota exceeded returns sanitized 429 with `message_key` and `reset_at`; regression coverage in `test_phase6_sanitization_regression.py`. |
| FR-153 | PASS | Redis/quota service failures raise `QuotaUnavailableError` and return sanitized 503; covered by quota fail-closed tests. |
| FR-154 | PASS with Low notes O6-L01/O6-L02 | Daily key suffix and TTL reset to midnight are implemented in `quota_service.py`; edge TTL handling noted below. |
| FR-155 | PASS | `quota.config.change` and `quota.exceeded` audit events emit sanitized contexts; enum coverage present. |
| FR-156 | PASS | `DetectionRule`, `RuleRegistry`, `HostileInputDetector`, and query integration are implemented. |
| FR-157 | PASS | Five built-in categories with EN/AR coverage are implemented and tested in `test_detection_coverage.py`. |
| FR-158 | PASS | Blocked hostile inputs return only `error.hostile_input_blocked`; UI banner renders localized text only. |
| FR-159 | PASS | Detection runs before quota/evaluator/LLM in `QueryService.submit_question()`. |
| FR-160 | PASS | English and Arabic hostile corpora cover prompt injection, SQL injection, RBAC bypass, schema exposure, destructive SQL. |
| FR-161 | PASS | Rule registry supports registration/listing and duplicate guard. |
| FR-162 | PASS | Detection threshold config API/UI validate `block_confidence > flag_confidence` and require `admin.security.manage`. |
| FR-163 | PASS | Hostile blocked/flagged events are audited with `input_summary="[REDACTED_INPUT]"` and input hash only. |
| FR-164 | PASS | Flagged events audit and continue to quota; blocked events return before quota. |
| FR-165 | PASS | No auto-suspension path found; hostile input is block/flag plus audit only. |
| FR-166 | PASS | Audit search endpoint filters by action/actor/outcome/resource/date and is permission gated. |
| FR-167 | PASS | Offset pagination and metadata are implemented in `AuditSearchService.search()`. |
| FR-168 | PASS | CSV/JSON export endpoint, UI controls, 50k limit, quota gate, and downloads are implemented. |
| FR-169 | PASS | Export metadata includes actor, timestamp, filter summary, record count, checksum. |
| FR-170 | PASS | Export requires `admin.audit.verify`, export quota is enforced, contexts and metadata are redacted. |
| FR-171 | PASS | CSV cells beginning with `=`, `+`, `-`, `@`, or `|` are tab-prefixed. |
| FR-172 | PASS | Search/export self-audit logs store sanitized filter summary and pagination/record count only. |
| FR-173 | PASS | Audit search enforces retention cutoff before pagination and export fetch. |
| FR-174 | PASS | External purge scheduler docs exist and state platform does not own scheduler timing. |
| FR-175 | PASS | `audit.purge` marker is inserted before delete with required boundary metadata. |
| FR-176 | PASS | Retention endpoint reports retention months, last purge time, and purged count only. |
| FR-177 | PASS | New permissions are in enum and built-in Admin migration update. |
| FR-178 | PASS | EN/AR locale keys and parity tests cover quota, detection, audit search/export/retention. |
| FR-179 | PASS | RTL tests and browser smoke cover quota, detection, audit, retention, quota status surfaces. |
| FR-180 | PASS | Error surfaces are localized and sanitized for quota, hostile blocked, export limit, validation, permission, quota-unavailable paths. |

## 4. SC Verification Table

| SC | Status | Evidence |
|---|---|---|
| SC-063 | PASS | Quota-gated query/execution/export paths fail closed; tests cover Redis/quota unavailability. |
| SC-064 | PASS | Phase 6 sanitization regression checks forbid counters, policies, detector internals, raw input, DB/Redis/provider/stack/token leaks. |
| SC-065 | PASS | Built-in hostile detector coverage tests meet EN/AR category corpus expectations. |
| SC-066 | PASS | Clear hostile inputs reach block threshold coverage; hostile blocked path returns 400. |
| SC-067 | PASS | Hostile audit redaction tests assert no raw hostile text in persisted audit context. |
| SC-068 | PASS | Audit search/export/retention permission tests cover 401, 403, and permitted cases. |
| SC-069 | PASS | Export tests cover CSV/JSON metadata, redaction, formula injection, and 50k limit. |
| SC-070 | PASS | Retention-window search tests assert cutoff filters are applied server-side. |
| SC-071 | PASS | Quota fail-closed tests assert LLM/source DB are not called when quota service is unavailable. |
| SC-072 | PASS | Locale coverage and frontend gates completed; EN/AR parity verified. |
| SC-073 | PASS | Browser smoke report substantiates UC-11 through UC-18 with desktop/tablet/mobile screenshots. |
| SC-074 | PASS | Frontend regression gate recorded complete for Wave 18.4b. |
| SC-075 | PASS | Backend regression/security gate recorded complete for Wave 18.4a. |
| SC-076 | PASS | Opus audit has 0 Critical and 0 High findings. |
| SC-077 | PASS with Mid note O6-M02 | Purge marker and purge-gap verification, including all-purged boundary, are implemented and covered; large-log memory behavior noted below. |

## 5. Findings By Severity

### Critical

None.

### High

None.

### Mid

#### O6-M01 - Planned quota config Redis cache is not implemented

- Severity: Mid
- File/line evidence:
  - `specs/006-quotas-hostile-input-audit-hardening/tasks.md:84` requires quota config lookup "with 60s Redis cache (`quota_config:{role_id}`)".
  - `backend/src/app/services/quota_service.py:88-126` calls `QuotaRepository.get(role_id)` directly on every capped check and then executes only the counter Lua script; there is no `quota_config:{role_id}` Redis read/write path.
- Impact: This does not weaken the fail-closed security posture, and config changes take effect immediately. It does create avoidable DB load and means transient DB unavailability blocks quota-gated requests even if Redis could have enforced a recently cached quota config.
- Suggested fix: Either implement the documented 60s `quota_config:{role_id}` cache with invalidation on quota updates/deletes, or update the Phase 6 task/spec record to state that immediate DB reads were intentionally chosen over caching.

#### O6-M02 - `verify_chain()` materializes the full retained audit log

- Severity: Mid
- File/line evidence:
  - `backend/src/app/services/audit_service.py:399-400` executes the full ordered query and immediately calls `entries = result.scalars().all()`.
- Impact: Tamper verification is functionally correct, including purge-gap and all-purged boundaries, but memory/time use scales with the entire retained audit table. Large installations can make `/admin/audit/verify` slow or memory-heavy, which is an availability risk for an admin security operation.
- Suggested fix: Stream or batch audit rows in sequence order, keeping only `prev_hash` and a purge-marker lookup/index needed for upcoming boundaries. If purge markers remain pre-indexed, load only marker metadata separately rather than every retained row.

### Low

#### O6-L01 - Quota counter TTL can floor to zero at the end of a UTC day

- Severity: Low
- File/line evidence:
  - `backend/src/app/services/quota_service.py:43-47` returns `int(delta.total_seconds())`.
  - `backend/src/app/services/quota_service.py:108-115` passes that TTL into the Redis Lua script.
- Impact: In the final fractional second before midnight UTC, `int()` can produce `0`. Redis `EXPIRE key 0` deletes the just-incremented key, creating a very narrow window where repeated requests may avoid effective counting.
- Suggested fix: Return `max(1, math.ceil(delta.total_seconds()))` or otherwise clamp TTL to at least one second.

#### O6-L02 - Existing quota keys do not repair a missing TTL

- Severity: Low
- File/line evidence:
  - `backend/src/app/services/quota_service.py:30-34` sets `EXPIRE` only when `INCR` returns `1`.
- Impact: If a quota key loses its TTL after restore, migration, or manual operator action, subsequent increments will not restore expiration. The likely result is false quota exhaustion after the intended reset window rather than data exposure.
- Suggested fix: In the Lua script, check `TTL KEYS[1]` after increment and set `EXPIRE` when the TTL is negative or missing, not only on first creation.

## 6. Final Gate

PASS.

Critical = 0 and High = 0, so T-902 passes the Phase 6 Wave 18.4 independent Opus audit gate. Mid/Low items are non-blocking hardening follow-ups.
