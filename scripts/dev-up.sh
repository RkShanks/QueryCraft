#!/usr/bin/env bash
# dev-up.sh — bootstrap or refresh the QueryCraft local stack.
#
# Handles three Compose gotchas:
#   1. `docker compose restart` does NOT pick up code changes — only `build` does
#   2. `docker compose restart` does NOT re-read .env — only `--force-recreate` does
#   3. `git pull` may add migrations — `alembic upgrade head` must be re-run
#
# Usage:
#   ./scripts/dev-up.sh           # smart up: rebuild backend if source/.env changed since image
#   ./scripts/dev-up.sh --rebuild # always rebuild backend image from scratch
#   ./scripts/dev-up.sh --reset   # wipe volumes and start fresh (destructive)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
COMPOSE="docker compose -f docker-compose.dev.yml"

ensure_env() {
  if [ ! -f .env ]; then
    echo "[dev-up] no .env found — copying from .env.example"
    cp .env.example .env
  fi
  if ! grep -qE "^PLATFORM_ENCRYPTION_KEY=.+$" .env; then
    KEY=$(python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())")
    sed -i.bak "s|^PLATFORM_ENCRYPTION_KEY=.*|PLATFORM_ENCRYPTION_KEY=$KEY|" .env && rm -f .env.bak
    echo "[dev-up] generated PLATFORM_ENCRYPTION_KEY"
  fi
}

wait_healthy() {
  for i in {1..60}; do
    state=$($COMPOSE ps --format json backend 2>/dev/null | grep -oE '"State":"[^"]*"' | head -1 || true)
    if echo "$state" | grep -q running; then
      echo "[dev-up] backend running"
      return 0
    fi
    sleep 1
  done
  echo "[dev-up] timed out waiting for backend; check 'docker compose -f docker-compose.dev.yml logs backend'"
  return 1
}

case "${1:-}" in
  --reset)
    ensure_env
    $COMPOSE down -v
    $COMPOSE up -d --build
    echo "[dev-up] running alembic upgrade head"
    $COMPOSE run --rm backend alembic upgrade head
    $COMPOSE up -d backend
    ;;
  --rebuild)
    ensure_env
    $COMPOSE build --no-cache backend
    $COMPOSE up -d --force-recreate
    ;;
  *)
    ensure_env
    $COMPOSE build backend
    $COMPOSE up -d --force-recreate
    ;;
esac

wait_healthy
echo "[dev-up] running alembic upgrade head"
$COMPOSE exec -T backend alembic upgrade head
echo
echo "[dev-up] stack ready at http://localhost:5173"
echo "[dev-up] sign in with the credentials from .env (ADMIN_USERNAME / ADMIN_PASSWORD)"
