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

- **Date**: 2026-06-23
- **Branch Context**: `main` at `e5444f969fcbf077f092b3f31e473dce7e8dbe34`
- **Status**: Wave 18.2 COMPLETE. T-822 through T-857 verified complete.
- **Next Dispatch**: Wave 18.3a backend audit search foundation, T-858 through T-862.
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
