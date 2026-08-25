#!/usr/bin/env bash
# scripts/restore-mssql.sh — restore AdventureWorksLT database and configure a read-only login.
#
# Hardening contract (IS-GAP-018):
#   - MSSQL_USER is allowlisted ([A-Za-z][A-Za-z0-9_]*) because identifiers cannot be parameters
#   - Passwords are embedded only as doubled-single-quote N'...' literals and are rejected
#     outright when they contain control characters
#   - Validation happens before any container command runs; hostile values never reach SQL
#   - A non-ONLINE AdventureWorksLT database (partial/interrupted restore) is dropped and
#     restored again, so reruns recover instead of failing or skipping silently
#   - An already-ONLINE database skips restore entirely (idempotent rerun)
#   - A failed restore aborts before login configuration and exits nonzero
#   - No environment value, credential, or raw driver error is ever printed
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

COMPOSE=(docker compose -f docker-compose.dev.yml)
SQLCMD="/opt/mssql-tools18/bin/sqlcmd"
DATABASE="AdventureWorksLT"
WAIT_ATTEMPTS=${RESTORE_WAIT_ATTEMPTS:-60}

die() {
  echo "[restore-mssql] $1" >&2
  exit 1
}

load_env_value() {
  local key=$1 line
  line=$(grep -E "^${key}=" .env 2>/dev/null | tail -n 1 || true)
  printf '%s\n' "${line#"${key}="}"
}

# Defaults matching .env.example. Precedence: explicit environment value beats .env,
# which beats the default. No assignment ever clobbers an inherited value.
if [ -f .env ]; then
  if [ -z "${MSSQL_SA_PASSWORD:-}" ]; then
    value=$(load_env_value MSSQL_SA_PASSWORD)
    [ -n "$value" ] && MSSQL_SA_PASSWORD=$value
  fi
  if [ -z "${MSSQL_USER:-}" ]; then
    value=$(load_env_value MSSQL_USER)
    [ -n "$value" ] && MSSQL_USER=$value
  fi
  if [ -z "${MSSQL_PASSWORD:-}" ]; then
    value=$(load_env_value MSSQL_PASSWORD)
    [ -n "$value" ] && MSSQL_PASSWORD=$value
  fi
fi
: "${MSSQL_SA_PASSWORD:=AdventureWorks_dev_1433!}"
: "${MSSQL_USER:=adventureworks_user}"
: "${MSSQL_PASSWORD:=adventureworks_dev_pwd}"

reject_control_characters() {
  local name=$1 value=$2
  # Bash regex matches across embedded newlines, unlike line-oriented grep.
  if [[ "$value" =~ [[:cntrl:]] ]]; then
    die "rejecting unsafe ${name} value"
  fi
}

if [[ ! "$MSSQL_USER" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]]; then
  die "rejecting unsafe MSSQL_USER value"
fi
reject_control_characters MSSQL_SA_PASSWORD "$MSSQL_SA_PASSWORD"
reject_control_characters MSSQL_PASSWORD "$MSSQL_PASSWORD"

escaped_password=${MSSQL_PASSWORD//\'/\'\'}

echo "Waiting for mssql-source to be healthy..."
attempt=1
while [ "$attempt" -le "$WAIT_ATTEMPTS" ]; do
  if "${COMPOSE[@]}" exec mssql-source "$SQLCMD" \
    -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C -Q "SELECT 1" &>/dev/null; then
    echo "mssql-source is healthy!"
    break
  fi
  sleep 2
  attempt=$((attempt + 1))
done

if [ "$attempt" -gt "$WAIT_ATTEMPTS" ]; then
  die "timed out waiting for mssql-source."
fi

database_status=$(
  "${COMPOSE[@]}" exec -T mssql-source "$SQLCMD" \
    -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C -h -1 <<'SQL' | tr -d '[:space:]'
SELECT CASE
         WHEN DB_ID(N'AdventureWorksLT') IS NULL THEN N'ABSENT'
         WHEN DATABASEPROPERTYEX(N'AdventureWorksLT', 'Status') = N'ONLINE' THEN N'ONLINE'
         ELSE N'RECOVERING'
       END;
SQL
)

if [ "$database_status" = "RECOVERING" ]; then
  echo "Preparing AdventureWorksLT for restore (status category: $database_status)..."
  "${COMPOSE[@]}" exec -T mssql-source "$SQLCMD" \
    -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C <<'SQL' || die "cleanup before restore failed."
IF DB_ID(N'AdventureWorksLT') IS NOT NULL
BEGIN
    DROP DATABASE [AdventureWorksLT];
END
GO
SQL
fi

if [ "$database_status" != "ONLINE" ]; then
  echo "Restoring AdventureWorksLT database..."
  "${COMPOSE[@]}" exec -T mssql-source "$SQLCMD" \
    -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C <<'SQL' || die "restore failed for AdventureWorksLT."
RESTORE DATABASE [AdventureWorksLT]
FROM DISK = N'/var/opt/mssql/backup/AdventureWorksLT2022.bak'
WITH MOVE N'AdventureWorksLT2022_Data' TO N'/var/opt/mssql/data/AdventureWorksLT.mdf',
     MOVE N'AdventureWorksLT2022_Log' TO N'/var/opt/mssql/data/AdventureWorksLT_log.ldf',
     REPLACE,
     RECOVERY;
GO
SQL
else
  echo "AdventureWorksLT is already online; skipping restore."
fi

echo "Configuring read-only application user..."
"${COMPOSE[@]}" exec -T mssql-source "$SQLCMD" \
  -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C <<SQL || die "login configuration failed."
USE [master];
IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = '${MSSQL_USER}')
BEGIN
    CREATE LOGIN [${MSSQL_USER}] WITH PASSWORD = N'${escaped_password}', DEFAULT_DATABASE = [${DATABASE}], CHECK_EXPIRATION = OFF, CHECK_POLICY = OFF;
END
GO
USE [${DATABASE}];
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = '${MSSQL_USER}')
BEGIN
    CREATE USER [${MSSQL_USER}] FOR LOGIN [${MSSQL_USER}];
END
GO
IF IS_ROLEMEMBER(N'db_datareader', N'${MSSQL_USER}') = 0
BEGIN
    ALTER ROLE [db_datareader] ADD MEMBER [${MSSQL_USER}];
END
GO
SQL

echo "MSSQL AdventureWorksLT restore complete and user configured!"
