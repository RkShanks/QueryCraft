# Pre-Flight Prerequisites

Prepared on 2026-07-03 from `main` at
`0ae7f526c65f257a09d0d3e53afcd98492083890`.

This file records lightweight prerequisite discovery only. It does not record a
full regression run.

## Required Tools

| Tool | Check command | Current discovery |
|---|---|---|
| Git/RTK | `rtk git status --short --branch` | `main...origin/main`, clean before branch creation |
| Python | `rtk python3 --version` | Python 3.12.3 |
| uv | `rtk uv --version` | uv 0.10.5 |
| Node | `rtk node --version` | v20.20.2 |
| npm | `rtk npm --version` | 11.14.1 |
| Docker | `rtk docker ps` | Docker reachable with escalation; QueryCraft containers running |
| Docker Compose | `rtk docker compose -f docker-compose.dev.yml ps` | QueryCraft compose services running |
| Playwright | `cd frontend && rtk npm exec playwright -- --version` | 1.59.1 |
| Browser | `rtk ls /home/avril/.cache/ms-playwright` | Chromium cache exists |
| Chrome binary | `rtk bash -lc 'command -v google-chrome'` | `/usr/bin/google-chrome` |

## Required Docker Services

Start command if needed:

```bash
rtk docker compose -f docker-compose.dev.yml up -d
```

Read-only status checks:

```bash
rtk docker ps
rtk docker compose -f docker-compose.dev.yml ps
rtk ss -ltnp
```

Current discovery:

- `querycraft-backend-1`: running on `8000`.
- `querycraft-frontend-1`: running on `5173`.
- `querycraft-postgres-platform-1`: healthy on `5433`.
- `querycraft-postgres-source-1`: healthy on `5434`.
- `querycraft-redis-1`: healthy on `6379`.
- `querycraft-mysql-source-1`: healthy on `3306`.
- `querycraft-mssql-source-1`: healthy on `1433`.

An unrelated `local-atlas-hybrid` container is present and unhealthy. It is not
part of the QueryCraft compose service list.

## Required Env Vars

Check shell visibility without printing values:

```bash
rtk bash -lc 'for n in DATABASE_URL REDIS_URL DB_CREDENTIAL_KEY PLATFORM_ENCRYPTION_KEY ADMIN_API_KEY LLM_PROVIDER LLM_API_KEY_GEMINI LLM_BASE_URL_OLLAMA LLM_MODEL_NAME MYSQL_ROOT_PASSWORD MYSQL_USER MYSQL_PASSWORD MSSQL_SA_PASSWORD MSSQL_USER MSSQL_PASSWORD; do if [ -n "${!n}" ]; then printf "%s=present\n" "$n"; else printf "%s=missing\n" "$n"; fi; done'
```

Check `.env` values without printing secrets:

```bash
rtk awk -F= '/^(DATABASE_URL|REDIS_URL|DB_CREDENTIAL_KEY|PLATFORM_ENCRYPTION_KEY|ADMIN_API_KEY|LLM_PROVIDER|LLM_API_KEY_ANTHROPIC|LLM_API_KEY_OPENAI|LLM_API_KEY_GEMINI|LLM_BASE_URL_OLLAMA|LLM_MODEL_NAME|MYSQL_ROOT_PASSWORD|MYSQL_USER|MYSQL_PASSWORD|MSSQL_SA_PASSWORD|MSSQL_USER|MSSQL_PASSWORD)=/ {print $1 "=" (($2 == "") ? "empty" : "set")}' .env
```

Current discovery:

- Current shell env is missing the obvious QueryCraft runtime variables.
- `.env` has `DATABASE_URL`, `REDIS_URL`, `PLATFORM_ENCRYPTION_KEY`,
  `DB_CREDENTIAL_KEY`, `ADMIN_API_KEY`, `LLM_PROVIDER`, `LLM_API_KEY_GEMINI`,
  `LLM_BASE_URL_OLLAMA`, `LLM_MODEL_NAME`, MySQL vars, and MSSQL vars set.
- `.env` has `LLM_API_KEY_ANTHROPIC` and `LLM_API_KEY_OPENAI` empty.

For host-run backend commands that need real runtime env, source `.env` safely or
run through the compose environment. Do not print secret values in reports.

## Required Browser / Playwright Setup

The project has `frontend/playwright.config.ts` with `testDir: ./tests/e2e`,
Chromium project, and default `E2E_BASE_URL` fallback behavior. The package
scripts include:

```bash
cd frontend && rtk npm run test:e2e
cd frontend && rtk npm run test:e2e:ui
```

Current discovery:

- `frontend/node_modules/.bin/playwright` exists.
- `cd frontend && rtk npm exec playwright -- --version` reports 1.59.1.
- `/home/avril/.cache/ms-playwright` contains Chromium browser caches.
- `frontend/node_modules/.cache/ms-playwright` does not exist, which is not a
  blocker because the global cache exists.

## Required MCP / DevTools

Phase 4/5 historical docs mention Chrome DevTools MCP smoke. In this Codex
session, no Chrome DevTools MCP tool is exposed.

Use Playwright for browser smoke unless the runner explicitly has Chrome
DevTools MCP. To check CDP manually:

```bash
rtk ss -ltnp
```

Current discovery:

- No obvious Chrome remote debugging port such as `9222` is listening.
- Standard app/service ports are listening.

## Required Real LLM Setup

Real LLM smoke requires:

- `LLM_PROVIDER` set to the desired provider.
- Provider key for cloud providers, such as `LLM_API_KEY_GEMINI`.
- `LLM_MODEL_NAME` pinned or adapter default accepted.
- For Ollama, `LLM_BASE_URL_OLLAMA` reachable from the backend runtime.

Current discovery:

- `.env` has `LLM_PROVIDER`, `LLM_API_KEY_GEMINI`, `LLM_BASE_URL_OLLAMA`, and
  `LLM_MODEL_NAME` set.
- Anthropic/OpenAI keys are empty.
- Current shell does not expose those variables; use compose env or explicitly
  export/safe-source `.env` before host-run real LLM smoke.

## Missing / Needs User Action

- Full regression execution still requires explicit approval; this artifact prep
  did not run full tests.
- Host-run commands that need env must be launched with `.env` loaded, because
  the current shell does not expose the runtime variables.
- Chrome DevTools MCP is not available in this session. Use Playwright, or start
  a CDP-enabled Chrome and provide MCP access if CDP-specific verification is
  required.
- Do not start T-905, edit Phase 6 freeze metadata, or mark Phase 6 frozen from
  this pre-flight.
