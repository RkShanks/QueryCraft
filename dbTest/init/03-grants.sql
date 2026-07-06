-- 03-grants.sql — runs AFTER 01-schema.sql and 02-data.sql.
-- Creates a true read-only role `pagila_readonly` with SELECT-only grants on all public tables.
-- Creates a login user `pagila_user` (the app connects as this user when stronger Inv 5 enforcement is desired).

DO $$
BEGIN
   IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pagila_readonly') THEN
      CREATE ROLE pagila_readonly NOLOGIN;
   END IF;
   IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pagila_user') THEN
      CREATE USER pagila_user WITH LOGIN PASSWORD 'pagila_dev_pwd';
   END IF;
END
$$;

-- Database-level connect grant
GRANT CONNECT ON DATABASE source_analytics TO pagila_readonly;

-- Schema usage on public
GRANT USAGE ON SCHEMA public TO pagila_readonly;

-- PostgreSQL's historical public schema defaults may grant CREATE to PUBLIC.
-- The app connector must stay read-only even if it inherits SELECT-only table
-- grants through pagila_readonly, so make schema creation explicitly admin-only.
ALTER SCHEMA public OWNER TO postgres;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM pagila_readonly;
REVOKE CREATE ON SCHEMA public FROM pagila_user;

-- SELECT on every existing table in public
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pagila_readonly;

-- SELECT on every future table created in public
ALTER DEFAULT PRIVILEGES IN SCHEMA public
   GRANT SELECT ON TABLES TO pagila_readonly;

-- Sequences (some queries do select from sequences)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO pagila_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
   GRANT USAGE, SELECT ON SEQUENCES TO pagila_readonly;

-- Defensively REVOKE write privileges (belt + suspenders; ALL TABLES grants from default were SELECT only)
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM pagila_readonly;

-- Hand the readonly role to pagila_user
GRANT pagila_readonly TO pagila_user;

-- Defensive: ensure pagila_user is NOT a superuser, NOT createrole, NOT createdb
ALTER USER pagila_user NOSUPERUSER NOCREATEROLE NOCREATEDB;
