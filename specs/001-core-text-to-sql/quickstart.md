# Quickstart: Core Text-to-SQL Vertical Slice

**Branch**: `001-core-text-to-sql` | **Date**: 2026-05-03

## Prerequisites

- Docker & Docker Compose v2
- Node.js 22.x LTS (for frontend development)
- Python 3.12 (for backend development outside Docker)

## Local Development Setup

### 1. Clone and checkout

```bash
git clone <repo-url> QueryCraft
cd QueryCraft
git checkout 001-core-text-to-sql
```

### 2. Configure environment

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` with:

```env
# Platform metadata database
PLATFORM_DB_URL=postgresql+asyncpg://querycraft:querycraft@localhost:5433/querycraft

# Source database (read-only)
SOURCE_DB_HOST=localhost
SOURCE_DB_PORT=5434
SOURCE_DB_NAME=source_analytics
SOURCE_DB_USER=readonly_user
SOURCE_DB_PASSWORD=readonly_pass

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM provider (one of: anthropic, openai, gemini, ollama)
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...
LLM_BASE_URL=  # Only needed for ollama (e.g., http://localhost:11434)

# Admin account (seeded on first run)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme123

# Session
SESSION_SECRET=<random-32-byte-hex>
SESSION_IDLE_TIMEOUT_HOURS=8

# CSRF (R-007)
ALLOWED_ORIGINS=["http://localhost:5173"]

# Encryption (R-008)
PLATFORM_ENCRYPTION_KEY=<base64-encoded-32-byte-key>

# Query
QUERY_TIMEOUT_SECONDS=30
MAX_QUESTION_LENGTH=2000
SCHEMA_CACHE_TTL_SECONDS=300
MAX_SCHEMA_TOKENS=60000
```

### 3. Start all services via Docker Compose

```bash
docker-compose -f docker-compose.dev.yml up -d
```

This starts:
- **Platform PostgreSQL** (port 5433) — metadata DB with migrations auto-applied
- **Source PostgreSQL** (port 5434) — sample analytics DB with seed data
- **Redis** (port 6379) — session store
- **Backend** (port 8000) — FastAPI with hot-reload
- **Frontend** (port 5173) — Vite dev server with HMR

### 4. Access the platform

Open `http://localhost:5173` in your browser. Sign in with:
- Username: `admin`
- Password: `changeme123`

### 5. Try the happy path

1. Type: "How many orders were placed last month?"
2. View the table result and the SQL
3. Click **Accept** — the query appears in History
4. Navigate to **History** — see your accepted query

## Development Workflow

### Backend (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start dev server
uvicorn src.app.main:app --reload --port 8000
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
cd backend && pytest tests/unit/ -v

# Backend integration tests (requires Docker services)
cd backend && pytest tests/integration/ -v

# Backend contract tests
cd backend && pytest tests/contract/ -v

# Frontend unit tests
cd frontend && npm test

# Frontend e2e tests (requires all services running)
cd frontend && npx playwright test
```

### Generating the API Client

After modifying any FastAPI route or schema:

```bash
# Export OpenAPI spec
cd backend && python -c "from app.main import app; import json; print(json.dumps(app.openapi()))" > ../docs/api/openapi.json

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
