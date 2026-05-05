#!/usr/bin/env bash
# Generate TypeScript API client from OpenAPI spec (T-026)
# Usage: ./scripts/generate-api-client.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"
SPEC_PATH="../specs/001-core-text-to-sql/contracts/openapi.yaml"
OUTPUT_DIR="src/api/generated"

echo "Generating API client from: ${SPEC_PATH}"
echo "Output directory: ${OUTPUT_DIR}"

npx -y @hey-api/openapi-ts \
  -i "${SPEC_PATH}" \
  -o "${OUTPUT_DIR}" \
  -c fetch

echo "API client generated successfully!"
