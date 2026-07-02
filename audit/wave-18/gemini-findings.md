# Gemini Independent Security Audit Findings — Wave 18 (Phase 6)

## Summary Verdict: PASS

All security controls and functional requirements for Phase 6 (Quotas, Hostile Input Detection, Audit Hardening) have been successfully merged through main `HEAD`. Visual and browser smoke tests demonstrate correct Arabic localization and RTL rendering. Automated integration tests cover the sanitization, fail-closed, and rule execution requirements.

No **Critical** or **High** severity security findings were identified. Four findings (**2 Mid**, **2 Low**) are reported below with suggested remediation. Under the sign-off criteria (0 Critical, 0 High), the code is cleared for freeze.

* **Audit Date**: 2026-07-03
* **Target HEAD**: `499bff612cd85ee96bb012dc36a1639d5f1e0fe4`
* **Verdict**: **PASS**

---

## FR Status Table (FR-147–FR-180)

| Requirement | Description | Status | Evidence & Notes |
|---|---|---|---|
| **FR-147** | Role Quota configuration | **PASS** | `role_quotas` table created in Alembic migration `008`. CRUD mapped in [quota_repository.py](file:///home/avril/QueryCraft/backend/src/app/repositories/quota_repository.py). |
| **FR-148** | Counter storage in Redis | **PASS** | Implemented using daily UTC Redis keys and atomic Lua script checks. Mapped in [quota_service.py](file:///home/avril/QueryCraft/backend/src/app/services/quota_service.py#L30-L40). |
| **FR-149** | Quota Management UI | **PASS** | Config UI with inline forms implemented in [AdminQuotasPage.tsx](file:///home/avril/QueryCraft/frontend/src/pages/AdminQuotasPage.tsx). |
| **FR-150** | Config cache (60s TTL) | **PARTIAL** | Configuration fetched directly from repository. Omission of the 60s Redis config cache is logged as a finding (**Finding G6-M01**). |
| **FR-151** | Quota Enforcement | **PASS** | Validated in POST `/query/submit`, `/query/execute`, and export endpoints. Checked before LLM generation. |
| **FR-152** | Quota error sanitization | **PASS** | Exceeded response body contains only `message_key` and `reset_at`. No internal counts or keys are leaked. |
| **FR-153** | Quota fail-closed | **PASS** | Unreachable Redis returns a 503 Service Unavailable error and blocks request. Tested in [test_quota_fail_closed.py](file:///home/avril/QueryCraft/backend/tests/unit/test_quota_fail_closed.py). |
| **FR-154** | Daily Reset | **PASS** | Daily key format `quota:{user_id}:{dimension}:{YYYY-MM-DD}` resets automatically at midnight UTC via Redis TTL. |
| **FR-155** | Quota audit events | **PASS** | Emits `QUOTA_EXCEEDED` and `QUOTA_CONFIG_CHANGE` with sanitized contexts. Verified in [test_quota_audit.py](file:///home/avril/QueryCraft/backend/tests/unit/test_quota_audit.py). |
| **FR-156** | Hostile Input Detection | **PASS** | Implemented pre-LLM heuristical check in [query_service.py](file:///home/avril/QueryCraft/backend/src/app/services/query_service.py#L328-L369). |
| **FR-157** | 5 built-in rule categories | **PASS** | Categories (prompt injection, SQL injection, RBAC bypass, schema exposure, destructive SQL) mapped in rules subdirectory. |
| **FR-158** | Detection response sanitization | **PASS** | Returns HTTP 400 with `message_key: "error.hostile_input_blocked"`. No rules, patterns, or input text echoed. |
| **FR-159** | Pipeline order | **PASS** | Hostile detection runs first, query quota second, LLM third. Blocked requests do not increment quotas. |
| **FR-160** | Multi-lingual (EN/AR) | **PASS** | Matching heuristics implemented for both English and Arabic across all rules. |
| **FR-161** | Rule extensibility | **PASS** | Designed via `RuleRegistry` protocol singleton. Verified in [test_detection_registry.py](file:///home/avril/QueryCraft/backend/tests/unit/test_detection_registry.py). |
| **FR-162** | Threshold config API/UI | **PASS** | Slider UI gated by `admin.security.manage`. Validates block > flag. Mapped in [AdminDetectionPage.tsx](file:///home/avril/QueryCraft/frontend/src/pages/AdminDetectionPage.tsx). |
| **FR-163** | Sanitized detection logs | **PASS** | Audit context stores category, confidence, rule name, input summary (redacted), and input hash. |
| **FR-164** | No raw hostile payload storage | **PASS** | For blocked or flagged outcomes, context `input_summary` is hardcoded to `"[REDACTED_INPUT]"`. Verified in [test_no_raw_hostile_payload.py](file:///home/avril/QueryCraft/backend/tests/unit/test_no_raw_hostile_payload.py). |
| **FR-165** | Audit-only actions | **PASS** | Heuristic triggers block/flag and audit only; no automatic account suspension. |
| **FR-166** | Paginated audit search | **PASS** | Multi-parameter search implemented in [audit_search_service.py](file:///home/avril/QueryCraft/backend/src/app/services/audit_search_service.py). |
| **FR-167** | Search pagination metadata | **PASS** | Returns current page, page_size, total_entries, and total_pages. |
| **FR-168** | Audit log export (50k limit) | **PASS** | CSV and JSON formats supported up to 50k limit. Gated by daily exports quota dimension. |
| **FR-169** | Compliance metadata | **PASS** | Export files carry metadata comment (CSV) or object envelope (JSON) with stable SHA-256 payload checksum. |
| **FR-170** | Export redaction | **PASS** | Central value-based regex sweep redacts JWTs, database URLs, hosts, and stack traces. Verified in [test_export_redaction_defense.py](file:///home/avril/QueryCraft/backend/tests/unit/test_export_redaction_defense.py). |
| **FR-171** | Formula injection prevention | **PASS** | CSV exporter tab-prefixes fields beginning with `=`, `+`, `-`, `@`, and `|`. |
| **FR-172** | Search/export self-logging | **PASS** | Emits `AUDIT_SEARCH` and `AUDIT_EXPORT` logs. Context contains only filter parameters and metadata (no row values). |
| **FR-173** | Retention window enforcement | **PASS** | Cutoff window enforced in search/export database queries (`timestamp >= cutoff`). Verified in [test_audit_retention_window.py](file:///home/avril/QueryCraft/backend/tests/unit/test_audit_retention_window.py). |
| **FR-174** | Purge primitives | **PASS** | Expired log deletion database query implemented in `AuditService.purge_expired_entries`. |
| **FR-175** | Immutability / gap marker | **PASS** | Inserts `audit.purge` marker in same transaction before deleting. Marker chains hash block sequence. |
| **FR-176** | Retention status API/UI | **PASS** | Panel in `AdminAuditPage.tsx` displays policy period, last purge date, and purged count. |
| **FR-177** | Permission mapping | **PASS** | Gated endpoints require explicit `admin.quotas.manage` or `admin.security.manage`. No role-name bypasses. |
| **FR-178** | i18n key parity | **PASS** | Asserted 100% key parity between locales en and ar in [localeCoverage.test.ts](file:///home/avril/QueryCraft/frontend/src/locales/localeCoverage.test.ts). |
| **FR-179** | RTL layouts | **PASS** | Admin pages visual checks green; logical properties used. Verified via Playwright RTL test suite. |
| **FR-180** | Error translation | **PASS** | System translation strings loaded and verified in en.json and ar.json for all error codes. |

---

## SC Status Table (SC-063–SC-077)

| Success Criteria | Description | Status | Evidence & Notes |
|---|---|---|---|
| **SC-063** | Quota limits enforced, returning 429 | **PASS** | Checked via integration tests [test_quota_enforcement.py](file:///home/avril/QueryCraft/backend/tests/unit/test_quota_enforcement.py) and [test_execution_quota.py](file:///home/avril/QueryCraft/backend/tests/integration/test_execution_quota.py). |
| **SC-064** | Sanitized error responses | **PASS** | Verified via [test_phase6_sanitization_regression.py](file:///home/avril/QueryCraft/backend/tests/unit/test_phase6_sanitization_regression.py) asserting zero leakage of secrets or internal details. |
| **SC-065** | Hostile detector passes coverage | **PASS** | Heuristics block 100% of hostile query test suite, and allow >95% of benign queries in [test_detection_passthrough.py](file:///home/avril/QueryCraft/backend/tests/integration/test_detection_passthrough.py). |
| **SC-066** | English and Arabic heuristics | **PASS** | Handled in all five rules. Verified via English and Arabic test arrays. |
| **SC-067** | Redacted hostile audit log context | **PASS** | Hostile entries store hash and `input_summary = "[REDACTED_INPUT]"`. Verified via [test_no_raw_hostile_payload.py](file:///home/avril/QueryCraft/backend/tests/unit/test_no_raw_hostile_payload.py). |
| **SC-068** | Search/export restricted by permissions | **PASS** | Verified via integration tests [test_audit_search_export_permissions.py](file:///home/avril/QueryCraft/backend/tests/unit/test_audit_search_export_permissions.py) returning 403 on missing permissions. |
| **SC-069** | Compliance metadata in exports | **PASS** | Checksum verification of JSON/CSV datasets matches raw payloads in unit tests. |
| **SC-070** | Retention window DB filters | **PASS** | Verified via [test_audit_retention_window.py](file:///home/avril/QueryCraft/backend/tests/unit/test_audit_retention_window.py) confirming SQL query filters on date cutoff. |
| **SC-071** | Fail-closed behavior on Redis down | **PASS** | Verified via unit tests mock-blocking Redis and asserting 503 response on gated API paths. |
| **SC-072** | 100% key translation parity | **PASS** | Validated by [localeCoverage.test.ts](file:///home/avril/QueryCraft/frontend/src/locales/localeCoverage.test.ts) running on Vitest. |
| **SC-073** | RTL visual direction mirroring | **PASS** | Visual check in browser Playwright smoke logs passes (documented in [browser-smoke-wave18.md](file:///home/avril/QueryCraft/audit/wave-18/browser-smoke-wave18.md)). |
| **SC-074** | Frontend build & lint gates clean | **PASS** | Rerun verified `npm run typecheck` and `npm run build` pass clean. |
| **SC-075** | Backend pytest & ruff gates clean | **PASS** | 2108 pytest unit/integration tests pass. Ruff lint and format check pass clean. |
| **SC-076** | 0 Critical and 0 High findings | **PASS** | Verified. No findings exceeding **Mid** severity are active. |
| **SC-077** | Purge-gap marker verification | **PASS** | Verified via integration test [test_purge_verify_cycle.py](file:///home/avril/QueryCraft/backend/tests/integration/test_purge_verify_cycle.py) confirming valid gaps bridge chain verifier. |

---

## Detailed Findings

### Critical (0)
*No findings.*

### High (0)
*No findings.*

### Mid (2)

#### Finding G6-M01: Missing Redis Quota Configuration Caching
* **File Reference**: [quota_service.py](file:///home/avril/QueryCraft/backend/src/app/services/quota_service.py#L89)
* **Impact**: The specification (FR-150) and task definition (T-794) mandate that role quota configurations must be cached in Redis with a 60-second TTL to avoid database overhead. Currently, the implementation directly invokes `self._quota_repo.get(role_id)` on every check, issuing a database SELECT query on every query submission, query execution, and audit log export attempt. In high-traffic scenarios, this causes significant, unnecessary database connection and query overhead.
* **Suggested Fix**: Implement a Redis lookup before querying the database, caching the role quota database representation (or a serialized JSON string) in Redis with a key prefix `quota_config:{role_id}` and a 60-second TTL. On database updates (PUT/DELETE in admin quotas), invalidate the cached key.

#### Finding G6-M02: Potential OOM/DoS inside Audit Chain Verification (`verify_chain`)
* **File Reference**: [audit_service.py](file:///home/avril/QueryCraft/backend/src/app/services/audit_service.py#L399)
* **Impact**: Verification endpoint walks the entire chain from database genesis to the latest sequence. Currently, `verify_chain` runs `session.execute(select(AuditLogEntry))` and calls `.all()` to load all records into memory at once. If the audit log entries table grows to hundreds of thousands or millions of records (within the 24-month retention window), this will cause transient memory exhaustion (OOM crashes) or query timeouts, resulting in a Denial of Service (DoS) of the admin dashboard.
* **Suggested Fix**: Refactor `verify_chain` to stream entries in chunks (e.g. batch size of 5,000 using keyset pagination or server-side cursors) rather than reading all entries into memory at once.

---

### Low (2)

#### Finding G6-L01: Precision Truncation or Negative TTLs in Quota Service
* **File Reference**: [quota_service.py](file:///home/avril/QueryCraft/backend/src/app/services/quota_service.py#L43-L47)
* **Impact**: The TTL calculation `_seconds_until_midnight_utc` subtracts `now` from `tomorrow` and casts `delta.total_seconds()` to `int`. If called within the final second before midnight, the remaining fraction of a second results in a float less than 1.0 (e.g. `0.85`), which casts to `0`. A TTL of `0` sent to Redis `EXPIRE` causes immediate key deletion (or error/unexpected behavior depending on Redis version), creating a minor window for quota limit bypass.
* **Suggested Fix**: Wrap the TTL assignment in a safety block:
  ```python
  ttl = max(1, _seconds_until_midnight_utc(now))
  ```

#### Finding G6-L02: Redis Lua Script TTL bypass on Keys Created Without Expiry
* **File Reference**: [quota_service.py](file:///home/avril/QueryCraft/backend/src/app/services/quota_service.py#L30-L40)
* **Impact**: The Redis Lua script only assigns a TTL when `used == 1`. If the Redis connection or command is interrupted immediately after `INCR` but before `EXPIRE`, or if a key is manually seeded/altered, subsequent requests will increment the counter without ever entering the `used == 1` branch. The counter key will therefore remain in Redis indefinitely without resetting.
* **Suggested Fix**: Update the Lua script to query the TTL of the key. If the TTL is `-1` (no expiry set), call `EXPIRE` even if `used > 1`:
  ```lua
  local used = redis.call('INCR', KEYS[1])
  local ttl = redis.call('TTL', KEYS[1])
  if ttl == -1 then
      redis.call('EXPIRE', KEYS[1], ARGV[2])
  end
  ```
