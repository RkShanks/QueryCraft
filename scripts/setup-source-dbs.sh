#!/usr/bin/env bash
# scripts/setup-source-dbs.sh — download and prepare MySQL Sakila and MSSQL AdventureWorksLT fixtures.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

echo "=== Preparing directories ==="
mkdir -p dbTest/mysql/init
mkdir -p dbTest/mssql/backup

# 1. MySQL Sakila Database Setup
echo "=== MySQL Sakila Database Setup ==="
if [ -f dbTest/mysql/init/01-schema.sql ] && [ -f dbTest/mysql/init/02-data.sql ]; then
  echo "[MySQL] Sakila schema and data files already present."
else
  echo "[MySQL] Downloading Sakila sample database..."
  TEMP_TAR=$(mktemp)
  curl -L -o "$TEMP_TAR" "http://downloads.mysql.com/docs/sakila-db.tar.gz"
  
  echo "[MySQL] Extracting files..."
  TEMP_DIR=$(mktemp -d)
  tar -xzf "$TEMP_TAR" -C "$TEMP_DIR"
  
  mv "$TEMP_DIR"/sakila-db/sakila-schema.sql dbTest/mysql/init/01-schema.sql
  mv "$TEMP_DIR"/sakila-db/sakila-data.sql dbTest/mysql/init/02-data.sql
  
  rm -rf "$TEMP_DIR" "$TEMP_TAR"
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
  echo "[MSSQL] Downloading AdventureWorksLT2022.bak from official Microsoft SQL Server samples..."
  curl -L -o dbTest/mssql/backup/AdventureWorksLT2022.bak "https://github.com/Microsoft/sql-server-samples/releases/download/adventureworks/AdventureWorksLT2022.bak"
  echo "[MSSQL] AdventureWorksLT backup downloaded."
fi

echo "=== Setup completed successfully! ==="
echo "To start services:"
echo "  docker compose -f docker-compose.dev.yml up -d mysql-source mssql-source"
echo
echo "To restore MSSQL AdventureWorksLT database:"
echo "  ./scripts/restore-mssql.sh"
