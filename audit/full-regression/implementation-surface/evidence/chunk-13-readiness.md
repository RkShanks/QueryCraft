# CHUNK-13 / IS-GAP-007 — liveness, readiness, and Compose gating

Status: implementation and isolated production-like proof passed on branch `phase-6/wave-19.13-readiness`; authoritative GitHub backend/frontend CI is pending.

Tested product commit: `1c56b6305329cbc82fff5cc4066c995f2717873b`.

## Operational contract

| Endpoint | Ready state | Degraded state | Authentication/session dependency |
| --- | --- | --- | --- |
| `GET /health` | 200 `{"status":"live"}` | 200 `{"status":"live"}` while the process serves requests | none |
| `GET /ready` | 200 `{"status":"ready"}` | 503 `{"status":"not_ready"}` | none |

Liveness performs zero dependency, migration, provider, source-database, session, audit, configuration, or credential checks. Both routes bypass session-cookie parsing, remain public, and expose only the constant bodies above.

Readiness requires a completed application startup, no begun shutdown, one read-only platform PostgreSQL query whose current Alembic revision matches the cached source-tree head, and one Redis PING. PostgreSQL and Redis checks run concurrently under one configured two-second deadline. The probe reuses application-managed pools/clients, caches only the expected source-tree head, reads the current database revision on every request, and permits one concurrent dependency-check group per process. Timeout, dependency error, malformed response, or revision mismatch fails closed to the same constant 503 body. Caller cancellation still propagates.

Provider, source PostgreSQL/MySQL/MSSQL, source-health-row, and SSO IdP calls are excluded. The probe performs no transaction, cache, session, audit, or configuration mutation.

## Lifecycle and startup ordering

- Readiness begins false before startup.
- It becomes true only after Redis initialization, startup migration validation, credential-provider initialization, source-row synchronization, and admin synchronization all complete.
- Startup failure never reaches ready.
- Readiness becomes false before the first existing shutdown closer runs; the closer sequence itself is unchanged.
- Liveness remains live while graceful-shutdown requests are still served.
- Runtime dependency and revision recovery restores readiness without a backend restart.

Compose retains platform PostgreSQL and Redis health gating, probes backend `/ready` with Python standard-library tooling already present in the backend image, and starts the frontend only after backend `service_healthy`. The backend healthcheck uses a two-second interval, three-second timeout, 15 retries, and ten-second start period. Optional source services do not gate backend readiness.

`scripts/dev-up.sh` retains `set -euo pipefail`, default, `--rebuild`, and explicit destructive `--reset` modes. It starts required infrastructure, waits for infrastructure health, stops the application services, applies `alembic upgrade head` in a one-off backend container, starts the backend, waits up to 60 seconds for Compose health, then starts the frontend. The disposable fake-command harness proved migration-before-backend and backend-health-before-frontend ordering in all three modes. Timeout exits nonzero with one constant operator-safe message pointing to the existing backend logs command.

## Isolated production-like proof

One dedicated Compose project was built and started through the real development script. Migration completed before backend creation; backend readiness completed before frontend creation. Initial application availability was established within 52.34 seconds, with backend restart count zero.

| Scenario | Backend process | `/health` | `/ready` | Compose backend | Recovery without backend restart |
| --- | --- | --- | --- | --- | --- |
| Initial migrated startup | running | 200 live | 200 ready | healthy | true |
| Redis unavailable | running | 200 live | 503 not_ready | unhealthy | true |
| Platform PostgreSQL unavailable | running | 200 live | 503 not_ready | unhealthy | true |
| Alembic revision drift | running | 200 live | 503 not_ready | unhealthy | true |
| Source database unavailable | running | 200 live | 200 ready | healthy | not required |
| Configured provider unavailable | running | 200 live | 200 ready | not evaluated | not required |

Every degraded and restored readiness/Compose transition was observed within the configured 60-second proof bound. Backend restart count remained zero through all dependency and revision loss/restoration cases. No migration ran concurrently with the serving backend.

## TDD commits

| Stage | Commit |
| --- | --- |
| RED public probe contract | `529a3d0cd4eb55d5c2408cc809bfe2ef211c8c11` |
| GREEN probe lifecycle | `07d85e37f906b40a29dae66dd85df3aca9cfc995` |
| RED dependency and revision drift | `b02dcc3902a2e55c8fa6adf28e1bb6bff4fcc134` |
| GREEN live control-plane dependencies | `90044fbd71af02a378310b80f8b26ef123b5d9b7` |
| RED Compose and script races | `5950103d7f7e008cc09df7ead49bd413e293733a` |
| GREEN Compose and script gating | `76488b1c9ecd9f99c91a6184f6ffcbe80bff1a70` |
| RED finite deadline validation | `4b224e4e9d3d2fc8ec0b60fefa42ae220a659b94` |
| GREEN finite deadline validation | `65f3f5b1926af788d4834995fc53883afa749bad` |
| REFACTOR contract guards and documentation | `b728bba5538f3e249798141a13db364ef50a1293` |
| Caller-sweep regression | `1c56b6305329cbc82fff5cc4066c995f2717873b` |

## Gates

| Gate | Result |
| --- | --- |
| Focused ASGI, lifecycle, configuration, Compose, and disposable script harness | 37 passed, 1 skipped |
| Backend unit foundation | 2,129 passed, 365 skipped, 44 deselected, 3 pre-existing warnings in 39.88s |
| Ruff check | passed |
| Ruff format check | 448 files already formatted |
| Docker Compose configuration validation | passed |
| Shell syntax validation | passed |
| Full Vitest | 71 files, 970 tests passed in 10.98s |
| ESLint | passed |
| TypeScript no-emit typecheck | passed |
| Production build | passed; existing chunk-size advisory only |
| CSS lint | passed |
| Isolated production-like Compose matrix | 6 scenarios passed; every transition within 60s; 0 backend restarts |
| Test Guard | passed with no unresolved findings |
| Clean Code Guard | passed with no unresolved findings |
| Docs Guard | passed with runtime/config/script assertions source-verified |
| JSON validation | passed for evidence and consolidated matrix |
| `git diff --check` | passed |
| GitHub backend-test | pending |
| GitHub frontend-test | pending |

## Cleanup and protected baseline

- Disposable Compose containers, networks, volumes, locally built images, and extra provider-proof containers remaining: 0.
- Disposable fake-command harness directories remaining: 0.
- Temporary CHUNK-13 probe and evidence-output files remaining: 0.
- Unrelated running projects changed or removed: 0.
- The protected baseline remains exactly 14 modified tracked PNGs, seven untracked historical screenshots, and two untracked trace archives; none was edited, staged, regenerated, deleted, or reverted by CHUNK-13.
- Static OpenAPI and generated clients were not broadly regenerated. CHUNK-14 remains blocked until authoritative CI and the CHUNK-13 squash merge complete.
- Evidence retains statuses, counts, booleans, bounded timings, restart counts, endpoint constants, and commit IDs only. It retains no environment values, dependency addresses, revision values, credentials, cookies, provider payloads, source rows, SQL, raw errors, logs, screenshots, videos, or traces.
