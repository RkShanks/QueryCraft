# Quickstart: Core Text-to-SQL Vertical Slice

**Branch**: `001-core-text-to-sql` | **Date**: 2026-05-03

## Prerequisites

- Docker & Docker Compose v2
- Node.js 22.x LTS (for frontend development)
- Python 3.12 (for backend development outside Docker)

## Local Dev Bootstrap

1. `git clone <repo> && cd querycraft && git checkout 001-core-text-to-sql`
2. `cp .env.example .env` and fill `PLATFORM_ENCRYPTION_KEY` (use the python one-liner from .env.example) and any LLM API key for your chosen provider.
3. `docker compose -f docker-compose.dev.yml up -d`
4. Wait for postgres-platform to be healthy, then: `docker compose exec backend alembic upgrade head` (this runs migrations 001 and 002 — admin user is seeded from the .env vars).
5. Visit http://localhost:5173 and sign in with the admin credentials from .env.

### 1. Try the happy path

1. Type: "How many orders were placed last month?"
2. View the table result and the SQL
3. Click **Accept** — the query appears in History
4. Navigate to **History** — see your accepted query

## Development Workflow

### Backend (without Docker)

uv is used for backend dependency management — it's faster than pip and produces a deterministic `uv.lock` committed to the repo.

```bash
cd backend
uv sync --all-extras

# Run migrations
uv run alembic upgrade head

# Start dev server
uv run uvicorn app.main:create_app --factory --reload --port 8000
```

### Frontend (without Docker)

```bash
cd frontend
npm install

# Generate API client from backend's OpenAPI
npm run generate-api

# Start dev server
npm run dev
```

### Running Tests

```bash
# Backend unit tests
cd backend && uv run pytest tests/unit/ -v

# Backend integration tests (requires Docker services)
cd backend && uv run pytest tests/integration/ -v

# Backend contract tests
cd backend && uv run pytest tests/contract/ -v

# Frontend unit tests
cd frontend && npm test

# Frontend e2e tests (requires all services running)
cd frontend && npx playwright test
```

### Generating the API Client

After modifying any FastAPI route or schema:

```bash
# Export OpenAPI spec
cd backend && uv run python -c "from app.main import app; import json; print(json.dumps(app.openapi()))" > ../docs/api/openapi.json

# Regenerate frontend client
cd frontend && npm run generate-api
```

## Key Directories

| Path | Purpose |
|------|---------|
| `backend/src/app/api/v1/` | FastAPI routers (thin controllers) |
| `backend/src/app/services/` | Business logic |
| `backend/src/app/evaluator/` | SQL evaluator pipeline |
| `backend/src/app/llm/` | LLM provider adapters |
| `backend/src/app/source_db/` | Source DB connector + schema introspection |
| `frontend/src/pages/` | React page components |
| `frontend/src/i18n/locales/en.json` | English i18n strings |
| `specs/001-core-text-to-sql/` | Spec, plan, contracts |
