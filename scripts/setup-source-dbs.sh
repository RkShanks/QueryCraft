#!/usr/bin/env bash
# scripts/setup-source-dbs.sh — download and prepare MySQL Sakila and MSSQL AdventureWorksLT fixtures.
#
# Hardening contract (IS-GAP-018):
#   - HTTPS-only downloads with fail-aware curl flags (-f, retries)
#   - SHA-256 checksum verification before any extraction or fixture installation
#   - Checksums come from an operator-maintained file (default scripts/fixtures.sha256,
#     override with SOURCE_FIXTURE_CHECKSUMS). Upstream publishes no vendor checksums for
#     these sample fixtures, so this repo records none itself — see
#     scripts/fixtures.sha256.example for the required format.
#   - All temporary state lives under one mktemp -d removed by an EXIT/INT/TERM trap
#   - Failures exit nonzero with category-only messages; environment values are never printed
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

CHECKSUM_FILE=${SOURCE_FIXTURE_CHECKSUMS:-"$ROOT/scripts/fixtures.sha256"}
SAKILA_URL="https://downloads.mysql.com/docs/sakila-db.tar.gz"
AWLT_URL="https://github.com/Microsoft/sql-server-samples/releases/download/adventureworks/AdventureWorksLT2022.bak"

WORK_DIR=$(mktemp -d)
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT INT TERM

fail() {
  echo "[setup-source-dbs] $1" >&2
  exit 1
}

require_checksum() {
  local name=$1 entry
  if [ ! -f "$CHECKSUM_FILE" ]; then
    fail "checksum file not found at ${CHECKSUM_FILE#$ROOT/}; refusing to download $name (see scripts/fixtures.sha256.example)"
  fi
  entry=$(grep -E "^[0-9a-fA-F]{64}[[:space:]]+\*?${name}[[:space:]]*$" "$CHECKSUM_FILE" | tail -n 1 || true)
  if [ -z "$entry" ]; then
    fail "missing checksum entry for $name; refusing to download (add it to ${CHECKSUM_FILE#$ROOT/})"
  fi
  printf '%s\n' "${entry%%[[:space:]]*}"
}

fetch_verified() {
  local url=$1 name=$2 out=$3 expected=$4 actual
  echo "[setup-source-dbs] downloading $name over HTTPS..."
  curl -fSL --retry 3 --proto '=https' -o "$out" "$url" || fail "download failed for $name"
  actual=$(sha256sum "$out") || fail "unable to hash downloaded $name"
  actual=${actual%%[[:space:]]*}
  if [ "${actual,,}" != "${expected,,}" ]; then
    fail "checksum mismatch for $name; rejecting before extraction or installation"
  fi
}

echo "=== Preparing directories ==="

SAKILA_EXPECTED=$(require_checksum "sakila-db.tar.gz")
AWLT_EXPECTED=$(require_checksum "AdventureWorksLT2022.bak")

mkdir -p dbTest/mysql/init
mkdir -p dbTest/mssql/backup

# 1. MySQL Sakila Database Setup
echo "=== MySQL Sakila Database Setup ==="
if [ -f dbTest/mysql/init/01-schema.sql ] && [ -f dbTest/mysql/init/02-data.sql ]; then
  echo "[MySQL] Sakila schema and data files already present."
else
  fetch_verified "$SAKILA_URL" "sakila-db.tar.gz" "$WORK_DIR/sakila-db.tar.gz" "$SAKILA_EXPECTED"

  echo "[MySQL] Extracting files..."
  tar -xzf "$WORK_DIR/sakila-db.tar.gz" -C "$WORK_DIR" || fail "archive extraction failed for sakila-db.tar.gz"
  if [ ! -f "$WORK_DIR/sakila-db/sakila-schema.sql" ] || [ ! -f "$WORK_DIR/sakila-db/sakila-data.sql" ]; then
    fail "archive is missing the expected Sakila members"
  fi

  mv -f "$WORK_DIR/sakila-db/sakila-schema.sql" dbTest/mysql/init/01-schema.sql
  mv -f "$WORK_DIR/sakila-db/sakila-data.sql" dbTest/mysql/init/02-data.sql
  echo "[MySQL] Sakila database files downloaded and prepared."
fi

# Write grants script dynamically
echo "[MySQL] Writing grants SQL script..."
cat << 'EOF' > dbTest/mysql/init/03-grants.sql
-- Revoke data-modifying privileges from sakila_user to enforce read-only access
REVOKE ALL PRIVILEGES ON sakila.* FROM 'sakila_user'@'%';
GRANT SELECT ON sakila.* TO 'sakila_user'@'%';
FLUSH PRIVILEGES;
EOF
echo "[MySQL] Grants script generated."

# 2. MSSQL AdventureWorksLT Setup
echo "=== MSSQL AdventureWorksLT Setup ==="
if [ -f dbTest/mssql/backup/AdventureWorksLT2022.bak ]; then
  echo "[MSSQL] AdventureWorksLT backup already present."
else
  fetch_verified "$AWLT_URL" "AdventureWorksLT2022.bak" "$WORK_DIR/AdventureWorksLT2022.bak" "$AWLT_EXPECTED"
  mv -f "$WORK_DIR/AdventureWorksLT2022.bak" dbTest/mssql/backup/AdventureWorksLT2022.bak
  echo "[MSSQL] AdventureWorksLT backup downloaded and verified."
fi

echo "=== Setup completed successfully! ==="
echo "To start services:"
echo "  docker compose -f docker-compose.dev.yml up -d mysql-source mssql-source"
echo
echo "To restore MSSQL AdventureWorksLT database:"
echo "  ./scripts/restore-mssql.sh"
