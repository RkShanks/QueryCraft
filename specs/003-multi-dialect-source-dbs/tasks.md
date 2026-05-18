# Tasks — Phase 3: Multi-Dialect SQL and Multiple Source Databases

**Feature**: Multi-Dialect SQL and Multiple Source Databases
**Spec**: [spec.md](file:///home/avril/QueryCraft/specs/003-multi-dialect-source-dbs/spec.md)
**Plan**: [plan.md](file:///home/avril/QueryCraft/specs/003-multi-dialect-source-dbs/plan.md)
**T-ID Range**: T-400 – T-471
**Status**: Draft

---

## TDD Evidence Requirements (all implementation tasks)

Every implementation task follows the commit triple:

1. **RED**: `test(T-XXX): <desc>` — failing test committed first
2. **GREEN**: `feat(T-XXX): <desc>` — minimal implementation to pass
3. **REFACTOR** (if needed): `refactor(T-XXX): <desc>`
4. **MARK**: `docs(T-XXX): mark task complete in tasks.md`

Wave Final Reports MUST include red/green evidence per task.

---

## Wave 11 — Backend Foundation: Connections, Encryption, Migration

**Branch**: `phase-3/wave-11.0-connection-foundation`
**Owner**: Qwen 3.6 Plus via opencode
**FRs**: FR-059, FR-060, FR-061, FR-062, FR-063, FR-064, FR-087, FR-088, FR-089, FR-090, FR-091
**SCs**: SC-025 (partial), SC-029, SC-033, SC-034

### Data Model & Migration

- [X] T-400 Add `DatabaseType`, `LifecycleState`, `HealthStatus`, `SchemaIntrospectionStatus` enums in `backend/src/app/db/models/enums.py` (FR-090)
- [X] T-401 Update `SourceDatabaseConnection` ORM model: rename table `database_connections` → `source_database_connections`, add `display_name`, `database_type`, `lifecycle_state`, `health_status`, `last_health_check_at`, `health_error_category`, `schema_introspection_status`, `schema_last_refreshed_at`; drop `name`, `schema_metadata`, `schema_cached_at` in `backend/src/app/db/models/database_connection.py` (FR-087, FR-090)
- [X] T-402 Add `connection_id` nullable FK to `Session` model in `backend/src/app/db/models/session.py` (FR-094)
- [X] T-403 Create Alembic migration `006_phase3_multi_dialect_connections.py` in `backend/alembic/versions/`: rename table, add columns, backfill `display_name` from `name`, set `database_type='postgresql'` + `lifecycle_state='active'`, drop obsolete columns, create `connection_schema_entries` table, add `connection_id` to `sessions`, update FK constraints (FR-087, FR-091)
- [X] T-404 Write migration tests: verify backfill of existing rows, NOT NULL constraint on new `accepted_queries`, legacy connection has `database_type='postgresql'` and `lifecycle_state='active'` in `backend/tests/unit/db/test_migration_006_phase3.py` (FR-091, SC-034)

### Credential Encryption

- [X] T-405 Implement `CredentialProvider` protocol and `FernetCredentialProvider` in `backend/src/app/core/credential_provider.py` using `cryptography.fernet.Fernet` with `DB_CREDENTIAL_KEY` env var (FR-062, ADR-9)
- [X] T-406 Add `DB_CREDENTIAL_KEY` to `Settings` in `backend/src/app/core/config.py`; implement startup guard — fail if key missing/invalid when encrypted credentials exist (FR-062, ADR-9)
- [X] T-407 Write encryption tests: Fernet round-trip, no plaintext in API response, startup fail on bad/missing key, provider abstraction contract in `backend/tests/unit/core/test_credential_provider.py` (SC-029)

### Connection Service

- [X] T-408 Implement `ConnectionService` in `backend/src/app/services/connection_service.py`: CRUD operations, lifecycle transitions (disable/enable), hard-delete guard (block if referenced by `accepted_queries` or `sessions`), health check (`SELECT 1` via dialect), password encryption on save (FR-059, FR-060, FR-061, FR-063, FR-064, FR-089, FR-090)
- [X] T-409 Implement `ConnectionRepository` in `backend/src/app/repositories/connection_repository.py`: DB access layer for `SourceDatabaseConnection` (FR-059)
- [X] T-410 Write connection service tests: create/read/update/delete all 3 DB types, password never returned, lifecycle transitions, hard-delete guard blocks when referenced in `backend/tests/unit/services/test_connection_service.py` (SC-025, SC-029)

### Pydantic Schemas

- [X] T-411 [P] Create connection request/response Pydantic schemas in `backend/src/app/schemas/connection.py`: `ConnectionCreate`, `ConnectionUpdate`, `ConnectionResponse`, `ConnectionTestResult`, `ConnectionListResponse` (FR-059, FR-060)

### Admin API Endpoints

- [X] T-412 Implement admin connection CRUD endpoints in `backend/src/app/api/v1/admin_connections.py`: `GET/POST /admin/connections`, `GET/PUT/DELETE /admin/connections/{id}` (FR-059, FR-060, FR-061)
- [X] T-413 Implement admin lifecycle endpoints in `backend/src/app/api/v1/admin_connections.py`: `POST .../disable`, `POST .../enable` (FR-089)
- [X] T-414 Implement admin health test endpoint in `backend/src/app/api/v1/admin_connections.py`: `POST .../test` with dialect-aware `SELECT 1` (FR-063, FR-064)
- [X] T-415 Write admin API contract tests: CRUD, lifecycle, health test, hard-delete guard, password never in response in `backend/tests/unit/api/test_admin_connections.py` (SC-025, SC-029)

### OpenAPI Client Regeneration

- [X] T-416 Regenerate OpenAPI client: run `npm run gen:api` in `frontend/`, verify `frontend/src/api/generated/types.gen.ts` updated with new admin connection types (Note: @hey-api/openapi-ts v0.95.0 known quirk — exits 0 but writes no files; spec updated, manual regeneration needed)

### Backend Gates

- [X] T-417 Run backend foundation gates and paste verbatim output:
  - `cd backend && uv run ruff check src tests`
  - `cd backend && uv run ruff format --check src tests`
  - `cd backend && uv run pytest -q -m "not integration"`
  (SC-033)

---

## Wave 12 — Backend Dialect, Introspection, Evaluator Routing

**Branch**: `phase-3/wave-12.0-dialect-introspection`
**Owner**: Qwen 3.6 Plus via opencode
**Depends on**: Wave 11 merged
**FRs**: FR-065, FR-066, FR-067, FR-068, FR-069, FR-070, FR-071, FR-072, FR-075, FR-077, FR-092, FR-093, FR-094
**SCs**: SC-026, SC-027, SC-028, SC-033, SC-035

### Driver Dependencies & Docs

- [X] T-418 Add `asyncmy` and `aioodbc` to `backend/pyproject.toml` dependencies; document MSSQL system deps (`unixODBC`, `freetds-dev`, `tdsodbc`) in `Dockerfile`, `docker-compose.yml`, and `README.md` (ADR-10)

### Source DB Adapter Abstraction

- [X] T-419 Implement `SourceDBAdapter` protocol and `PostgresAdapter` in `backend/src/app/source_db/adapters.py`: async connect, execute parameterized query, health check, close (ADR-10, FR-069)
- [X] T-420 [P] Implement `MySQLAdapter` in `backend/src/app/source_db/adapters.py` using `asyncmy`; parameterized queries only (ADR-10, FR-069)
- [X] T-421 [P] Implement `MSSQLAdapter` in `backend/src/app/source_db/adapters.py` using `aioodbc`; parameterized queries only (ADR-10, FR-069)
- [X] T-422 Write adapter tests: connect/execute/health-check for all 3 adapters with fake/mock connections in `backend/tests/unit/source_db/test_adapters.py` (SC-027)

### Schema Introspection

- [X] T-423 Create `ConnectionSchemaEntry` ORM model in `backend/src/app/db/models/connection_schema.py` (table `connection_schema_entries`, cascade delete) (FR-065, FR-066)
- [X] T-424 Implement `SchemaIntrospector` strategy pattern in `backend/src/app/source_db/schema_introspector.py`: per-dialect `information_schema` queries for PG/MySQL/MSSQL, full-replace refresh logic (FR-065, FR-066, ADR-11)
- [X] T-425 Implement auto-introspect pipeline in `ConnectionService`: on first save → health check → introspect; mark status accordingly (FR-093)
- [X] T-426 Add admin schema endpoints: `POST .../refresh-schema` and `GET .../schema` in `backend/src/app/api/v1/admin_connections.py` (FR-066, FR-067, FR-068)
- [X] T-427 Write introspection tests: PG/MySQL/MSSQL fake adapter returns expected metadata, full-replace on refresh, failure handling, auto-introspect on save in `backend/tests/unit/source_db/test_schema_introspector.py` (SC-026)

### User-Facing Connection Endpoint

- [X] T-428 Implement `GET /api/v1/connections` endpoint: returns active + healthy + introspected connections (minimal payload: id, display_name, database_type) in `backend/src/app/api/v1/connections.py` (FR-073, FR-077)

### Dialect-Aware Evaluator

- [X] T-429 Update `ReadOnlyRule` in `backend/src/app/evaluator/rules/read_only.py`: parameterize `sqlglot.parse(sql, read=dialect)` per connection's `database_type`; add dialect mapping (FR-071, FR-072)
- [X] T-430 Implement dialect validation: reject on parse failure or low confidence → trigger regeneration with dialect hint; never execute unvalidated SQL in `backend/src/app/evaluator/rules/dialect_validation.py` (FR-071, FR-092)
- [X] T-431 Write dialect evaluator tests: PG `LIMIT` ok / T-SQL `LIMIT` rejected; T-SQL `TOP` ok / PG `TOP` rejected; INSERT/UPDATE/DELETE rejected across all 3 dialects; parse failure → reject → hint in `backend/tests/unit/evaluator/test_dialect_evaluator.py` (SC-027, SC-028)

### Prompt Builder & Query Flow

- [ ] T-432 Update `prompt_builder.py` in `backend/src/app/llm/prompt_builder.py`: add `target_dialect` parameter, include `TARGET_DIALECT:` instruction, include only selected connection's schema (FR-070)
- [ ] T-433 Update `POST /api/v1/query/submit` in `backend/src/app/api/v1/query.py`: require `connection_id`, validate connection state (active + healthy + introspected), store on attempt; route query to correct adapter (FR-075, FR-094)
- [ ] T-434 Add `PATCH /api/v1/sessions/{session_id}/connection` endpoint in `backend/src/app/api/v1/sessions.py` (FR-094)
- [ ] T-435 Write query flow tests: submit with connection_id, schema isolation (only selected connection's schema in prompt), disabled connection blocked, retry exhaustion → error card in `backend/tests/unit/api/test_query_connection_routing.py` (SC-027, SC-035)

### OpenAPI Client Regeneration

- [ ] T-436 Regenerate OpenAPI client: run `npm run gen:api` in `frontend/`, verify `types.gen.ts` includes schema/introspection/user-connections/session-connection types

### Backend Gates

- [ ] T-437 Run backend foundation gates and paste verbatim output:
  - `cd backend && uv run ruff check src tests`
  - `cd backend && uv run ruff format --check src tests`
  - `cd backend && uv run pytest -q -m "not integration"`
  (SC-033)

---

## Wave 13 — Frontend Admin Connection UI + Login Polish

**Branch**: `phase-3/wave-13.0-admin-ui`
**Owner**: Gemini (Chrome DevTools MCP)
**Depends on**: Wave 12 merged (API contracts stable)
**FRs**: FR-059 (UI), FR-060 (UI), FR-061 (UI), FR-063 (UI), FR-067 (UI), FR-080, FR-082, FR-083, FR-084, FR-085, FR-086, FR-089 (UI)
**SCs**: SC-025, SC-030 (partial), SC-031 (partial), SC-032 (partial), SC-033

### Admin Connections Page

- [ ] T-438 Create `AdminConnectionsPage` component with connection list, lifecycle/health/schema status indicators, and `schema_last_refreshed_at` display in `frontend/src/pages/AdminConnectionsPage.tsx` (FR-080, FR-064, FR-090)
- [ ] T-439 Create `AdminConnectionsPage.test.tsx` co-located test: renders list, status indicators, empty state in `frontend/src/pages/AdminConnectionsPage.test.tsx`
- [ ] T-440 Create `ConnectionForm` component: add/edit form with database type selector, port auto-fill per dialect (5432/3306/1433), password placeholder on edit in `frontend/src/components/admin/ConnectionForm.tsx` (FR-059, FR-060)
- [ ] T-441 Create `ConnectionForm.test.tsx` co-located test: form validation, type switching, port auto-fill, password placeholder in `frontend/src/components/admin/ConnectionForm.test.tsx`
- [ ] T-442 Implement test-connection button with loading state and result display (success with latency, failure with localized error) in `frontend/src/components/admin/ConnectionTestButton.tsx` (FR-063)
- [ ] T-443 Create `ConnectionTestButton.test.tsx` co-located test in `frontend/src/components/admin/ConnectionTestButton.test.tsx`
- [ ] T-444 Implement refresh-schema button with loading state, summary display, and `schema_last_refreshed_at` update in `frontend/src/components/admin/RefreshSchemaButton.tsx` (FR-066, FR-067, FR-068)
- [ ] T-445 Create `RefreshSchemaButton.test.tsx` co-located test in `frontend/src/components/admin/RefreshSchemaButton.test.tsx`
- [ ] T-446 Implement disable/enable toggle and hard-delete with confirmation dialog and blocked-error display in `frontend/src/components/admin/ConnectionActions.tsx` (FR-061, FR-089)
- [ ] T-447 Create `ConnectionActions.test.tsx` co-located test: disable/enable, delete confirmation, delete-blocked error in `frontend/src/components/admin/ConnectionActions.test.tsx`

### API Hooks

- [ ] T-448 [P] Create `useConnections` admin hook (list, create, update, delete, test, disable, enable, refresh-schema) in `frontend/src/hooks/useConnections.ts`
- [ ] T-449 [P] Create `useConnections.test.tsx` co-located test in `frontend/src/hooks/useConnections.test.tsx`

### Typed Error UX

- [ ] T-450 Add typed/localized error display for: `credential_config`, `connection_auth_failed`, `connection_network_unreachable`, `introspection_failed`, `connection_referenced_delete_blocked`, `connection_disabled` in admin components (FR-078, SC-035)

### i18n

- [ ] T-451 [P] Add all Wave 13 i18n keys to `frontend/src/locales/en.json` and `frontend/src/locales/ar.json`: connection CRUD labels, status labels, error messages, admin page titles (FR-084, SC-030)

### Login UI Polish

- [ ] T-452 Refresh `SignInPage` and `SignInForm` UI: premium dark-mode styling, accent glow, branded elements — no auth semantics change in `frontend/src/pages/SignInPage.tsx` and `frontend/src/components/auth/SignInForm.tsx` (FR-082)

### Route & Navigation

- [ ] T-453 Add admin connections route to `AppShell`/router; add navigation link with `lucide-react` `Database` icon in `frontend/src/components/shell/AppShell.tsx` (FR-083)

### Chrome DevTools MCP Smoke

- [ ] T-454 Chrome DevTools MCP smoke: login UI, admin connection list/add/edit/test/refresh/disable/enable/delete-guard, console errors, network checks, i18n resolution, RTL layout (FR-086, SC-032)

### Frontend Gates

- [ ] T-455 Run frontend foundation gates and paste verbatim output:
  - `cd frontend && npm run test -- --run`
  - `cd frontend && NODE_OPTIONS=--trace-warnings npm run test -- --run`
  - `cd frontend && npm run lint`
  - `cd frontend && npm run typecheck`
  - `cd frontend && npm run build`
  - `cd frontend && npm run lint:css`
  (SC-033)

---

## Wave 14 — Frontend Workspace DB Selector + Query Flow Metadata

**Branch**: `phase-3/wave-14.0-workspace-selector`
**Owner**: Gemini (Chrome DevTools MCP)
**Depends on**: Wave 13 merged
**FRs**: FR-073, FR-074, FR-075, FR-076, FR-077, FR-078, FR-079, FR-081, FR-084, FR-085, FR-086, FR-094
**SCs**: SC-027 (UI), SC-030, SC-031, SC-032, SC-033, SC-034, SC-035

### Database Selector

- [ ] T-456 Create `DatabaseSelector` dropdown/popover component near prompt input: shows active connections with display name + database type icon (`lucide-react`), mirrors in RTL in `frontend/src/components/chat/DatabaseSelector.tsx` (FR-073, FR-074, FR-081)
- [ ] T-457 Create `DatabaseSelector.test.tsx` co-located test: renders connections, selection, auto-select single, empty state, RTL in `frontend/src/components/chat/DatabaseSelector.test.tsx`

### Per-Session Connection State

- [ ] T-458 Create `useConnectionSelection` hook: per-session `connection_id` state, auto-select when single active connection, `PATCH /sessions/{id}/connection` on change in `frontend/src/hooks/useConnectionSelection.ts` (FR-094)
- [ ] T-459 Create `useConnectionSelection.test.tsx` co-located test in `frontend/src/hooks/useConnectionSelection.test.tsx`
- [ ] T-460 Integrate `DatabaseSelector` into `WorkspacePage`/`PromptInput`: disable prompt until DB selected, block first query with localized prompt/error until selection in `frontend/src/pages/WorkspacePage.tsx` and `frontend/src/components/chat/PromptInput.tsx` (FR-094, FR-077)

### Query Flow Integration

- [ ] T-461 Update `useQuerySubmit` hook to send selected `connection_id` with each query submission in `frontend/src/hooks/useQuerySubmit.ts` (FR-075)
- [ ] T-462 Update `AssistantResponseCard` to display connection name + database type badge in response card header in `frontend/src/components/chat/AssistantResponseCard.tsx` (FR-076)
- [ ] T-463 Write `AssistantResponseCard` connection metadata test in `frontend/src/components/chat/AssistantResponseCard.test.tsx`

### Mid-Session Switch & History

- [ ] T-464 Implement mid-session DB switch: update session connection, prior turns keep original metadata; workspace displays active DB/dialect in `frontend/src/pages/WorkspacePage.tsx` (FR-094)
- [ ] T-465 Update history views to show source DB/dialect metadata per query in `frontend/src/components/history/HistoryDetail.tsx` and `frontend/src/components/history/HistoryList.tsx` (FR-076)

### Error UX

- [ ] T-466 Implement error UX for: disabled connection, unhealthy connection, no schema, no connections available, query execution failure — localized inline error cards in `frontend/src/components/chat/ConnectionErrorCard.tsx` (FR-077, FR-078, FR-079, SC-035)

### i18n / RTL / a11y

- [ ] T-467 [P] Add all Wave 14 i18n keys to `frontend/src/locales/en.json` and `frontend/src/locales/ar.json`: selector labels, connection status, error messages, query metadata labels (FR-084, SC-030)

### Chrome DevTools MCP Smoke

- [ ] T-468 Chrome DevTools MCP smoke: selector interaction, first-query blocking, selected-DB query, switch mid-session, disabled/error paths, console errors, network checks, i18n, RTL (FR-086, SC-032)

### Frontend Gates

- [ ] T-469 Run frontend foundation gates and paste verbatim output:
  - `cd frontend && npm run test -- --run`
  - `cd frontend && NODE_OPTIONS=--trace-warnings npm run test -- --run`
  - `cd frontend && npm run lint`
  - `cd frontend && npm run typecheck`
  - `cd frontend && npm run build`
  - `cd frontend && npm run lint:css`
  (SC-033)

---

## Wave 15 — E2E Hardening, Audit, Phase 3 Closure

**Branch**: `phase-3/wave-15.0-hardening`
**Owner**: Qwen + Gemini + Opus
**Depends on**: Wave 14 merged
**SCs**: SC-025–SC-035 (all, final verification)

### Full Foundation Gates

- [ ] T-470 Run full backend gates on merged main and paste verbatim output:
  - `cd backend && uv run ruff check src tests`
  - `cd backend && uv run ruff format --check src tests`
  - `cd backend && uv run pytest -q -m "not integration"`
  (SC-033)
- [ ] T-471 Run full frontend gates on merged main and paste verbatim output:
  - `cd frontend && npm run test -- --run`
  - `cd frontend && NODE_OPTIONS=--trace-warnings npm run test -- --run`
  - `cd frontend && npm run lint`
  - `cd frontend && npm run typecheck`
  - `cd frontend && npm run build`
  - `cd frontend && npm run lint:css`
  (SC-033)

### Optional Integration Smoke

- [ ] T-472 Optional/manual: real MySQL integration smoke with `@pytest.mark.integration` if MySQL service available (ADR-10)
- [ ] T-473 Optional/manual: real MSSQL integration smoke with `@pytest.mark.integration` if MSSQL service available (ADR-10)

### Chrome DevTools MCP Full Phase 3 Smoke

- [ ] T-474 Full Chrome DevTools MCP smoke across all Phase 3 flows: login, admin DB management (CRUD/test/refresh/disable/enable/delete-guard), workspace DB selector, query flow with dialect verification, failure paths — both English and Arabic, RTL (FR-086, SC-032)

### Multi-Model Audit

- [ ] T-475 Gemini audit: frontend/browser UX, i18n completeness, RTL correctness, a11y — produce `audit/wave-15/gemini-findings.md`
- [ ] T-476 Backend model audit: dialect/security, evaluator edge cases, credential leakage, schema isolation — produce `audit/wave-15/backend-findings.md`
- [ ] T-477 Opus consolidation: merge audit findings, severity triage, produce consolidation report in `audit/wave-15/consolidation-report.md`

### Critical/High Finding Fixes

- [ ] T-478 Fix all Critical findings from audit before Phase 3 closure (block on T-477)
- [ ] T-479 Fix all High findings from audit before Phase 3 closure (block on T-477)

### Phase 3 Closure

- [ ] T-480 Update `specs/003-multi-dialect-source-dbs/plans/orchestration-log.md` with Phase 3 summary (block on T-478, T-479)
- [ ] T-481 Produce `specs/003-multi-dialect-source-dbs/plans/wave-final-snapshot.md` (block on T-480)

---

## Dispatch Order & Ownership

| Wave | T-ID Range | Owner | Branch | Depends On |
|------|-----------|-------|--------|------------|
| 11 | T-400 – T-417 | Qwen 3.6 Plus (opencode) | `phase-3/wave-11.0-connection-foundation` | main green |
| 12 | T-418 – T-437 | Qwen 3.6 Plus (opencode) | `phase-3/wave-12.0-dialect-introspection` | Wave 11 merged |
| 13 | T-438 – T-455 | Gemini (Chrome DevTools MCP) | `phase-3/wave-13.0-admin-ui` | Wave 12 merged |
| 14 | T-456 – T-469 | Gemini (Chrome DevTools MCP) | `phase-3/wave-14.0-workspace-selector` | Wave 13 merged |
| 15 | T-470 – T-481 | Qwen + Gemini + Opus | `phase-3/wave-15.0-hardening` | Wave 14 merged |

## Parallel-Safe Notes

- **Within Wave 11**: T-411 (schemas) is parallel-safe with T-405–T-407 (encryption). T-400–T-404 (model/migration) must complete before T-408–T-410 (service).
- **Within Wave 12**: T-420 (MySQL adapter) and T-421 (MSSQL adapter) are parallel-safe with each other but depend on T-419 (protocol). T-423 (schema model) is parallel-safe with T-419–T-422.
- **Within Wave 13**: T-448–T-449 (hooks) and T-451 (i18n) are parallel-safe. Component tasks (T-438–T-447) are sequential (page → form → buttons → actions).
- **Within Wave 14**: T-467 (i18n) is parallel-safe with component work.
- **Wave 15**: Sequential — gates → smoke → audit → fixes → closure.

## Dependency Graph

```
Wave 11 (Backend Foundation)
    │
    ▼
Wave 12 (Dialect + Introspection)
    │
    ▼
Wave 13 (Frontend Admin UI)
    │
    ▼
Wave 14 (Frontend Workspace Selector)
    │
    ▼
Wave 15 (Hardening + Audit + Closure)
```

All waves are strictly sequential. No cross-wave parallelism.

## Governance Reminder

- Implementers may ONLY toggle `[ ]` → `[X]` in this file.
- All other governance docs (spec.md, plan.md, data-model.md, research.md, contracts/) are **READ-ONLY** for implementers.
- Every commit MUST reference a T-ID in its subject line (Conventional Commits).
- PR descriptions MUST reference T-IDs + FR/SC numbers.
- `[NEEDS DECISION]` → STOP and report to orchestrator. Never invent product decisions.
