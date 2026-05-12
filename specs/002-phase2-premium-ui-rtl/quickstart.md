# Phase 2 Quickstart

## Prerequisites

- Docker + Docker Compose (for PostgreSQL + Redis)
- Node.js 22+ / npm 10+
- Python 3.12+ / uv
- Git

## Setup

```bash
# Start infrastructure
docker compose -f docker-compose.dev.yml up -d

# Backend
cd backend
uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run gen:api    # regenerate API client from FastAPI OpenAPI
npm run dev        # starts on http://localhost:3000
```

## Quality Gates (run before every PR)

```bash
# Backend
cd backend
uv run pytest
uv run ruff check
uv run ruff format --check

# Frontend
cd frontend
npm run test
npm run lint
npm run lint:css      # Constitution VI physical-direction lint
npm run typecheck
npm run build
```

## Key Commands

| Command | Purpose |
|---------|---------|
| `uv run alembic revision --autogenerate -m "desc"` | New migration |
| `uv run alembic upgrade head` | Apply migrations |
| `npm run gen:api` | Regenerate frontend API client |
| `npm run test:e2e` | Playwright end-to-end tests |
| `npm run test:e2e:ui` | Playwright UI mode |

## Environment Variables

See `.env.example` for all required environment variables. Key additions for Phase 2:

- No new env vars required — `llm_context_cap` is stored in the `app_config` DB table.
