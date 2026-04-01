#!/bin/bash
# Initialise PostgreSQL roles required by Supabase services (GoTrue, PostgREST).
#
# Runs as a docker-entrypoint-initdb.d script on first container start.
# Must sort before the SQL migrations (00001_extensions.sql, etc.) so that
# roles exist before any GRANT or OWNER statements reference them.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- ---------------------------------------------------------------
    -- Roles used by PostgREST (anon / authenticated / authenticator)
    -- ---------------------------------------------------------------
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'anon') THEN
            CREATE ROLE anon NOLOGIN NOINHERIT;
        END IF;

        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'authenticated') THEN
            CREATE ROLE authenticated NOLOGIN NOINHERIT;
        END IF;

        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'authenticator') THEN
            CREATE ROLE authenticator LOGIN NOINHERIT;
        END IF;
    END
    \$\$;

    ALTER ROLE authenticator WITH PASSWORD '${POSTGRES_PASSWORD}';

    -- PostgREST switches from authenticator -> anon/authenticated via SET ROLE
    GRANT anon TO authenticator;
    GRANT authenticated TO authenticator;

    -- ---------------------------------------------------------------
    -- Role used by GoTrue (supabase_auth_admin)
    -- ---------------------------------------------------------------
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'supabase_auth_admin') THEN
            CREATE ROLE supabase_auth_admin LOGIN NOINHERIT CREATEROLE CREATEDB;
        END IF;
    END
    \$\$;

    ALTER ROLE supabase_auth_admin WITH PASSWORD '${POSTGRES_PASSWORD}';

    -- GoTrue needs to be able to escalate to postgres for migrations
    GRANT supabase_auth_admin TO postgres;

    -- ---------------------------------------------------------------
    -- Schema permissions
    -- ---------------------------------------------------------------

    -- Create the auth schema if it doesn't exist (GoTrue will populate it)
    CREATE SCHEMA IF NOT EXISTS auth;

    GRANT ALL ON SCHEMA auth TO supabase_auth_admin;

    GRANT USAGE ON SCHEMA public TO anon;
    GRANT USAGE ON SCHEMA public TO authenticated;
EOSQL
