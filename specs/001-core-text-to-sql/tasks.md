# Tasks: Core Text-to-SQL Vertical Slice

**Feature Branch**: `001-core-text-to-sql` | **Phase**: 1  
**Input**: Design documents from `specs/001-core-text-to-sql/` — spec.md, plan.md, research.md, data-model.md, contracts/openapi.yaml

This file is the actionable task breakdown for Phase 1 of the Text-to-SQL Analytics Platform. It covers the full vertical slice: sign in → ask a question → see validated table result → accept/reject/regenerate → browse history. The file is generated in four parts; this is **Part 1 (Foundation cluster only)**.

---

## How to Read This File

Each task follows the format:

```
- [ ] T-NNN [P?] [type] Title — file path(s)
```

| Token | Meaning |
|-------|---------|
| `- [ ]` | Unchecked = not started. Mark `[x]` when done. |
| `T-NNN` | Sequential task ID. IDs are globally unique across all parts. |
| `[P]` | **Parallelizable** — this task touches different files and has no dependency on an incomplete task in the same cluster. Absent = sequential (depends on a prior task). |
| `[test]` | Task produces test code (unit, integration, contract, or e2e). |
| `[backend]` | Task produces backend (Python) code or config. |
| `[frontend]` | Task produces frontend (TypeScript/React) code or config. |
| `[infra]` | Task produces infrastructure files (Docker, CI, compose). |
| `[docs]` | Task produces documentation. |

**Cluster layout**: Tasks are grouped into clusters. The **Foundation** cluster must complete before any user-story cluster begins. User-story clusters (US-1 … US-6) can run in parallel once Foundation is done, subject to per-task dependency lists. A final **Polish** cluster handles cross-cutting concerns.

**Test-first discipline**: Where a task has a companion test task, the test task appears first and must be written (and fail) before the implementation task is started. Test tasks carry the `[test]` tag.

**Parallelism markers**: Tasks marked `[P]` can be executed concurrently with other `[P]` tasks in the same cluster, provided their listed dependencies are met. Tasks without `[P]` must wait for their explicit dependencies.

---

## Pre-Execution Clarifications

_No blocking ambiguities were surfaced during artifact review. All design decisions are resolved in plan.md and research.md._

---

## Legend

| Tag | Meaning |
|-----|---------|
| `[test]` | Produces test code |
| `[backend]` | Produces backend Python code or configuration |
| `[frontend]` | Produces frontend TypeScript/React code or configuration |
| `[infra]` | Produces infrastructure files (Docker, CI, docker-compose) |
| `[docs]` | Produces documentation |

---

## Cluster: Foundation
**Goal:** Establish the monorepo layout, tooling, infrastructure, and cross-cutting libraries that every user-story cluster depends on. All tasks in this cluster must complete before any US-1 … US-6 task starts.

### Monorepo scaffold + backend project

- [x] **T-001** [P] [infra] **Monorepo scaffold** — cluster: Foundation | deps: — | | effort: XS
  Done when: repo root contains `backend/`, `frontend/`, `shared/` directories with `.gitkeep` or initial config, and a placeholder `docker-compose.dev.yml`; `git status` shows new directories tracked.

- [x] **T-002** [P] [backend] **Backend pyproject.toml with pinned deps** — cluster: Foundation | deps: — | | effort: S
  Done when: `backend/pyproject.toml` declares Python 3.12 with all pinned production deps (FastAPI, Uvicorn, SQLAlchemy 2.0 async, asyncpg, Alembic, Pydantic v2, pydantic-settings, sqlglot, httpx, argon2-cffi, redis[hiredis], structlog, opentelemetry-api, opentelemetry-sdk) and dev deps (pytest, pytest-asyncio, pytest-cov, testcontainers[postgres,redis], schemathesis, ruff); `backend/uv.lock` is committed, and `uv sync --all-extras` from a clean checkout produces a working venv with no resolution errors.

### Alembic + migrations

- [x] **T-003** [backend] **Alembic initialisation** — cluster: Foundation | deps: T-002 | | effort: S
  Done when: `backend/alembic.ini` points to an async-compatible `sqlalchemy.url` placeholder; `backend/alembic/env.py` uses the async engine; `alembic --help` from `backend/` succeeds.

- [x] **T-004** [backend] **Initial schema migration** — cluster: Foundation | deps: T-003 | FR-001,FR-004,FR-016,FR-021,FR-027 | effort: M
  Done when: migration `001_initial_schema.py` creates four tables (`users`, `database_connections`, `accepted_queries`, `app_config`) matching `data-model.md` exactly; reversible (`alembic downgrade -1`); applies against a blank PostgreSQL 16 database.

- [x] **T-005** [backend] **Seed admin user migration** — cluster: Foundation | deps: T-004 | FR-001 | effort: S
  Done when: migration `002_seed_admin_user.py` reads `ADMIN_USERNAME`/`ADMIN_DISPLAY_NAME`/`ADMIN_PASSWORD` from env, hashes with Argon2id, upserts into `users` with `role='admin'`; reversible; missing env vars raise a clear error.

### Backend core modules

- [x] **T-006** [backend] **Async engine + session factory** — cluster: Foundation | deps: T-002 | | effort: S
  Done when: `backend/src/app/db/base.py` exports `async_engine`, `async_session_factory`, and `get_db` async generator for FastAPI `Depends()`; uses SQLAlchemy 2.0 async with asyncpg; pool params configurable via pydantic-settings.

- [x] **T-007** [P] [backend] **Pydantic-settings config module** — cluster: Foundation | deps: T-002 | FR-003,FR-004,FR-007,FR-009,FR-012 | effort: M
  Done when: `backend/src/app/core/config.py` defines `Settings(BaseSettings)` loading all env vars from plan.md (`DATABASE_URL`, `REDIS_URL`, `PLATFORM_ENCRYPTION_KEY`, `ALLOWED_ORIGINS`, `LLM_PROVIDER`, all `LLM_API_KEY_*`, `LLM_BASE_URL_OLLAMA`, `SOURCE_DB_*`, `ADMIN_*`, `QUERY_TIMEOUT_SECONDS`, `MAX_QUESTION_LENGTH`, `SESSION_IDLE_TIMEOUT_HOURS`, `SCHEMA_CACHE_TTL_SECONDS`, `MAX_SCHEMA_TOKENS`); validators reject missing mandatory keys; exports `get_settings()` singleton.

### Encryption helpers

- [x] **T-008** [P] [test] **AES-256-GCM encryption tests** — cluster: Foundation | deps: T-002 | | effort: S
  Done when: `backend/tests/unit/test_encryption.py` tests round-trip, ciphertext≠plaintext, wrong-key error, tampered-ciphertext integrity error, and empty-plaintext round-trip; all fail because `core/encryption.py` does not yet exist.

- [x] **T-009** [backend] **AES-256-GCM encrypt/decrypt** — cluster: Foundation | deps: T-008 | | effort: S
  Done when: `backend/src/app/core/encryption.py` exports `encrypt()`/`decrypt()` using AESGCM with 12-byte IV; output format `base64(iv || ciphertext || tag)`; all T-008 tests pass.

### Security middleware

- [x] **T-010** [P] [test] **Session middleware + Origin validation tests** — cluster: Foundation | deps: T-002 | FR-003 | effort: S
  Done when: `backend/tests/unit/test_security.py` tests cookie flags (HttpOnly/Secure/SameSite=Strict), expired session 401, missing Origin 403, invalid Origin 403, valid Origin pass-through, GET bypasses Origin; all fail because `core/security.py` does not yet exist.

- [x] **T-011** [backend] **Session middleware + Origin validator** — cluster: Foundation | deps: T-006,T-007,T-010 | FR-003 | effort: M
  Done when: `backend/src/app/core/security.py` provides `SessionMiddleware` (Redis-backed, idle timeout, cookie flags) and `OriginValidatorMiddleware` (POST/PUT/PATCH/DELETE Origin check); exports `hash_password`/`verify_password` (Argon2id); all T-010 tests pass.

### Logging + app factory + Redis

- [x] **T-012** [P] [backend] **Structured logging + OpenTelemetry bootstrap** — cluster: Foundation | deps: T-002 | FR-020 | effort: S
  Done when: `backend/src/app/core/logging.py` configures structlog JSON output with request-correlated context (trace ID, user ID), log-level env var control, and no-op OTel exporter; `setup_logging()` produces structured JSON.

- [x] **T-013** [backend] **FastAPI app factory + lifespan** — cluster: Foundation | deps: T-006,T-007,T-011,T-012 | FR-004 | effort: M
  Done when: `backend/src/app/main.py` exports `create_app()` that attaches middlewares (session, Origin, CORS), registers lifespan event (upsert `database_connections` row, encrypt password), includes v1 router stubs, calls `setup_logging()`; starts with `uvicorn` when env vars are set.

- [x] **T-014** [P] [backend] **Redis client wiring** — cluster: Foundation | deps: T-007 | | effort: XS
  Done when: `backend/src/app/core/dependencies.py` exports `get_redis` (async generator, `redis.asyncio.Redis` from `REDIS_URL`), re-exports `get_db`, and provides `get_current_user` stub (reads session from request state, returns user or raises 401); Redis verified on startup via lifespan ping.

### Infrastructure

- [x] **T-015** [P] [infra] **Backend Dockerfile** — cluster: Foundation | deps: T-002 | | effort: S
  Done when: `backend/Dockerfile` uses multi-stage build (builder + runtime on `python:3.12-slim`), runs as non-root `appuser`; `docker build -t querycraft-backend backend/` succeeds.

### Contract + test harness

- [x] **T-016** [test] **Schemathesis contract-test harness** — cluster: Foundation | deps: T-013 | SC-002 | effort: S
  Done when: `backend/tests/contract/test_openapi_contract.py` loads `contracts/openapi.yaml`, runs schemathesis smoke test against `GET /auth/me` and `POST /auth/sign-in`; passes when backend conforms to contract.

- [x] **T-017** [test] **Pytest shared fixtures** — cluster: Foundation | deps: T-006,T-007,T-013,T-014 | | effort: M
  Done when: `backend/tests/conftest.py` provides `db_engine`/`db_session` (testcontainers Postgres 16 + Alembic), `redis_client` (testcontainers Redis 7), `authenticated_client` (httpx ASGI + pre-seeded session), `mock_llm` (controllable SQL mock); session-scoped where appropriate.

### Frontend project

- [x] **T-018** [P] [frontend] **Frontend package.json with pinned deps** — cluster: Foundation | deps: — | | effort: S
  Done when: `frontend/package.json` declares all pinned production deps (React 18, Vite, TypeScript 5.x, React Router, TanStack Query/Table, i18next, Tailwind v4, Radix UI, react-hook-form, zod) and dev deps (vitest, RTL, msw, playwright, eslint, stylelint, openapi-typescript-codegen); `npm install` succeeds with no peer-dep conflicts.

- [x] **T-019** [frontend] **Vite + TypeScript + ESLint config** — cluster: Foundation | deps: T-018 | FR-024,SC-009 | effort: M
  Done when: `vite.config.ts` (React plugin, dev proxy), `tsconfig.json` (ES2022, strict, `@/` alias), and `eslint.config.js` (custom no-inline-string-literals rule) are configured; lint test catches `<p>Hello</p>` and allows `<p>{t('key')}</p>`; `npm run lint` passes.

- [x] **T-020** [P] [frontend] **Stylelint logical-properties config** — cluster: Foundation | deps: T-018 | FR-025,SC-010 | effort: S
  Done when: `.stylelintrc.json` errors on `left`, `right`, `margin-left`, `margin-right`, `padding-left`, `padding-right`, `text-align: left/right` and border equivalents; sample violation triggers error; `npm run lint:css` passes.

- [x] **T-021** [frontend] **Tailwind CSS v4 logical-only config** — cluster: Foundation | deps: T-018 | FR-025,SC-010 | effort: S
  Done when: `tailwind.config.ts` enables only logical-property utilities (`ms-*`, `me-*`, `ps-*`, `pe-*`); `globals.css` imports Tailwind layers; physical-direction utilities (`ml-*`, `mr-*`) are not generated; `npm run build` succeeds.

- [x] **T-022** [frontend] **i18next setup with English locale** — cluster: Foundation | deps: T-018 | FR-024,SC-009 | effort: S
  Done when: `frontend/src/i18n/index.ts` initialises i18next with fallback `en`, interpolation escaping; `en.json` contains all ≈50 Phase 1 keys from plan.md (`auth.*`, `query.*`, `history.*`, `error.*`, `evaluator.*`); `t()` works in a unit test.

- [x] **T-023** [frontend] **React Router scaffolding** — cluster: Foundation | deps: T-019,T-022 | FR-002,FR-006 | effort: S
  Done when: `App.tsx` sets up routes `/sign-in` → SignInPage, `/` → AskQuestionPage (auth-guarded), `/history` → HistoryPage (auth-guarded), `/history/:id` → HistoryPage; each page renders placeholder heading via `t()`; unauthenticated → redirect to `/sign-in`.

- [x] **T-024** [P] [frontend] **TanStack Query provider + defaults** — cluster: Foundation | deps: T-018 | | effort: S
  Done when: `main.tsx` wraps app in `QueryClientProvider` (staleTime 5min, retry 1 mutations, retry 2 queries); `api-client.ts` exports fetch wrapper with `credentials: 'include'`; global error handler redirects to `/sign-in` on 401.

- [x] **T-025** [P] [test] **MSW setup for tests** — cluster: Foundation | deps: T-018 | | effort: S
  Done when: `frontend/src/mocks/handlers.ts` (empty array), `browser.ts` (service worker), `server.ts` (`setupServer`) are created; smoke test imports `server.ts`, starts/stops, passes.

- [x] **T-026** [frontend] **OpenAPI client generation script** — cluster: Foundation | deps: T-018 | | effort: S
  Done when: `package.json` contains `gen:api` script reading `contracts/openapi.yaml` and emitting TypeScript into `src/api/generated/`; `npm run gen:api` produces typed interfaces; `tsc --noEmit` passes.

### Infrastructure (frontend + compose + CI + docs)

- [x] **T-027** [P] [infra] **Frontend Dockerfile** — cluster: Foundation | deps: T-018 | | effort: S
  Done when: `frontend/Dockerfile` uses multi-stage build (node builder + nginx runtime); nginx serves SPA with `default.conf` routing all paths to `index.html`; `docker build -t querycraft-frontend frontend/` succeeds.

- [x] **T-028** [infra] **Docker Compose dev environment** — cluster: Foundation | deps: T-015,T-027 | | effort: M
  Done when: `docker-compose.dev.yml` defines five services (backend, frontend, platform-db Postgres 16, source-db Postgres 16 with sample init, redis 7) on shared network; env vars templated via `.env.example`; `docker compose -f docker-compose.dev.yml config` validates.

- [x] **T-029** [P] [infra] **CI pipeline skeleton** — cluster: Foundation | deps: T-002,T-018 | | effort: M
  Done when: `.github/workflows/ci.yml` triggers on push/PR to `main` and `001-core-text-to-sql`; three parallel jobs (backend lint+test+cov, frontend lint+typecheck+test+build, contract schemathesis); dependency caching; YAML is valid.

- [x] **T-030** [P] [docs] **Repo-root README with quickstart** — cluster: Foundation | deps: T-028 | | effort: S
  Done when: `README.md` contains project title, architecture overview, local-dev quickstart (clone → `.env.example` → docker compose up → Alembic → seed → sign in), links to specs and CI badge; new developer zero-to-signed-in in <10 minutes.

---

## Cluster: US-1 — Ask, Validate, See a Table, Accept
**Goal:** Deliver the irreducible core loop: sign in → ask a question → LLM generates SQL → evaluator validates → execute against source DB → render paginated table with SQL → accept to history.

### Architectural-invariant tests (Constitution Principle I)

- [x] **T-031** [P] [test] **Session cookie security flags** — cluster: US-1 | deps: T-011 | FR-003,SC-001 | effort: S
  Done when: `backend/tests/unit/test_session_cookie_flags.py` asserts sign-in response sets `HttpOnly`, `Secure`, `SameSite=Strict` on the `session_id` cookie and tests fail if any flag is missing.

- [x] **T-032** [P] [test] **Origin header validation enforcement** — cluster: US-1 | deps: T-011 | FR-003 | effort: S
  Done when: `backend/tests/unit/test_origin_enforcement.py` asserts POST with missing/invalid Origin returns 403 and GET bypasses the check; tests pass against the running middleware.

- [x] **T-033** [P] [test] **Argon2id password verification** — cluster: US-1 | deps: T-011 | FR-001 | effort: S
  Done when: `backend/tests/unit/test_argon2_verification.py` asserts `verify_password` returns True for correct password, False for wrong password, and the hash uses Argon2id variant.

### Architectural-invariant tests (Constitution Principles II & III)

- [x] **T-034** [P] [test] **Evaluator gate — no bypass path** — cluster: US-1 | deps: T-017 | SC-002 | effort: S
  Done when: `backend/tests/integration/test_evaluator_gate.py` submits a question with a mock evaluator returning FAIL and asserts the source DB executor is never called.

- [x] **T-035** [P] [test] **Accept-only persistence — reject writes nothing** — cluster: US-1 | deps: T-017 | SC-012 | effort: S
  Done when: `backend/tests/integration/test_accept_only_persistence.py` calls reject and regenerate handlers and asserts zero rows exist in `accepted_queries`.

### Backend Pydantic schemas

- [x] **T-036** [P] [test] **Auth schema validation** — cluster: US-1 | deps: T-002 | FR-001 | effort: XS
  Done when: `backend/tests/unit/test_schemas_auth.py` validates `SignInRequest` rejects empty username, empty password, and username >64 chars; `UserProfile` round-trips all required fields.

- [x] **T-037** [backend] **Auth Pydantic schemas** — cluster: US-1 | deps: T-036 | FR-001 | effort: S
  Done when: `backend/src/app/schemas/auth.py` defines `SignInRequest` and `UserProfile` matching openapi.yaml `SignInRequest` and `UserProfile` schemas; all T-036 tests pass.

- [x] **T-038** [P] [test] **Query schema validation** — cluster: US-1 | deps: T-002 | FR-007,FR-014,FR-015 | effort: S
  Done when: `backend/tests/unit/test_schemas_query.py` validates `SubmitQuestionRequest` rejects empty/whitespace/over-2000-char questions; `QueryResult` enforces `kind="result"` discriminator and required fields; `EvaluatorRejection` and `RefinePrompt` round-trip correctly.

- [x] **T-039** [backend] **Query Pydantic schemas** — cluster: US-1 | deps: T-038 | FR-007,FR-014,FR-015,FR-028 | effort: S
  Done when: `backend/src/app/schemas/query.py` defines `SubmitQuestionRequest`, `QueryResult`, `ColumnMeta`, `EvaluatorRejection`, `Violation`, `AcceptQueryRequest`, `RejectQueryRequest`, `RefinePrompt`, `AcceptedQuerySummary` matching openapi.yaml; all T-038 tests pass.

- [x] **T-040** [P] [test] **History schema validation** — cluster: US-1 | deps: T-002 | FR-021,FR-023 | effort: XS
  Done when: `backend/tests/unit/test_schemas_history.py` validates `HistoryListResponse` contains items list and nullable cursor; `AcceptedQueryDetail` includes all required fields per openapi.yaml.

- [x] **T-041** [backend] **History Pydantic schemas** — cluster: US-1 | deps: T-040 | FR-021,FR-023 | effort: XS
  Done when: `backend/src/app/schemas/history.py` defines `HistoryListResponse` and `AcceptedQueryDetail` matching openapi.yaml; all T-040 tests pass.

### Backend ORM models

- [x] **T-042** [P] [test] **ORM model unit tests** — cluster: US-1 | deps: T-006 | FR-001,FR-004,FR-016 | effort: S
  Done when: `backend/tests/unit/test_orm_models.py` asserts `User`, `AcceptedQuery`, `DatabaseConnection`, `AppConfig` models can be instantiated, have correct table names, and column types match data-model.md.

- [x] **T-043** [backend] **ORM models** — cluster: US-1 | deps: T-042,T-006 | FR-001,FR-004,FR-016,FR-027 | effort: M
  Done when: `backend/src/app/db/models/user.py`, `accepted_query.py`, `database_connection.py`, `app_config.py` define SQLAlchemy 2.0 mapped classes matching data-model.md exactly; all T-042 tests pass.

### Backend repositories

- [x] **T-044** [P] [test] **UserRepository tests** — cluster: US-1 | deps: T-017 | FR-001 | effort: S
  Done when: `backend/tests/integration/test_user_repository.py` tests `get_by_username` returns the seeded admin user and returns None for unknown username, using testcontainers PostgreSQL.

- [x] **T-045** [backend] **UserRepository** — cluster: US-1 | deps: T-044,T-043 | FR-001 | effort: S
  Done when: `backend/src/app/repositories/user_repository.py` implements `get_by_username(username) → User | None`; all T-044 tests pass.

- [x] **T-046** [P] [test] **AcceptedQueryRepository tests** — cluster: US-1 | deps: T-017 | FR-016,FR-021 | effort: S
  Done when: `backend/tests/integration/test_accepted_query_repository.py` tests `create`, `list_by_user` (reverse-chrono, cursor pagination), and `get_by_id`; verifies FK constraints and index usage.

- [x] **T-047** [backend] **AcceptedQueryRepository** — cluster: US-1 | deps: T-046,T-043 | FR-016,FR-021,FR-023 | effort: M
  Done when: `backend/src/app/repositories/accepted_query_repository.py` implements `create`, `list_by_user(user_id, cursor, limit) → (list, next_cursor)`, `get_by_id(query_id, user_id) → AcceptedQuery | None`; all T-046 tests pass.

### Backend services

- [x] **T-048** [P] [test] **AuthService tests** — cluster: US-1 | deps: T-017 | FR-001,FR-002,FR-003 | effort: S
  Done when: `backend/tests/unit/test_auth_service.py` tests sign-in with correct/incorrect credentials, session creation in Redis, sign-out deletes session, and `get_me` returns profile; uses mocked repository and Redis.

- [x] **T-049** [backend] **AuthService** — cluster: US-1 | deps: T-048,T-045,T-014 | FR-001,FR-002,FR-003 | effort: M
  Done when: `backend/src/app/services/auth_service.py` implements `sign_in(username, password) → (UserProfile, session_id)`, `sign_out(session_id)`, `get_me(session_id) → UserProfile`; all T-048 tests pass.

- [x] **T-050** [P] [test] **QueryService submit tests** — cluster: US-1 | deps: T-017 | FR-006,FR-007,FR-008,FR-010,FR-013,FR-014,FR-030,SC-001,SC-002 | effort: M
  Done when: `backend/tests/unit/test_query_service_submit.py` tests: (1) happy path returns QueryResult with columns/rows, (2) evaluator failure returns EvaluatorRejection, (3) LLM error returns 502 error, (4) source-DB timeout returns 504, (5) concurrent submission returns 409, (6) attempt stored in Redis with session ownership; uses mocked LLM, evaluator, and source-DB.

- [x] **T-051** [P] [test] **QueryService accept tests** — cluster: US-1 | deps: T-017 | FR-016,FR-020,SC-012 | effort: S
  Done when: `backend/tests/unit/test_query_service_accept.py` tests: (1) accept persists to AcceptedQueryRepository, (2) accept deletes Redis attempt, (3) accept with expired attempt returns 400, (4) accept with wrong session returns 400.

- [x] **T-052** [backend] **QueryService** — cluster: US-1 | deps: T-050,T-051,T-047,T-014 | FR-006,FR-007,FR-008,FR-010,FR-012,FR-013,FR-014,FR-016,FR-020,FR-027,FR-030 | effort: L
  Done when: `backend/src/app/services/query_service.py` implements `submit_question`, `accept_query` with Redis mutex (FR-030), ephemeral attempt storage, evaluator gate, source-DB execution with timeout, and accept-only persistence; all T-050 and T-051 tests pass.

- [x] **T-053** [P] [test] **HistoryService tests** — cluster: US-1 | deps: T-017 | FR-021,FR-023 | effort: S
  Done when: `backend/tests/unit/test_history_service.py` tests `list_history` returns reverse-chronological entries with cursor, `get_detail` returns full entry or 404; uses mocked repository.

- [x] **T-054** [backend] **HistoryService** — cluster: US-1 | deps: T-053,T-047 | FR-021,FR-022,FR-023 | effort: S
  Done when: `backend/src/app/services/history_service.py` implements `list_history(user_id, cursor, limit)` and `get_detail(query_id, user_id)`; all T-053 tests pass.

### Backend routers

- [x] **T-055** [P] [test] **Auth router integration tests** — cluster: US-1 | deps: T-049,T-013 | FR-001,FR-002,FR-003 | effort: S
  Done when: `backend/tests/integration/test_api_auth.py` tests POST `/auth/sign-in` (200 + cookie, 401 wrong creds, 422 empty fields), POST `/auth/sign-out` (204, 401 unauthenticated), GET `/auth/me` (200 profile, 401 expired); uses ASGI transport.

- [x] **T-056** [backend] **Auth router** — cluster: US-1 | deps: T-055,T-049,T-037 | FR-001,FR-002,FR-003 | effort: S
  Done when: `backend/src/app/api/v1/auth.py` exposes `POST /auth/sign-in`, `POST /auth/sign-out`, `GET /auth/me` matching openapi.yaml; all T-055 tests pass.

- [x] **T-057** [P] [test] **Query router integration tests** — cluster: US-1 | deps: T-052,T-013 | FR-006,FR-007,FR-014,FR-016,SC-001,SC-002 | effort: M
  Done when: `backend/tests/integration/test_api_query.py` tests POST `/query/submit` (200 QueryResult, 400 validation, 401 unauth, 409 concurrent, 422 evaluator rejection, 502 LLM down, 504 timeout), POST `/query/accept` (201 persisted, 400 expired/invalid); uses authenticated_client and mock_llm fixtures.

- [x] **T-058** [backend] **Query router** — cluster: US-1 | deps: T-057,T-052,T-039 | FR-006,FR-007,FR-014,FR-015,FR-016,FR-028 | effort: M
  Done when: `backend/src/app/api/v1/query.py` exposes `POST /query/submit` and `POST /query/accept` matching openapi.yaml response schemas and status codes; all T-057 tests pass.

- [x] **T-059** [P] [test] **History router integration tests** — cluster: US-1 | deps: T-054,T-013 | FR-021,FR-023 | effort: S
  Done when: `backend/tests/integration/test_api_history.py` tests GET `/history` (200 list, cursor pagination, 401 unauth), GET `/history/{id}` (200 detail, 404 not found); uses authenticated_client with pre-seeded accepted queries.

- [x] **T-060** [backend] **History router** — cluster: US-1 | deps: T-059,T-054,T-041 | FR-021,FR-022,FR-023 | effort: S
  Done when: `backend/src/app/api/v1/history.py` exposes `GET /history` and `GET /history/{id}` matching openapi.yaml; all T-059 tests pass.

### Frontend: OpenAPI client regeneration

- [x] **T-061** [frontend] **Regenerate OpenAPI TypeScript client** — cluster: US-1 | deps: T-026,T-056,T-058,T-060 | FR-001,FR-014,FR-021 | effort: XS
  Done when: `npm run gen:api` produces updated `frontend/src/api/generated/` types matching the implemented backend endpoints; `tsc --noEmit` passes.

### Frontend hooks

- [x] **T-062** [P] [test] **useAuth hook tests** — cluster: US-1 | deps: T-025,T-061 | FR-001,FR-002 | effort: S
  Done when: `frontend/tests/unit/useAuth.test.tsx` tests sign-in mutation calls API and sets query cache, sign-out clears cache and redirects, `useAuth` returns user profile when authenticated and null when not; uses MSW server.

- [x] **T-063** [frontend] **useAuth hook** — cluster: US-1 | deps: T-062,T-024,T-061 | FR-001,FR-002,FR-003 | effort: S
  Done when: `frontend/src/hooks/useAuth.ts` implements `useAuth()` returning `{ user, isLoading, signIn, signOut }` using TanStack Query mutations backed by generated API client; all T-062 tests pass.

- [x] **T-064** [P] [test] **useQuerySubmit hook tests** — cluster: US-1 | deps: T-025,T-061 | FR-006,FR-007,FR-014,FR-016 | effort: S
  Done when: `frontend/tests/unit/useQuerySubmit.test.tsx` tests submit mutation returns QueryResult, accept mutation returns AcceptedQuerySummary, handles 422 evaluator rejection, handles 409 concurrent error, and disables submit while processing (FR-030); uses MSW server.

- [x] **T-065** [frontend] **useQuerySubmit hook** — cluster: US-1 | deps: T-064,T-024,T-061 | FR-006,FR-007,FR-014,FR-015,FR-016,FR-030 | effort: M
  Done when: `frontend/src/hooks/useQuerySubmit.ts` implements `useSubmitQuestion()`, `useAcceptQuery()`, `useHistory()` returning TanStack Query mutations/queries; all T-064 tests pass. US-2 exports (useRejectQuery, useRegenerateQuery) removed. Hook returns strict QueryResult on submit.

### Frontend components

- [x] **T-066** [P] [test] **SignInForm component tests** — cluster: US-1 | deps: T-025,T-063 | FR-001,FR-002 | effort: S
  Done when: `frontend/tests/unit/SignInForm.test.tsx` tests form renders with i18n keys, validates empty fields, calls signIn on submit, shows error on 401, and redirects on success; uses RTL + MSW.

- [x] **T-067** [frontend] **SignInForm + SignInPage** — cluster: US-1 | deps: T-066,T-063,T-022,T-023 | FR-001,FR-002,SC-009 | effort: M
  Done when: `frontend/src/components/SignInForm.tsx` renders a RHF+Zod form with i18n strings, `frontend/src/pages/SignInPage.tsx` wraps SignInForm with layout; all T-066 tests pass and `npm run lint` shows no inline string violations.

- [x] **T-068** [P] [test] **QueryInput component tests** — cluster: US-1 | deps: T-025,T-065 | FR-006,FR-007,SC-009 | effort: S
  Done when: `frontend/tests/unit/QueryInput.test.tsx` tests textarea renders with i18n placeholder, enforces 2000-char limit with live counter, disables submit on empty/whitespace, disables submit while processing, and calls submitQuestion on enter/click; uses RTL.

- [x] **T-069** [frontend] **QueryInput component** — cluster: US-1 | deps: T-068,T-065,T-022 | FR-006,FR-007,FR-030,SC-009 | effort: S
  Done when: `frontend/src/components/QueryInput.tsx` renders a chat-style input with char counter, submit button, and processing lock; all i18n keys from `en.json`; all T-068 tests pass.

- [x] **T-070** [P] [test] **ResultTable + QueryActions component tests** — cluster: US-1 | deps: T-025,T-065 | FR-014,FR-015,FR-029,SC-009 | effort: S
  Done when: `frontend/tests/unit/ResultTable.test.tsx` tests TanStack Table renders columns/rows from QueryResult, shows "no results" message on zero rows (FR-029), displays generated SQL, and renders Accept button with i18n label; uses RTL. US-2 assertions (Reject/Regenerate) removed.

- [x] **T-071** [frontend] **ResultTable + SqlDisplay + QueryActions** — cluster: US-1 | deps: T-070,T-065,T-022 | FR-014,FR-015,FR-029,SC-009 | effort: M
  Done when: `frontend/src/components/ResultTable.tsx` renders TanStack Table with pagination, `SqlDisplay.tsx` shows syntax-highlighted SQL, `QueryActions.tsx` renders Accept only; all T-070 tests pass.

- [x] **T-072** [P] [test] **AskQuestionPage integration tests** — cluster: US-1 | deps: T-025,T-069,T-071 | FR-006,FR-014,SC-001 | effort: S
  Done when: `frontend/tests/unit/AskQuestionPage.test.tsx` tests AskQuestionPage renders QueryInput, submitting a question shows ResultTable with QueryActions, accepting shows confirmation alert, and evaluator rejection shows error message; uses MSW + RTL. US-2 tests (reject/regenerate/refine) removed.

- [x] **T-073** [frontend] **AskQuestionPage assembly** — cluster: US-1 | deps: T-072,T-069,T-071,T-023 | FR-006,FR-014,FR-015,FR-016,SC-009 | effort: M
  Done when: `frontend/src/pages/AskQuestionPage.tsx` composes QueryInput, ResultTable, SqlDisplay, QueryActions into the main query interface with inline alert for confirmations/errors; all T-072 tests pass.

### Playwright e2e — US-1 independent test criterion

- [x] **T-074** [test] **E2E: sign in → ask → see table → accept → verify in history** — cluster: US-1 | deps: T-028,T-073,T-060 | FR-001,FR-006,FR-014,FR-016,FR-021,SC-001 | effort: L
  Done when: `frontend/tests/e2e/auth.spec.ts` and `frontend/tests/e2e/query-flow.spec.ts` run against docker-compose.dev.yml: (1) navigates to `/`, is redirected to `/sign-in`, (2) signs in with admin credentials, (3) types a question and submits, (4) sees a table result with generated SQL and Accept/Reject/Regenerate buttons, (5) clicks Accept and sees confirmation, (6) navigates to `/history` and sees the accepted query; all assertions pass in CI-compatible headless Chromium.

## Cluster: US-2 (backend) — Reject, Regenerate, Evaluator, LLM Adapters, Source-DB
**Goal:** Implement the reject/retry state machine, four evaluator rules, four LLM adapters, source-DB execution with timeout, schema introspection with caching, and all supporting infrastructure (Redis lock, ephemeral attempts). Backend only — frontend tasks follow in Part 3b.

### LLM provider abstraction

- [x] **T-075** [P] [test] **LLMProvider protocol contract tests** — cluster: US-2 | deps: T-002 | FR-009 | effort: S
  Done when: `backend/tests/unit/test_llm_protocol.py` defines a test that instantiates each of the four adapters and asserts they satisfy the `LLMProvider` protocol (`generate_sql` signature with `question`, `schema_context`, `negative_examples`).

- [x] **T-076** [backend] **LLMProvider protocol** — cluster: US-2 | deps: T-075 | FR-009 | effort: XS
  Done when: `backend/src/app/llm/base.py` defines `LLMProvider` as a `typing.Protocol` with `async def generate_sql(self, question: str, schema_context: str, negative_examples: list[str] | None = None) -> str`; T-075 protocol check compiles.

- [ ] **T-077** [P] [test] **AnthropicAdapter unit test** — cluster: US-2 | deps: T-076 | FR-009 | effort: S
  Done when: `backend/tests/unit/test_llm_anthropic.py` mocks `httpx.AsyncClient.post` and asserts `generate_sql` sends the correct Messages API payload, extracts SQL from the response, and raises on HTTP errors.

- [x] **T-078** [backend] **AnthropicAdapter** — cluster: US-2 | deps: T-077,T-076 | FR-009 | effort: S
  Done when: `backend/src/app/llm/anthropic_adapter.py` implements `LLMProvider` using `httpx` against the Anthropic Messages API; all T-077 tests pass.

- [ ] **T-079** [P] [test] **OpenAIAdapter unit test** — cluster: US-2 | deps: T-076 | FR-009 | effort: S
  Done when: `backend/tests/unit/test_llm_openai.py` mocks `httpx.AsyncClient.post` and asserts `generate_sql` sends the correct Chat Completions payload and extracts SQL from the response.

- [x] **T-080** [backend] **OpenAIAdapter** — cluster: US-2 | deps: T-079,T-076 | FR-009 | effort: S
  Done when: `backend/src/app/llm/openai_adapter.py` implements `LLMProvider` using `httpx` against the OpenAI Chat Completions API; all T-079 tests pass.

- [ ] **T-081** [P] [test] **GeminiAdapter unit test** — cluster: US-2 | deps: T-076 | FR-009 | effort: S
  Done when: `backend/tests/unit/test_llm_gemini.py` mocks `httpx.AsyncClient.post` and asserts `generate_sql` sends the correct Gemini generateContent payload and extracts SQL.

- [x] **T-082** [backend] **GeminiAdapter** — cluster: US-2 | deps: T-081,T-076 | FR-009 | effort: S
  Done when: `backend/src/app/llm/gemini_adapter.py` implements `LLMProvider` using `httpx` against the Gemini API; all T-081 tests pass.

- [ ] **T-083** [P] [test] **OllamaAdapter unit test** — cluster: US-2 | deps: T-076 | FR-009 | effort: S
  Done when: `backend/tests/unit/test_llm_ollama.py` mocks `httpx.AsyncClient.post` and asserts `generate_sql` sends the correct Ollama `/api/generate` payload and extracts SQL.

- [x] **T-084** [backend] **OllamaAdapter** — cluster: US-2 | deps: T-083,T-076 | FR-009 | effort: S
  Done when: `backend/src/app/llm/ollama_adapter.py` implements `LLMProvider` using `httpx` against `LLM_BASE_URL_OLLAMA`; all T-083 tests pass.

- [ ] **T-085** [test] **LLM factory selection test** — cluster: US-2 | deps: T-078,T-080,T-082,T-084 | FR-009,FR-026,SC-008 | effort: S
  Done when: `backend/tests/unit/test_llm_factory.py` asserts `create_llm_provider(settings)` returns the correct adapter for each `LLM_PROVIDER` enum value and raises on unsupported values.

- [x] **T-086** [backend] **LLM factory** — cluster: US-2 | deps: T-085 | FR-009,FR-026 | effort: XS
  Done when: `backend/src/app/llm/factory.py` implements `create_llm_provider(settings: Settings) -> LLMProvider` selecting by `settings.LLM_PROVIDER`; all T-085 tests pass.

- [x] **T-087** [P] [backend] **Prompt builder** — cluster: US-2 | deps: T-076 | FR-008 | effort: S
  Done when: `backend/src/app/llm/prompt.py` implements `build_prompt(question, schema_context, negative_examples) -> str` following R-001 prompt structure; a unit test in `backend/tests/unit/test_prompt_builder.py` asserts schema injection, negative-example block, and SQL-fence extraction.

### Evaluator pipeline and rules

- [x] **T-088** [P] [test] **EvaluatorRule protocol + pipeline tests** — cluster: US-2 | deps: T-002 | FR-010,FR-011 | effort: S
  Done when: `backend/tests/unit/test_evaluator_pipeline.py` asserts the pipeline fans out to all registered rules, collects violations, and returns `EvaluatorResult(passed=True)` when no violations and `passed=False` otherwise.

- [x] **T-089** [backend] **Evaluator base + pipeline** — cluster: US-2 | deps: T-088 | FR-010,FR-011 | effort: S
  Done when: `backend/src/app/evaluator/base.py` defines `EvaluatorRule` protocol and `EvaluatorResult`/`EvaluatorViolation` dataclasses; `pipeline.py` implements `evaluate(sql, schema) -> EvaluatorResult` fanning out to rules; all T-088 tests pass.

- [ ] **T-090** [P] [test] **ReadOnlyRule unit tests** — cluster: US-2 | deps: T-089 | FR-010,SC-003 | effort: M
  Done when: `backend/tests/unit/test_rule_read_only.py` tests pass cases (SELECT, CTE, subquery, DISTINCT ON, window functions) and fail cases (INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, CREATE — 7 data-modifying keywords); at least 15 test cases.

- [ ] **T-091** [backend] **ReadOnlyRule** — cluster: US-2 | deps: T-090 | FR-010,SC-003 | effort: S
  Done when: `backend/src/app/evaluator/rules/read_only_rule.py` parses SQL with `sqlglot` (postgres dialect), rejects any non-SELECT/CTE AST node, and returns violations with `evaluator.violation.dataModifying` message key; all T-090 tests pass.

- [ ] **T-092** [P] [test] **SingleStatementRule unit tests** — cluster: US-2 | deps: T-089 | FR-010 | effort: S
  Done when: `backend/tests/unit/test_rule_single_statement.py` tests pass case (single SELECT) and fail cases (two SELECTs separated by semicolon, SELECT followed by DROP); at least 5 test cases.

- [ ] **T-093** [backend] **SingleStatementRule** — cluster: US-2 | deps: T-092 | FR-010 | effort: XS
  Done when: `backend/src/app/evaluator/rules/single_statement_rule.py` rejects SQL containing multiple statements; all T-092 tests pass.

- [ ] **T-094** [P] [test] **SchemaValidationRule unit tests** — cluster: US-2 | deps: T-089 | FR-010,SC-004 | effort: M
  Done when: `backend/tests/unit/test_rule_schema_validation.py` tests pass cases (references existing tables/columns) and fail cases (unknown table, unknown column, aliased table with wrong column); at least 10 test cases with a mock `SchemaContext`.

- [ ] **T-095** [backend] **SchemaValidationRule** — cluster: US-2 | deps: T-094 | FR-010,SC-004 | effort: M
  Done when: `backend/src/app/evaluator/rules/schema_validation_rule.py` extracts table/column refs via `sqlglot`, validates against `SchemaContext`, and returns violations with `evaluator.violation.unknownTable`/`unknownColumn` keys; all T-094 tests pass.

- [ ] **T-096** [P] [test] **UnsafePatternRule unit tests** — cluster: US-2 | deps: T-089 | FR-010 | effort: S
  Done when: `backend/tests/unit/test_rule_unsafe_pattern.py` tests pass cases (normal SELECT) and fail cases (platform-defined patterns like `pg_sleep`, `COPY`, `SET ROLE`); at least 6 test cases.

- [ ] **T-097** [backend] **UnsafePatternRule** — cluster: US-2 | deps: T-096 | FR-010 | effort: S
  Done when: `backend/src/app/evaluator/rules/unsafe_pattern_rule.py` checks for platform-defined unsafe patterns and returns violations; all T-096 tests pass.

- [ ] **T-098** [P] [backend] **SchemaContext model** — cluster: US-2 | deps: T-089 | FR-008,FR-010 | effort: S
  Done when: `backend/src/app/evaluator/schema_context.py` defines `SchemaContext` dataclass with `tables: dict[str, list[ColumnInfo]]` and `foreign_keys` list, plus `to_prompt_string()` for LLM context and lookup methods for evaluator validation.

### Source-DB introspector + connector + executor

- [ ] **T-099** [P] [test] **SchemaIntrospector unit tests** — cluster: US-2 | deps: T-017 | FR-008 | effort: S
  Done when: `backend/tests/integration/test_introspector.py` tests introspector against testcontainers PostgreSQL with a known schema, asserts correct table/column/FK extraction, TTL cache re-reads after expiry, and manual refresh clears cache.

- [ ] **T-100** [backend] **SchemaIntrospector** — cluster: US-2 | deps: T-099,T-098 | FR-008 | effort: M
  Done when: `backend/src/app/source_db/introspector.py` queries `information_schema` for tables/columns/FKs, builds `SchemaContext`, caches with `SCHEMA_CACHE_TTL_SECONDS`, and exposes `refresh()` method; all T-099 tests pass.

- [ ] **T-101** [test] **SchemaTokenLimitExceeded test** — cluster: US-2 | deps: T-100 | | effort: S
  Done when: `backend/tests/unit/test_schema_token_limit.py` asserts that when token count exceeds `MAX_SCHEMA_TOKENS`, `SchemaTokenLimitExceeded` is raised with the computed count and configured limit.

- [ ] **T-102** [backend] **Schema token limit escalation** — cluster: US-2 | deps: T-101,T-100 | | effort: S
  Done when: `backend/src/app/source_db/introspector.py` computes approximate token count after introspection and raises `SchemaTokenLimitExceeded` (defined in `core/exceptions.py`) when it exceeds `MAX_SCHEMA_TOKENS`; T-101 test passes.

- [ ] **T-103** [P] [test] **SourceDBConnector read-only test** — cluster: US-2 | deps: T-017 | FR-005,FR-013 | effort: S
  Done when: `backend/tests/integration/test_source_db_connector.py` asserts the connector creates a read-only asyncpg pool using decrypted credentials and that INSERT/UPDATE statements fail at the DB level.

- [ ] **T-104** [backend] **SourceDBConnector** — cluster: US-2 | deps: T-103,T-009 | FR-005,FR-013 | effort: S
  Done when: `backend/src/app/source_db/connector.py` creates an async connection pool with read-only role credentials decrypted via `core/encryption.py`; all T-103 tests pass.

- [ ] **T-105** [test] **SourceDBExecutor timeout test** — cluster: US-2 | deps: T-104 | FR-012,FR-013,SC-011 | effort: S
  Done when: `backend/tests/integration/test_source_db_executor.py` asserts that a query exceeding `QUERY_TIMEOUT_SECONDS` is cancelled and raises a timeout error, and that a normal query returns rows and column metadata.

- [ ] **T-106** [backend] **SourceDBExecutor** — cluster: US-2 | deps: T-105,T-104 | FR-012,FR-013,SC-011 | effort: M
  Done when: `backend/src/app/source_db/executor.py` implements `execute(sql, timeout) -> (columns, rows)` using `statement_timeout` and `asyncio.wait_for`; all T-105 tests pass.

### Redis infrastructure: processing lock + ephemeral attempts

- [ ] **T-107** [P] [test] **Redis processing lock tests** — cluster: US-2 | deps: T-014 | FR-030 | effort: S
  Done when: `backend/tests/unit/test_processing_lock.py` asserts: (1) acquiring lock returns True when free, (2) acquiring lock returns False when held by same session, (3) lock is released in finally block, (4) lock TTL matches `query_timeout + 10` capped at 60.

- [ ] **T-108** [backend] **Redis processing lock** — cluster: US-2 | deps: T-107,T-014 | FR-030 | effort: S
  Done when: `backend/src/app/core/processing_lock.py` implements `acquire_lock(session_id, redis) -> bool` and `release_lock(session_id, redis)` using `SET NX EX`; all T-107 tests pass.

- [ ] **T-109** [P] [test] **Ephemeral attempt storage tests** — cluster: US-2 | deps: T-014 | | effort: S
  Done when: `backend/tests/unit/test_attempt_store.py` asserts: (1) store creates key `attempt:{id}` with 15-min TTL, (2) get returns attempt data, (3) get with wrong session_id raises ownership error, (4) delete removes key, (5) expired key returns None.

- [ ] **T-110** [backend] **Ephemeral attempt store** — cluster: US-2 | deps: T-109,T-014 | | effort: S
  Done when: `backend/src/app/core/attempt_store.py` implements `store_attempt`, `get_attempt(attempt_id, session_id)`, `delete_attempt` against Redis with 15-min TTL and session ownership validation; all T-109 tests pass.

### QueryService reject/regenerate + state machine

- [ ] **T-111** [P] [test] **QueryService reject tests** — cluster: US-2 | deps: T-017,T-110 | FR-017,FR-018,FR-020,SC-005,SC-012 | effort: M
  Done when: `backend/tests/unit/test_query_service_reject.py` tests: (1) reject attempt #1 triggers LLM with negative context and returns new QueryResult, (2) byte-equal regenerated SQL returns RefinePrompt, (3) reject attempt #2 returns RefinePrompt, (4) rejected SQL not written to `accepted_queries`, (5) attempt ownership validated.

- [ ] **T-112** [P] [test] **QueryService regenerate tests** — cluster: US-2 | deps: T-017,T-110 | FR-019,SC-005 | effort: S
  Done when: `backend/tests/unit/test_query_service_regenerate.py` tests that regenerate behaves identically to reject (same one-retry limit, same byte-equal detection, same RefinePrompt on second rejection).

- [ ] **T-113** [backend] **QueryService reject + regenerate** — cluster: US-2 | deps: T-111,T-112,T-052,T-086,T-089,T-106,T-108,T-110 | FR-017,FR-018,FR-019,FR-020,SC-005,SC-012 | effort: L
  Done when: `backend/src/app/services/query_service.py` adds `reject_query` and `regenerate_query` methods implementing the state machine from plan.md: negative-context LLM call, byte-equal detection, evaluator re-check, max-retry enforcement, ephemeral Redis lifecycle, and processing lock; all T-111 and T-112 tests pass.
  > **Note:** Inv 4 logic implemented here; dedicated invariant assertion test deferred to T-159 (US-4).

### Backend routers: reject, regenerate, admin

- [ ] **T-114** [P] [test] **Reject router integration test** — cluster: US-2 | deps: T-113,T-013 | FR-017,FR-018 | effort: S
  Done when: `backend/tests/integration/test_api_reject.py` tests POST `/query/reject` returns 200 with `QueryResult` (kind=result) on first rejection, 200 with `RefinePrompt` (kind=refine) on second rejection, 400 on expired attempt, 401 on unauthenticated.

- [ ] **T-115** [backend] **Reject router** — cluster: US-2 | deps: T-114,T-113,T-039 | FR-017,FR-018 | effort: S
  Done when: `backend/src/app/api/v1/query.py` adds `POST /query/reject` matching openapi.yaml discriminated union response; all T-114 tests pass.

- [ ] **T-116** [P] [test] **Regenerate router integration test** — cluster: US-2 | deps: T-113,T-013 | FR-019 | effort: S
  Done when: `backend/tests/integration/test_api_regenerate.py` tests POST `/query/regenerate` returns 200 with `QueryResult` or `RefinePrompt` using the `kind` discriminator; same edge cases as reject.

- [ ] **T-117** [backend] **Regenerate router** — cluster: US-2 | deps: T-116,T-113,T-039 | FR-019 | effort: XS
  Done when: `backend/src/app/api/v1/query.py` adds `POST /query/regenerate` delegating to `QueryService.regenerate_query`; all T-116 tests pass.

- [ ] **T-118** [P] [test] **Admin refresh-schema router integration test** — cluster: US-2 | deps: T-100,T-013 | | effort: S
  Done when: `backend/tests/integration/test_api_admin.py` tests POST `/admin/refresh-schema` returns 200 with `tables_count`, `columns_count`, `approximate_tokens`, `refreshed_at`; returns 422 when schema exceeds token limit; returns 401 unauthenticated.

- [ ] **T-119** [backend] **Admin refresh-schema router** — cluster: US-2 | deps: T-118,T-100 | | effort: S
  Done when: `backend/src/app/api/v1/admin.py` exposes `POST /admin/refresh-schema` matching openapi.yaml; all T-118 tests pass.

### Architectural-invariant tests

- [ ] **T-120** [P] [test] **Invariant 1: Evaluator gate — no DB contact on eval failure** — cluster: US-2 | deps: T-113 | SC-002 | effort: S
  Done when: `backend/tests/integration/test_invariant_evaluator_gate.py` submits a question, mocks evaluator to return FAIL, and asserts `SourceDBExecutor.execute` was never called.

- [ ] **T-121** [P] [test] **Invariant 3: No concurrent submissions** — cluster: US-2 | deps: T-108,T-113 | FR-030 | effort: S
  Done when: `backend/tests/integration/test_invariant_no_concurrent.py` acquires the Redis lock for a session, submits a second question on the same session, and asserts 409 Conflict is returned.

- [ ] **T-122** [P] [test] **Invariant 5: Read-only source DB** — cluster: US-2 | deps: T-104 | FR-005 | effort: S
  Done when: `backend/tests/integration/test_invariant_read_only.py` attempts `INSERT INTO` and `DROP TABLE` via the SourceDBConnector and asserts both fail at the database level.

- [ ] **T-123** [P] [test] **Invariant 6: Ephemeral attempt ownership** — cluster: US-2 | deps: T-110 | | effort: S
  Done when: `backend/tests/unit/test_invariant_attempt_ownership.py` stores an attempt for session A, then calls `get_attempt` with session B, and asserts ownership validation error is raised.

### Schemathesis contract test

- [ ] **T-124** [test] **Schemathesis contract: /query/submit** — cluster: US-2 | deps: T-058 | SC-002 | effort: S
  Done when: `backend/tests/contract/test_openapi_contract.py` is extended with schemathesis-driven property tests for `POST /query/submit` validating that all response codes (200, 400, 401, 409, 422, 502, 504) conform to openapi.yaml schemas.

- [ ] **T-125** [test] **Schemathesis contract: /query/reject, /query/regenerate** — cluster: US-2 | deps: T-115,T-117 | FR-017,FR-019 | effort: S
  Done when: `backend/tests/contract/test_openapi_contract.py` is extended with schemathesis-driven property tests for `POST /query/reject` and `POST /query/regenerate` validating discriminated union responses (`kind=result` | `kind=refine`) conform to openapi.yaml.

- [ ] **T-126** [P] [test] **Schemathesis contract: /admin/refresh-schema** — cluster: US-2 | deps: T-119 | | effort: XS
  Done when: `backend/tests/contract/test_openapi_contract.py` is extended with schemathesis-driven property tests for `POST /admin/refresh-schema` validating 200 and 422 responses conform to openapi.yaml.

### Custom exceptions module

- [ ] **T-127** [P] [test] **Custom exceptions test** — cluster: US-2 | deps: T-002 | | effort: XS
  Done when: `backend/tests/unit/test_exceptions.py` asserts all custom exceptions (`EvaluatorRejectionError`, `LLMUnavailableError`, `QueryTimeoutError`, `ConcurrentSubmissionError`, `AttemptExpiredError`, `AttemptOwnershipError`, `SchemaTokenLimitExceeded`) can be instantiated with expected attributes.

- [ ] **T-128** [backend] **Custom exceptions module** — cluster: US-2 | deps: T-127 | | effort: XS
  Done when: `backend/src/app/core/exceptions.py` defines all custom exception classes with message-key attributes for i18n-compatible error responses; all T-127 tests pass.

## Cluster: US-2 (frontend) — Reject, Regenerate, Error States, E2E
**Goal:** Wire the frontend to the US-2 backend: OpenAPI client regen, MSW test handlers for all /query error codes, AskQuestionPage + QueryInput + ResultTable + SqlDisplay + error-state components with RTL tests, useSubmitQuestion hook with oneOf discrimination, i18n key verification, and Playwright e2e covering all US-2 acceptance scenarios.

### OpenAPI client regeneration

- [ ] **T-129** [frontend] **Regenerate OpenAPI client for US-2 endpoints** — cluster: US-2 | deps: T-061,T-115,T-117,T-119 | FR-017,FR-019 | effort: XS
  Done when: `npm run gen:api` produces updated `frontend/src/api/generated/` types including `rejectQuery`, `regenerateQuery`, `RefinePrompt` (with `kind` discriminator), and `refreshSchema`; `tsc --noEmit` passes.

### MSW handlers for /query/submit scenarios

- [ ] **T-130** [P] [test] **MSW handlers for /query/submit success, evaluator rejection, timeout, 409, 502** — cluster: US-2 | deps: T-025,T-129 | FR-007,FR-014,FR-017,FR-028,FR-030 | effort: S
  Done when: `frontend/src/mocks/handlers-query.ts` exports named handler factories for 200 `QueryResult`, 422 `EvaluatorRejection`, 504 timeout `ErrorResponse`, 409 concurrent `ErrorResponse`, and 502 LLM-unavailable `ErrorResponse`; a smoke test in `frontend/tests/unit/msw-handlers-query.test.ts` activates each handler, fetches, and asserts the expected status code and `kind`/`message_key` fields.

### useSubmitQuestion hook

- [ ] **T-131** [P] [test] **useSubmitQuestion hook RTL tests** — cluster: US-2 | deps: T-130 | FR-006,FR-007,FR-014,FR-017,FR-019,FR-030 | effort: M
  Done when: `frontend/tests/unit/useSubmitQuestion.test.tsx` tests: (1) submit returns `QueryResult` on 200, (2) reject returns `QueryResult` (kind=result) on first rejection, (3) reject returns `RefinePrompt` (kind=refine) on second rejection discriminated via `kind`, (4) regenerate mirrors reject behavior, (5) 409 sets `error.concurrent` state, (6) 502 sets `error.llmUnavailable` state, (7) submit-lock prevents concurrent calls; uses MSW server with T-130 handlers.

- [ ] **T-132** [frontend] **useSubmitQuestion hook** — cluster: US-2 | deps: T-131,T-024,T-129 | FR-006,FR-007,FR-014,FR-017,FR-019,FR-030 | effort: M
  Done when: `frontend/src/hooks/useSubmitQuestion.ts` implements `useSubmitQuestion()` returning `{ submitQuestion, rejectQuery, regenerateQuery, acceptQuery, isSubmitting, result, refinePrompt, error }` with `kind` discriminator switch for oneOf responses and submit-lock state; all T-131 tests pass.

### QueryInput component

- [ ] **T-133** [P] [test] **QueryInput RTL tests** — cluster: US-2 | deps: T-025,T-132 | FR-006,FR-007,SC-009 | effort: S
  Done when: `frontend/tests/unit/QueryInput.test.tsx` tests: (1) renders textarea with i18n placeholder `query.input.placeholder`, (2) displays live character counter updating on keystrokes, (3) prevents submission and shows validation when text exceeds 2000 chars, (4) disables submit button while `isSubmitting` is true, (5) calls `submitQuestion` on button click and on Enter key; uses RTL + MSW.

- [ ] **T-134** [frontend] **QueryInput component** — cluster: US-2 | deps: T-133,T-132,T-022 | FR-006,FR-007,FR-030,SC-009 | effort: S
  Done when: `frontend/src/components/QueryInput.tsx` renders a textarea with `{current}/{max}` character counter, submit button disabled on empty/whitespace/over-limit/isSubmitting, all strings via `t()`; all T-133 tests pass.

### ResultTable + SqlDisplay component (TanStack Table + SQL block)

- [ ] **T-135** [P] [test] **ResultTable + SqlDisplay state-machine integration RTL tests** — cluster: US-2 | deps: T-025,T-132 | FR-014,FR-015,FR-029,SC-009 | effort: S
  Done when: `frontend/tests/unit/ResultTable.test.tsx` and `frontend/tests/unit/SqlDisplay.test.tsx` test the existing components against US-2 state-machine inputs: (1) TanStack Table renders columns and rows from `QueryResult`, (2) displays `query.result.noRows` i18n key on zero-row result, (3) shows generated SQL in a code block, (4) renders Accept/Reject/Regenerate buttons with i18n labels, (5) shows `query.result.lastRetry` indicator when `is_last_auto_retry` is true; uses RTL.

- [ ] **T-136** [frontend] **ResultTable + SqlDisplay state-machine wiring** — cluster: US-2 | deps: T-135,T-132,T-022 | FR-014,FR-015,FR-029,SC-009 | effort: M
  Done when: `frontend/src/components/ResultTable.tsx` and `frontend/src/components/SqlDisplay.tsx` are extended with Reject/Regenerate wiring (Accept/Reject/Regenerate action buttons, `is_last_auto_retry` indicator) without creating new components; all T-135 tests pass.

### Error state components

- [ ] **T-137** [P] [test] **EvaluatorRejectionBanner RTL tests** — cluster: US-2 | deps: T-025 | FR-028,SC-009 | effort: XS
  Done when: `frontend/tests/unit/EvaluatorRejectionBanner.test.tsx` tests: (1) renders translated `query.evaluator.rejected` message, (2) displays violation list with translated `message_key` per violation, (3) renders nothing when violations array is empty; uses RTL.

- [ ] **T-138** [frontend] **EvaluatorRejectionBanner component** — cluster: US-2 | deps: T-137,T-022 | FR-028,SC-009 | effort: XS
  Done when: `frontend/src/components/EvaluatorRejectionBanner.tsx` renders an alert with translated evaluator message and violations; all T-137 tests pass.

- [ ] **T-139** [P] [test] **RefinePromptBanner RTL tests** — cluster: US-2 | deps: T-025 | FR-018,SC-009 | effort: XS
  Done when: `frontend/tests/unit/RefinePromptBanner.test.tsx` tests: (1) renders translated `query.refine.message`, (2) shows fresh question input prompt; uses RTL.

- [ ] **T-140** [frontend] **RefinePromptBanner component** — cluster: US-2 | deps: T-139,T-022 | FR-018,SC-009 | effort: XS
  Done when: `frontend/src/components/RefinePromptBanner.tsx` renders a prompt with translated refine message and resets input state; all T-139 tests pass.

- [ ] **T-141** [P] [test] **TimeoutBanner RTL tests** — cluster: US-2 | deps: T-025 | FR-012,SC-009 | effort: XS
  Done when: `frontend/tests/unit/TimeoutBanner.test.tsx` tests: (1) renders translated `query.error.timeout` message, (2) renders nothing when error type is not timeout; uses RTL.

- [ ] **T-142** [frontend] **TimeoutBanner component** — cluster: US-2 | deps: T-141,T-022 | FR-012,SC-009 | effort: XS
  Done when: `frontend/src/components/TimeoutBanner.tsx` renders an alert with translated timeout message; all T-141 tests pass.

### AskQuestionPage assembly (US-2 extension)

- [ ] **T-143** [test] **AskQuestionPage US-2 integration tests** — cluster: US-2 | deps: T-130,T-134,T-136,T-138,T-140,T-142 | FR-006,FR-014,FR-017,FR-018,FR-028,SC-001 | effort: M
  Done when: `frontend/tests/unit/AskQuestionPage-us2.test.tsx` tests: (1) submitting shows ResultTable + SqlDisplay, (2) clicking Reject shows new ResultTable + SqlDisplay with `is_last_auto_retry=true`, (3) second rejection shows RefinePromptBanner, (4) evaluator-422 shows EvaluatorRejectionBanner, (5) 504 shows TimeoutBanner, (6) 409 shows concurrent-error toast, (7) 502 shows LLM-unavailable toast; uses MSW + RTL.

- [ ] **T-144** [frontend] **AskQuestionPage US-2 wiring** — cluster: US-2 | deps: T-143,T-134,T-136,T-138,T-140,T-142,T-023 | FR-006,FR-014,FR-017,FR-018,FR-019,FR-028,FR-030,SC-009 | effort: M
  Done when: `frontend/src/pages/AskQuestionPage.tsx` integrates QueryInput, ResultTable, SqlDisplay, EvaluatorRejectionBanner, RefinePromptBanner, TimeoutBanner, and Radix toasts for 409/502; `kind` discriminator drives which component renders; all T-143 tests pass.

### Frontend i18n key verification

- [ ] **T-145** [test] **i18n key verification — no inline string literals** — cluster: US-2 | deps: T-022,T-144 | SC-009 | effort: S
  Done when: `npm run lint` passes with zero violations of the no-inline-string-literals ESLint rule across all files in `frontend/src/components/` and `frontend/src/pages/`; a CI script `frontend/scripts/verify-i18n-keys.ts` loads `en.json` and asserts every key referenced by `t()` in source files exists in the locale file and vice-versa.

### Playwright e2e — US-2 independent test criterion

- [ ] **T-146** [test] **E2E: reject → auto-retry → new result → accept** — cluster: US-2 | deps: T-028,T-144,T-115 | FR-017,FR-018,SC-005 | effort: L
  Done when: `frontend/tests/e2e/reject-retry.spec.ts` runs against `docker-compose.dev.yml`: (1) signs in, (2) submits a question, (3) clicks Reject on first result, (4) sees a new result with different SQL and `is_last_auto_retry` indicator, (5) clicks Accept on second result, (6) navigates to `/history` and sees the accepted query; assertions pass in headless Chromium.

- [ ] **T-147** [test] **E2E: double-reject → refine prompt → new question resets counter** — cluster: US-2 | deps: T-028,T-144,T-115 | FR-018,FR-019,SC-005 | effort: M
  Done when: `frontend/tests/e2e/reject-retry.spec.ts` extends with scenario: (1) submits a question, (2) rejects first result, (3) rejects second result, (4) sees RefinePromptBanner with `query.refine.message`, (5) types a new question and submits, (6) sees a fresh result (counter reset); no rejected queries appear in `/history`.

- [ ] **T-148** [test] **E2E: evaluator rejection + timeout + concurrent error rendering** — cluster: US-2 | deps: T-028,T-144 | FR-012,FR-028,FR-030 | effort: M
  Done when: `frontend/tests/e2e/error-states.spec.ts` runs against `docker-compose.dev.yml` with mock LLM configured to trigger each error: (1) evaluator rejection shows EvaluatorRejectionBanner, (2) timeout shows TimeoutBanner, (3) concurrent submission shows 409 toast; all assertions pass in headless Chromium.

## Cluster: US-3 — Evaluator Blocks Unsafe SQL
**Goal:** Prove end-to-end that every generated SQL passes through the evaluator gate before database contact, covering all seven acceptance scenarios (data-modifying, schema-invalid, multi-statement, valid pass-through, timeout), evaluator extensibility (FR-011), frontend violation-type display, and Playwright e2e for the independent-test criterion.

### Backend acceptance integration tests

- [ ] **T-149** [P] [test] **Acceptance: data-modifying SQL blocked via submit pipeline** — cluster: US-3 | deps: T-058,T-091 | FR-010,SC-002,SC-003 | effort: M
  Done when: `backend/tests/integration/test_us3_data_modifying.py` submits questions via `POST /query/submit` with mock LLM returning SQL containing each of INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, CREATE (7 cases); asserts each returns 422 `EvaluatorRejection` with `evaluator.violation.dataModifying` message key, source-DB executor spy confirms zero calls, and `accepted_queries` has zero new rows.

- [ ] **T-150** [P] [test] **Acceptance: schema-invalid SQL blocked via submit pipeline** — cluster: US-3 | deps: T-058,T-095 | FR-010,SC-004 | effort: S
  Done when: `backend/tests/integration/test_us3_schema_validation.py` submits questions with mock LLM returning SQL referencing a non-existent table and a non-existent column; asserts 422 with violations containing `evaluator.violation.unknownTable` and `evaluator.violation.unknownColumn` respectively, and source-DB executor is never called.

- [ ] **T-151** [P] [test] **Acceptance: multi-statement SQL blocked via submit pipeline** — cluster: US-3 | deps: T-058,T-093 | FR-010 | effort: XS
  Done when: `backend/tests/integration/test_us3_multi_statement.py` submits a question with mock LLM returning two SELECT statements separated by semicolon; asserts 422 with `evaluator.violation.multiStatement` and source-DB executor is never called.

- [ ] **T-152** [P] [test] **Acceptance: valid read-only SELECT and CTE pass evaluator** — cluster: US-3 | deps: T-058,T-089,T-106 | FR-010,FR-013 | effort: S
  Done when: `backend/tests/integration/test_us3_valid_passthrough.py` submits two questions — one with mock LLM returning a plain SELECT referencing existing tables, one returning a read-only CTE; asserts both return 200 `QueryResult` with columns and rows from the source DB.

- [ ] **T-153** [P] [test] **Acceptance: query timeout cancellation and cleanup** — cluster: US-3 | deps: T-058,T-106 | FR-012,SC-011 | effort: S
  Done when: `backend/tests/integration/test_us3_timeout.py` submits a question with mock LLM returning `SELECT pg_sleep(120)` (passes evaluator); asserts 504 with `error.timeout` message key within `QUERY_TIMEOUT_SECONDS + 5s`, source-DB connection is released, and no row is written to `accepted_queries`.

- [ ] **T-154** [P] [test] **Evaluator extensibility: custom rule registration** — cluster: US-3 | deps: T-089 | FR-011 | effort: S
  Done when: `backend/tests/integration/test_evaluator_extensibility.py` defines a custom `EvaluatorRule` implementation that rejects SQL containing `LIMIT 0`, registers it in the pipeline, submits SQL with `LIMIT 0`; asserts the pipeline returns the custom violation without modifying or removing any existing built-in rules.

### Frontend violation-type display verification

- [ ] **T-155** [P] [test] **EvaluatorRejectionBanner violation-type differentiation** — cluster: US-3 | deps: T-130,T-138 | FR-028,SC-009 | effort: S
  Done when: `frontend/tests/unit/EvaluatorViolationTypes.test.tsx` renders `EvaluatorRejectionBanner` with five distinct violation payloads (`dataModifying`, `unknownTable`, `unknownColumn`, `multiStatement`, `unsafePattern`); asserts each renders its unique translated message with correct interpolation params (`{{statement}}`, `{{table}}`, `{{column}}`).

### Playwright e2e — US-3 independent test criterion

- [ ] **T-156** [test] **E2E: evaluator blocks unsafe SQL — full acceptance sweep** — cluster: US-3 | deps: T-028,T-144,T-058 | FR-010,FR-028,SC-002,SC-003,SC-004 | effort: L
  Done when: `frontend/tests/e2e/evaluator-blocks.spec.ts` runs against `docker-compose.dev.yml` with controllable mock LLM: (1) submits with LLM returning `UPDATE` SQL → sees evaluator rejection banner, (2) submits with LLM returning unknown-table SQL → sees schema-mismatch message, (3) submits with valid SELECT → sees table result with rows, (4) verifies `/history` contains only the accepted valid query and zero rejected entries; all assertions pass in headless Chromium.

- [ ] **T-157** [test] **E2E: timeout displays message and writes no history** — cluster: US-3 | deps: T-028,T-144,T-058 | FR-012,SC-011 | effort: S
  Done when: `frontend/tests/e2e/evaluator-blocks.spec.ts` extends with timeout scenario: submits a question triggering a long-running query, sees timeout banner within configured timeout + 5 seconds, navigates to `/history` and confirms no entry from the timed-out question exists.

## Cluster: US-4 — Browse and Search History
**Goal:** Deliver the History view: reverse-chronological list of accepted queries, client-side free-text filter, detail panel, empty state, and prove that rejected/regenerated queries never appear — backed by architectural invariant tests for accept-only persistence, byte-equal duplicate detection, and ephemeral attempt ownership.

### Architectural invariant tests

- [ ] **T-158** [P] [test] **Invariant 2: accept-only persistence — reject/regenerate write nothing** — cluster: US-4 | deps: T-113,T-047 | SC-012 | effort: S
  Done when: `backend/tests/integration/test_invariant_accept_only.py` calls `reject_query` and `regenerate_query` through the full service layer, then asserts `accepted_queries` table has zero new rows; only `accept_query` produces a row.

- [ ] **T-159** [P] [test] **Invariant 4: byte-equal duplicate detection emits RefinePrompt** — cluster: US-4 | deps: T-113 | SC-005 | effort: S
  Done when: `backend/tests/integration/test_invariant_byte_equal.py` mocks the LLM to return identical SQL on retry, calls `reject_query`, and asserts the response is a `RefinePrompt` (kind=refine) with `query.refine.message` key — no second execution occurs.

- [ ] **T-160** [P] [test] **Invariant 6: cross-session ephemeral attempt ownership** — cluster: US-4 | deps: T-110 | | effort: S
  Done when: `backend/tests/integration/test_invariant_attempt_ownership.py` stores an attempt for session A, calls `accept_query` / `reject_query` with session B's credentials, and asserts both return 400 with `error.attemptInvalid` message key.

### Backend contract test

- [ ] **T-161** [P] [test] **Schemathesis contract: /history, /history/{id}** — cluster: US-4 | deps: T-060 | FR-021,FR-023 | effort: S
  Done when: `backend/tests/contract/test_openapi_contract.py` is extended with schemathesis-driven property tests for `GET /history` (200 list, cursor pagination) and `GET /history/{id}` (200 detail, 404 not found) validating responses conform to openapi.yaml.

- [ ] **T-161b** [P] [test] **HistoryListResponse.total first-page-only contract** — cluster: US-4 | deps: T-060 | FR-021 | effort: XS
  Done when: `backend/tests/integration/test_history_total_field.py` asserts `GET /history` with no cursor returns `total` in the response body, and `GET /history?cursor=<token>` omits `total` entirely.

### Frontend: useHistory hook

- [ ] **T-162** [P] [test] **useHistory hook RTL tests** — cluster: US-4 | deps: T-025,T-061 | FR-021,FR-023 | effort: S
  Done when: `frontend/tests/unit/useHistory.test.tsx` tests: (1) `useHistoryList` returns items in reverse-chronological order, (2) returns empty array when no accepted queries, (3) `useHistoryDetail` returns full entry by ID, (4) returns 404 error for unknown ID; uses MSW server.

- [ ] **T-163** [frontend] **useHistory hook** — cluster: US-4 | deps: T-162,T-024,T-061 | FR-021,FR-022,FR-023 | effort: S
  Done when: `frontend/src/hooks/useHistory.ts` implements `useHistoryList()` and `useHistoryDetail(id)` using TanStack Query backed by generated API client; all T-162 tests pass.

### Frontend: HistoryList component

- [ ] **T-164** [P] [test] **HistoryList component RTL tests** — cluster: US-4 | deps: T-025,T-163 | FR-021,FR-022,SC-006,SC-007,SC-009 | effort: M
  Done when: `frontend/tests/unit/HistoryList.test.tsx` tests: (1) renders entries reverse-chronologically showing question, SQL snippet, and timestamp, (2) empty state renders `history.empty` i18n key, (3) filter input narrows list to entries matching typed word in question or SQL, (4) filter returns within 1 second for 1000 mock entries, (5) all strings use `t()`; uses RTL.

- [ ] **T-165** [frontend] **HistoryList component** — cluster: US-4 | deps: T-164,T-163,T-022 | FR-021,FR-022,SC-006,SC-007,SC-009 | effort: M
  Done when: `frontend/src/components/HistoryList.tsx` renders a scrollable list of `AcceptedQuerySummary` entries with a free-text filter input (`history.filter.placeholder`), empty-state message, and click handler to select an entry; all T-164 tests pass.

### Frontend: HistoryDetail component

- [ ] **T-166** [P] [test] **HistoryDetail component RTL tests** — cluster: US-4 | deps: T-025,T-163 | FR-023,SC-009 | effort: S
  Done when: `frontend/tests/unit/HistoryDetail.test.tsx` tests: (1) renders full question text, full SQL, and formatted acceptance timestamp, (2) all labels use i18n keys `history.detail.question`, `history.detail.sql`, `history.detail.acceptedAt`, (3) renders 404 message for unknown ID; uses RTL.

- [ ] **T-167** [frontend] **HistoryDetail component** — cluster: US-4 | deps: T-166,T-163,T-022 | FR-023,SC-009 | effort: S
  Done when: `frontend/src/components/HistoryDetail.tsx` renders the detail view with question, SQL (via `SqlDisplay`), and timestamp; all T-166 tests pass.

### Frontend: HistoryPage assembly

- [ ] **T-168** [test] **HistoryPage integration tests** — cluster: US-4 | deps: T-025,T-165,T-167 | FR-021,FR-022,FR-023,SC-009 | effort: M
  Done when: `frontend/tests/unit/HistoryPage.test.tsx` tests: (1) renders HistoryList on `/history`, (2) clicking an entry navigates to `/history/:id` and shows HistoryDetail, (3) filter narrows displayed entries, (4) empty state shown when no entries, (5) all strings via `t()`; uses MSW + RTL.

- [ ] **T-169** [frontend] **HistoryPage assembly** — cluster: US-4 | deps: T-168,T-165,T-167,T-023 | FR-021,FR-022,FR-023,SC-009 | effort: M
  Done when: `frontend/src/pages/HistoryPage.tsx` composes HistoryList and HistoryDetail with React Router nested routing for `/history` and `/history/:id`; all T-168 tests pass.

### Frontend: kind discriminator for reject/regenerate responses

- [ ] **T-170** [P] [test] **useSubmitQuestion kind discriminator integration test** — cluster: US-4 | deps: T-130,T-132 | FR-017,FR-019 | effort: S
  Done when: `frontend/tests/unit/useSubmitQuestion-discriminator.test.tsx` tests: (1) reject returning `{kind:"result",...}` sets `result` state, (2) reject returning `{kind:"refine",...}` sets `refinePrompt` state, (3) regenerate mirrors the same discrimination; uses MSW with T-130 handler factories.

### Playwright e2e — US-4 independent test criterion

- [ ] **T-171** [test] **E2E: history list, reverse-chrono order, filter, detail** — cluster: US-4 | deps: T-028,T-169,T-060 | FR-021,FR-022,FR-023,SC-006,SC-007 | effort: L
  Done when: `frontend/tests/e2e/history.spec.ts` runs against `docker-compose.dev.yml`: (1) accepts three queries, (2) navigates to `/history`, (3) sees three entries in reverse-chronological order, (4) types a filter word and sees only matching entries, (5) clicks an entry and sees full question, SQL, and timestamp; all assertions pass in headless Chromium.

- [ ] **T-172** [test] **E2E: empty history state** — cluster: US-4 | deps: T-028,T-169 | FR-021 | effort: S
  Done when: `frontend/tests/e2e/history.spec.ts` extends with scenario: signs in with a fresh session (no accepted queries), navigates to `/history`, sees the empty-state message with `history.empty` text.

- [ ] **T-173** [test] **E2E: rejected queries absent from history** — cluster: US-4 | deps: T-028,T-169,T-115 | FR-020,SC-012 | effort: M
  Done when: `frontend/tests/e2e/history.spec.ts` extends with scenario: (1) submits and rejects a query, (2) submits and accepts a different query, (3) navigates to `/history`, (4) sees only the accepted query — the rejected question text does not appear anywhere in the list.

## Cluster: US-5 — Configurable LLM Provider
**Goal:** Verify that the LLM provider abstraction (built in US-2) supports config-only switching between Anthropic, OpenAI, Gemini, and Ollama without code changes, preserves history across provider switches, routes exclusively to the configured adapter, and fails fast on invalid configuration.

### Backend acceptance integration tests

- [ ] **T-174** [P] [test] **Acceptance: provider switch preserves accepted_queries** — cluster: US-5 | deps: T-086,T-047,T-052 | FR-026,SC-008 | effort: M
  Done when: `backend/tests/integration/test_us5_provider_switch.py` starts the app with `LLM_PROVIDER=ollama`, submits and accepts a query, restarts the app with `LLM_PROVIDER=openai`, asserts all previously accepted queries are intact via `GET /history`, and a new submission routes to the OpenAI adapter (verified by httpx mock).

- [ ] **T-175** [P] [test] **Acceptance: invalid LLM_PROVIDER fails at startup** — cluster: US-5 | deps: T-007,T-086 | FR-009,SC-008 | effort: XS
  Done when: `backend/tests/unit/test_us5_invalid_provider.py` sets `LLM_PROVIDER=unsupported_vendor`, calls `create_llm_provider(settings)`, and asserts a `ValueError` (or pydantic validation error) is raised with a human-readable message listing valid providers; app factory refuses to start.

- [ ] **T-176** [P] [test] **Acceptance: Ollama-exclusive routing — no cloud API contact** — cluster: US-5 | deps: T-084,T-086,T-052 | FR-009 | effort: S
  Done when: `backend/tests/integration/test_us5_ollama_routing.py` configures `LLM_PROVIDER=ollama` and `LLM_BASE_URL_OLLAMA=http://mock-ollama:11434`, submits a question, asserts httpx call targets `http://mock-ollama:11434/api/generate` and zero calls are made to any Anthropic/OpenAI/Gemini endpoint.

- [ ] **T-177** [P] [test] **Acceptance: reconfigured provider handles new questions** — cluster: US-5 | deps: T-086,T-052 | FR-009,FR-026 | effort: S
  Done when: `backend/tests/integration/test_us5_provider_switch.py` extends with scenario: after switching from Ollama to Gemini, submits a new question and asserts the Gemini adapter's httpx call targets the Gemini `generateContent` URL pattern; the Ollama adapter receives zero calls.

### Playwright e2e — US-5 independent test criterion

- [ ] **T-178** [test] **E2E: deploy with provider A → accept queries → switch to provider B → old history + new query** — cluster: US-5 | deps: T-028,T-169,T-086 | FR-009,FR-026,SC-008 | effort: L
  Done when: `frontend/tests/e2e/provider-switch.spec.ts` runs against `docker-compose.dev.yml`: (1) deploys with `LLM_PROVIDER=ollama`, (2) submits and accepts a query, (3) restarts backend with `LLM_PROVIDER=openai` (via env override), (4) navigates to `/history` and sees the previously accepted query, (5) submits a new question and sees a result; all assertions pass in headless Chromium.

## Cluster: US-6 — i18n and RTL-Ready Foundation
**Goal:** Verify that 100% of user-facing strings route through i18n keys with no inline literals, 0 instances of hardcoded directional CSS exist, all English keys render without missing-key placeholders, and the codebase is ready for Arabic/RTL activation without component rework.

### Frontend lint + audit verification

- [ ] **T-179** [P] [test] **ESLint no-inline-strings: full codebase sweep** — cluster: US-6 | deps: T-019,T-144,T-169 | FR-024,SC-009 | effort: S
  Done when: `npm run lint` passes with zero violations of the no-inline-string-literals rule across every file in `frontend/src/components/`, `frontend/src/pages/`, and `frontend/src/hooks/`; any new violation added as a regression test in `frontend/tests/lint/no-inline-strings.test.ts` is caught.

- [ ] **T-180** [P] [test] **Stylelint logical-properties: full codebase sweep** — cluster: US-6 | deps: T-020,T-144,T-169 | FR-025,SC-010 | effort: S
  Done when: `npm run lint:css` passes with zero violations across every CSS and TSX file; a grep for `margin-left`, `margin-right`, `padding-left`, `padding-right`, `text-align: left`, `text-align: right` in `frontend/src/` returns zero matches.

- [ ] **T-181** [P] [test] **Tailwind output contains no physical-direction utilities** — cluster: US-6 | deps: T-021 | FR-025,SC-010 | effort: XS
  Done when: `npm run build` succeeds and a grep of the production CSS bundle for `ml-`, `mr-`, `pl-`, `pr-` class names returns zero matches; only `ms-`, `me-`, `ps-`, `pe-` logical equivalents are present.

### i18n key completeness

- [ ] **T-182** [P] [test] **en.json key completeness: every t() call has a key, every key is used** — cluster: US-6 | deps: T-022,T-144,T-169 | FR-024,SC-009 | effort: S
  Done when: `frontend/scripts/verify-i18n-keys.ts` (or vitest wrapper) loads `en.json`, scans all `t('...')` calls in `frontend/src/`, asserts (1) every referenced key exists in `en.json`, (2) every key in `en.json` is referenced at least once, (3) zero orphaned or missing keys.

- [ ] **T-183** [P] [test] **en.json renders without missing-key placeholders** — cluster: US-6 | deps: T-022,T-144,T-169 | FR-024,SC-009 | effort: S
  Done when: `frontend/tests/unit/i18n-render.test.tsx` renders every page component (SignInPage, AskQuestionPage, HistoryPage) in a RTL test environment and asserts zero DOM nodes contain the i18next missing-key fallback pattern (default: the raw key string with no translation wrapper).

### Backend i18n key consistency

- [ ] **T-184** [P] [test] **Backend error responses use message_key from en.json** — cluster: US-6 | deps: T-128,T-022 | FR-024 | effort: S
  Done when: `backend/tests/unit/test_message_keys.py` collects all `message_key` values returned by custom exceptions and error handlers, asserts each key exists in `frontend/src/i18n/locales/en.json`; zero orphaned backend keys.

### Playwright e2e — US-6 independent test criterion

- [ ] **T-185** [test] **E2E: no missing-key placeholders across all pages** — cluster: US-6 | deps: T-028,T-144,T-169 | FR-024,SC-009 | effort: M
  Done when: `frontend/tests/e2e/i18n-audit.spec.ts` runs against `docker-compose.dev.yml`: navigates to `/sign-in`, `/` (after sign-in), `/history`, and asserts zero DOM elements contain raw i18n key strings (pattern: `key.with.dots` not wrapped in translation); all assertions pass in headless Chromium.

- [ ] **T-186** [test] **E2E: no physical-direction CSS in rendered pages** — cluster: US-6 | deps: T-028,T-144,T-169 | FR-025,SC-010 | effort: S
  Done when: `frontend/tests/e2e/i18n-audit.spec.ts` extends with scenario: for each page, inspects computed styles of all elements and asserts zero `margin-left`, `margin-right`, `padding-left`, `padding-right` declarations originating from project stylesheets (excludes browser defaults and third-party resets).

## Cluster: Polish
**Goal:** Phase 1 is production-ready, not just functionally complete — coverage gates, CI pipeline, performance budgets, operational docs, and security review are all enforced.

### Coverage gates

- [ ] **T-187** [P] [infra] **Backend coverage gate: pytest-cov + CI threshold** — cluster: Polish | deps: T-058,T-115,T-128 | | effort: S
  Done when: `pyproject.toml` adds `[tool.pytest.ini_options]` with `--cov` flags; CI step fails if services/evaluator coverage < 80% or routers coverage < 60%.

- [ ] **T-188** [P] [infra] **Frontend coverage gate: Vitest coverage + CI threshold** — cluster: Polish | deps: T-145,T-169,T-186 | | effort: S
  Done when: `vitest.config.ts` enables `coverage` provider with `thresholds: { statements: 70 }` for `hooks/`, `services/`, `utils/`; CI step fails below threshold.

### CI workflow

- [ ] **T-189** [infra] **Unified CI workflow: lint → typecheck → test → build → contract → e2e** — cluster: Polish | deps: T-187,T-188 | | effort: M
  Done when: `.github/workflows/ci.yml` defines a single pipeline: `lint` (ESLint + Stylelint + Ruff), `typecheck` (tsc + mypy), `test` (pytest + vitest with coverage), `build` (vite build), `contract` (schemathesis), `e2e` (Playwright against docker-compose); pipeline passes on a clean checkout.

### Success criteria coverage suite

- [ ] **T-190** [test] **SC coverage suite: SC-001..SC-012 mapped to assertions** — cluster: Polish | deps: T-074,T-148,T-156,T-157,T-171,T-173,T-178,T-185,T-186 | SC-001,SC-002,SC-003,SC-004,SC-005,SC-006,SC-007,SC-008,SC-009,SC-010,SC-011,SC-012 | effort: M
  Done when: `tests/sc-coverage.test.ts` (or equivalent) imports and re-exports the specific test that covers each SC-NNN, annotated with `@sc:NNN`; running `npm run test:sc` executes all 12 and reports pass/fail per criterion.

### Performance budget verification

- [ ] **T-191** [test] **Performance-budget verification** — cluster: Polish | deps: T-074,T-171 | SC-001,SC-006,SC-007,SC-011 | effort: M
  Done when: `frontend/tests/e2e/performance.spec.ts` asserts: (1) full question-to-result loop completes in < 60s excluding LLM time (SC-001), (2) source-DB timeout fires within config + 5s (SC-011), (3) history view renders ≤ 1000 entries in < 3s (SC-006), (4) filter returns results within 1s of keystop (SC-007); all pass in headless Chromium against docker-compose.

### Documentation

- [ ] **T-192** [P] [docs] **quickstart.md verified on a fresh machine** — cluster: Polish | deps: T-189 | | effort: S
  Done when: `specs/001-core-text-to-sql/quickstart.md` is updated and a clean `git clone` + `docker compose -f docker-compose.dev.yml up` + documented steps successfully brings up the full platform with a working sign-in → ask → accept → history flow.

- [ ] **T-193** [P] [docs] **Operator runbook** — cluster: Polish | deps: T-189 | | effort: M
  Done when: `docs/runbook.md` documents: env-var reference table, PLATFORM_ENCRYPTION_KEY rotation procedure, SchemaTokenLimitExceeded resolution steps, Redis session-lock cleanup, admin-password reset procedure, and LLM provider switch checklist.

### Security review

- [ ] **T-194** [test] **Security-review checklist** — cluster: Polish | deps: T-058,T-115,T-128,T-144 | | effort: M
  Done when: `docs/security-review.md` documents and `backend/tests/security/test_security_checklist.py` verifies: (1) Argon2id params ≥ OWASP minimums, (2) session cookie flags HttpOnly+Secure+SameSite=Strict, (3) Origin allow-list enforced on POST/PATCH/DELETE, (4) AES-256-GCM encryption of source-DB credentials at rest, (5) source-DB role is read-only, (6) no credentials in log output, (7) no PII in OTel spans, (8) no stack traces in 5xx responses; all 8 assertions pass.

### Performance debt

- [ ] **T-191b** [P] [backend] **Replace per-request Redis instantiation with request-scoped pool tied to event loop** — cluster: Polish | deps: — | effort: S
  **Why:** Currently `SessionMiddleware._get_redis()` creates a fresh `Redis.from_url()` per request because schemathesis's per-example event loops invalidate cached connections. This adds ~1ms/request connection-setup overhead. For KSA Phase 1 traffic (100–1000 users) this is acceptable, but it is genuine perf debt.
  **Done when:** `backend/src/app/core/security.py` uses a `redis.asyncio.ConnectionPool` scoped to the active request's event loop, or uses a per-worker pool with proper loop-attachment handling; existing event-loop safety tests still pass; benchmark shows reduced p99 session-cookie verify latency vs current implementation.

- [ ] **T-191c** [P] [backend] **Reconcile dual default on `accepted_queries.accepted_at`** — cluster: Polish | deps: — | effort: XS
  **Why:** During US-1 we added `default=lambda: datetime.now(UTC)` Python-side to fix a flaky test (PostgreSQL's `now()` returns transaction start time, so multiple inserts in the same db_session got identical timestamps). The original `server_default=text("now()")` was kept as a fallback for raw SQL inserts. Two sources of truth for the same column is fragile and confusing.
  **Done when:** `backend/src/app/db/models/accepted_query.py` uses a single authoritative default for `accepted_at`. Pick one of:
  (a) drop `server_default` and rely on Python-side default since all inserts go through SQLAlchemy ORM, OR
  (b) drop the Python-side default and use `default=func.now()` so SQLAlchemy emits the same `now()` call to PostgreSQL but flushes per-row, ensuring per-row precision.
  Existing flake-resistance test still passes; no regression in coverage.

---

## Traceability

### Table 1 — Functional Requirements

| FR | Covered by (impl tasks) | Verified by (test tasks) |
|---|---|---|
| FR-001 | T-037,T-043,T-045,T-049,T-056,T-060,T-063,T-067 | T-033,T-036,T-042,T-044,T-048,T-055,T-062,T-066,T-074 |
| FR-002 | T-045,T-049,T-056,T-063,T-067 | T-048,T-055,T-062,T-066 |
| FR-003 | T-032,T-045,T-049,T-056,T-063 | T-031,T-048,T-055,T-062 |
| FR-004 | T-043 | T-042 |
| FR-005 | T-104 | T-103,T-122 |
| FR-006 | T-052,T-058,T-065,T-069,T-071,T-073,T-132,T-134,T-136,T-144 | T-050,T-057,T-064,T-068,T-072,T-074,T-131,T-133,T-143 |
| FR-007 | T-039,T-052,T-058,T-065,T-069,T-132,T-134 | T-038,T-050,T-057,T-064,T-068,T-130,T-131,T-133 |
| FR-008 | T-052,T-087,T-098,T-100 | T-050,T-076,T-089,T-099 |
| FR-009 | T-076,T-078,T-080,T-082,T-084,T-086 | T-075,T-077,T-079,T-081,T-083,T-085,T-175,T-176,T-177,T-178 |
| FR-010 | T-089,T-091,T-093,T-095,T-097,T-098 | T-088,T-090,T-092,T-094,T-096,T-149,T-150,T-151,T-152,T-156 |
| FR-011 | T-089 | T-088,T-154 |
| FR-012 | T-106,T-142,T-144 | T-105,T-141,T-148,T-153,T-157 |
| FR-013 | T-104,T-106 | T-103,T-105,T-152 |
| FR-014 | T-039,T-052,T-058,T-065,T-071,T-073,T-132,T-136,T-144 | T-038,T-050,T-057,T-064,T-070,T-072,T-074,T-130,T-131,T-135,T-143 |
| FR-015 | T-039,T-058,T-065,T-071,T-073,T-136 | T-038,T-057,T-064,T-070,T-072,T-135 |
| FR-016 | T-043,T-047,T-052,T-058,T-065,T-073 | T-042,T-046,T-050,T-057,T-064,T-072,T-074 |
| FR-017 | T-108,T-110,T-113,T-115,T-117,T-119,T-132,T-144 | T-111,T-112,T-114,T-116,T-125,T-130,T-131,T-143,T-146,T-170 |
| FR-018 | T-108,T-110,T-113,T-115,T-140,T-144 | T-111,T-112,T-114,T-139,T-143,T-146,T-147 |
| FR-019 | T-108,T-110,T-113,T-117,T-119,T-132,T-144 | T-112,T-116,T-125,T-131,T-143,T-147,T-170 |
| FR-020 | T-052,T-108,T-110,T-113 | T-051,T-111,T-112,T-173 |
| FR-021 | T-041,T-047,T-054,T-060,T-163,T-165,T-169 | T-040,T-046,T-053,T-059,T-074,T-161,T-161b,T-162,T-164,T-168,T-171,T-172 |
| FR-022 | T-054,T-060,T-163,T-165,T-169 | T-053,T-059,T-162,T-164,T-168,T-171 |
| FR-023 | T-041,T-047,T-054,T-060,T-163,T-167,T-169 | T-040,T-046,T-053,T-059,T-161,T-162,T-166,T-168,T-171 |
| FR-024 | T-022,T-144,T-169 | T-019,T-179,T-182,T-183,T-184,T-185 |
| FR-025 | T-144,T-169 | T-020,T-021,T-180,T-181,T-186 |
| FR-026 | T-086 | T-085,T-174,T-177,T-178 |
| FR-027 | T-043,T-052 | T-042,T-050 |
| FR-028 | T-039,T-058,T-138,T-144 | T-038,T-057,T-130,T-137,T-143,T-148,T-155,T-156 |
| FR-029 | T-071,T-136 | T-070,T-135 |
| FR-030 | T-052,T-065,T-069,T-108,T-132,T-134,T-144 | T-050,T-064,T-068,T-107,T-121,T-130,T-131,T-133,T-143,T-148 |

### Table 2 — Success Criteria

| SC | Covered by (task IDs) | Measurement method |
|---|---|---|
| SC-001 | T-031,T-050,T-057,T-072,T-074,T-143,T-191 | Playwright timing assertion in e2e (T-074,T-191) |
| SC-002 | T-034,T-050,T-057,T-120,T-124,T-149,T-156 | Integration test with evaluator spy (T-120,T-124,T-149); E2E sweep (T-156) |
| SC-003 | T-090,T-091,T-149,T-156 | Unit tests per keyword (T-090); integration via submit pipeline (T-149); E2E (T-156) |
| SC-004 | T-094,T-095,T-150,T-156 | Unit tests per schema violation (T-094); integration via submit pipeline (T-150); E2E (T-156) |
| SC-005 | T-111,T-112,T-113,T-146,T-147,T-159 | Integration test with identical-SQL mock (T-159); E2E reject flows (T-146,T-147) |
| SC-006 | T-164,T-165,T-171,T-191 | RTL render timing (T-164); Playwright timing assertion with 1000 entries (T-191) |
| SC-007 | T-164,T-165,T-171,T-191 | RTL filter latency (T-164); Playwright keystop timing (T-191) |
| SC-008 | T-085,T-174,T-175,T-178 | Integration test config swap (T-174); invalid config failure (T-175); E2E full workflow (T-178) |
| SC-009 | T-019,T-066,T-067,T-133,T-134,T-137,T-138,T-145,T-155,T-164,T-165,T-179,T-182,T-183,T-185 | ESLint no-inline-strings (T-179); key completeness script (T-182); render audit (T-183,T-185) |
| SC-010 | T-020,T-021,T-180,T-181,T-186 | Stylelint logical-properties (T-180); Tailwind output grep (T-181); E2E computed-style audit (T-186) |
| SC-011 | T-105,T-106,T-153,T-157,T-191 | Integration test timeout cancellation (T-153); E2E timeout (T-157); perf budget (T-191) |
| SC-012 | T-035,T-051,T-111,T-113,T-158,T-173 | Invariant: accept-only persistence (T-158); E2E rejected absent from history (T-173) |

### Gaps identified

No coverage gaps identified — all 30 functional requirements and 12 success criteria are covered by at least one implementation task and at least one verification task.
