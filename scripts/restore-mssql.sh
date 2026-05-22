#!/usr/bin/env bash
# scripts/restore-mssql.sh — restore AdventureWorksLT database and configure a read-only login.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

# Set defaults matching .env.example
MSSQL_SA_PASSWORD="AdventureWorks_dev_1433!"
MSSQL_USER="adventureworks_user"
MSSQL_PASSWORD="adventureworks_dev_pwd"

# Load env variables if .env exists, overriding defaults
if [ -f .env ]; then
  MSSQL_SA_PASSWORD=$(grep -E "^MSSQL_SA_PASSWORD=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'" || echo "$MSSQL_SA_PASSWORD")
  MSSQL_USER=$(grep -E "^MSSQL_USER=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'" || echo "$MSSQL_USER")
  MSSQL_PASSWORD=$(grep -E "^MSSQL_PASSWORD=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'" || echo "$MSSQL_PASSWORD")
fi

# Fallback to defaults if values are empty in .env
MSSQL_SA_PASSWORD=${MSSQL_SA_PASSWORD:-AdventureWorks_dev_1433!}
MSSQL_USER=${MSSQL_USER:-adventureworks_user}
MSSQL_PASSWORD=${MSSQL_PASSWORD:-adventureworks_dev_pwd}

echo "Waiting for mssql-source to be healthy..."
for i in {1..60}; do
  if docker compose -f docker-compose.dev.yml exec mssql-source /opt/mssql-tools18/bin/sqlcmd \
     -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C -Q "SELECT 1" &>/dev/null; then
    echo "mssql-source is healthy!"
    break
  fi
  echo -n "."
  sleep 2
done

if [ $i -eq 60 ]; then
  echo "Timed out waiting for mssql-source."
  exit 1
fi

echo "Restoring AdventureWorksLT database..."
# Run the restore commands
docker compose -f docker-compose.dev.yml exec -T mssql-source /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C <<EOF
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'AdventureWorksLT')
BEGIN
    RESTORE DATABASE [AdventureWorksLT]
    FROM DISK = N'/var/opt/mssql/backup/AdventureWorksLT2022.bak'
    WITH MOVE N'AdventureWorksLT2022_Data' TO N'/var/opt/mssql/data/AdventureWorksLT.mdf',
         MOVE N'AdventureWorksLT2022_Log' TO N'/var/opt/mssql/data/AdventureWorksLT_log.ldf',
         REPLACE;
END
GO
EOF

echo "Configuring read-only application user..."
docker compose -f docker-compose.dev.yml exec -T mssql-source /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C <<EOF
USE [master];
IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = '${MSSQL_USER}')
BEGIN
    CREATE LOGIN [${MSSQL_USER}] WITH PASSWORD = '${MSSQL_PASSWORD}', DEFAULT_DATABASE = [AdventureWorksLT], CHECK_EXPIRATION = OFF, CHECK_POLICY = OFF;
END
GO
USE [AdventureWorksLT];
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = '${MSSQL_USER}')
BEGIN
    CREATE USER [${MSSQL_USER}] FOR LOGIN [${MSSQL_USER}];
END
GO
ALTER ROLE [db_datareader] ADD MEMBER [${MSSQL_USER}];
GO
EOF

echo "MSSQL AdventureWorksLT restore complete and user configured!"
