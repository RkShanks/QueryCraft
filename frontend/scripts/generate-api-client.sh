#!/usr/bin/env bash
# Generate the TypeScript API client from the canonical runtime OpenAPI artifact.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"

cd "$FRONTEND_DIR"
exec node scripts/generate-api-client.mjs "$@"
