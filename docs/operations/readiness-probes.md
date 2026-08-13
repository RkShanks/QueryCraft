# Operational liveness and readiness

QueryCraft exposes two public root-level HTTP probes. Neither probe parses the session cookie.

| Probe | Success | Failure | Dependencies |
| --- | --- | --- | --- |
| `GET /health` | `200 {"status":"live"}` | None while the event loop serves requests | None |
| `GET /ready` | `200 {"status":"ready"}` | `503 {"status":"not_ready"}` | Startup lifecycle, platform PostgreSQL, current Alembic revision, Redis |

`/health` does not read PostgreSQL, Redis, source databases, provider configuration, sessions, audit state, migrations, or credentials. It remains live during graceful shutdown while the server still accepts requests.

`/ready` becomes eligible for success only after Redis initialization, startup migration validation, credential-provider initialization, source-row synchronization, and admin synchronization. Shutdown marks it not ready before the first closer runs. Each request then performs two concurrent checks within `READINESS_TIMEOUT_SECONDS`, which defaults to 2 seconds:

- one read-only, autocommit platform PostgreSQL query verifies both `SELECT 1` and the current `alembic_version` against the cached source-tree head;
- one `PING` uses the initialized application Redis client.

The checks reuse the application-managed SQLAlchemy engine pool and Redis client. A single readiness slot bounds concurrent pool use. The database revision is read on every request, so PostgreSQL, Redis, and revision recovery can restore readiness without restarting the backend. Timeout, malformed response, revision mismatch, and dependency error paths all return the same constant 503 body.

Source PostgreSQL/MySQL/MSSQL databases, source-connection health rows, LLM providers, and SSO identity providers are excluded. Their failures are feature-specific and do not make the control plane unready.

## Compose and local startup

The backend Compose healthcheck uses Python from the backend image to call `/ready`. It runs every 2 seconds with a 3-second timeout, 15 retries, and a 10-second start period. Platform PostgreSQL and Redis remain health-gated dependencies; source databases are not backend-readiness dependencies. Frontend creation waits for backend `service_healthy`.

`./scripts/dev-up.sh`, `./scripts/dev-up.sh --rebuild`, and the destructive `./scripts/dev-up.sh --reset` follow the same order:

1. Build the required application image and start healthy platform PostgreSQL and Redis infrastructure.
2. Stop any existing frontend and backend application containers.
3. Run `alembic upgrade head` in a one-off, non-serving backend container.
4. Start the backend and wait for Compose to report it healthy.
5. Start the frontend.

If backend readiness does not arrive within 60 seconds, the script exits nonzero and points to:

```bash
docker compose -f docker-compose.dev.yml logs backend
```
