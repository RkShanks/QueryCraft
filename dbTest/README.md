# Source DB Test Data — Pagila

QueryCraft uses [Pagila](https://github.com/devrimgunduz/pagila) (a PostgreSQL port of the Sakila DVD-rental sample DB) as the test data set for the source DB during local development and integration tests.

## Files

- `init/01-schema.sql` — table, type, sequence, function, view definitions (~120 KB).
- `init/02-data.sql` — sample data: ~30 MB of INSERTs covering ~30k rows across 15 tables.
- `init/03-grants.sql` — committed; sets up the `pagila_readonly` role with SELECT-only grants. Runs after `01-schema.sql` and `02-data.sql` during postgres-source container init.

## Why are the .sql files not in git?

Pagila is public-domain, but the data SQL is large (~30 MB), bloats clones, and is canonical upstream. We download it on demand instead.

## Setup

From the repo root:

```bash
cd dbTest/init
curl -L -o 01-schema.sql https://raw.githubusercontent.com/devrimgunduz/pagila/master/pagila-schema.sql
curl -L -o 02-data.sql https://raw.githubusercontent.com/devrimgunduz/pagila/master/pagila-data.sql
```

If you already have `dbTest/pagila-schema.sql` and `dbTest/pagila-data.sql` from an earlier step, move them instead:

```bash
mkdir -p dbTest/init
mv dbTest/pagila-schema.sql dbTest/init/01-schema.sql
mv dbTest/pagila-data.sql dbTest/init/02-data.sql
```

Verify:
```bash
wc -l dbTest/init/01-schema.sql dbTest/init/02-data.sql
head -5 dbTest/init/01-schema.sql
```

Then bring up the source DB:
```bash
docker compose -f docker-compose.dev.yml down -v   # only on first run; -v wipes the source-db-data volume
docker compose -f docker-compose.dev.yml up -d postgres-source
docker compose logs -f postgres-source             # watch for "PostgreSQL init process complete"
```

## Verifying the setup

```bash
# Tables loaded?
docker compose exec postgres-source psql -U source_readonly -d source_analytics -c "\dt"
# Should list: actor, address, category, city, country, customer, film, film_actor,
#              film_category, inventory, language, payment, rental, staff, store

# pagila_readonly role exists with SELECT-only?
docker compose exec postgres-source psql -U pagila_user -d source_analytics \
  -c "SELECT count(*) FROM actor;"
# → 200

docker compose exec postgres-source psql -U pagila_user -d source_analytics \
  -c "INSERT INTO actor (first_name, last_name) VALUES ('Devin', 'Test');"
# → ERROR: permission denied for table actor
```

## Connection details

| Role | User | Password env var | Privileges | Connect from app? |
|---|---|---|---|---|
| Cluster superuser | `source_readonly` | `SOURCE_DB_PASSWORD` | ALL (cluster owner) | Currently yes (legacy from US-1; see Inv 5 nuance below) |
| App-level read-only | `pagila_user` (member of `pagila_readonly` role) | `PAGILA_READONLY_PASSWORD` | SELECT on all `public` tables only | Recommended for Inv 5 enforcement (Chunk 3.4 may switch to this) |

### Inv 5 (Read-Only Source DB) note

The constitution and plan stipulate that the app must connect to the source DB with a role that has no data-modifying capability. The current `source_readonly` user is the cluster superuser, which violates this in practice. Chunk 3.4 (SourceDBConnector) should connect as `pagila_user` so the read-only invariant is enforced at the database engine level. The cluster superuser remains for migrations and admin operations.

---

# Multi-Dialect Test Databases Setup (MySQL & MSSQL)

QueryCraft supports MySQL and Microsoft SQL Server (MSSQL) as source databases starting in Phase 3. Follow the instructions below to download, start, and verify the sample datasets for local manual testing.

## Setup

1. **Download sample databases:**
   From the repository root, run the setup script to download MySQL Sakila and MSSQL AdventureWorksLT backup/fixtures:
   ```bash
   ./scripts/setup-source-dbs.sh
   ```
   This will:
   - Create the directories `dbTest/mysql/init` and `dbTest/mssql/backup`.
   - Download the official MySQL Sakila database files and place them under `dbTest/mysql/init/`.
   - Generate `dbTest/mysql/init/03-grants.sql` to restrict application user privileges.
   - Download Microsoft's official `AdventureWorksLT2022.bak` backup file under `dbTest/mssql/backup/`.

2. **Start the database containers:**
   Start the services:
   ```bash
   docker compose -f docker-compose.dev.yml up -d mysql-source mssql-source
   ```

3. **Restore the MSSQL AdventureWorksLT database:**
   Run the restore helper script:
   ```bash
   ./scripts/restore-mssql.sh
   ```
   This script waits for the SQL Server container to become healthy, restores the database from the backup file, and configures the read-only application login/user.

---

## Verifying the Setup

### 1. MySQL (Sakila Database)

- **List tables:**
  ```bash
  docker compose -f docker-compose.dev.yml exec mysql-source mysql -u sakila_user -psakila_dev_pwd -e "SHOW TABLES IN sakila;"
  ```
  *(Should list 16 tables including `actor`, `customer`, `film`, etc.)*

- **Count rows in `actor` table:**
  ```bash
  docker compose -f docker-compose.dev.yml exec mysql-source mysql -u sakila_user -psakila_dev_pwd -e "SELECT COUNT(*) FROM sakila.actor;"
  ```
  *(Should output `200`)*

- **Verify read-only constraint:**
  ```bash
  docker compose -f docker-compose.dev.yml exec mysql-source mysql -u sakila_user -psakila_dev_pwd -e "INSERT INTO sakila.actor (first_name, last_name) VALUES ('TEST', 'USER');"
  ```
  *(Should fail with: `ERROR 1142 (42000): INSERT command denied to user 'sakila_user'@'...' for table 'actor'`)*

### 2. MSSQL (AdventureWorksLT Database)

- **List tables:**
  ```bash
  docker compose -f docker-compose.dev.yml exec mssql-source /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U adventureworks_user -P adventureworks_dev_pwd -C \
    -Q "SELECT TABLE_SCHEMA, TABLE_NAME FROM AdventureWorksLT.INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE';"
  ```
  *(Should list SalesLT tables including `Customer`, `Product`, `SalesOrderHeader`, etc.)*

- **Count rows in `SalesLT.Customer` table:**
  ```bash
  docker compose -f docker-compose.dev.yml exec mssql-source /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U adventureworks_user -P adventureworks_dev_pwd -C \
    -Q "SELECT COUNT(*) FROM AdventureWorksLT.SalesLT.Customer;"
  ```
  *(Should output `847`)*

- **Verify read-only constraint:**
  ```bash
  docker compose -f docker-compose.dev.yml exec mssql-source /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U adventureworks_user -P adventureworks_dev_pwd -C \
    -Q "INSERT INTO AdventureWorksLT.SalesLT.Customer (FirstName, LastName, PasswordHash, PasswordSalt, RowGuid) VALUES ('TEST', 'USER', 'abc', '123', NEWID());"
  ```
  *(Should fail with: `Msg 229, Level 14, State 5, Line 1... The INSERT permission was denied on the object 'Customer', database 'AdventureWorksLT', schema 'SalesLT'.`)*

---

## Connecting from QueryCraft Admin UI

When adding or editing connections in the Admin Connections dashboard (`/admin/connections`), use the following parameters:

| Field | MySQL Sakila | MSSQL AdventureWorksLT |
|---|---|---|
| **Display Name** | Sakila DB | AdventureWorks DB |
| **Database Type** | `mysql` | `mssql` |
| **Host** | `mysql-source` *(from inside docker)* or `localhost` *(from host)* | `mssql-source` *(from inside docker)* or `localhost` *(from host)* |
| **Port** | `3306` | `1433` |
| **Database Name** | `sakila` | `AdventureWorksLT` |
| **Username** | `sakila_user` | `adventureworks_user` |
| **Password** | `sakila_dev_pwd` | `adventureworks_dev_pwd` |

> [!NOTE]
> When QueryCraft connects from the backend docker container, it must resolve the hostnames via the Compose network (`mysql-source` or `mssql-source`). When connecting or querying from your local machine (outside docker), use `localhost`.

---

## Troubleshooting

### MySQL Initialization Issues
- The MySQL container executes initialization scripts under `/docker-entrypoint-initdb.d` **only when the volume is completely empty**.
- If the import fails or you need to restart from scratch, purge the volume and restart:
  ```bash
  docker compose -f docker-compose.dev.yml down -v
  docker compose -f docker-compose.dev.yml up -d mysql-source
  ```

### MSSQL Restore Issues
- The SQL Server service must be healthy and running before the restore script can connect. Ensure you run `./scripts/restore-mssql.sh` after the service starts.
- If you need to force a restore or reset the MSSQL database:
  ```bash
  docker compose -f docker-compose.dev.yml down -v
  docker compose -f docker-compose.dev.yml up -d mssql-source
  ./scripts/restore-mssql.sh
  ```

