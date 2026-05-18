# Implementation Plan — Phase 3: Multi-Dialect SQL and Multiple Source Databases

**Created**: 2026-05-18
**Phase**: 3 (ACTIVE)
**Spec**: [spec.md](file:///home/avril/QueryCraft/specs/003-multi-dialect-source-dbs/spec.md)
**Research**: [research.md](file:///home/avril/QueryCraft/specs/003-multi-dialect-source-dbs/research.md)
**Data Model**: [data-model.md](file:///home/avril/QueryCraft/specs/003-multi-dialect-source-dbs/data-model.md)
**Contracts**: [api-contracts.md](file:///home/avril/QueryCraft/specs/003-multi-dialect-source-dbs/contracts/api-contracts.md)

---

## Technical Context

| Item | Value |
|------|-------|
| Backend | FastAPI, Python 3.12, SQLAlchemy 2, Alembic, asyncpg, Redis 7 |
| Frontend | React 19, Tailwind v4, Vite, TanStack Query, Zustand, i18next, lucide-react |
| LLM | Gemini (default), provider-agnostic via adapters |
| SQL Evaluator | sqlglot ≥26.0.0 (dialect-aware parsing) |
| New deps (backend) | `cryptography` (Fernet), `asyncmy`, `aioodbc` |
| New sys deps (MSSQL) | `unixODBC`, `unixodbc-dev`, `freetds-dev`, `tdsodbc` |
| Existing encryption | AES-256-GCM via `core/encryption.py` (`PLATFORM_ENCRYPTION_KEY`) |
| New encryption | Fernet via `DB_CREDENTIAL_KEY` env var behind `CredentialProvider` abstraction |

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Security | ✅ Extended | DB creds encrypted (Fernet), never in API/logs |
| II — Query Validation | ✅ Extended | Evaluator parameterized by dialect; reject on parse failure |
| III — Validated Knowledge | ✅ Preserved | No changes to retrieval memory |
| IV — Hostile Input | ⏸️ Deferred | Phase 6 (no trigger in Phase 3) |
| V — LLM-Agnostic | ✅ Preserved | Prompt builder gains dialect param, adapters unchanged |
| VI — Language ↔ Dialect | ✅ **EXTENDED** | PG/MySQL/T-SQL dialect-aware generation |
| VII — Role Auth | ⏸️ Deferred | Phase 5 (single provisional admin) |
| VIII — Brokered DB Access | ✅ **EXTENDED** | Admin manages multiple connections centrally |
| IX — Audit | ⏸️ Deferred | Phase 5 |
| X — Quotas | ⏸️ Deferred | Phase 5 |
| XI — Modularity | ✅ **EXTENDED** | Dialect routing, driver abstraction, per-connection schema |
| XII — API Contract | ✅ Preserved | New endpoints added to OpenAPI |

## Locked Decisions

- **ADR-9**: Fernet + `CredentialProvider` abstraction + `DB_CREDENTIAL_KEY`. Startup fail on missing key. **LOCKED.**
- **ADR-10**: `asyncmy` (MySQL) + `aioodbc` (MSSQL). Parameterized only. ODBC deps documented. **LOCKED.**
- **ADR-13**: Per-session DB selector. `connection_id` on session record. Auto-select if single connection. **LOCKED.**
- **Lifecycle**: active/disabled/hard-delete. Hard-delete only if unreferenced.
- **Migration**: Legacy PG connection → first row. Backfill all `accepted_queries`. NOT NULL `connection_id`.
- **Evaluator**: Dialect parse failure → reject + regenerate with hint. Never execute unvalidated SQL.
- **Introspection**: Auto on first save + health check pass. Manual refresh thereafter.

---

## Wave Structure

### Wave 11 — Backend Foundation: Connections, Encryption, Migration (Qwen)

**Branch**: `phase-3/wave-11.0-connection-foundation`
**Model**: Qwen 3.6 Plus via opencode

**Scope**:
- Rename `database_connections` → `source_database_connections` table
- Add `DatabaseType`, `LifecycleState`, `HealthStatus`, `SchemaIntrospectionStatus` enums
- Add new columns: `display_name`, `database_type`, `lifecycle_state`, `health_status`, `last_health_check_at`, `health_error_category`, `schema_introspection_status`, `schema_last_refreshed_at`
- Drop obsolete columns: `name`, `schema_metadata` JSONB, `schema_cached_at`
- Add `connection_id` nullable FK to `sessions` table
- Backfill existing rows with `database_type='postgresql'`, `lifecycle_state='active'`
- Implement `CredentialProvider` protocol + `FernetCredentialProvider` (ADR-9)
- Add `DB_CREDENTIAL_KEY` to `Settings`, fail startup if missing when encrypted creds exist
- Admin CRUD endpoints: `GET/POST/PUT/DELETE /admin/connections`
- Admin lifecycle endpoints: `POST .../disable`, `POST .../enable`
- Admin health test: `POST .../test` (dialect-aware `SELECT 1`)
- Hard-delete guard: block if referenced, return `error.connection_referenced_delete_blocked`
- Regenerate OpenAPI client (`npm run gen:api`)

**FRs**: FR-059, FR-060, FR-061, FR-062, FR-063, FR-064, FR-087, FR-088, FR-089, FR-090, FR-091
**SCs**: SC-025 (partial: CRUD), SC-029, SC-034

**Gates**:
```bash
cd backend && uv run ruff check src tests
cd backend && uv run ruff format --check src tests
cd backend && uv run pytest -q -m "not integration"
```

**Tests**:
- Migration: backfill verification, NOT NULL constraint, legacy connection type
- Encryption: Fernet round-trip, no plaintext in API response, startup fail on bad key
- CRUD: create/read/update/delete all 3 types, password never returned
- Lifecycle: disable/enable transitions, hard-delete guard
- Health check: success with latency, failure with categorized error

---

### Wave 12 — Backend Dialect, Introspection, Evaluator Routing (Qwen)

**Branch**: `phase-3/wave-12.0-dialect-introspection`
**Model**: Qwen 3.6 Plus via opencode
**Depends on**: Wave 11 merged

**Scope**:
- Add `asyncmy`, `aioodbc` to `pyproject.toml` dependencies
- Document MSSQL system deps in `Dockerfile`, `docker-compose.yml`, `README`
- Implement `SourceDBAdapter` protocol with `PostgresAdapter`, `MySQLAdapter`, `MSSQLAdapter`
- Each adapter: async connect, execute parameterized query, health check, close
- Implement per-dialect `SchemaIntrospector` strategy (`information_schema` queries)
- Create `connection_schema_entries` table
- Implement auto-introspect on first save (FR-093): health check → introspect pipeline
- Manual refresh endpoint: `POST .../refresh-schema`
- Schema summary endpoint: `GET .../schema`
- User connections endpoint: `GET /connections` (active + healthy + introspected only)
- Update `prompt_builder.py`: add `target_dialect` parameter, include `TARGET_DIALECT:` instruction
- Update `ReadOnlyRule`: parameterize `sqlglot.parse(sql, read=dialect)` per connection type
- Add dialect validation: reject on parse failure → regeneration with dialect hint (FR-071, FR-092)
- Update `POST /query/submit`: require `connection_id`, validate connection state
- Add `PATCH /sessions/{id}/connection` endpoint
- Regenerate OpenAPI client

**FRs**: FR-065, FR-066, FR-067, FR-068, FR-069, FR-070, FR-071, FR-072, FR-073 (API), FR-075, FR-077, FR-092, FR-093, FR-094 (API)
**SCs**: SC-026, SC-027, SC-028, SC-035

**Gates**: Same as Wave 11

**Tests**:
- Introspection: PG/MySQL/MSSQL fake adapter returns expected metadata
- Dialect routing: same question → different SQL per dialect
- Evaluator: PG `LIMIT` ok, T-SQL `LIMIT` rejected; T-SQL `TOP` ok, PG `TOP` rejected
- Read-only: INSERT/UPDATE/DELETE rejected across all 3 dialects
- Parse failure: malformed SQL → reject → regeneration hint
- Retry exhaustion: max attempts → localized error card (FR-092)
- Schema isolation: only selected connection's schema in prompt
- Auto-introspect: create connection → auto health check + introspect

---

### Wave 13 — Frontend Admin Connection UI + Login Polish (Gemini)

**Branch**: `phase-3/wave-13.0-admin-ui`
**Model**: Gemini (Chrome DevTools MCP)
**Depends on**: Wave 12 merged (API contracts stable)

**Scope**:
- Admin connections page: list with lifecycle/health/schema status indicators
- Connection form: add/edit with type selector, port auto-fill, password placeholder
- Test connection button with loading state and result display
- Refresh schema button with loading state and summary display
- Disable/enable toggle per connection
- Hard-delete with confirmation dialog and blocked-error display
- Schema summary view per connection
- Login page UI refresh (premium dark mode, accent glow) — no auth changes
- All new strings in `en.json` + `ar.json`
- All components use logical CSS directions
- All icons from `lucide-react`
- Chrome DevTools MCP smoke: login flow, connection CRUD, test, refresh, disable/enable

**FRs**: FR-080, FR-082, FR-083, FR-084, FR-085, FR-086 (partial)
**SCs**: SC-025 (complete), SC-030 (partial), SC-031 (partial), SC-032 (partial)

**Gates**:
```bash
cd frontend && npm run test -- --run
cd frontend && npm run lint
cd frontend && npm run typecheck
cd frontend && npm run build
cd frontend && npm run lint:css
```

---

### Wave 14 — Frontend Workspace DB Selector + Query Flow (Gemini)

**Branch**: `phase-3/wave-14.0-workspace-selector`
**Model**: Gemini (Chrome DevTools MCP)
**Depends on**: Wave 13 merged

**Scope**:
- Database selector dropdown/popover near prompt input
- Per-session selection: disabled prompt until connection chosen (multi-connection)
- Auto-select when single active connection
- Submit `connection_id` with each query
- Response card: connection name + database type badge
- Mid-session switch: update session connection, prior turns keep metadata
- Error states: disabled, unhealthy, no schema, no connections, query failure
- History view: show connection name/type per historical query
- All new strings in `en.json` + `ar.json`
- Chrome DevTools MCP smoke: selector, query flow, mid-session switch, failure paths

**FRs**: FR-073, FR-074, FR-075 (UI), FR-076, FR-077, FR-078, FR-079, FR-081, FR-084, FR-085, FR-086 (complete), FR-094 (UI)
**SCs**: SC-027 (UI verification), SC-030 (complete), SC-031 (complete), SC-032 (complete), SC-034, SC-035

**Gates**: Same as Wave 13

---

### Wave 15 — End-to-End Hardening, Audit, Phase 3 Closure (Qwen + Gemini + Opus)

**Branch**: `phase-3/wave-15.0-hardening`
**Depends on**: Wave 14 merged

**Scope**:
- Full backend + frontend foundation gates on merged main
- Optional/manual real MySQL/MSSQL integration tests (`@pytest.mark.integration`)
- Chrome DevTools MCP full Phase 3 smoke (all flows, both languages, RTL)
- Multi-model audit:
  - Gemini: frontend/browser UX, i18n completeness, RTL, a11y
  - Backend model: dialect/security, evaluator edge cases, credential leakage
  - Opus: consolidation report, severity triage
- Fix Critical/High findings before closure
- Update `orchestration-log.md` with Phase 3 summary
- Produce `wave-final-snapshot.md`

**SCs**: SC-033 (all gates), all SCs final verification

---

## Security Notes

1. **No plaintext credentials**: `encrypted_password` never returned in API, never logged. `password` field accepted on create/edit only, immediately encrypted.
2. **Schema leakage prevention**: User-facing `GET /connections` returns only `id`, `display_name`, `database_type`. No host/port/credentials.
3. **Read-only evaluator**: Parameterized by dialect. Parse failure → reject (never execute).
4. **`DB_CREDENTIAL_KEY` startup guard**: If encrypted credentials exist and key is missing/invalid → typed `ConfigurationError`, startup blocked.
5. **Parameterized queries only**: All source DB adapters use parameterized queries. No string interpolation.

## Setup / Docker / CI Notes

### New Backend Dependencies
```toml
# pyproject.toml additions
"asyncmy>=0.2.9,<1.0.0",
"aioodbc>=0.5.0,<1.0.0",
```

### Dockerfile Additions (MSSQL support)
```dockerfile
RUN apt-get update && apt-get install -y \
    unixodbc unixodbc-dev freetds-dev tdsodbc \
    && rm -rf /var/lib/apt/lists/*
```

### CI Notes
- MySQL/MSSQL real-service tests are `@pytest.mark.integration` (not run in default CI)
- Default CI runs: `pytest -q -m "not integration"` (adapter/fake tests only)
- Optional CI job: `pytest -m integration` with MySQL + MSSQL containers

### Environment Variables (new)
```env
DB_CREDENTIAL_KEY=<base64-encoded-Fernet-key>
```

## i18n Message Keys

See [api-contracts.md](file:///home/avril/QueryCraft/specs/003-multi-dialect-source-dbs/contracts/api-contracts.md) § Error Message Keys for the full list. All keys must have entries in both `en.json` and `ar.json`.

## Per-Wave Foundation Gates

### Backend (Waves 11, 12, 15)
```bash
cd backend && uv run ruff check src tests
cd backend && uv run ruff format --check src tests
cd backend && uv run pytest -q -m "not integration"
```

### Frontend (Waves 13, 14, 15)
```bash
cd frontend && npm run test -- --run
cd frontend && NODE_OPTIONS=--trace-warnings npm run test -- --run
cd frontend && npm run lint
cd frontend && npm run typecheck
cd frontend && npm run build
cd frontend && npm run lint:css
```

## Explicitly Out of Scope

Cross-DB joins, read replicas, connection-pooling UI, SSO/RBAC/audit/quotas/dashboard/reports, charts/visualizations, scheduled reports, mobile shell, saved queries library, automatic periodic schema re-introspection. See spec.md § Explicitly Out of Scope.
