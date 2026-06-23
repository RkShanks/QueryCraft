# Tasks — Phase 6: Quotas, Hostile Input Detection, Audit Hardening

**Feature**: Phase 6 — Quotas, Hostile Input Detection, Audit Search/Export/Retention Hardening
**Task ID range**: T-779 – T-909
**Phase 5 closed at**: T-778
**Generated**: 2026-06-08
**Source documents**: spec.md, plan.md, data-model.md, contracts/api-contracts.md, research.md, quickstart.md

---

## Dispatch Legend

- **BE** — Backend Implementer
- **FE** — Frontend Implementer
- **OR** — Orchestrator only (audits, closeout docs, AGENTS.md)
- **[P]** — Parallelizable (no blocking dependencies within same wave)

---

## Wave 18.0 — Foundation

> Branch: `phase-6/wave-18.0-foundation`
> Dependencies: None (first wave)
> Dispatch: BE for T-779–T-789, T-792; OR for T-790, T-791

### Goals
Migration, models, enum extensions, permission extensions, Pydantic schemas, shared test fixtures, initial orchestration log and audit dir.

### FR/SC Coverage
FR-177 (permissions), FR-147 partial (model), FR-155 partial (enum taxonomy)
SC-074 partial, SC-075 partial (foundation gates)

---

- [X] T-779 [P] Write RED contract test asserting `GET /admin/quotas` returns 403 for unauthenticated request, `GET /admin/detection/config` returns 403 for unauthenticated request, and `GET /admin/audit/entries` returns 403 for unauthenticated request in `backend/tests/contract/test_phase6_contracts.py` **Dispatch: BE**

- [X] T-780 Create Alembic migration `backend/alembic/versions/008_phase6_quotas_detection_audit_hardening.py` with `upgrade()` creating `role_quotas` table (id UUID PK, role_id UUID FK→roles.id CASCADE UNIQUE, daily_query_limit INTEGER NULLABLE, daily_execution_limit INTEGER NULLABLE, daily_export_limit INTEGER NULLABLE, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ) and `detection_threshold_config` table (id UUID PK, block_confidence FLOAT NOT NULL DEFAULT 0.8, flag_confidence FLOAT NOT NULL DEFAULT 0.5, updated_at TIMESTAMPTZ, updated_by UUID FK→users.id SET NULL); `downgrade()` drops both tables. Depends on T-779. **Dispatch: BE**

- [X] T-781 [P] Create SQLAlchemy model `backend/src/app/db/models/role_quota.py` defining `RoleQuota` ORM class mapped to `role_quotas` table with all columns and the FK relationship to `Role`. Add import to `backend/src/app/db/models/__init__.py`. Depends on T-780. **Dispatch: BE**

- [X] T-782 [P] Create SQLAlchemy model `backend/src/app/db/models/detection_config.py` defining `DetectionThresholdConfig` ORM class mapped to `detection_threshold_config` table with all columns. Add import to `backend/src/app/db/models/__init__.py`. Depends on T-780. **Dispatch: BE**

- [X] T-783 Extend `backend/src/app/db/models/enums.py`: add to `AuditActionType` enum: `QUOTA_CONFIG_CHANGE = "quota.config.change"`, `QUOTA_EXCEEDED = "quota.exceeded"`, `QUOTA_WARNING = "quota.warning"`, `HOSTILE_INPUT_BLOCKED = "hostile.input.blocked"`, `HOSTILE_INPUT_FLAGGED = "hostile.input.flagged"`, `DETECTION_CONFIG_CHANGE = "detection.config.change"`, `AUDIT_SEARCH = "audit.search"`, `AUDIT_EXPORT = "audit.export"`, `AUDIT_PURGE = "audit.purge"`; add to `Permission` enum: `ADMIN_QUOTAS_MANAGE = "admin.quotas.manage"`, `ADMIN_SECURITY_MANAGE = "admin.security.manage"`. Depends on T-780. **Dispatch: BE**

- [X] T-784 Update built-in admin role seeding (locate in `backend/src/app/core/security.py` or relevant bootstrap file) to include `admin.quotas.manage` and `admin.security.manage` in the built-in admin permission set. Depends on T-783. **Dispatch: BE**

- [X] T-785 [P] Create Pydantic schemas `backend/src/app/schemas/quota.py`: `RoleQuotaConfig` (role_id, role_name, daily_query_limit nullable int, daily_execution_limit nullable int, daily_export_limit nullable int, created_at, updated_at), `RoleQuotaUpsert` (request body, all limit fields nullable), `QuotaDimensionStatus` (limit nullable int, used int, remaining nullable int), `RoleQuotaStatus` (role_id, role_name, dimensions dict, reset_at), `QuotaStatusResponse` (status list), `QuotaListResponse` (quotas list). Depends on T-783. **Dispatch: BE**

- [X] T-786 [P] Create Pydantic schemas `backend/src/app/schemas/detection.py`: `DetectionThresholdRead` (block_confidence float, flag_confidence float, updated_at), `DetectionThresholdUpdate` (block_confidence float, flag_confidence float; validate block > flag, both in [0.0,1.0]). Depends on T-783. **Dispatch: BE**

- [X] T-787 [P] Create Pydantic schemas `backend/src/app/schemas/audit_search.py`: `AuditSearchParams` (start_date optional, end_date optional, action_type optional str, actor_identity optional str, outcome optional str, resource_type optional str, page int default 1, page_size int default 50 max 100), `AuditEntryRead` (sequence_number, timestamp, actor_identity, action_type, resource_type, resource_id, outcome, context dict), `AuditSearchResponse` (entries list, pagination with page/page_size/total_entries/total_pages), `AuditExportRequest` (format literal["csv","json"], plus optional filter fields matching search params). Depends on T-783. **Dispatch: BE**

- [X] T-788 [P] Create shared test fixtures in `backend/tests/conftest.py` (or `backend/tests/integration/conftest.py`): factory functions `make_role_quota(role_id, daily_query_limit, daily_execution_limit, daily_export_limit)`, `make_detection_config(block=0.8, flag=0.5)`, `make_audit_entry(action_type, actor_identity, outcome, context)`. Depends on T-781, T-782, T-783. **Dispatch: BE**

- [X] T-789 [P] Write RED unit tests for enum completeness in `backend/tests/unit/test_phase6_enums.py`: assert all 9 new `AuditActionType` values exist with correct string values, assert `ADMIN_QUOTAS_MANAGE` and `ADMIN_SECURITY_MANAGE` exist in `Permission` enum. Depends on T-783. **Dispatch: BE**

- [X] T-790 [P] Create `audit/wave-18/` directory and stub files `audit/wave-18/gemini-findings.md` and `audit/wave-18/opus-findings.md` with headers (Phase 6 audit scope, FR-147–FR-180, SC-063–SC-077, status: PENDING). Depends on nothing. **Dispatch: OR**

- [X] T-791 [P] Initialize orchestration log at `specs/006-quotas-hostile-input-audit-hardening/plans/orchestration-log.md` with Wave 18.0 dispatch entry (date, wave, branch, dispatcher, status: IN PROGRESS). Depends on nothing. **Dispatch: OR**

- [X] T-792 Run Wave 18.0 backend gates: `cd backend && uv run pytest tests/unit/test_phase6_enums.py tests/contract/test_phase6_contracts.py -x --tb=short && uv run ruff check src/ && uv run ruff format --check src/ && git diff --check`. All must pass before Wave 18.0 PR. Depends on T-779–T-789. **Dispatch: BE**


---

## Wave 18.1 — Quotas

> Branch: `phase-6/wave-18.1-quotas`
> Dependencies: Wave 18.0 merged
> Dispatch: BE for T-793–T-809; FE for T-810–T-821

### Goals
QuotaService (Redis atomic counter), QuotaRepository CRUD, admin quota router, enforcement integration in query/execute endpoints, quota audit events, admin quota UI, i18n/RTL.

### FR/SC Coverage
FR-147, FR-148, FR-149, FR-150, FR-151, FR-152, FR-153, FR-154, FR-155, FR-178 (quota i18n), FR-179 (quota RTL), FR-180 (quota errors)
SC-063, SC-064, SC-071, SC-072, SC-073, SC-074, SC-075

---

- [X] T-793 [P] Write RED unit tests for `QuotaService` in `backend/tests/unit/test_quota_service.py`: test `check_and_increment("queries")` increments Redis counter and returns (used, limit, reset_at); test exhausted quota returns QuotaExceededError with dimension and reset_at; test `QuotaUnavailableError` raised when Redis unreachable (mock redis to raise ConnectionError); test daily TTL key format `quota:{user_id}:{dim}:{YYYY-MM-DD}` with TTL ≤86400s; test uncapped role (NULL limit) always allows. Depends on T-788. **Dispatch: BE**

- [X] T-794 Create `backend/src/app/services/quota_service.py`: `QuotaService` class with `async check_and_increment(user_id, role_id, dimension)` using Redis Lua script for atomic INCR-and-check (key `quota:{user_id}:{dimension}:{YYYY-MM-DD}`, TTL = seconds until next midnight UTC); raises `QuotaExceededError(dimension, reset_at)` if limit reached; raises `QuotaUnavailableError` if Redis unreachable; fetches role config from `QuotaRepository` with 60s Redis cache (`quota_config:{role_id}`). NULL limit = uncapped (always returns allowed). Depends on T-793, T-783, T-781. **Dispatch: BE**

- [X] T-795 [P] Write RED unit tests for `QuotaRepository` in `backend/tests/unit/test_quota_repository.py`: test upsert creates new row when role has no quota; test upsert updates existing row; test get returns None for unconfigured role; test delete removes row; test list returns all configured roles with quota data. Depends on T-788. **Dispatch: BE**

- [X] T-796 Create `backend/src/app/repositories/quota_repository.py`: `QuotaRepository` with async methods `get(role_id) → RoleQuota | None`, `upsert(role_id, data: RoleQuotaUpsert) → RoleQuota`, `delete(role_id) → bool`, `list_all() → list[RoleQuota]`. Uses SQLAlchemy 2 async session. Depends on T-795, T-781. **Dispatch: BE**

- [X] T-797 [P] Write RED integration tests for quota admin API in `backend/tests/integration/test_quota_admin.py`: test `GET /admin/quotas` returns 200 with quotas list for admin with `admin.quotas.manage`; test 403 for user without permission; test `PUT /admin/quotas/{role_id}` creates/updates config and returns updated object; test `DELETE /admin/quotas/{role_id}` returns 204; test `GET /admin/quotas/{role_id}` returns 404 for unconfigured role; test `GET /admin/quotas/status` returns consumption status per role; test `PUT` emits `quota.config.change` audit event. Depends on T-788, T-783. **Dispatch: BE**

- [X] T-798 Create `backend/src/app/api/v1/admin_quotas.py`: router at `/admin/quotas` with: `GET /` → list all quota configs (`admin.quotas.manage`); `GET /status` → consumption status across roles; `GET /{role_id}` → single config (404 if none); `PUT /{role_id}` → upsert config, emit `QUOTA_CONFIG_CHANGE` audit event with sanitized context (role_id, dims changed — no counter values); `DELETE /{role_id}` → remove config, emit `QUOTA_CONFIG_CHANGE` with `{"action":"removed"}`. All endpoints use `require_permission(Permission.ADMIN_QUOTAS_MANAGE)`. Register router in `backend/src/app/main.py`. Depends on T-797, T-796, T-794. **Dispatch: BE**

- [X] T-799 [P] Write RED unit tests for quota enforcement in `backend/tests/unit/test_quota_enforcement.py`: test POST /query/submit calls `QuotaService.check_and_increment("queries")` before LLM invocation on a normal allowed query path; test request rejected (429 + localized message_key) when quota exceeded; test LLM never called when quota exceeded; test fail-closed: QuotaUnavailableError → 503 localized "service_unavailable" message. **Note**: detection-before-quota ordering and no-increment-on-hostile-block assertions belong in Wave 18.2 (T-845/T-846). Depends on T-793. **Dispatch: BE**

- [X] T-800 Modify `backend/src/app/api/v1/query.py`: in `POST /query/submit` handler add `QuotaService.check_and_increment(user_id, role_id, "queries")` before LLM invocation (no detection stub — Wave 18.2 inserts real detection ahead of this check). On `QuotaExceededError` return 429 JSON `{"message_key":"error.quota_exceeded","reset_at":"<ISO>"}`. On `QuotaUnavailableError` return 503 JSON `{"message_key":"error.service_unavailable"}`. No stack traces, no counter values, no policy IDs in response. Depends on T-799, T-794. **Dispatch: BE**

- [X] T-801 [P] Write RED integration tests for execution quota in `backend/tests/integration/test_execution_quota.py`: test POST /query/{id}/execute blocked (429) when daily_execution_limit exhausted; test success when under limit; test fail-closed (503) when Redis unavailable. Depends on T-793. **Dispatch: BE**

- [X] T-802 Modify `backend/src/app/api/v1/query.py`: in `POST /query/{question_id}/execute` handler add `QuotaService.check_and_increment(user_id, role_id, "executions")` before SQL execution. Same error response pattern as T-800. Depends on T-801, T-794. **Dispatch: BE**

- [X] T-803 [P] Write RED unit tests for quota audit events in `backend/tests/unit/test_quota_audit.py`: test `QUOTA_EXCEEDED` audit event emitted with action_type, actor_identity, outcome="blocked", context has dimension and reset_at but NO counter values or policy IDs; test `QUOTA_CONFIG_CHANGE` event has sanitized context. Depends on T-783, T-788. **Dispatch: BE**

- [X] T-804 Implement quota audit event emission: add `AuditService.log(QUOTA_EXCEEDED, actor, outcome="blocked", context={"dimension":dim,"reset_at":str(reset_at)})` call in `backend/src/app/api/v1/query.py` quota rejection path. Ensure context contains NO counter values, NO policy IDs, NO role internal identifiers beyond role_id. Depends on T-803, T-800. **Dispatch: BE**

- [X] T-805 [P] Write RED unit tests for quota error message sanitization in `backend/tests/unit/test_quota_error_sanitization.py`: assert quota exceeded response body contains only `message_key` and `reset_at`; assert no fields: `counter`, `limit`, `policy_id`, `role_id`, `provider`, `sql`, `stack`; assert message_key value is constant string `"error.quota_exceeded"`. Depends on T-800. **Dispatch: BE**

- [X] T-806 Write RED security test for fail-closed behavior in `backend/tests/unit/test_quota_fail_closed.py`: mock Redis to be completely unreachable; assert quota-gated endpoints available in Wave 18.1 (submit, execute) return 503 with `message_key="error.service_unavailable"` and no request proceeds to LLM or DB. Export fail-closed coverage is added in Wave 18.3 T-867. Depends on T-800, T-802. **Dispatch: BE**

- [X] T-807 Verify fail-closed behavior passes green: run `uv run pytest tests/unit/test_quota_fail_closed.py tests/unit/test_quota_enforcement.py -x --tb=short`. Fix any implementation gaps. Depends on T-806, T-800, T-802. **Dispatch: BE**

- [X] T-808 [P] Write RED unit tests for quota daily reset in `backend/tests/unit/test_quota_reset.py`: test counter key includes date suffix; test TTL is ≤86400 and >0; test new day generates new key (old key irrelevant). Depends on T-794. **Dispatch: BE**

- [X] T-809 Backend gates Wave 18.1: `cd backend && uv run pytest tests/unit/test_quota_service.py tests/unit/test_quota_repository.py tests/unit/test_quota_enforcement.py tests/unit/test_quota_audit.py tests/unit/test_quota_error_sanitization.py tests/unit/test_quota_fail_closed.py tests/unit/test_quota_reset.py tests/integration/test_quota_admin.py tests/integration/test_execution_quota.py -x --tb=short && uv run ruff check src/ && uv run ruff format --check src/ && git diff --check`. Depends on T-807, T-804, T-805, T-808, T-798. **Dispatch: BE**

- [X] T-810 [P] Write RED component tests for AdminQuotasPage in `frontend/src/pages/AdminQuotasPage.test.tsx`: test page renders role list with limits; test form allows setting daily_query_limit; test submit calls PUT /admin/quotas/{role_id}; test 403 renders access-denied message; test quota status panel shows used/remaining per dimension; test Arabic locale renders RTL layout. Use MSW handlers mocking `/admin/quotas` API contract. Depends on api-contracts.md quota contract (no backend fixture dependency). **Dispatch: FE**

- [X] T-811 Create `frontend/src/pages/AdminQuotasPage.tsx`: admin page at `/admin/quotas` with quota configuration table (role name, query limit, execution limit, export limit columns), inline edit form (nullable int inputs per dimension, null = uncapped label), save/delete controls. Add permission guard (`admin.quotas.manage`). Follow AdminRolesPage layout pattern. Depends on T-810, T-798. **Dispatch: FE**

- [X] T-812 [P] Create `frontend/src/api/quotas.ts`: typed API client functions `listQuotas()`, `getQuotaStatus()`, `upsertQuota(roleId, data)`, `deleteQuota(roleId)` using fetch/TanStack Query patterns consistent with existing API clients. Depends on T-798. **Dispatch: FE**

- [X] T-813 [P] Create `frontend/src/pages/AdminQuotaStatusPage.tsx` or integrate quota status panel into `AdminQuotasPage.tsx`: display per-role consumption table (role, dimension, used/limit/remaining, reset time). Depends on T-812, T-811. **Dispatch: FE**

- [X] T-814 [P] Write RED component tests for quota exceeded error display in `frontend/src/components/query/QuotaExceededBanner.test.tsx`: test banner renders with localized message; test reset_at timestamp shown; test no internal counter values shown; test Arabic locale shows Arabic message. No backend fixture dependency. **Dispatch: FE**

- [X] T-815 Create `frontend/src/components/query/QuotaExceededBanner.tsx`: displays localized quota exceeded error from API response. Integrate into `frontend/src/pages/AskQuestionPage.tsx` (or WorkspacePage) query submission error handling path. Depends on T-814. **Dispatch: FE**

- [X] T-816 Add i18n keys for Wave 18.1 to `frontend/src/locales/en.json`: `quota.page_title`, `quota.role_column`, `quota.query_limit`, `quota.execution_limit`, `quota.export_limit`, `quota.uncapped`, `quota.status_title`, `quota.used`, `quota.remaining`, `quota.reset_at`, `error.quota_exceeded`, `error.service_unavailable`. Depends on T-811. **Dispatch: FE**

- [X] T-817 Add matching Arabic translations (100% key parity) to `frontend/src/locales/ar.json` for all keys added in T-816. Zero English fallback. Depends on T-816. **Dispatch: FE**

- [X] T-818 [P] Add route for `/admin/quotas` to `frontend/src/App.tsx` (or router config), wrapped in `PermissionGuard` requiring `admin.quotas.manage`. Add navigation link in admin sidebar/nav. Depends on T-811. **Dispatch: FE**

- [X] T-819 [P] Write RTL visual check test in `frontend/src/pages/AdminQuotasPage.test.tsx` (or separate file): render page with `dir="rtl"` and Arabic locale, assert no `text-align: left`, no `margin-left`/`padding-left`/`margin-right`/`padding-right` inline styles, assert logical properties used. Depends on T-811, T-817. **Dispatch: FE**

- [X] T-820 [P] Run i18n key parity test: `cd frontend && npm test -- --run locales/localeCoverage` — all Phase 6 Wave 18.1 keys present in both en.json and ar.json. Fix any gaps. Depends on T-816, T-817. **Dispatch: FE**

- [X] T-821 Frontend gates Wave 18.1: `cd frontend && npm test -- --run && npm run lint && npm run typecheck && npm run build && npm run lint:css && git diff --check`. All must pass. Depends on T-819, T-820, T-815, T-818. **Dispatch: FE**


---

## Wave 18.2 — Hostile Input Detection

> Branch: `phase-6/wave-18.2-hostile-detection`
> Dependencies: Wave 18.0 merged; Wave 18.1 quota service must exist (T-794) for post-detection quota check wiring
> Parallelization: Detection service (T-822–T-840) parallelizable with quota UI (T-810–T-820) from Wave 18.1 if separate sessions
> Dispatch: BE for T-822–T-847; FE for T-848–T-855; BE for T-856 gate; FE for T-857 gate

### Goals
HostileInputDetector service with DetectionRule protocol + RuleRegistry, 5 built-in rule categories (English + Arabic), threshold config CRUD, pre-generation integration in /query/submit, safe audit events (redacted, no raw payload), admin threshold config UI, i18n/RTL.

### FR/SC Coverage
FR-156, FR-157, FR-158, FR-159, FR-160, FR-161, FR-162, FR-163, FR-164, FR-165, FR-178, FR-179, FR-180
SC-064, SC-065, SC-066, SC-067, SC-072, SC-073, SC-074, SC-075

---

- [X] T-822 [P] Write RED unit tests for `DetectionRule` protocol and `RuleRegistry` in `backend/tests/unit/test_detection_registry.py`: test rule registration by name; test duplicate name raises error; test list_rules returns all registered rules; test `DetectionRule` protocol has required methods `detect(text) -> DetectionResult`. Depends on T-788. **Dispatch: BE**

- [X] T-823 Create detection package `backend/src/app/services/detection/__init__.py` and `backend/src/app/services/detection/protocol.py`: define `DetectionResult` dataclass (category: str, confidence: float, explanation: str), `DetectionRule` Protocol with `name: str` property and `detect(text: str) -> DetectionResult` method, `RuleRegistry` class with `register(rule)`, `list_rules()`, singleton `REGISTRY` instance. Depends on T-822. **Dispatch: BE**

- [X] T-824 [P] Write RED unit tests for `HostileInputDetector` in `backend/tests/unit/test_hostile_detector.py`: test detector runs ALL rules (not short-circuit); test block if any result confidence >= block_threshold; test flag if any result confidence >= flag_threshold (but < block); test allow if all below flag_threshold; test detector returns `DetectionOutcome(outcome, results_list, max_confidence)`; test with mocked rules returning controlled confidence values. Depends on T-822. **Dispatch: BE**

- [X] T-825 Create `backend/src/app/services/detection/detector.py`: `HostileInputDetector` service with `async detect(text: str, thresholds: DetectionThresholdConfig) -> DetectionOutcome`; runs all registered rules via `REGISTRY.list_rules()`; aggregates `DetectionResult` list; `outcome` = "blocked" if max_confidence >= block_confidence, "flagged" if >= flag_confidence, "allowed" otherwise. Depends on T-824, T-823. **Dispatch: BE**

- [X] T-826 [P] Write RED unit tests for PromptInjectionRule in `backend/tests/unit/test_rule_prompt_injection.py`: test English patterns ("ignore previous instructions", "you are now", "system prompt", "pretend you are", "disregard all prior"); test Arabic patterns ("تجاهل التعليمات", "تصرف كأنك", "أنت الآن"); test benign business query scores below 0.5; test confidence ≥ 0.8 for clear injection attempts. Depends on T-823. **Dispatch: BE**

- [X] T-827 Create `backend/src/app/services/detection/rules/prompt_injection.py`: `PromptInjectionRule` implementing `DetectionRule` protocol; pattern list covering English and Arabic prompt injection signatures (as per research.md R-03 and ADR-23); returns `DetectionResult(category="prompt_injection", confidence, explanation)`. Register in `backend/src/app/services/detection/__init__.py`. Depends on T-826, T-823. **Dispatch: BE**

- [X] T-828 [P] Write RED unit tests for SqlInjectionRule in `backend/tests/unit/test_rule_sql_injection.py`: test English: "UNION SELECT", "; DELETE", "1=1", "OR 1=1", backtick abuse, "DROP TABLE" in NL context; test Arabic: "احذف الجدول", "اختر كل"; test benign SQL-adjacent business query (e.g., "show me union membership counts") scores below block threshold. Depends on T-823. **Dispatch: BE**

- [X] T-829 Create `backend/src/app/services/detection/rules/sql_injection.py`: `SqlInjectionRule` with English and Arabic SQL injection fragment patterns. Register in detection package. Depends on T-828, T-823. **Dispatch: BE**

- [X] T-830 [P] Write RED unit tests for RbacBypassRule in `backend/tests/unit/test_rule_rbac_bypass.py`: test English: "show me all users", "bypass filter", "ignore row restrictions", "show all data", "override policy"; test Arabic: "تجاوز القيود", "أظهر كل البيانات"; test benign: "show me sales data for this quarter" passes. Depends on T-823. **Dispatch: BE**

- [X] T-831 Create `backend/src/app/services/detection/rules/rbac_bypass.py`: `RbacBypassRule` with English and Arabic RBAC/policy bypass patterns. Register in detection package. Depends on T-830, T-823. **Dispatch: BE**

- [X] T-832 [P] Write RED unit tests for SchemaExposureRule in `backend/tests/unit/test_rule_schema_exposure.py`: test English: "show all tables", "list columns", "database password", "connection string", "show config", "environment variables"; test Arabic: "اعرض الجداول", "كلمة مرور قاعدة البيانات"; test benign: "show me the sales table results" passes. Depends on T-823. **Dispatch: BE**

- [X] T-833 Create `backend/src/app/services/detection/rules/schema_exposure.py`: `SchemaExposureRule` with English and Arabic schema/secret exposure patterns. Register in detection package. Depends on T-832, T-823. **Dispatch: BE**

- [X] T-834 [P] Write RED unit tests for DestructiveSqlRule in `backend/tests/unit/test_rule_destructive_sql.py`: test English: "delete all records", "drop the table", "truncate orders", "alter table users", "update all rows"; test Arabic: "احذف جميع السجلات", "أسقط الجدول"; test benign: "delete my saved search" is below block threshold. Depends on T-823. **Dispatch: BE**

- [X] T-835 Create `backend/src/app/services/detection/rules/destructive_sql.py`: `DestructiveSqlRule` with English and Arabic destructive SQL generation patterns. Register in detection package. Depends on T-834, T-823. **Dispatch: BE**

- [X] T-836 [P] Write RED integration test for 95% pass-through in `backend/tests/integration/test_detection_passthrough.py`: run a curated list of ≥20 normal business queries (English and Arabic) through `HostileInputDetector`; assert at least 95% return outcome="allowed"; assert 0 normal queries trigger outcome="blocked". Depends on T-825, T-827, T-829, T-831, T-833, T-835. **Dispatch: BE**

- [X] T-837 [P] Write RED integration tests for full hostile input coverage in `backend/tests/integration/test_detection_coverage.py`: run curated hostile test suite (min 5 per category, EN+AR) through detector; assert all return outcome="blocked" or "flagged" with confidence >= flag_threshold; assert 100% block rate for clear hostile patterns (confidence ≥ 0.8). Depends on T-825–T-835. **Dispatch: BE**

- [X] T-838 [P] Write RED unit tests for DetectionThresholdConfig repository in `backend/tests/unit/test_detection_config_repo.py`: test get returns singleton row (creates with defaults if missing); test update changes block/flag confidence; test update validates block > flag (raises validation error otherwise). Depends on T-782, T-788. **Dispatch: BE**

- [X] T-839 Create `backend/src/app/repositories/detection_config_repository.py`: `DetectionConfigRepository` with `async get() -> DetectionThresholdConfig` (creates singleton with defaults 0.8/0.5 if missing), `async update(data: DetectionThresholdUpdate) -> DetectionThresholdConfig` (validates block > flag). Depends on T-838, T-782. **Dispatch: BE**

- [X] T-840 [P] Write RED integration tests for detection admin API in `backend/tests/integration/test_detection_admin.py`: test `GET /admin/detection/config` returns 200 with thresholds for admin with `admin.security.manage`; test 403 for user without permission; test `PUT /admin/detection/config` updates thresholds and returns updated object; test PUT with block <= flag returns 422; test PUT emits `detection.config.change` audit event. Depends on T-786, T-788. **Dispatch: BE**

- [X] T-841 Create `backend/src/app/api/v1/admin_detection.py`: router at `/admin/detection` with: `GET /config` → get thresholds (permission: `admin.security.manage`); `PUT /config` → update thresholds, emit `DETECTION_CONFIG_CHANGE` audit event. Register in `backend/src/app/main.py`. Depends on T-840, T-839. **Dispatch: BE**

- [X] T-842 [P] Write RED unit tests for redacted audit representation in `backend/tests/unit/test_hostile_audit_redaction.py`: test `build_redacted_summary(text)` returns at most 100 chars; test hostile patterns replaced with `[REDACTED_PATTERN]`; test `compute_input_hash(text)` returns SHA-256 hex string; test raw hostile text never appears in audit context; test audit context contains: `category`, `confidence`, `rules_triggered` (names only, no patterns), `outcome`, `input_summary` (redacted), `input_hash`. Depends on T-783. **Dispatch: BE**

- [X] T-843 Create `backend/src/app/services/detection/audit_representation.py`: `build_redacted_summary(text: str) -> str` (first 100 chars, patterns replaced with `[REDACTED_PATTERN]`); `compute_input_hash(text: str) -> str` (SHA-256 hex); `build_detection_audit_context(outcome, results, text) -> dict` producing safe context dict with all required fields and NO raw hostile text. Depends on T-842. **Dispatch: BE**

- [X] T-844 [P] Write RED unit tests for detection error sanitization in `backend/tests/unit/test_detection_error_sanitization.py`: assert blocked response body contains only `message_key="error.hostile_input_blocked"`; assert no fields: `rule_name`, `confidence`, `pattern`, `category`, `input`, `payload`, `stack`; assert response does NOT echo any part of the input. Depends on T-800. **Dispatch: BE**

- [X] T-845 Integrate `HostileInputDetector` into `backend/src/app/api/v1/query.py` `POST /query/submit`: (1) run detection FIRST (before quota check — stubs removed from T-800); (2) if blocked: emit `HOSTILE_INPUT_BLOCKED` audit event via `build_detection_audit_context`, return 400 JSON `{"message_key":"error.hostile_input_blocked"}` with NO detection details, NO input echo; (3) if flagged: emit `HOSTILE_INPUT_FLAGGED` audit event, continue to quota check; (4) if allowed: continue to quota check then LLM. Blocked requests do NOT increment quota counter. Depends on T-844, T-843, T-825, T-800. **Dispatch: BE**

- [X] T-846 [P] Write RED unit tests asserting raw hostile text never stored: in `backend/tests/unit/test_no_raw_hostile_payload.py` mock `AuditService.log`, call detect+submit with known hostile input, inspect all `log()` call arguments, assert no call contains the raw hostile string in `context` dict at any key. Depends on T-845. **Dispatch: BE**

- [X] T-847 Verify green: run full detection test suite `uv run pytest tests/unit/test_detection_registry.py tests/unit/test_hostile_detector.py tests/unit/test_rule_prompt_injection.py tests/unit/test_rule_sql_injection.py tests/unit/test_rule_rbac_bypass.py tests/unit/test_rule_schema_exposure.py tests/unit/test_rule_destructive_sql.py tests/unit/test_hostile_audit_redaction.py tests/unit/test_detection_error_sanitization.py tests/unit/test_no_raw_hostile_payload.py tests/unit/test_detection_config_repo.py tests/integration/test_detection_passthrough.py tests/integration/test_detection_coverage.py tests/integration/test_detection_admin.py -x --tb=short`. Depends on T-836, T-837, T-846, T-841. **Dispatch: BE**

- [X] T-848 [P] Write RED component tests for detection threshold config UI in `frontend/src/pages/AdminDetectionPage.test.tsx`: test sliders/inputs render with current thresholds; test submit calls PUT /admin/detection/config; test validation error when block <= flag; test 403 renders access-denied; test Arabic locale RTL layout. Use MSW handlers mocking `/admin/detection/config` API contract. No backend fixture dependency. **Dispatch: FE**

- [X] T-849 Create `frontend/src/pages/AdminDetectionPage.tsx`: admin page or section for detection threshold configuration (block_confidence and flag_confidence numeric inputs, validation block > flag, save button). Permission guard: `admin.security.manage`. Integrate into admin nav. Depends on T-848, T-841. **Dispatch: FE**

- [X] T-850 [P] Create `frontend/src/api/detection.ts`: typed API client for `getDetectionConfig()` and `updateDetectionConfig(data)`. Depends on T-841. **Dispatch: FE**

- [X] T-851 [P] Write RED component tests for hostile input blocked error display in `frontend/src/components/query/HostileInputBlockedBanner.test.tsx`: test banner renders localized message; test no rule names, confidence, or pattern shown; test Arabic locale shows Arabic message only. No backend fixture dependency. **Dispatch: FE**

- [X] T-852 Create `frontend/src/components/query/HostileInputBlockedBanner.tsx`: displays localized hostile input blocked error from API response. Integrate into query submission error handling path in AskQuestionPage/WorkspacePage. Depends on T-851. **Dispatch: FE**

- [X] T-853 Add i18n keys for Wave 18.2 to `frontend/src/locales/en.json`: `detection.page_title`, `detection.block_threshold`, `detection.flag_threshold`, `detection.save`, `detection.validation_error`, `error.hostile_input_blocked`. Depends on T-849, T-852. **Dispatch: FE**

- [X] T-854 Add matching Arabic translations (100% key parity) to `frontend/src/locales/ar.json` for all keys added in T-853. Depends on T-853. **Dispatch: FE**

- [X] T-855 [P] Add route `/admin/detection` to `frontend/src/App.tsx` wrapped in PermissionGuard (`admin.security.manage`). Add nav link. Depends on T-849. **Dispatch: FE**

- [X] T-856 Backend gates Wave 18.2: `cd backend && uv run pytest tests/unit/test_detection_registry.py tests/unit/test_hostile_detector.py tests/unit/test_rule_prompt_injection.py tests/unit/test_rule_sql_injection.py tests/unit/test_rule_rbac_bypass.py tests/unit/test_rule_schema_exposure.py tests/unit/test_rule_destructive_sql.py tests/unit/test_hostile_audit_redaction.py tests/unit/test_detection_error_sanitization.py tests/unit/test_no_raw_hostile_payload.py tests/unit/test_detection_config_repo.py tests/integration/test_detection_passthrough.py tests/integration/test_detection_coverage.py tests/integration/test_detection_admin.py -x --tb=short && uv run ruff check src/ && uv run ruff format --check src/ && git diff --check`. Depends on T-847. **Dispatch: BE**

- [X] T-857 Frontend gates Wave 18.2: `cd frontend && npm test -- --run && npm run lint && npm run typecheck && npm run build && npm run lint:css && git diff --check`. Depends on T-854, T-855, T-852. **Dispatch: FE**


---

## Wave 18.3 — Audit Search/Export/Retention

> Branch: `phase-6/wave-18.3-audit-hardening`
> Dependencies: Wave 18.0 (schemas, migration), Wave 18.1 (export quota enforcement), Wave 18.2 (hostile input events available to search)
> Dispatch: BE for T-858–T-879; FE for T-880–T-891

### Goals
AuditSearchService (filtered+paginated), AuditExportService (CSV/JSON, 50k limit, formula injection prevention, integrity metadata), purge-gap marker + verify_chain update, external purge docs, retention status endpoint, export quota enforcement, audit search/export self-logging, admin audit UI enhancement, i18n/RTL.

### FR/SC Coverage
FR-166, FR-167, FR-168, FR-169, FR-170, FR-171, FR-172, FR-173, FR-174, FR-175, FR-176, FR-178, FR-179
SC-068, SC-069, SC-070, SC-072, SC-073, SC-074, SC-075, SC-077

---

- [X] T-858 [P] Create new Alembic migration `backend/alembic/versions/009_phase6_audit_search_indexes.py` adding B-tree indexes on `audit_log_entries.action_type`, `audit_log_entries.actor_identity`, `audit_log_entries.outcome`, `audit_log_entries.timestamp`; GIN index on `audit_log_entries.context`. Use `IF NOT EXISTS` for idempotency. `downgrade()` drops all added indexes. Migration 008 (Wave 18.0) must already be merged. Depends on T-780. **Dispatch: BE**

- [X] T-859 [P] Write RED unit tests for `AuditSearchService` in `backend/tests/unit/test_audit_search_service.py`: test filter by action_type returns only matching entries; test filter by actor_identity; test filter by outcome; test filter by date range; test pagination (page=2 returns correct offset); test retention enforcement — entries outside configured window excluded (WHERE timestamp >= cutoff); test combined filters work together; test default sort is timestamp DESC. Depends on T-787, T-788. **Dispatch: BE**

- [X] T-860 Create `backend/src/app/services/audit_search_service.py`: `AuditSearchService` with `async search(params: AuditSearchParams, retention_months: int) -> AuditSearchResponse`; builds SQLAlchemy query with dynamic WHERE clauses for all filter params; enforces `timestamp >= now() - retention_months months`; offset pagination (page/page_size); returns `AuditSearchResponse` with entries list and pagination metadata. Depends on T-859, T-787. **Dispatch: BE**

- [X] T-861 [P] Write RED integration tests for audit search API in `backend/tests/integration/test_audit_search.py`: test `GET /admin/audit/entries` returns 200 with paginated entries for admin with `admin.audit.verify`; test 403 for user without permission; test date range filter works; test action_type filter; test actor_identity filter; test outcome filter; test entries outside retention window absent; test search emits `audit.search` audit event with filter summary (no result values); test total_entries and total_pages correct. Depends on T-860, T-787. **Dispatch: BE**

- [X] T-862 Extend `backend/src/app/api/v1/admin_audit.py` with `GET /entries` endpoint: permission `admin.audit.verify` (existing Phase 5 permission — no new permission); parse `AuditSearchParams` from query string; call `AuditSearchService.search()`; emit `AUDIT_SEARCH` audit event with sanitized filter summary (no result content); return `AuditSearchResponse`. Depends on T-861, T-860. **Dispatch: BE**

- [ ] T-863 [P] Write RED unit tests for `AuditExportService` CSV in `backend/tests/unit/test_audit_export_csv.py`: test CSV output contains correct headers; test formula injection prevention — cells starting with `=`,`+`,`-`,`@`,`|` are tab-prefixed; test compliance metadata header row present (export_actor, export_timestamp, filter_summary, record_count, checksum); test checksum is SHA-256 of data payload; test 50k limit: assert service raises ExportLimitExceededError when filtered count > 50000. Depends on T-787, T-788. **Dispatch: BE**

- [ ] T-864 [P] Write RED unit tests for `AuditExportService` JSON in `backend/tests/unit/test_audit_export_json.py`: test JSON output is valid; test metadata wrapper present (export_actor, export_timestamp, filter_summary, record_count, checksum); test no formula injection concerns (JSON inherently safe); test 50k limit respected; test defense-in-depth redaction — inject mock entry with unexpected sensitive value in context, assert export output does NOT contain it. Depends on T-787, T-788. **Dispatch: BE**

- [ ] T-865 Create `backend/src/app/services/audit_export_service.py`: `AuditExportService` with `async export_csv(entries, metadata) -> bytes` and `async export_json(entries, metadata) -> bytes`. CSV: apply central redaction pass, then formula injection prevention (tab-prefix cells starting with `=`,`+`,`-`,`@`,`|`), then serialize with compliance metadata row first. JSON: apply central redaction pass, then wrap in `{"metadata":{...},"entries":[...]}`. Compute SHA-256 checksum of data payload. Both: enforce 50k limit (raise `ExportLimitExceededError` if exceeded). Depends on T-863, T-864. **Dispatch: BE**

- [ ] T-866 [P] Write RED unit tests for export redaction defense-in-depth in `backend/tests/unit/test_export_redaction_defense.py`: simulate a stored audit entry whose context contains a sensitive value that bypassed storage-time redaction; run through `AuditExportService`; assert the sensitive value is absent from the export output. This verifies the defense-in-depth central redaction pass. Depends on T-865. **Dispatch: BE**

- [ ] T-867 [P] Write RED integration tests for audit export API in `backend/tests/integration/test_audit_export.py`: test `POST /admin/audit/export` with format="csv" returns file download; test format="json" returns JSON file; test 422 when filtered result exceeds 50k; test export requires `admin.audit.verify` (403 without); test daily export quota enforced (429 when exhausted); test export emits `audit.export` audit event with filter summary and record_count (no exported data); test CSV contains formula injection prevention. Depends on T-865, T-787. **Dispatch: BE**

- [ ] T-868 Extend `backend/src/app/api/v1/admin_audit.py` with `POST /export` endpoint: permission `admin.audit.verify`; check daily export quota via `QuotaService.check_and_increment(user_id, role_id, "exports")`; parse `AuditExportRequest`; query entries via `AuditSearchService`; if count > 50000 return 422 with message_key; call `AuditExportService`; emit `AUDIT_EXPORT` audit event with sanitized filter summary and record count (no exported data values); return file response with correct Content-Type and Content-Disposition headers. Depends on T-867, T-865, T-862, T-802. **Dispatch: BE**

- [ ] T-869 [P] Write RED unit tests for purge-gap marker in `backend/tests/unit/test_purge_gap_marker.py`: test `AuditService.purge_expired_entries()` inserts `audit.purge` marker BEFORE deleting entries (same transaction); test marker context contains all required fields: `purged_from_seq`, `purged_to_seq`, `purged_count`, `retention_months`, `first_surviving_seq`, `first_surviving_prev_hash`, `last_retained_hash`, `last_retained_seq`; test no existing audit entries are modified (immutability preserved); test marker is itself immutable (before_delete/before_update guards apply). Depends on T-783, T-788. **Dispatch: BE**

- [ ] T-870 Modify `backend/src/app/services/audit_service.py` method `purge_expired_entries()`: (1) identify entries to purge (before deletion); (2) compute boundary metadata (`purged_from_seq`, `purged_to_seq`, `first_surviving_seq`, `first_surviving_prev_hash`, `last_retained_hash`, `last_retained_seq`, `purged_count`); (3) insert `audit.purge` marker via `AuditService.log()` in same transaction BEFORE delete; (4) delete expired entries. Marker chains normally into hash sequence. No existing entries rewritten. Depends on T-869. **Dispatch: BE**

- [ ] T-871 [P] Write RED unit tests for `verify_chain()` purge-gap handling in `backend/tests/unit/test_verify_chain_purge.py`: test `verify_chain()` on a log with purge gap and valid marker returns status="ok" distinguishing intentional purge; test `verify_chain()` on a log with gap and NO matching marker returns status="broken" indicating tampering; test `verify_chain()` matches marker `first_surviving_prev_hash` to orphaned `prev_hash` of first surviving entry; test normal chain without purge still verifies correctly. Depends on T-870. **Dispatch: BE**

- [ ] T-872 Modify `backend/src/app/services/audit_service.py` method `verify_chain()`: when walking retained entries, if an orphaned `prev_hash` is detected (first surviving entry's predecessor was deleted), look for a retained `audit.purge` marker whose `first_surviving_seq` and `first_surviving_prev_hash` match; if found, treat gap as intentional purge (continue verification); if no matching marker, report gap as tampering. No existing entries are rewritten. Depends on T-871. **Dispatch: BE**

- [ ] T-873 [P] Write RED integration test for full purge+verify cycle in `backend/tests/integration/test_purge_verify_cycle.py`: seed audit entries; call `purge_expired_entries()`; verify marker exists with correct boundary metadata; call `verify_chain()`; assert result is "ok" (gap treated as intentional); add entry after purge; verify chain still valid end-to-end. Depends on T-872, T-870. **Dispatch: BE**

- [ ] T-874 [P] Write RED unit tests for retention status endpoint in `backend/tests/unit/test_audit_retention_status.py`: test `GET /admin/audit/retention` returns retention_months from settings, last_purge_at from last `audit.purge` entry, purged_count from that entry's context; test last_purge_at is null when no purge has occurred; test permission `admin.audit.verify` required. Depends on T-787. **Dispatch: BE**

- [ ] T-875 Extend `backend/src/app/api/v1/admin_audit.py` with `GET /retention` endpoint: permission `admin.audit.verify`; read `retention_months` from `Settings.AUDIT_RETENTION_MONTHS`; query most recent `audit.purge` entry for `last_purge_at` and `purged_count` (null if none); return `{"retention_months":N,"last_purge_at":"...","purged_count":N}`. No external scheduler timing displayed. Depends on T-874. **Dispatch: BE**

- [ ] T-876 [P] Write operational documentation at `docs/operations/audit-purge-scheduler.md`: describe how to invoke `AuditService.purge_expired_entries()` via external scheduler; provide example cron expression, Kubernetes CronJob spec, and systemd timer configuration; document expected behavior (marker insertion, entries deleted, verify_chain grace); note platform does NOT manage or display external scheduler timing. Depends on T-870. **Dispatch: BE**

- [ ] T-877 [P] Write RED security tests for search/export permission gates in `backend/tests/unit/test_audit_search_export_permissions.py`: test `GET /admin/audit/entries` returns 403 for user missing `admin.audit.verify`; test `POST /admin/audit/export` returns 403; test `GET /admin/audit/retention` returns 403; test authenticated admin WITH permission returns non-403. Depends on T-862, T-868, T-875. **Dispatch: BE**

- [ ] T-878 [P] Write RED unit test for retention window enforcement in `backend/tests/unit/test_audit_retention_window.py`: seed entries spanning 25 months; call `AuditSearchService.search()` with no date filter; assert entries older than retention_months (24) are absent; assert no SQL query is made without `WHERE timestamp >= cutoff`. Depends on T-860. **Dispatch: BE**

- [ ] T-879 Backend gates Wave 18.3: `cd backend && uv run pytest tests/unit/test_audit_search_service.py tests/unit/test_audit_export_csv.py tests/unit/test_audit_export_json.py tests/unit/test_export_redaction_defense.py tests/unit/test_purge_gap_marker.py tests/unit/test_verify_chain_purge.py tests/unit/test_audit_retention_status.py tests/unit/test_audit_search_export_permissions.py tests/unit/test_audit_retention_window.py tests/integration/test_audit_search.py tests/integration/test_audit_export.py tests/integration/test_purge_verify_cycle.py -x --tb=short && uv run ruff check src/ && uv run ruff format --check src/ && git diff --check`. Depends on T-873, T-875, T-877, T-878, T-876. **Dispatch: BE**

- [ ] T-880 [P] Write RED component tests for audit search UI in `frontend/src/pages/AdminAuditPage.test.tsx` (extend existing): test search filter form renders date range, action_type, actor, outcome, resource_type fields; test filter submit calls GET /admin/audit/entries with params; test paginated results table renders entries; test next/prev page controls work; test Arabic locale RTL layout. Use MSW handlers mocking `/admin/audit/entries` API contract. No backend fixture dependency. **Dispatch: FE**

- [ ] T-881 Extend `frontend/src/pages/AdminAuditPage.tsx` with search/filter UI: add filter form panel (date range picker, action_type dropdown, actor_identity input, outcome dropdown, resource_type input), submit button, reset button; connect to `GET /admin/audit/entries` via TanStack Query; render paginated results table (timestamp, actor, action_type, outcome, resource_type columns); add pagination controls. RTL: all layout via logical CSS properties. Depends on T-880, T-862. **Dispatch: FE**

- [ ] T-882 [P] Write RED component tests for audit export controls in `frontend/src/pages/AdminAuditPage.test.tsx`: test CSV export button triggers POST /admin/audit/export with format="csv" and current filters; test JSON export button triggers format="json"; test 422 response shows "narrow filters" localized message; test 429 (quota exceeded) shows localized error. Use MSW handlers mocking `/admin/audit/export` API contract. No backend fixture dependency. **Dispatch: FE**

- [ ] T-883 Add export controls to `frontend/src/pages/AdminAuditPage.tsx`: CSV and JSON export buttons that POST to `/admin/audit/export` with current filter state; handle 422 (limit exceeded) with localized message; handle 429 (export quota exhausted) with localized error; trigger file download on success. Depends on T-882, T-868, T-881. **Dispatch: FE**

- [ ] T-884 [P] Write RED component tests for retention status display in `frontend/src/pages/AdminAuditPage.test.tsx`: test retention panel shows retention_months, last_purge_at (or "Never"), purged_count; test Arabic locale renders retention info in Arabic. Use MSW handler mocking `/admin/audit/retention`. No backend fixture dependency. **Dispatch: FE**

- [ ] T-885 Add retention status panel to `frontend/src/pages/AdminAuditPage.tsx`: section showing retention_months, last_purge_at (formatted datetime or "Never" localized), purged_count. Connect to `GET /admin/audit/retention`. Depends on T-884, T-875. **Dispatch: FE**

- [ ] T-886 [P] Create/extend `frontend/src/api/audit.ts`: add typed API functions `searchAuditEntries(params)`, `exportAuditEntries(request)`, `getAuditRetention()`. Follows existing API client patterns. Depends on T-862, T-868, T-875. **Dispatch: FE**

- [ ] T-887 Add i18n keys for Wave 18.3 to `frontend/src/locales/en.json`: `audit.search.title`, `audit.search.date_from`, `audit.search.date_to`, `audit.search.action_type`, `audit.search.actor`, `audit.search.outcome`, `audit.search.resource_type`, `audit.search.submit`, `audit.search.reset`, `audit.export.csv`, `audit.export.json`, `audit.export.limit_exceeded`, `audit.export.quota_exceeded`, `audit.retention.title`, `audit.retention.period`, `audit.retention.last_purge`, `audit.retention.never`, `audit.retention.purged_count`. Depends on T-883, T-885. **Dispatch: FE**

- [ ] T-888 Add matching Arabic translations (100% key parity) to `frontend/src/locales/ar.json` for all keys added in T-887. Depends on T-887. **Dispatch: FE**

- [ ] T-889 [P] Run i18n key parity test: `cd frontend && npm test -- --run locales/localeCoverage` — all Wave 18.3 keys present in both locales. Depends on T-887, T-888. **Dispatch: FE**

- [ ] T-890 [P] Write RTL check for audit search/export/retention UI: render AdminAuditPage with Arabic locale and `dir="rtl"`; assert no physical directional CSS properties in rendered output; assert filter form and table are RTL-correct. Depends on T-885, T-888. **Dispatch: FE**

- [ ] T-891 Frontend gates Wave 18.3: `cd frontend && npm test -- --run && npm run lint && npm run typecheck && npm run build && npm run lint:css && git diff --check`. Depends on T-889, T-890, T-883, T-885. **Dispatch: FE**


---

## Wave 18.4 — Verification, Polish, Closeout

> Branch: `phase-6/wave-18.4-verification-closeout`
> Dependencies: Waves 18.0–18.3 all merged to main
> Dispatch: BE for T-892, T-894, T-895; FE for T-893, T-896–T-900; OR for T-901–T-909 (audits + closeout docs)

### Goals
Full backend/frontend gate re-run on merged main, Arabic/RTL browser smoke for all new Phase 6 surfaces (UC-11–UC-18), mobile viewport smoke, independent Gemini+Opus dual security audit, findings consolidation, wave-final-snapshot, orchestration log closeout, AGENTS.md Phase 6 FROZEN update.

### FR/SC Coverage
SC-063–SC-077 (final verification of all Phase 6 success criteria)
SC-072, SC-073 (i18n parity + RTL smoke final pass)
SC-074, SC-075 (full gates on merged state)
SC-076 (0 Critical/High before freeze)

---

- [ ] T-892 Run full backend regression on merged main: `cd backend && uv run pytest tests/ -x --tb=short && uv run ruff check src/ && uv run ruff format --check src/ && git diff --check`. Document pass/fail in wave-18.4 PR description. Depends on all Wave 18.0–18.3 backend tasks merged. **Dispatch: BE**

- [ ] T-893 [P] Run full frontend regression on merged main: `cd frontend && npm test -- --run && npm run lint && npm run typecheck && npm run build && npm run lint:css && git diff --check`. Document pass/fail. Depends on all Wave 18.0–18.3 frontend tasks merged. **Dispatch: FE**

- [ ] T-894 [P] Cross-dialect quota enforcement verification: write or extend `backend/tests/integration/test_cross_dialect_quota.py` — verify quota enforcement at execution boundary works correctly when source DB is PostgreSQL, MySQL, and MSSQL (execution counter incremented on each dialect's execute call, blocked when exhausted regardless of dialect). Depends on T-802, T-892. **Dispatch: BE**

- [ ] T-895 [P] Write security regression test `backend/tests/unit/test_phase6_sanitization_regression.py`: assert all Phase 6 endpoints return no internal values in error responses (iterate through all error paths for quota exceeded, hostile blocked, export limit, detection config validation, permission denied) and verify none contain: counter values, policy IDs, rule names, patterns, confidence scores, raw hostile text, DB host/port, provider names, stack traces, OIDC/SAML tokens. Depends on T-892. **Dispatch: BE**

- [ ] T-896 [P] Arabic/RTL browser smoke — desktop: open browser at `/admin/quotas` with Arabic locale; verify UC-11 (quota config page) — all labels Arabic, RTL layout, no English fallback, form inputs RTL. Document screenshot evidence in `audit/wave-18/browser-smoke-wave18.md`. Depends on T-893. **Dispatch: FE**

- [ ] T-897 [P] Arabic/RTL browser smoke — query flow: with Arabic locale submit a query that triggers quota exceeded (UC-12) — verify error message in Arabic, no internal details; submit a hostile query (UC-13) — verify blocked message in Arabic, no input echo; navigate to detection config (UC-14) — verify Arabic labels RTL. Document evidence. Depends on T-893. **Dispatch: FE**

- [ ] T-898 [P] Arabic/RTL browser smoke — audit surfaces: with Arabic locale navigate to audit search page (UC-15) — verify filter labels Arabic RTL; trigger CSV export (UC-16) — verify export button Arabic; view retention status (UC-17) — Arabic RTL; view quota status dashboard (UC-18) — Arabic RTL. Document evidence. Depends on T-893. **Dispatch: FE**

- [ ] T-899 [P] Mobile viewport smoke (375px, 768px): verify no clipping on AdminQuotasPage (UC-11), AdminDetectionPage (UC-14), audit search page (UC-15), audit retention panel (UC-17), quota status panel (UC-18) at 375px and 768px. Document any regressions. Note: UC-12, UC-13, UC-16 mobile not required per plan. Depends on T-893. **Dispatch: FE**

- [ ] T-900 [P] Consolidate all Wave 18.4 smoke evidence into `audit/wave-18/browser-smoke-wave18.md`: table of UC-11–UC-18 with English/Arabic/Mobile pass status, notes, screenshot references. Depends on T-896, T-897, T-898, T-899. **Dispatch: FE**

- [ ] T-901 Independent security audit — Gemini: perform full-wave audit of FR-147–FR-180 and SC-063–SC-077 across all Phase 6 merged code. Write findings to `audit/wave-18/gemini-findings.md` including: per-FR verification status, sanitization evidence (no raw payloads, no internal details in errors), quota fail-closed evidence, detection pipeline coverage, export redaction defense-in-depth, purge-gap chain integrity, permission gate coverage. Gate: 0 Critical, 0 High before freeze. Depends on T-892, T-895, T-900. **Dispatch: OR**

- [ ] T-902 Independent security audit — Opus: perform full-wave audit of FR-147–FR-180 and SC-063–SC-077. Write findings to `audit/wave-18/opus-findings.md` with same scope as T-901 but independent analysis. Gate: 0 Critical, 0 High. Depends on T-892, T-895. **Dispatch: OR**

- [ ] T-903 Findings consolidation: read both `audit/wave-18/gemini-findings.md` and `audit/wave-18/opus-findings.md`; produce `audit/wave-18/consolidation-report.md` summarizing: Critical/High/Mid/Low counts, any findings requiring remediation before freeze, any agreed-upon deferred items (with rationale), final gate status (PASS/BLOCK). Depends on T-901, T-902. **Dispatch: OR**

- [ ] T-904 [P] If any Critical or High findings in T-903: create remediation tasks, implement fixes, re-run gates, re-audit. BLOCK freeze until 0 Critical/High. This task is conditional — skip if T-903 shows 0 Critical/High. **Dispatch: BE or FE per finding**

- [ ] T-905 Create `specs/006-quotas-hostile-input-audit-hardening/plans/wave-final-snapshot.md`: capture final state of Phase 6 — all merged PRs and branch names, task count summary per wave, FR-147–FR-180 completion status (all DONE), SC-063–SC-077 completion status (all PASS), deferred items (none expected), audit gate result (0 Critical/High), Phase 5 deferred items status (F-003, SMOKE-002, SMOKE-003 remain deferred). Depends on T-903, T-892, T-893. **Dispatch: OR**

- [ ] T-906 Update orchestration log `specs/006-quotas-hostile-input-audit-hardening/plans/orchestration-log.md`: append Wave 18.4 closeout entry (date, all waves complete, task count T-779–T-909, audit gate PASS, freeze status PENDING AGENTS.md update, final PR merged). Depends on T-905. **Dispatch: OR**

- [ ] T-907 Update Phase 6 status in `specs/006-quotas-hostile-input-audit-hardening/spec.md` header: change `Status: Draft` to `Status: FROZEN`. Append freeze date and final PR reference. Depends on T-905. **Dispatch: OR**

- [ ] T-908 Verify `specs/005-sso-rbac-row-column-security/` is still listed as FROZEN and Phase 6 directory exists in `AGENTS.md` phase table. No AGENTS.md edits yet — this is pre-check only. Depends on T-905. **Dispatch: OR**

- [ ] T-909 After final Phase 6 PR merges to main: update `AGENTS.md` Phase table entry for Phase 6 from `ACTIVE` to `FROZEN` with directory `specs/006-quotas-hostile-input-audit-hardening/` and final PR reference. Update Phase 7 row from `PLANNED` to reflect readiness. This is the final task — do NOT execute before T-905 and T-906 complete. Depends on T-906, T-907, T-908. **Dispatch: OR**

---

## Dependency Graph

```
Wave 18.0 (T-779–T-792) ──────────────────────────────────────┐
    │                                                           │
    ▼                                                           ▼
Wave 18.1 (T-793–T-821)      Wave 18.2 (T-822–T-857) ────────►Wave 18.3 (T-858–T-891)
    │  QuotaService exists         Detection service built          │  Needs export quota
    │  (T-794 needed by 18.2       in parallel with 18.1 UI         │  from Wave 18.1
    │  for post-detection          if separate sessions)             │
    │  quota check wiring)                                          │
    └─────────────────────────────────────────────────────────►Wave 18.4 (T-892–T-909)
                                                                    All waves merged
```

### Parallelization Opportunities

- **Within Wave 18.0**: T-779, T-790, T-791 fully parallel; T-781, T-782, T-785, T-786, T-787, T-788, T-789 parallel after T-780/T-783.
- **Wave 18.1 vs 18.2**: Detection service backend (T-822–T-847) can run in parallel with quota UI frontend (T-810–T-821) in separate implementer sessions.
- **Within Wave 18.2**: All 5 rule RED+impl pairs (T-826–T-835) fully parallel after T-823.
- **Within Wave 18.3**: Search (T-859–T-862), Export (T-863–T-868), Purge (T-869–T-876) are independent service paths — parallel with separate implementers.
- **Wave 18.4 browser smoke tasks**: T-896, T-897, T-898, T-899 fully parallel after T-893.
- **Wave 18.4 audits**: T-901 and T-902 fully parallel (independent auditors).

---

## FR/SC Coverage Summary

| FR | Wave | Tasks |
|----|------|-------|
| FR-147 | 18.0+18.1 | T-780,T-781,T-785,T-796,T-798 |
| FR-148 | 18.1 | T-794,T-796 |
| FR-149 | 18.1 | T-798,T-811,T-813 |
| FR-150 | 18.1 | T-794 (60s cache TTL, immediate effect) |
| FR-151 | 18.1 | T-799,T-800,T-801,T-802 |
| FR-152 | 18.1 | T-800,T-804,T-805 |
| FR-153 | 18.1 | T-806,T-807 |
| FR-154 | 18.1 | T-794,T-808 |
| FR-155 | 18.1 | T-803,T-804 |
| FR-156 | 18.2 | T-822,T-823,T-824,T-825,T-845 |
| FR-157 | 18.2 | T-826–T-835,T-836,T-837 |
| FR-158 | 18.2 | T-844,T-845,T-852 |
| FR-159 | 18.2 | T-845 (runs before evaluator, not replacing) |
| FR-160 | 18.2 | T-826–T-835 (EN+AR patterns in each rule) |
| FR-161 | 18.2 | T-822,T-823 (RuleRegistry protocol) |
| FR-162 | 18.2 | T-838,T-839,T-840,T-841,T-849 |
| FR-163 | 18.2 | T-842,T-843,T-845 |
| FR-164 | 18.2 | T-842,T-843,T-846 |
| FR-165 | 18.2 | T-845 (no auto-suspension, audit only) |
| FR-166 | 18.3 | T-859,T-860,T-861,T-862,T-881 |
| FR-167 | 18.3 | T-860,T-862 (offset pagination) |
| FR-168 | 18.3 | T-863–T-868,T-883 |
| FR-169 | 18.3 | T-863,T-864,T-865 (compliance metadata) |
| FR-170 | 18.3 | T-863,T-864,T-865,T-868,T-877 |
| FR-171 | 18.3 | T-863,T-865 (tab-prefix formula injection) |
| FR-172 | 18.3 | T-862 (AUDIT_SEARCH), T-868 (AUDIT_EXPORT) |
| FR-173 | 18.3 | T-860,T-878 |
| FR-174 | 18.3 | T-870,T-876 |
| FR-175 | 18.3 | T-869,T-870 |
| FR-176 | 18.3 | T-874,T-875,T-885 |
| FR-177 | 18.0 | T-783,T-784 |
| FR-178 | 18.1+18.2+18.3 | T-816,T-817,T-853,T-854,T-887,T-888 |
| FR-179 | 18.1+18.2+18.3 | T-819,T-820,T-890 |
| FR-180 | 18.1+18.2 | T-805,T-844 |

| SC | Wave | Gate Tasks |
|----|------|------------|
| SC-063 | 18.1 | T-799,T-801 |
| SC-064 | 18.1+18.2 | T-805,T-844 |
| SC-065 | 18.2 | T-837 |
| SC-066 | 18.2 | T-836 |
| SC-067 | 18.2 | T-842,T-843,T-846 |
| SC-068 | 18.3 | T-877 |
| SC-069 | 18.3 | T-863,T-864,T-866 |
| SC-070 | 18.3 | T-878 |
| SC-071 | 18.1 | T-806,T-807 |
| SC-072 | 18.1+18.2+18.3+18.4 | T-820,T-854,T-889,T-893 |
| SC-073 | 18.1+18.2+18.3+18.4 | T-819,T-890,T-896–T-899 |
| SC-074 | All waves | T-821,T-857,T-891,T-893 |
| SC-075 | All waves | T-809,T-856,T-879,T-892 |
| SC-076 | 18.4 | T-901,T-902,T-903 |
| SC-077 | 18.3 | T-869,T-870,T-871,T-872,T-873 |

---

## Summary

| Wave | Task Range | Count | Dispatch |
|------|-----------|-------|---------|
| Wave 18.0 — Foundation | T-779–T-792 | 14 | BE (12), OR (2) |
| Wave 18.1 — Quotas | T-793–T-821 | 29 | BE (17), FE (12) |
| Wave 18.2 — Hostile Detection | T-822–T-857 | 36 | BE (27), FE (9) |
| Wave 18.3 — Audit Search/Export | T-858–T-891 | 34 | BE (22), FE (12) |
| Wave 18.4 — Verification/Closeout | T-892–T-909 | 18 | BE (3), FE (6), OR (8), conditional (1) |
| **TOTAL** | **T-779–T-909** | **131** | |

**FR coverage**: FR-147–FR-180 (34/34 — 100%)
**SC coverage**: SC-063–SC-077 (15/15 — 100%)

**No gaps identified.** All user stories (US-34–US-40), all FRs, all SCs covered.
