-- 00-create-postgres-role.sql
-- The pagila schema script expects a "postgres" role to exist for ownership.
-- Our container uses "source_readonly" as the superuser, so we create "postgres"
-- as an alias role so schema init succeeds.

DO $
BEGIN
   IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres') THEN
      CREATE ROLE postgres WITH LOGIN SUPERUSER PASSWORD 'source_dev';
   END IF;
END
$;
