# QueryCraft — Text-to-SQL Analytics Platform

Enterprise-grade, secure, LLM-agnostic analytics platform for querying PostgreSQL, MySQL, and MSSQL databases using natural language.

## Supported Source Databases

| Database | Driver | Default Port |
|----------|--------|-------------|
| PostgreSQL | `asyncpg` | 5432 |
| MySQL | `asyncmy` | 3306 |
| MSSQL | `aioodbc` | 1433 |

### MSSQL System Dependencies (Linux)

The MSSQL adapter requires ODBC driver libraries. On Debian/Ubuntu-based systems:

```bash
apt-get install -y unixodbc unixodbc-dev freetds-dev tdsodbc
```

These are pre-installed in the Docker image (see `backend/Dockerfile`). macOS users can install via Homebrew: `brew install unixodbc freetds`.

## Local Source Database Setup

QueryCraft ships with a local PostgreSQL source DB for query execution and smoke testing. The source DB is seeded from `dbTest/init/` and uses the Pagila sample schema/data.

### 1. Load Pagila seed files

From repo root:

```bash
cd dbTest/init
curl -L -o 01-schema.sql https://raw.githubusercontent.com/devrimgunduz/pagila/master/pagila-schema.sql
curl -L -o 02-data.sql https://raw.githubusercontent.com/devrimgunduz/pagila/master/pagila-data.sql
```

If you already downloaded them earlier, keep the filenames exactly as `01-schema.sql` and `02-data.sql` so Docker init picks them up in order.

### 2. Start the source DB

```bash
docker compose -f docker-compose.dev.yml up -d postgres-source
```

The container runs the files in `dbTest/init/` during first boot and applies `03-grants.sql` for the read-only app role.

### 3. Verify the seed

```bash
docker compose exec postgres-source psql -U pagila_user -d source_analytics -c "SELECT count(*) FROM actor;"
docker compose exec postgres-source psql -U pagila_user -d source_analytics -c "INSERT INTO actor (first_name, last_name) VALUES ('Devin', 'Test');"
```

The first command should return the expected row count. The second should fail with read-only permission denied.

### 4. App connection values

The backend reads source DB credentials from `.env`:

- `SOURCE_DB_HOST`
- `SOURCE_DB_PORT`
- `SOURCE_DB_NAME`
- `SOURCE_DB_USER`
- `SOURCE_DB_PASSWORD`
- `SOURCE_DB_SSL_MODE`

The default local compose values in `.env.example` point at `postgres-source` on port `5432` with the Pagila readonly user.

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

```bash
./scripts/dev-up.sh           # bootstrap or refresh the local stack
```

The script handles `.env` creation, encryption-key generation, image rebuild, container recreate, and `alembic upgrade head` automatically.

Sign in at http://localhost:5173 with the credentials from `.env`.

**After every `git pull`, run `./scripts/dev-up.sh --rebuild`** — `docker compose restart` does NOT pick up Python source changes, env-file changes, or new migrations.

Other helpers:
- `./scripts/dev-up.sh --rebuild` — force a clean image rebuild + recreate
- `./scripts/dev-up.sh --reset` — wipe volumes and start fresh (destructive)

### Manual Bootstrap (alternative)

If you prefer to run the steps manually:

1. `cp .env.example .env` and fill `PLATFORM_ENCRYPTION_KEY` (use the python one-liner from .env.example) and any LLM API key for your chosen provider.
2. `docker compose -f docker-compose.dev.yml up -d`
3. Wait for postgres-platform to be healthy, then: `docker compose exec backend alembic upgrade head` (this runs migrations 001 and 002 — admin user is seeded from the .env vars).
4. Visit http://localhost:5173 and sign in with the admin credentials from .env.

### 3. Native Bootstrap (Backend)
1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. `cd backend && uv sync --all-extras`
3. `uv run pytest -q`
4. `uv run uvicorn app.main:create_app --factory --reload`

## Database Connections

Database connections are managed from the admin UI under the Connections page.

### Add a connection

1. Open the app and sign in as an admin user.
2. Open the sidebar `Connections` link.
3. Click the `+` add button in the page header.
4. Enter a display name, choose the database type, and fill host, port, database name, user, and password.
5. Click `Test Connection` before saving.

### Edit or disable a connection

- Use the row actions to edit, disable, enable, or delete a connection.
- `Test Connection` verifies reachability and auth.
- `Refresh Schema` reloads introspected tables and columns.

### Workspace usage

- The workspace selector shows only active and healthy connections.
- When only one usable connection exists, it auto-selects.
- Queries always run against the selected connection.
- History entries show the user-facing connection display name and database type, not raw IDs.

### Smoke checklist

- Workspace loads and selector is visible.
- History list opens and returns with browser back/forward.
- New Chat returns to `/` and clears the current session.
- Admin connection status messages clear automatically after a short delay.
- Arabic/RTL route renders correctly with localized labels.

## LLM Provider Configuration

QueryCraft is LLM-agnostic — pick one of `anthropic`, `openai`, `gemini`, or `ollama` via `LLM_PROVIDER` and provide the matching credentials in `.env`. Optionally pin a specific model with `LLM_MODEL_NAME`; if omitted, each adapter uses a sensible default (`claude-3-5-sonnet-20241022` / `gpt-4o` / `gemini-1.5-pro` / `llama3.1`).

After editing `.env`, restart the backend so the lifespan picks up the new settings:

```bash
docker compose -f docker-compose.dev.yml restart backend
```

### Example: Gemini 2.5 Pro

```env
LLM_PROVIDER=gemini
LLM_MODEL_NAME=gemini-2.5-pro
LLM_API_KEY_GEMINI=<your key from https://aistudio.google.com/apikey>
```

### Example: Local Ollama model

```bash
ollama pull qwen2.5-coder:14b   # or whatever tag you want
ollama serve                     # default port 11434
```

```env
LLM_PROVIDER=ollama
LLM_MODEL_NAME=qwen2.5-coder:14b
# Bridging from inside docker-compose to your host's Ollama:
#   macOS / Windows:  http://host.docker.internal:11434
#   Linux:            http://172.17.0.1:11434
LLM_BASE_URL_OLLAMA=http://host.docker.internal:11434
```

Verify the backend container can reach Ollama before submitting a query:

```bash
docker compose -f docker-compose.dev.yml exec backend \
  curl -s http://host.docker.internal:11434/api/tags
```

### Switching providers

The `LLMProviderFactory` caches one adapter instance per `(provider, model, api-key fingerprint)` and the FastAPI lifespan closes its `httpx.AsyncClient` cleanly on shutdown — so flipping `LLM_PROVIDER` in `.env` and restarting the backend is safe and leak-free.
