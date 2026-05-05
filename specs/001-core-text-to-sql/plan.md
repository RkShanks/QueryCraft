# Implementation Plan: Core Text-to-SQL Vertical Slice

**Branch**: `001-core-text-to-sql` | **Date**: 2026-05-03 | **Spec**: [spec.md](file:///home/avril/QueryCraft/specs/001-core-text-to-sql/spec.md)  
**Input**: Feature specification from `specs/001-core-text-to-sql/spec.md`

## Summary

Build Phase 1 of the Text-to-SQL Analytics Platform: a complete vertical slice where a single user signs in, asks a question in English about a connected PostgreSQL database, receives a validated table result, and can accept/reject/regenerate the answer. Accepted queries persist to a personal history. The architecture establishes foundations for i18n, RTL, swappable LLM providers, and per-user identity attribution that later phases build on.

## Technical Context

**Project Type**: Monorepo with two independently deployable units — a Python web-service backend and a React SPA frontend — communicating only through a versioned, contract-tested HTTP API (Constitution Principles XI and XII).

**Backend — Language/Version**: Python 3.12  
**Backend — Architecture**: Layered (Clean) Architecture — Routers → Services → Repositories → ORM Models, with Pydantic v2 Schemas separate from ORM entities.

**Backend — Primary Dependencies**:
- FastAPI (latest stable), Uvicorn (ASGI)
- SQLAlchemy 2.0 (async), asyncpg (driver)
- Alembic (migrations)
- Pydantic v2 + pydantic-settings
- sqlglot (dialect-aware SQL parsing for the evaluator)
- httpx (unified HTTP client for all LLM provider adapters)
- argon2-cffi (password hashing)
- Redis-backed server-side sessions (secure HttpOnly cookies, 8-hour idle expiry)
- structlog (structured logging)
- OpenTelemetry SDK (instrumented, not yet wired to a collector)

**Backend — Storage**:
- PostgreSQL 16 — platform metadata database (users, accepted queries, app config)
- PostgreSQL 16 — source database (customer's data, read-only)
- Redis 7 — session store + ephemeral attempt store

**Backend — Testing**: pytest, pytest-asyncio, pytest-cov, httpx ASGI transport, testcontainers-python, schemathesis (contract tests). Coverage gate: ≥80% services/evaluator, ≥60% routers.

**Frontend — Language/Version**: TypeScript 5.x on Node 22.x LTS  
**Frontend — Primary Dependencies**:
- React 18 + Vite
- React Router, TanStack Query, TanStack Table
- Generated API client from OpenAPI via openapi-typescript-codegen
- i18next + react-i18next (keyed strings, `en` locale only)
- Tailwind CSS v4 (logical-property utilities only — `ms-*`, `me-*`, `ps-*`, `pe-*`)
- Radix UI primitives
- React Hook Form + Zod

**Frontend — Testing**: Vitest + React Testing Library, MSW, Playwright (e2e)

**Target Platforms**:
- Backend: Linux (containerized), multi-stage Dockerfile
- Frontend: Last 2 versions of Chrome, Firefox, Safari, Edge

**Performance Goals (Phase 1)**:
- p95 backend latency (excl. LLM): ≤ 200 ms
- Source-DB query: bounded by configurable timeout (default 30 s)
- Frontend TTI: ≤ 2 s cold load
- History first render: ≤ 3 s for ≤ 1,000 entries; ≤ 1 s filter

**Scale/Scope**: 1 admin user, 1 source DB, ~9 HTTP endpoints, ~4 metadata tables

---

## Constitution Check

*GATE: Verified pre-design. Re-checked post-design below.*

### Principles Enforced in Phase 1

| Principle | How Enforced | Verification |
|-----------|-------------|--------------|
| **I — Security & Data Protection** | TLS terminated at reverse proxy. Platform PostgreSQL assumes disk-level encryption at infrastructure. Secrets loaded from env-only — never committed. Passwords hashed with Argon2id. Session cookies: HttpOnly, Secure, SameSite=Strict (R-007). Origin header validated on all state-changing requests against `ALLOWED_ORIGINS` (R-007). Source-DB credentials encrypted at column level with AES-256-GCM via `PLATFORM_ENCRYPTION_KEY` (R-008). Source-DB credentials never exposed to API. | Secrets not in repo. Cookie flags set in code. Argon2 verified in unit tests. Origin middleware tested. Encryption round-trip tested. |
| **II — Every Query Validated** | The evaluator gate is a mandatory step in `QueryService.submit_question()`. There is no code path that reaches `SourceDBExecutor.execute()` without first passing `Evaluator.evaluate()`. This is an architectural invariant documented and tested. | Integration test: mock evaluator-fail → verify DB never called. |
| **III — Only Validated Knowledge Persists** | Only `QueryService.accept()` writes to `accepted_queries`. `reject()` and `regenerate()` never call `AcceptedQueryRepository.create()`. Rejected/failed attempts are ephemeral (Redis-only, 15-min TTL). | Unit test: reject handler → assert no repository write. |
| **V — LLM-Agnostic** | `LLMProvider` protocol with 4 adapters: `AnthropicAdapter`, `OpenAIAdapter`, `GeminiAdapter`, `OllamaAdapter`. Selected at startup by config. All share `generate_sql(question, schema_context, negative_examples)` signature. | Contract test: each adapter implements the protocol. Config switch test. |
| **VIII — Centrally Brokered DB Access** | Source-DB credentials configured at platform level in `database_connections` table. API endpoints never accept DB credentials. `SourceDBConnector` reads credentials from config, not from request payloads. | Code review: no route accepts DB credentials. |
| **XI — Modularity** | Backend and frontend are sibling directories, independently buildable and deployable. Backend layers (routers, services, repositories, evaluator, LLM) have clean dependency boundaries. | Build test: `docker build backend/` and `docker build frontend/` independently. |
| **XII — API Contract** | OpenAPI 3.1 generated from FastAPI at build time. Frontend types generated from it via `openapi-typescript-codegen`. Contract tests via `schemathesis` on every CI run. | Contract test pass. No hand-written request/response types in frontend. |

### Principles Deferred to Later Phases

| Principle | Deferral Scope | Target Phase |
|-----------|---------------|--------------|
| **IV — Hostile Input as Security Event** | Injection detection beyond the basic evaluator read-only check. Auto-suspension on repeat offenders. | Phase 6 |
| **VI — Language Decoupled from SQL Dialect** | Arabic + RTL activation. Phase 1 lays foundations only (i18n string layer, logical CSS). | Phase 4 |
| **VII — Role-Appropriate Authentication** | SSO (SAML/OIDC), multi-user, RBAC. Phase 1 uses local admin credentials only. | Phase 5 |
| **IX — Observability & Auditability** | Tamper-evident audit log with 24-month retention. Phase 1 uses structlog for short-term operational logs. | Phase 6 |
| **X — Quotas Enforced** | Token/query/cost quotas. Not applicable in Phase 1's single-user scope. | Phase 6 |

---

## Project Structure

### Documentation (this feature)

```text
specs/001-core-text-to-sql/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research output
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Developer quickstart
├── contracts/
│   └── openapi.yaml     # API contract (source of truth)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
QueryCraft/
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       └── 002_seed_admin_user.py
│   ├── src/app/
│   │   ├── __init__.py
│   │   ├── main.py                         # FastAPI app factory, lifespan (source-DB upsert), middleware
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py                   # pydantic-settings: env-based config
│   │   │   ├── security.py                 # Argon2 hashing, session middleware, Origin validation
│   │   │   ├── encryption.py               # AES-256-GCM encrypt/decrypt for source-DB credentials
│   │   │   ├── dependencies.py             # DI wiring (get_db, get_redis, get_current_user)
│   │   │   ├── exceptions.py               # Custom exception classes
│   │   │   └── logging.py                  # structlog + OpenTelemetry setup
│   │   ├── api/v1/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                     # POST /sign-in, /sign-out, GET /me
│   │   │   ├── query.py                    # POST /submit, /accept, /reject, /regenerate
│   │   │   ├── history.py                  # GET /history, /history/{id}
│   │   │   └── admin.py                    # POST /admin/refresh-schema
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py             # Login/logout, session management
│   │   │   ├── query_service.py            # Submit → LLM → evaluate → execute → result
│   │   │   ├── history_service.py          # Accept, list, get history entries
│   │   │   └── admin_service.py            # Schema refresh, admin operations
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── user_repository.py
│   │   │   ├── accepted_query_repository.py
│   │   │   └── app_config_repository.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                     # SQLAlchemy async engine + session factory
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── user.py
│   │   │       ├── accepted_query.py
│   │   │       ├── database_connection.py
│   │   │       └── app_config.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                     # SignInRequest, UserProfile
│   │   │   ├── query.py                    # SubmitQuestionRequest, QueryResult, etc.
│   │   │   └── history.py                  # HistoryListResponse, AcceptedQueryDetail
│   │   ├── evaluator/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                     # EvaluatorRule protocol, EvaluatorResult
│   │   │   ├── pipeline.py                 # evaluate(sql, schema) → fans out to rules
│   │   │   ├── rules/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── read_only_rule.py       # Rejects non-SELECT / data-modifying
│   │   │   │   ├── single_statement_rule.py # Rejects multi-statement SQL
│   │   │   │   ├── schema_validation_rule.py # Validates table/column references
│   │   │   │   └── unsafe_pattern_rule.py  # Platform-defined unsafe patterns
│   │   │   └── schema_context.py           # Schema representation for evaluator
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                     # LLMProvider protocol
│   │   │   ├── factory.py                  # Provider selection from config
│   │   │   ├── prompt.py                   # Prompt construction (system prompt + schema)
│   │   │   ├── anthropic_adapter.py
│   │   │   ├── openai_adapter.py
│   │   │   ├── gemini_adapter.py
│   │   │   └── ollama_adapter.py
│   │   └── source_db/
│   │       ├── __init__.py
│   │       ├── connector.py                # Read-only connection pool
│   │       ├── executor.py                 # Execute SQL with timeout
│   │       └── introspector.py             # Schema introspection + cache
│   ├── tests/
│   │   ├── conftest.py                     # Shared fixtures
│   │   ├── unit/
│   │   │   ├── test_evaluator_rules.py     # 50+ PostgreSQL SQL patterns
│   │   │   ├── test_query_service.py       # Reject/retry state machine
│   │   │   ├── test_auth_service.py
│   │   │   └── test_history_service.py
│   │   ├── integration/
│   │   │   ├── test_api_auth.py
│   │   │   ├── test_api_query.py
│   │   │   ├── test_api_history.py
│   │   │   └── test_source_db.py
│   │   └── contract/
│   │       └── test_openapi_contract.py    # schemathesis-driven
│   └── Dockerfile                          # Multi-stage build
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts                  # Logical-property-only config
│   ├── .eslintrc.cjs                       # i18next + no-directional-CSS rules
│   ├── src/
│   │   ├── main.tsx                        # App entry, i18n init, providers
│   │   ├── App.tsx                         # Router setup
│   │   ├── api/                            # Generated from OpenAPI (checked in)
│   │   │   └── generated/                  # openapi-typescript-codegen output
│   │   ├── components/
│   │   │   ├── Layout.tsx                  # Shell layout with nav
│   │   │   ├── QueryInput.tsx              # Question input with validation
│   │   │   ├── ResultTable.tsx             # TanStack Table result grid
│   │   │   ├── QueryActions.tsx            # Accept/Reject/Regenerate buttons
│   │   │   ├── SqlDisplay.tsx              # Syntax-highlighted SQL viewer
│   │   │   ├── HistoryList.tsx             # History entries with filter
│   │   │   ├── HistoryDetail.tsx           # Full query detail view
│   │   │   └── SignInForm.tsx              # Login form (RHF + Zod)
│   │   ├── pages/
│   │   │   ├── SignInPage.tsx
│   │   │   ├── AskQuestionPage.tsx         # Main query interface
│   │   │   └── HistoryPage.tsx
│   │   ├── hooks/
│   │   │   ├── useAuth.ts                  # Auth state + sign-in/out mutations
│   │   │   ├── useQuery.ts                 # Submit/accept/reject/regenerate
│   │   │   └── useHistory.ts               # Cursor-paginated history list + detail queries
│   │   ├── i18n/
│   │   │   ├── index.ts                    # i18next configuration
│   │   │   └── locales/
│   │   │       └── en.json                 # All user-facing strings
│   │   ├── lib/
│   │   │   ├── api-client.ts               # Configured axios/fetch instance
│   │   │   └── constants.ts                # Shared constants
│   │   └── styles/
│   │       └── globals.css                 # Tailwind imports, base styles
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── QueryInput.test.tsx
│   │   │   ├── ResultTable.test.tsx
│   │   │   └── HistoryList.test.tsx
│   │   └── e2e/
│   │       ├── auth.spec.ts                # Sign-in/out flow
│   │       ├── query-flow.spec.ts          # Submit → evaluate → result → accept
│   │       ├── reject-retry.spec.ts        # Reject → auto-retry → refine
│   │       └── history.spec.ts             # History list + filter + detail
│   └── Dockerfile                          # Multi-stage build (nginx)
├── docker-compose.yml                      # Production-like compose
├── docker-compose.dev.yml                  # Dev compose with hot-reload
├── docs/
│   └── api/
│       └── openapi.json                    # Generated at build time
├── .specify/
└── specs/
```

**Structure Decision**: Option 2 — Web application with `backend/` and `frontend/` as independently deployable sibling directories. This aligns with Constitution Principle XI (modularity) and Principle XII (API contract as single source of truth).

---

## Architectural Invariants

These invariants are non-negotiable and must be enforced by code structure and tests:

1. **Evaluator Gate (Principle II)**: `QueryService.submit_question()` MUST call `Evaluator.evaluate()` before `SourceDBExecutor.execute()`. There is no bypass path. Tested by integration tests that mock evaluator-fail and verify DB is never contacted.

2. **Accept-Only Persistence (Principle III)**: Only `HistoryService.accept()` calls `AcceptedQueryRepository.create()`. The reject and regenerate handlers MUST NOT write to `accepted_queries`. Tested by unit tests that assert no repository write on reject/regenerate.

3. **No Concurrent Submissions (FR-030)**: Enforced server-side via a Redis-based per-session mutex (`SET session:{id}:processing NX EX <query_timeout_seconds + 10, capped at 60>`). The lock TTL is a safety net for crashed processes only — the `QueryService` MUST release the lock in a `finally` block at the end of every submit/reject/regenerate handler. The frontend also disables the submit button during processing.

4. **Byte-Equal Duplicate Detection (SC-005)**: After regeneration, `QueryService` compares the new SQL byte-for-byte against the rejected SQL. If identical, it treats it as a failed regeneration (same behavior as two consecutive rejections).

5. **Read-Only Source DB (FR-005, Principle VIII)**: The `SourceDBConnector` connects with a read-only PostgreSQL role. The evaluator also rejects non-SELECT SQL as a defense-in-depth measure.

6. **Ephemeral Attempt Ownership (Redis)**: Ephemeral attempts are stored in Redis under `attempt:{attempt_id}` with a 15-minute TTL. `QueryService` MUST validate `attempt_id` ownership against the current session before any accept/reject/regenerate operation. If `session_id` in the stored attempt does not match the current session, the handler returns `400 Bad Request`. This prevents cross-session attempt hijacking.

---

## Component Design

### Backend: Evaluator Pipeline

```
evaluate(sql: str, schema: SchemaContext) → EvaluatorResult
    ├── ReadOnlyRule          # Parse AST, reject non-SELECT/CTE
    ├── SingleStatementRule   # Reject multi-statement SQL
    ├── SchemaValidationRule  # Check table/column references vs. schema
    └── UnsafePatternRule     # Platform-defined patterns (extensible)
```

Each rule implements the `EvaluatorRule` protocol:
```python
class EvaluatorRule(Protocol):
    def check(self, parsed: sqlglot.Expression, schema: SchemaContext) -> list[EvaluatorViolation]: ...
```

The pipeline fans out to all rules, collects violations, and returns `EvaluatorResult(passed=len(violations)==0, violations=violations)`. Adding a future LLM-judge rule means appending to the rule list — no changes to `QueryService` or the pipeline itself (FR-011).

### Backend: LLM Provider Abstraction

```python
class LLMProvider(Protocol):
    async def generate_sql(
        self,
        question: str,
        schema_context: str,
        negative_examples: list[str] | None = None,
    ) -> str: ...
```

Four adapters (`AnthropicAdapter`, `OpenAIAdapter`, `GeminiAdapter`, `OllamaAdapter`) implement this protocol using `httpx` as the HTTP client. The factory reads `LLM_PROVIDER` from config and instantiates the matching adapter at startup.

### Backend: Query Service State Machine

```
User submits question
    │
    ▼
LLM generates SQL (attempt #1)
    │
    ▼
Evaluator checks SQL
    ├── FAIL → Return evaluator rejection to user
    │
    ├── PASS → Execute SQL against source DB
    │           │
    │           ├── Timeout → Return timeout error
    │           ├── Error → Return execution error
    │           └── Success → Return QueryResult (attempt=1, is_last=false)
    │
    ▼
User decision:
    ├── Accept → Persist to accepted_queries → confirmation
    │
    ├── Reject/Regenerate (attempt #1)
    │       │
    │       ▼
    │   LLM generates SQL (attempt #2, with negative context)
    │       │
    │       ├── Byte-equal to rejected SQL → RefinePrompt
    │       │
    │       ├── Evaluator FAIL → RefinePrompt (cannot retry further)
    │       │
    │       └── Evaluator PASS → Execute → Return QueryResult (attempt=2, is_last=true)
    │               │
    │               ├── Accept → Persist
    │               └── Reject → RefinePrompt (max retries reached)
    │
    └── New question → Reset counter, start fresh
```

### Frontend: Page Routing

| Route | Page | Auth Required |
|-------|------|---------------|
| `/sign-in` | `SignInPage` | No |
| `/` | `AskQuestionPage` | Yes |
| `/history` | `HistoryPage` | Yes |
| `/history/:id` | `HistoryPage` (detail panel) | Yes |

### Frontend: i18n Key Structure

```json
{
  "auth.signIn.title": "Sign In",
  "auth.signIn.username": "Username",
  "auth.signIn.password": "Password",
  "auth.signIn.submit": "Sign In",
  "auth.signIn.error.invalid": "Invalid username or password",
  "query.input.placeholder": "Ask a question about your data...",
  "query.input.charLimit": "{{current}}/{{max}} characters",
  "query.input.submit": "Ask",
  "query.result.title": "Results",
  "query.result.sql": "Generated SQL",
  "query.result.noRows": "No results found for your query",
  "query.result.accept": "Accept",
  "query.result.reject": "Reject",
  "query.result.regenerate": "Regenerate",
  "query.result.lastRetry": "This is the last automatic attempt",
  "query.result.accepted": "Query saved to history",
  "query.evaluator.rejected": "We couldn't generate a safe query for your question. Please try rephrasing it in a different way.",
  "query.refine.message": "We couldn't find a different answer. Please try refining or rephrasing your question.",
  "query.error.timeout": "The query took too long to execute. Please try a simpler question.",
  "query.error.llmUnavailable": "The query service is temporarily unavailable. Please try again later.",
  "query.error.concurrent": "A question is already being processed. Please wait.",
  "error.unauthorized": "Your session has expired or you are not signed in. Please sign in again.",
  "error.forbidden": "This request was blocked for security reasons.",
  "error.notFound": "The requested resource was not found.",
  "error.attemptExpired": "This query attempt has expired. Please submit a new question.",
  "error.attemptInvalid": "No active query result to act on.",
  "error.timeout": "The query took too long to execute. Please try a simpler question.",
  "error.llmUnavailable": "The query service is temporarily unavailable. Please try again later.",
  "error.concurrent": "A question is already being processed. Please wait.",
  "error.schemaTokenLimit": "The database schema is too large ({{tokens}} tokens, limit {{limit}}). Please contact your administrator.",
  "error.validation.questionTooLong": "Question must be at most {{max}} characters.",
  "error.validation.questionEmpty": "Question cannot be empty.",
  "error.validation.generic": "Validation failed. Please check your input.",
  "evaluator.violation.dataModifying": "The generated SQL contains data-modifying statements ({{statement}}) which are not allowed.",
  "evaluator.violation.multiStatement": "The generated SQL contains multiple statements. Only a single query is allowed.",
  "evaluator.violation.unknownTable": "The generated SQL references a table '{{table}}' that does not exist in the database.",
  "evaluator.violation.unknownColumn": "The generated SQL references a column '{{column}}' that does not exist in table '{{table}}'.",
  "evaluator.violation.unsafePattern": "The generated SQL contains an unsafe pattern that is not allowed.",
  "history.title": "Query History",
  "history.empty": "No accepted queries yet",
  "history.filter.placeholder": "Filter by question or SQL...",
  "history.detail.question": "Question",
  "history.detail.sql": "SQL",
  "history.detail.acceptedAt": "Accepted"
}
```

---

## Constitution Check — Post-Design Re-evaluation

| Principle | Pre-Design | Post-Design | Notes |
|-----------|-----------|-------------|-------|
| I — Security | ✅ Pass | ✅ Pass | Argon2, HttpOnly/SameSite=Strict cookies (R-007), Origin validation (R-007), AES-256-GCM source-DB credential encryption (R-008), env-only secrets, read-only source DB. |
| II — Query Validated | ✅ Pass | ✅ Pass | Evaluator pipeline is mandatory in QueryService. No bypass path. |
| III — Validated Knowledge | ✅ Pass | ✅ Pass | Only accept() writes to history. reject()/regenerate() are ephemeral (Redis-only, 15-min TTL). |
| V — LLM-Agnostic | ✅ Pass | ✅ Pass | Protocol + 4 adapters + factory. Config-driven selection. |
| VIII — Centrally Brokered | ✅ Pass | ✅ Pass | DB creds in platform config only. No user-facing credential input. |
| XI — Modularity | ✅ Pass | ✅ Pass | Layered backend, independent frontend, versioned API. |
| XII — API Contract | ✅ Pass | ✅ Pass | OpenAPI generated, frontend types generated, schemathesis tests. |
| IV — Injection Detection | ⏸ Deferred | ⏸ Deferred | Phase 6. Basic evaluator is not injection detection. |
| VI — Arabic + RTL | ⏸ Deferred | ⏸ Deferred | Phase 4. Foundations (i18n keys, logical CSS) are in place. |
| VII — SSO + RBAC | ⏸ Deferred | ⏸ Deferred | Phase 5. Local admin only. |
| IX — Audit Log | ⏸ Deferred | ⏸ Deferred | Phase 6. structlog operational logs are not tamper-evident audit. |
| X — Quotas | ⏸ Deferred | ⏸ Deferred | Phase 6. Single user, no quotas needed. |

**All gates pass. No violations to justify.**

---

## Complexity Tracking

No complexity violations. All design decisions align with spec and constitution requirements.

---

## Research Artifacts

All research items from the technical context have been resolved in [research.md](file:///home/avril/QueryCraft/specs/001-core-text-to-sql/research.md):

| Research Item | Decision | Reference |
|---------------|----------|-----------|
| LLM prompt structure | Structured system prompt with chain-of-thought, dynamic schema injection, strict output format | R-001 |
| Session backing store | Redis 7 with TTL-based idle expiry | R-002 |
| Schema introspection + cache | `information_schema` views, in-memory cache with 5-min TTL, manual refresh endpoint, token-limit escalation | R-003 |
| sqlglot PostgreSQL support | Suitable for Phase 1; CTEs, window functions, JSON operators supported; targeted test suite mitigates edge cases | R-004 |
| Architecture pattern | Layered (Clean) Architecture | R-005 |
| Contract-first development | FastAPI auto-generates OpenAPI; frontend types generated from it | R-006 |
| CSRF strategy | SameSite=Strict cookie + Origin header validation on state-changing requests | R-007 |
| Source-DB credential encryption | AES-256-GCM with `PLATFORM_ENCRYPTION_KEY` env var; column-level encryption in `database_connections` | R-008 |

---

## Design Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| Research | [research.md](file:///home/avril/QueryCraft/specs/001-core-text-to-sql/research.md) | All research decisions and rationale |
| Data Model | [data-model.md](file:///home/avril/QueryCraft/specs/001-core-text-to-sql/data-model.md) | 4 tables + ephemeral entities + Redis sessions + schema token escalation |
| API Contract | [openapi.yaml](file:///home/avril/QueryCraft/specs/001-core-text-to-sql/contracts/openapi.yaml) | OpenAPI 3.1 — 9 endpoints (incl. admin) |
| Quickstart | [quickstart.md](file:///home/avril/QueryCraft/specs/001-core-text-to-sql/quickstart.md) | Developer setup guide |
