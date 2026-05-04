# QueryCraft — Text-to-SQL Analytics Platform

Enterprise-grade, secure, LLM-agnostic analytics platform for querying PostgreSQL databases using natural language.

## Monorepo Structure

- `backend/`: FastAPI + SQLAlchemy 2.0 async + PostgreSQL backend
- `frontend/`: React 18 + TypeScript + Vite + Tailwind CSS v4 frontend
- `shared/`: (Placeholder)
- `specs/`: Project specifications, requirements, and design documents

## Local Dev Bootstrap

1. `git clone <repo> && cd querycraft && git checkout 001-core-text-to-sql`
2. `cp .env.example .env` and fill `PLATFORM_ENCRYPTION_KEY` (use the python one-liner from .env.example) and any LLM API key for your chosen provider.
3. `docker compose -f docker-compose.dev.yml up -d`
4. Wait for postgres-platform to be healthy, then: `docker compose exec backend alembic upgrade head` (this runs migrations 001 and 002 — admin user is seeded from the .env vars).
5. Visit http://localhost:5173 and sign in with the admin credentials from .env.
