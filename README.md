# QueryCraft — Text-to-SQL Analytics Platform

Enterprise-grade, secure, LLM-agnostic analytics platform for querying PostgreSQL databases using natural language.

## Monorepo Structure

- `backend/`: FastAPI + SQLAlchemy 2.0 async + PostgreSQL backend
- `frontend/`: React 18 + TypeScript + Vite + Tailwind CSS v4 frontend
- `shared/`: (Placeholder)
- `specs/`: Project specifications, requirements, and design documents

## Local Development Quickstart

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Start all services using Docker Compose:
   ```bash
   docker compose -f docker-compose.dev.yml up -d --build
   ```

3. Access the applications:
   - Frontend: http://localhost:3000
   - Backend API Docs: http://localhost:8000/docs
