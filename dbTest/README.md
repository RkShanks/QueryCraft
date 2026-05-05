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
