-- Invoked by setup-database.mjs with a protected stdin variable, never a CLI password.
\set ON_ERROR_STOP on
SET log_statement = 'none';
SET log_min_error_statement = 'panic';
\getenv db_name POSTGRES_DB
SELECT format('CREATE ROLE sentinel_migrator LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION', :'migration_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sentinel_migrator')
\gexec
GRANT CONNECT ON DATABASE :"db_name" TO sentinel_migrator;
GRANT USAGE, CREATE ON SCHEMA public TO sentinel_migrator;
-- No role membership or schema DDL is granted to sentinel_app.
