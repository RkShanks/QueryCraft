# QueryCraft — Text-to-SQL Analytics Platform

Enterprise-grade, secure, LLM-agnostic analytics platform for querying PostgreSQL databases using natural language.

## Monorepo Structure

- `backend/`: FastAPI + SQLAlchemy 2.0 async + PostgreSQL backend
- `frontend/`: React 18 + TypeScript + Vite + Tailwind CSS v4 frontend
- `shared/`: (Placeholder)
- `specs/`: Project specifications, requirements, and design documents

## Local Dev Bootstrap

uv is used for backend dependency management — it's faster than pip and produces a deterministic `uv.lock` committed to the repo.

### 1. Initial Setup
1. `git clone <repo> && cd querycraft && git checkout 001-core-text-to-sql`
2. `cp .env.example .env` and fill `PLATFORM_ENCRYPTION_KEY` (use the python one-liner from .env.example) and any LLM API key for your chosen provider.

### 2. Docker Bootstrap (Recommended)
1. `docker compose -f docker-compose.dev.yml up -d`
2. Wait for postgres-platform to be healthy, then: `docker compose exec backend alembic upgrade head` (this runs migrations 001 and 002 — admin user is seeded from the .env vars).
3. Visit http://localhost:5173 and sign in with the admin credentials from .env.

### 3. Native Bootstrap (Backend)
1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. `cd backend && uv sync --all-extras`
3. `uv run pytest -q`
4. `uv run uvicorn app.main:create_app --factory --reload`
