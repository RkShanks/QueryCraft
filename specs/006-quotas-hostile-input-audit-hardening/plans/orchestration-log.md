# Phase 6 Orchestration Log

## Phase 6 Initialization

- **Status**: ACTIVE
- **Date**: 2026-06-21
- **Spec Directory**: `specs/006-quotas-hostile-input-audit-hardening/`
- **Tasks**: `specs/006-quotas-hostile-input-audit-hardening/tasks.md`
- **Prior Phase Status**: Phase 5 FROZEN on `main`
- **Branch Context**: `main`

### Locked Scope

- Role-level quotas only; no per-user overrides.
- Quota dimensions: daily queries, daily executions, daily audit exports.
- Reset interval: daily only.
- Query flow order: hostile detection first, query quota second, LLM generation third.
- Wave 18.1 enforces query and execution quotas only; export quota comes in Wave 18.3.
- No auto-suspension in Phase 6.
- Hostile detection v1 is heuristic/rule-based with 5 built-in categories.
- Hostile input audit logs must never store raw hostile payloads.
- Frontend role discovery rule: call `/admin/roles` only with `admin.roles.manage`; quota-only admins must not call role or SSO group-mapping endpoints.

### Wave Structure

| Wave | Tasks | Scope | Owner |
|---|---:|---|---|
| 18.0 | T-779-T-792 | Foundation schemas, migration, enums, orchestration/audit stubs | Backend + Orchestrator |
| 18.1 | T-793-T-821 | Role quotas, quota enforcement, admin quota UI | Backend + Frontend |
| 18.2 | T-822-T-857 | Hostile input detection, detection config API/UI | Backend + Frontend |
| 18.3 | T-858-T-891 | Audit search/export/retention hardening | Backend + Frontend |
| 18.4 | T-892-T-909 | Cross-dialect verification, browser smoke, audits, closeout | Backend + Frontend + Orchestrator |

---

## Wave 18.0 — Foundation

### Dispatch

- **Date**: 2026-06-21
- **Model**: Backend Implementer
- **T-IDs**: T-779 through T-789, T-792
- **Branch**: `phase-6/wave-18.0-foundation`
- **Status**: MERGED before Wave 18.1 dispatch

### Orchestrator Tasks

- **T-790**: `audit/wave-18/` stubs created.
- **T-791**: This orchestration log initialized.

---

## Wave 18.1 — Quotas Backend

### Review & Merge

- **Date**: 2026-06-21
- **PR**: https://github.com/RkShanks/QueryCraft/pull/155
- **Branch**: `phase-6/wave-18.1-quotas`
- **Final HEAD**: `8aaed603954431ce98a55e9a49dfbfbb5e8b9754`
- **Merge Commit**: `6adea46b374f0ffb78cd866fb67105ffc0b5979b`
- **Status**: MERGED
- **Tasks Completed**: T-793 through T-809
- **CI**: `backend-test` SUCCESS, `frontend-test` SUCCESS
- **Gate Notes**: Backend quota gate recorded complete in PR branch; GitHub CI green after merge.

### Scope

- Role quota model/repository/service.
- Redis atomic quota counter with daily UTC reset.
- Query quota enforced before LLM generation in Wave 18.1.
- Execution quota enforced before SQL execution.
- Quota admin API gated by `admin.quotas.manage`.
- Quota audit events sanitized: no counter values or policy IDs in responses.

---

## Wave 18.1 — Quotas Frontend

### Review & Merge

- **Date**: 2026-06-21
- **PR**: https://github.com/RkShanks/QueryCraft/pull/156
- **Branch**: `phase-6/wave-18.1-quotas-ui`
- **Final HEAD**: `d55783db86ef65348aa519a3206aeab26edc454c`
- **Merge Commit**: `a85f211fcdbde0895b47e3cbae10374cd72cb4e0`
- **Status**: MERGED
- **Tasks Completed**: T-810 through T-821
- **CI**: `backend-test` SUCCESS, `frontend-test` SUCCESS
- **Local Gates Verified Before Merge**: `npm test -- --run` (692 tests), `npm run lint`, `npm run typecheck`, `npm run build`, `npm run lint:css`, `git diff --check`.

### Review Finding Resolved

- `useAdminRoles({ enabled: false })` now gates both `/admin/roles` and `/admin/sso/group-mappings`.
- Regression coverage added in `frontend/src/hooks/__tests__/useAdminRoles.test.tsx`.
- Missing i18n keys added: `common.saveSuccess`, `admin.quotas.deleteSuccess`.

---

## Wave 18.2 — Hostile Input Detection Backend

### Dispatch

- **Date**: 2026-06-22
- **Model**: Backend Implementer
- **T-IDs**: T-822 through T-847, T-856
- **Branch**: `phase-6/wave-18.2-hostile-detection`
- **Status**: DISPATCHED
- **Dependency State**: Wave 18.1 merged; `QuotaService` exists for post-detection quota check wiring.
- **Frontend Hold**: T-848 through T-855 and T-857 remain held until backend/API is available.

### Dispatch Constraints

- Read `.agents/skills/BACKEND_IMPLEMENTER.md`, `.agents/skills/KARPATHY.md`, and `.agents/skills/TDD.md` before product edits.
- Follow TDD commit discipline: RED test commit, GREEN implementation commit, docs/gate commit as needed.
- Detection runs before quota. Blocked hostile input must not increment quota.
- Hostile input audit logs must never store raw hostile payloads.
- Response sanitization is mandatory: blocked response body contains only `{"message_key":"error.hostile_input_blocked"}`.
- Rule v1 is heuristic/rule-based with 5 built-in categories: prompt injection, SQL injection, RBAC bypass, schema/secret exposure, destructive SQL.
- Built-in categories must cover English and Arabic patterns.
- Threshold config API uses `admin.security.manage`.
- No auto-suspension in Phase 6; hostile inputs are blocked/flagged and audited only.

### Dispatch Correction — Split for Cheap Model

- **Date**: 2026-06-22
- **Reason**: T-822 through T-847 plus T-856 is too large for a cheap implementer model in one prompt.
- **Supersedes**: Single large Wave 18.2 backend dispatch above.
- **Revised First Dispatch**: Wave 18.2a backend foundation, T-822 through T-825 only.
- **Hold**: T-826 through T-847 and T-856 remain undispatched until 18.2a merges.
- **Later Suggested Slices**:
  - 18.2b rules: T-826 through T-835.
  - 18.2c coverage + config API: T-836 through T-841.
  - 18.2d audit redaction + query integration + backend gate: T-842 through T-847, T-856.

---

## Wave 18.2a — Detection Foundation

### Review & Merge

- **Date**: 2026-06-22
- **PR**: https://github.com/RkShanks/QueryCraft/pull/157
- **Branch**: `phase-6/wave-18.2a-detection-foundation`
- **Final HEAD**: `1dbf2eb260d7ae5d0e1a863dabf6a84b8c64837f`
- **Merge Commit**: `9650856d87e299506495ea0fa65d867429b3d572`
- **Status**: MERGED
- **Tasks Completed**: T-822 through T-825
- **CI**: backend-test SUCCESS, frontend-test SUCCESS
- **Local Review Gates**: `rtk uv run ruff check src tests`; `rtk uv run pytest tests/unit/test_detection_registry.py tests/unit/test_hostile_detector.py -x --tb=short` (22 passed); `rtk git diff --check`.

### Review Finding Resolved

- Initial backend CI failed on Ruff F401 for unused `DetectionRule` imports in `backend/tests/unit/test_detection_registry.py`.
- Fix commit `1dbf2eb` added `# noqa: F401` to the protocol-documentation imports; focused gates passed after fix.

---

## Wave 18.2b — Built-in Detection Rules

### Review & Merge

- **Date**: 2026-06-22
- **PR**: https://github.com/RkShanks/QueryCraft/pull/158
- **Branch**: `phase-6/wave-18.2b-detection-rules`
- **Final HEAD**: `769cca496f77ae5a8dfee0e5019ab6b665febf79`
- **Merge Commit**: `80d24d002c30f570426adcbf839201c8a2748347`
- **Status**: MERGED
- **Tasks Completed**: T-826 through T-835
- **CI**: backend-test SUCCESS, frontend-test SUCCESS
- **Local Review Gates**: `rtk uv run pytest tests/unit/test_detection_package_registration.py tests/unit/test_rule_prompt_injection.py tests/unit/test_rule_sql_injection.py tests/unit/test_rule_rbac_bypass.py tests/unit/test_rule_schema_exposure.py tests/unit/test_rule_destructive_sql.py -x --tb=short` (109 passed); `rtk uv run ruff check src tests`; `rtk uv run ruff format --check src tests`; `rtk git diff --check`.

### Review Finding Resolved

- Built-in rule modules initially self-registered only when directly imported; `REGISTRY` was empty after a plain `import app.services.detection`.
- Fix commit `769cca49` imports all built-in rule modules from `backend/src/app/services/detection/__init__.py` and adds package-registration regression coverage.

---

## Wave 18.2c — Detection Coverage and Config API

### Review & Merge

- **Date**: 2026-06-22
- **PR**: https://github.com/RkShanks/QueryCraft/pull/159
- **Branch**: `phase-6/wave-18.2c-detection-coverage-config`
- **Final HEAD**: `211b06e589b650739db2bb7cd8cd8931aefe515e`
- **Merge Commit**: `0c549429324ce666f723e495e07ef9967df5301f`
- **Status**: MERGED
- **Tasks Completed**: T-836 through T-841
- **CI**: backend-test SUCCESS, frontend-test SUCCESS
- **Local Review Gates**: focused detection/admin gates reported by implementer; reviewer confirmed CI green after fixes.

### Review Findings Resolved

- `admin_detection.py` initially instantiated `DetectionThresholdUpdate` manually, which could bypass FastAPI's 422 `RequestValidationError` path. Fix commit `cdf27353` changed PUT body binding to typed `DetectionThresholdUpdate`.
- Ruff I001 import sorting in `test_detection_config_repo.py` fixed in `cdf27353`.
- Full backend suite initially failed because `detection.config.change` remained in audit `KNOWN_DEFERRED` and new audit context keys were not in `_SAFE_KEYS`. Fix commit `211b06e5` updated audit coverage/redaction guardrails.

---

## Wave 18.2d — Detection Audit Redaction and Query Integration

### Dispatch

- **Date**: 2026-06-22
- **Model**: Backend Implementer
- **T-IDs**: T-842 through T-847, T-856
- **Branch**: `phase-6/wave-18.2d-detection-integration`
- **Status**: DISPATCHED
- **Dependency State**: Wave 18.2c merged; built-in rules and detection config API available on `main`.

### Dispatch Constraints

- Read `.agents/skills/BACKEND_IMPLEMENTER.md`, `.agents/skills/TDD.md`, `.agents/skills/KARPATHY.md`, and `~/.codex/RTK.md` before product edits.
- Use RTK for shell commands.
- Follow TDD commit discipline: RED test commit, GREEN implementation commit, docs/gate commit as needed.
- Run detection before quota in `POST /query/submit`.
- Blocked hostile input must not increment quota.
- Hostile input audit logs must never store raw hostile payloads.
- Blocked response body must contain only `{"message_key":"error.hostile_input_blocked"}`.
- Flagged input emits `HOSTILE_INPUT_FLAGGED` and continues to quota check.
- No frontend work in this slice.

### Review and Merge Result

- **PR**: #160
- **Merged**: 2026-06-23
- **Merge Commit**: `e5444f969fcbf077f092b3f31e473dce7e8dbe34`
- **Tasks Completed**: T-842 through T-847, T-856
- **CI**: backend-test SUCCESS, frontend-test SUCCESS
- **Local Review Gates**: focused backend blocker gates passed; local full backend suite only failed on missing local DB services, not PR code.

### Review Findings Resolved

- Audit coverage matrix still deferred `hostile.input.blocked` and `hostile.input.flagged` after `query_service.py` shipped the emitters. Fix commit `a0a832bc` marks both as shipped and updates the matrix to 27 of 31 shipped / 4 deferred.
- Frontend locales lacked `error.hostile_input_blocked`. Fix commit `a0a832bc` adds EN and AR keys.
- Existing QueryService unit tests with mocked DB sessions crashed on detection config threshold comparison. Fix commit `a0a832bc` adds a unit-test conftest default detector stub for non-detection unit tests.

### Current Wave Checkpoint

- **Date**: 2026-07-01
- **Branch Context**: `main` at `a0ef02c5359bc747973072fa0a39de3b4834db6c`
- **Status**: Wave 18.3h COMPLETE. T-876 verified complete.
- **Next Dispatch**: Wave 18.3i backend final audit hardening gate, T-877 through T-879.
- **Frontend Dispatch Hold**: cleared; backend/API is available on `main`.

---

## Wave 18.2e — Hostile Input Detection UI

### Dispatch

- **Date**: 2026-06-23
- **Model**: Frontend Implementer
- **T-IDs**: T-848 through T-855, and T-857
- **Branch**: `phase-6/wave-18.2e-detection-ui`
- **Status**: COMPLETE
- **Local Review Gates**: `npm test -- --run` (passed), `npm run lint` (passed), `npm run typecheck` (passed), `npm run build` (passed), `npm run lint:css` (passed), `git diff --check` (passed).
- **PR**: #161

### Scope

- Typed API client (`frontend/src/api/detection.ts`) for config configuration
- React Query hook (`useAdminDetection.ts`) for config management
- Config threshold page (`AdminDetectionPage.tsx`) with sliders, numeric inputs, verification (block > flag), status metrics, and access-denied display
- Error banners (`HostileInputBlockedBanner.tsx`) in both AskQuestionPage and WorkspacePage
- Dynamic locales (en/ar) translation keys for settings and block errors
- AppShell sidebar links and App route protection wrapper for permission `admin.security.manage`

### Review and Merge Result

- **PR**: #161
- **Merged**: 2026-06-23
- **Merge Commit**: `6550c51f7868f39ab762701b2ab2bc46c1079229`
- **Tasks Completed**: T-848 through T-855, T-857
- **CI**: backend-test SUCCESS, frontend-test SUCCESS
- **Local Review Gates**: focused reviewer check `npm test -- --run AdminDetectionPage HostileInputBlockedBanner Sidebar` passed (44 tests); `git diff --check` clean.
- **Review Result**: no blocking findings.

### Next Dispatch

- Wave 18.3a backend audit search foundation, T-858 through T-862.

---

## Wave 18.3a — Audit Search Foundation

### Dispatch

- **Date**: 2026-06-23
- **Model**: Backend Implementer
- **T-IDs**: T-858 through T-862
- **Branch**: `phase-6/wave-18.3a-audit-search`
- **Status**: DISPATCHED
- **Dependency State**: Wave 18.2 merged; hostile input audit events are available on `main`.

### Dispatch Constraints

- Read `.agents/skills/BACKEND_IMPLEMENTER.md`, `.agents/skills/TDD.md`, `.agents/skills/KARPATHY.md`, and `~/.codex/RTK.md` before product edits.
- Use RTK for shell commands.
- Follow TDD commit discipline: RED test commit, GREEN implementation commit, docs/gate commit as needed.
- Keep this slice to audit search only: migration, `AuditSearchService`, and `GET /admin/audit/entries`.
- Do not implement export, purge markers, retention endpoint, or frontend UI in this slice.
- `AUDIT_SEARCH` context must contain only sanitized filter summary and pagination metadata, never returned audit entry values.
- Search must enforce retention window server-side before pagination.

### Review and Merge Result

- **PR**: #162
- **Merged**: 2026-06-23
- **Merge Commit**: `ae2c0f2d25c5e19d6974e2d5053cdd6ac2f6d09c`
- **Tasks Completed**: T-858 through T-862
- **CI**: backend-test SUCCESS, frontend-test SUCCESS
- **Local Review Gates**: `pytest tests/unit -q -m "not integration"` passed (1692 passed, 292 skipped); `ruff check src tests` passed; `git diff --check` clean.
- **Review Result**: initial CI blockers resolved in `d0b1ad7` (`filters`/`page`/`page_size` safe context keys, `error.invalid_date` EN/AR locale keys). No blocking findings after fix.

### Next Dispatch

- Wave 18.3b backend audit export service, T-863 through T-866.

---

## Wave 18.3b — Audit Export Service

### Dispatch

- **Date**: 2026-06-23
- **Model**: Backend Implementer
- **T-IDs**: T-863 through T-866
- **Branch**: `phase-6/wave-18.3b-audit-export-service`
- **Status**: DISPATCHED
- **Dependency State**: Wave 18.3a merged; `AuditSearchService` and `GET /admin/audit/entries` are available on `main`.

### Dispatch Constraints

- Read `.agents/skills/BACKEND_IMPLEMENTER.md`, `.agents/skills/TDD.md`, `.agents/skills/KARPATHY.md`, and `~/.codex/RTK.md` before product edits.
- Use RTK for shell commands.
- Follow TDD commit discipline: RED test commit, GREEN implementation commit, docs/gate commit as needed.
- Keep this slice to export service only: CSV/JSON export serialization, 50k limit, checksum metadata, formula-injection prevention, and defense-in-depth redaction tests.
- Do not implement `POST /admin/audit/export`, quota enforcement, purge markers, retention endpoint, or frontend UI in this slice.
- Export output must pass a central redaction pass before serialization.
- CSV formula injection prevention must tab-prefix cells starting with `=`, `+`, `-`, `@`, or `|`.
- Checksum must be SHA-256 of the data payload, not of mutable headers around it.

### Review and Merge Result

- **PR**: #163
- **Merged**: 2026-06-23
- **Merge Commit**: `8dde1a7dbeb6bf4ff7f4b0e8a9024fa0d8accf56`
- **Tasks Completed**: T-863 through T-866
- **CI**: backend-test SUCCESS, frontend-test SUCCESS
- **Local Review Gates**: focused export tests passed (48 tests); `ruff check src tests` passed; `ruff format --check src tests` passed; `git diff --check` clean.
- **Review Result**: no blocking findings.

### Next Dispatch

- Wave 18.3c backend audit export API, T-867 through T-868.

---

## Wave 18.3c — Audit Export API

### Dispatch

- **Date**: 2026-06-23
- **Model**: Backend Implementer
- **T-IDs**: T-867 through T-868
- **Branch**: `phase-6/wave-18.3c-audit-export-api`
- **Status**: COMPLETE
- **Dependency State**: Wave 18.3b merged; `AuditExportService`, `AuditSearchService`, and `GET /admin/audit/entries` are available on `main`.

### Dispatch Constraints

- Read `.agents/skills/BACKEND_IMPLEMENTER.md`, `.agents/skills/TDD.md`, `.agents/skills/KARPATHY.md`, and `~/.codex/RTK.md` before product edits.
- Use RTK for shell commands.
- Follow TDD commit discipline: RED test commit, GREEN implementation commit, docs/gate commit as needed.
- Keep this slice to `POST /admin/audit/export` only.
- Do not implement purge markers, verify-chain purge-gap handling, retention endpoint, frontend UI, or final Wave 18.3 backend gate in this slice.
- Permission is existing `admin.audit.verify`.
- Export quota must use `QuotaService.check_and_increment(user_id, role_id, "exports")`.
- Quota exhausted returns 429 with localized `message_key`; quota unavailable returns 503 with localized `message_key`.
- Export limit > 50,000 must return 422 with localized `message_key`.
- `AUDIT_EXPORT` context must include only sanitized filter summary and `record_count`; never exported entry values.
- Response must set correct `Content-Type` and `Content-Disposition` for CSV and JSON downloads.

### Results

- **T-867** ✅ RED integration tests — `backend/tests/integration/test_audit_export.py` (357 lines). Tests: 403 without permission, CSV/JSON download headers, compliance metadata, formula injection, quota 429/503, 422 limit, AUDIT_EXPORT event emission + no-entry-data invariant.
- **T-868** ✅ GREEN endpoint — `POST /admin/audit/export` in `backend/src/app/api/v1/admin_audit.py`. Quota-gated, 50k-limited, AuditExportService serialization, AUDIT_EXPORT emit (sanitized context only), correct Content-Type/Content-Disposition.
- **Coverage updates**: `audit.export` removed from `KNOWN_DEFERRED`; coverage matrix updated to 28/31 shipped / 3 deferred. `TestAuditExportEmits` class added to `test_audit_event_coverage.py`.
- **Redaction safe-keys**: `filter_summary`, `record_count`, `format` added to `_SAFE_KEYS` in `test_audit_redaction_comprehensive.py`.
- **Localization**: `error.export_limit_exceeded` added to `en.json` and `ar.json`.
- **Gate**: `ruff check`/`format` clean across all 372 backend files; 1742 unit tests passed, 0 failed.
- **Commits**: `a084dfb` (RED T-867), `192cd2a` (GREEN T-868 + fixups).
- **Diff**: 6 files, 645 insertions.

### Next Dispatch

- Wave 18.3d or final Wave 18.3 backend gate (T-869+, purge markers, verify_chain purge-gap handling) — to be dispatched per orchestrator plan.

---

## Wave 18.3c — Blocker Fix Review + PR

**Date**: 2026-06-30
**Orchestrator action**: Review of Wave 18.3c branch → identified three blockers → applied fixes directly (user-authorized) → pushed + opened PR.

### Review Findings (pre-fix)

| # | File | Issue |
|---|------|-------|
| B1 | `admin_audit.py` `export_audit_entries` | Manual `request.json() + AuditExportRequest(**body)` → Pydantic validation errors swallowed as 500s |
| B2 | `admin_audit.py` `export_audit_entries` | Inline `timedelta(days=months*30)` retention cutoff and raw SQLAlchemy query duplicates `AuditSearchService` logic |
| B3 | `test_audit_event_coverage.py` | `audit.export` still in `KNOWN_DEFERRED`; docstring says 28/31 / 3 deferred; unit test uses stale `request.json()` mock pattern |

### Fixes applied (commit `f70690f`)

- **B1**: Replaced `request.json()` + manual construction with `export_req: AuditExportRequest = Body(...)` typed FastAPI dependency. Pydantic 422s now surface correctly.
- **B2**: Replaced inline cutoff + raw query with `AuditSearchService.search()` — count check (`page_size=1`) then full fetch (`page_size=min(total,50_000)`). Reuses relativedelta-aware retention and ORM filters.
- **B3**: Removed `audit.export` from `KNOWN_DEFERRED`; updated table row 30; docstring now reads **29/31 shipped / 2 deferred**; unit test updated to typed-param call + `AuditSearchService.search` patch.

### Foundation gates (post-fix)

- `pytest tests/unit -q`: **1742 passed, 295 skipped** ✅
- `ruff check src/app/api/v1/admin_audit.py tests/unit/test_audit_event_coverage.py`: **All checks passed** ✅
- `ruff format --check`: **2 files already formatted** ✅

### PR

- **PR #164**: https://github.com/RkShanks/QueryCraft/pull/164
- Branch: `phase-6/wave-18.3c-audit-export-api` → `main`
- 4 commits total: RED (T-867), GREEN (T-868), docs, fix blockers

### Final Review and Merge Result

- **PR**: #164
- **Merged**: 2026-06-30
- **Merge Commit**: `c931e460c84010edc1366f6ef9df0db6075fefb4`
- **Tasks Completed**: T-867 through T-868
- **CI**: backend-test SUCCESS, frontend-test SUCCESS
- **Final Fix**: `94ad416` fixed export 500s for 101 through 50,000 matching entries by adding `AuditSearchService.get_all_entries_for_export()` and avoiding `AuditSearchParams.page_size` (`le=100`) for full export fetches.
- **Review Result**: no blocking findings after final fix.

### Next dispatch

- Wave 18.3d backend purge marker, T-869 through T-870.

---

## Wave 18.3d — Audit Purge Marker

### Dispatch

- **Date**: 2026-06-30
- **Model**: Backend Implementer
- **T-IDs**: T-869 through T-870
- **Branch**: `phase-6/wave-18.3d-audit-purge-marker`
- **Status**: DISPATCHED
- **Dependency State**: Wave 18.3c merged; audit search/export APIs and services are available on `main`.

### Dispatch Constraints

- Read `.agents/skills/BACKEND_IMPLEMENTER.md`, `.agents/skills/TDD.md`, `.agents/skills/KARPATHY.md`, and `~/.codex/RTK.md` before product edits.
- Use RTK for shell commands.
- Follow TDD commit discipline: RED test commit, GREEN implementation commit, docs/gate commit as needed.
- Keep this slice to purge marker creation only: T-869 RED unit tests and T-870 `AuditService.purge_expired_entries()` changes.
- Do not implement verify-chain purge-gap handling, purge+verify integration tests, retention endpoint, frontend UI, or final Wave 18.3 backend gate in this slice.
- Insert the `audit.purge` marker before deleting expired entries and in the same transaction.
- Marker context must include: `purged_from_seq`, `purged_to_seq`, `purged_count`, `retention_months`, `first_surviving_seq`, `first_surviving_prev_hash`, `last_retained_hash`, `last_retained_seq`.
- Do not modify existing audit entries. Preserve immutability guards.

### Results

- **T-869** ✅ RED unit tests — `backend/tests/unit/test_purge_gap_marker.py` (467 lines). Tests: marker inserted before deletion, no marker when nothing to purge, marker is latest entry, all 8 required context fields, purged_from_seq/purged_to_seq/purged_count/retention_months/first_surviving_seq/first_surviving_prev_hash/last_retained_hash/last_retained_seq, surviving entries unchanged, ORM delete/update on marker raises immutability guard, marker chains into hash sequence (prev_hash and row_hash correct).
- **T-870** ✅ GREEN implementation — `backend/src/app/services/audit_service.py` `purge_expired_entries()`. Identifies expired entries before deletion; computes boundary metadata; inserts `AUDIT_PURGE` marker via `AuditService.log()` in same transaction BEFORE delete; then deletes expired rows. Returns count of deleted entries. No existing entries rewritten.
- **Coverage updates**: `audit.purge` removed from `KNOWN_DEFERRED`; coverage matrix updated to **30/31 shipped / 1 deferred** (quota.warning). `TestAuditPurgeEmits` class added.
- **Redaction safe-keys**: 7 purge context keys added to `_SAFE_KEYS` in `test_audit_redaction_comprehensive.py`.
- **Gate**: `ruff check`/`format` clean across 373 backend files; **1745 unit tests passed**, 0 failed.
- **Commits**: `b82cecb` (RED T-869), `baa7ef8` (GREEN T-870 + fixups).

### Review and Merge Result

- **PR**: #165
- **Merged**: 2026-06-30
- **Merge Commit**: `cf90666e18480b0c83503e6e52cb5d307b4e7e7d`
- **Tasks Completed**: T-869 through T-870
- **CI**: backend-test SUCCESS, frontend-test SUCCESS
- **Local Review Gates**: focused purge/audit guard tests passed (50 passed, 136 skipped); `ruff check src tests` passed; `git diff --check` clean.
- **Review Result**: no blocking findings.

### Next Dispatch

- Wave 18.3e backend verify-chain purge-gap handling, T-871 through T-872.

---

## Wave 18.3e — Verify Chain Purge-Gap Handling

### Dispatch

- **Date**: 2026-06-30
- **Model**: Backend Implementer
- **T-IDs**: T-871 through T-872
- **Branch**: `phase-6/wave-18.3e-verify-chain-purge-gap`
- **Status**: DISPATCHED
- **Dependency State**: Wave 18.3d merged; `audit.purge` marker insertion is available on `main`.

### Dispatch Constraints

- Read `.agents/skills/BACKEND_IMPLEMENTER.md`, `.agents/skills/TDD.md`, `.agents/skills/KARPATHY.md`, and `~/.codex/RTK.md` before product edits.
- Use RTK for shell commands.
- Follow TDD commit discipline: RED test commit, GREEN implementation commit, docs/gate commit as needed.
- Keep this slice to verify-chain purge-gap handling only: T-871 RED unit tests and T-872 `AuditService.verify_chain()` changes.
- Do not implement purge+verify integration tests, retention endpoint, scheduler docs, frontend UI, or final Wave 18.3 backend gate in this slice.
- If a retained entry has an orphaned `prev_hash`, look for a retained `audit.purge` marker whose `first_surviving_seq` and `first_surviving_prev_hash` match.
- If a matching purge marker exists, treat the gap as intentional and continue verification.
- If no matching purge marker exists, report the gap as tampering.
- Do not rewrite or mutate existing audit entries.

### Results

- **T-871** ✅ RED unit tests — `backend/tests/unit/test_verify_chain_purge.py` (375 lines). Tests: normal chain verifies (3 entries, empty, single), purge gap + valid marker returns verified=True (single entry, multi-entry, entries appended after purge), marker first_surviving_prev_hash matches orphaned prev_hash, entries_checked includes survivor+marker, gap with no marker returns verified=False, first_break_at points to orphaned entry, mismatched marker context treated as tampering.
- **T-872** ✅ GREEN implementation — `backend/src/app/services/audit_service.py` `verify_chain()`. Pre-indexes retained `audit.purge` markers by `first_surviving_seq`. During chain walk, when linkage break detected (`entry.prev_hash != prev_hash`): if matching marker covers it (`first_surviving_prev_hash == entry.prev_hash`), gap is intentional — continue; otherwise report tampering. Row-hash integrity always checked using entry's own `prev_hash`. No entries rewritten or mutated.
- **Gate**: `uv run pytest tests/unit -q` → **1756 passed, 311 skipped** ✅; `ruff check src tests` → **All checks passed** ✅; `ruff format --check src tests` → **374 files already formatted** ✅.
- **Commits**: `e2db48d` (RED T-871), `e4babf2` (GREEN T-872).

### Next Dispatch

- Wave 18.3 remaining tasks: T-873 (purge+verify integration test), T-874–T-875 (retention endpoint), T-876 (scheduler docs), T-877–T-878 (permission/retention window tests), T-879 (backend gate).

### Review and Merge Result

- **PR**: #166
- **Merged**: 2026-07-01
- **Merge Commit**: `5f1a516d8d14eb0e153c8a2d78cf308b0b3c4131`
- **Tasks Completed**: T-871 through T-872
- **CI**: backend-test SUCCESS, frontend-test SUCCESS
- **Local Review Gates**: `pytest tests/unit/test_verify_chain_purge.py -x --tb=short` passed with live Postgres (**11 passed**); `ruff check src tests` passed; `ruff format --check src tests` passed; `git diff --check` clean.
- **Review Result**: no blocking findings.

---

## Wave 18.3f — Purge + Verify Integration Cycle

### Dispatch

- **Date**: 2026-07-01
- **Model**: Backend Implementer
- **T-IDs**: T-873 only
- **Branch**: `phase-6/wave-18.3f-purge-verify-cycle`
- **Status**: DISPATCHED
- **Dependency State**: Wave 18.3e merged; purge markers and verify-chain purge-gap handling are available on `main`.

### Dispatch Constraints

- Read `.agents/skills/BACKEND_IMPLEMENTER.md`, `.agents/skills/TDD.md`, `.agents/skills/KARPATHY.md`, and `~/.codex/RTK.md` before product edits.
- Use RTK for shell commands.
- Follow TDD commit discipline: RED integration-test commit, GREEN/fix commit only if needed, docs/gate commit as needed.
- Keep this slice to T-873 only: full purge+verify integration test in `backend/tests/integration/test_purge_verify_cycle.py`.
- Do not implement retention endpoint, scheduler docs, permission tests, retention-window tests, frontend UI, or final Wave 18.3 backend gate in this slice.
- Test must use live DB fixtures and cover: seed audit entries, call `purge_expired_entries()`, verify `audit.purge` marker exists with correct boundary metadata, call `verify_chain()` and assert verified/ok, append entry after purge, verify chain still valid end-to-end.

### Results

- **T-873** ✅ RED integration test — `backend/tests/integration/test_purge_verify_cycle.py` (349 lines). Tests: core purge marker + verify cycle, multi-entry purge boundary metadata, append-after-purge chain validity, no-purge/no-marker path, and entries_checked after purge.
- **Gate**: CI backend-test SUCCESS and frontend-test SUCCESS. Local reviewer run skipped because local Postgres was unavailable at review time; `ruff check src tests` passed, `ruff format --check src tests` passed, `git diff --check` clean.
- **Commits**: `b77e1ea` (RED T-873), `f1d4ee7` (docs T-873).

### Review and Merge Result

- **PR**: #167
- **Merged**: 2026-07-01
- **Merge Commit**: `70bb1c7faedd4efeecc0fae34e248f5016bf8218`
- **Tasks Completed**: T-873
- **CI**: backend-test SUCCESS, frontend-test SUCCESS
- **Review Result**: no blocking findings.

---

## Wave 18.3g — Audit Retention Status Endpoint

### Dispatch

- **Date**: 2026-07-01
- **Model**: Backend Implementer
- **T-IDs**: T-874 through T-875
- **Branch**: `phase-6/wave-18.3g-audit-retention-status`
- **Status**: DISPATCHED
- **Dependency State**: Wave 18.3f merged; purge markers, verify-chain purge-gap handling, and purge+verify integration coverage are available on `main`.

### Dispatch Constraints

- Read `.agents/skills/BACKEND_IMPLEMENTER.md`, `.agents/skills/TDD.md`, `.agents/skills/KARPATHY.md`, and `~/.codex/RTK.md` before product edits.
- Use RTK for shell commands.
- Follow TDD commit discipline: RED unit-test commit, GREEN implementation commit, docs/gate commit as needed.
- Keep this slice to T-874 and T-875 only.
- Implement `GET /admin/audit/retention` in `backend/src/app/api/v1/admin_audit.py`.
- Permission: `admin.audit.verify`.
- Response must include `retention_months` from `Settings.AUDIT_RETENTION_MONTHS`, latest purge marker timestamp as `last_purge_at` or null, and latest marker `purged_count` or null.
- Do not display or infer external scheduler timing.
- Do not implement scheduler docs, search/export permission sweep, retention-window tests, frontend UI, or final Wave 18.3 backend gate in this slice.

### Results

- **T-874** ✅ RED unit tests — `backend/tests/unit/test_audit_retention_status.py` (9 tests). Tests: no session 401, missing permission 403, no-purge null fields, configured retention_months, purge marker timestamp/count, response fields present, no scheduler fields, purged_count=0.
- **T-875** ✅ GREEN implementation — `backend/src/app/api/v1/admin_audit.py` `GET /admin/audit/retention` plus `_get_latest_purge_marker()`.
- **Gate**: `pytest tests/unit/test_audit_retention_status.py -x --tb=short` → 9 passed; `ruff check src tests` passed; `ruff format --check src tests` passed; `git diff --check` clean.
- **Commits**: `4c3e813` (RED T-874), `f63b448` (GREEN T-875), `db583c9` (docs T-874/T-875).
- **Quirk rolled into skill**: `require_permission` returns 401 for no session and 403 for missing permission.

### Review and Merge Result

- **PR**: #168
- **Merged**: 2026-07-01
- **Merge Commit**: `29aee8d39bf1e13dcadfd41edb069baee635d16e`
- **Tasks Completed**: T-874 through T-875
- **CI**: backend-test SUCCESS, frontend-test SUCCESS
- **Review Result**: no blocking findings.

---

## Wave 18.3h — Audit Purge Scheduler Docs

### Dispatch

- **Date**: 2026-07-01
- **Model**: Backend Implementer
- **T-IDs**: T-876 only
- **Branch**: `phase-6/wave-18.3h-audit-purge-scheduler-docs`
- **Status**: DISPATCHED
- **Dependency State**: Wave 18.3g merged; purge service, verify-chain handling, purge+verify integration coverage, and retention status endpoint are available on `main`.

### Dispatch Constraints

- Read `.agents/skills/BACKEND_IMPLEMENTER.md`, `.agents/skills/TDD.md`, `.agents/skills/KARPATHY.md`, and `~/.codex/RTK.md` before edits.
- Use RTK for shell commands.
- Keep this slice to T-876 only: create `docs/operations/audit-purge-scheduler.md`.
- Document external scheduler invocation of `AuditService.purge_expired_entries()`.
- Include example cron expression, Kubernetes CronJob spec, and systemd timer/service configuration.
- Document expected behavior: `audit.purge` marker insertion, expired entries deleted, `verify_chain()` accepts valid purge gaps, retention status endpoint reports last purge summary.
- Explicitly state the platform does not manage, execute, or display external scheduler timing.
- Do not implement permission sweep tests, retention-window tests, frontend UI, or final Wave 18.3 backend gate in this slice.

### Results

- **T-876** ✅ Operational docs — `docs/operations/audit-purge-scheduler.md` (236 lines). Covers external invocation, standalone runner example, cron, Kubernetes CronJob, systemd timer/service, expected purge marker/deletion/verify_chain behavior, retention status endpoint, and platform non-ownership of scheduler timing.
- **Gate**: CI backend-test SUCCESS and frontend-test SUCCESS; local `ruff check src tests` passed; `ruff format --check src tests` passed; `git diff --check` clean.
- **Commits**: `9f84481` (docs T-876), `7903b84` (tasks.md T-876).

### Review and Merge Result

- **PR**: #169
- **Merged**: 2026-07-01
- **Merge Commit**: `a0ef02c5359bc747973072fa0a39de3b4834db6c`
- **Tasks Completed**: T-876
- **CI**: backend-test SUCCESS, frontend-test SUCCESS
- **Review Result**: no blocking findings.

---

## Wave 18.3i — Backend Final Audit Hardening Gate

### Dispatch

- **Date**: 2026-07-01
- **Model**: Backend Implementer
- **T-IDs**: T-877 through T-879
- **Branch**: `phase-6/wave-18.3i-audit-backend-gate`
- **Status**: DISPATCHED
- **Dependency State**: Wave 18.3h merged; audit search/export, purge marker, verify-chain purge gap, retention status endpoint, and scheduler docs are all available on `main`.

### Dispatch Constraints

- Read `.agents/skills/BACKEND_IMPLEMENTER.md`, `.agents/skills/TDD.md`, `.agents/skills/KARPATHY.md`, and `~/.codex/RTK.md` before edits.
- Use RTK for shell commands.
- Follow TDD commit discipline: RED test commits, GREEN/fix commits only if needed, docs/gate commit as needed.
- Keep this slice to T-877, T-878, and T-879 only.
- T-877: permission gate tests for `GET /admin/audit/entries`, `POST /admin/audit/export`, and `GET /admin/audit/retention`; no session must be 401, missing permission must be 403, session with `admin.audit.verify` must be non-403.
- T-878: retention-window enforcement test for `AuditSearchService.search()`; entries older than retention cutoff excluded and query includes `timestamp >= cutoff`.
- T-879: run Wave 18.3 backend gate exactly as listed in `tasks.md`, using RTK prefixes.
- Do not implement frontend audit UI, frontend i18n, frontend gates, Wave 18.4 regression/smoke/audit work, or closeout docs in this slice.
