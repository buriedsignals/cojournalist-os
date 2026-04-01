#!/bin/bash
# Initialise PostgreSQL roles required by Supabase services (GoTrue v2.170.0, PostgREST).
#
# Runs as a docker-entrypoint-initdb.d script on first container start.
# Must sort before the SQL migrations (00001_extensions.sql, etc.) so that
# roles exist before any GRANT or OWNER statements reference them.
#
# Execution order:
#   1. postgres role (referenced in DATABASE_URL, healthchecks, migrations)
#   2. PostgREST roles (anon, authenticated, authenticator, service_role)
#   3. GoTrue role (supabase_auth_admin)
#   4. Auth schema creation + ownership transfer
#   5. Auth enum types required by GoTrue v2.170.0
#   6. Schema permissions
#   7. Migration record sync (if both public.schema_migrations and auth.schema_migrations exist)
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- ---------------------------------------------------------------
    -- 1. postgres role
    --    The supabase/postgres image uses supabase_admin as superuser,
    --    but postgres is referenced in DATABASE_URL, healthchecks, and
    --    migration runners. Must exist and have LOGIN.
    -- ---------------------------------------------------------------
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'postgres') THEN
            CREATE ROLE postgres LOGIN SUPERUSER CREATEDB CREATEROLE REPLICATION BYPASSRLS;
        END IF;
    END
    \$\$;

    ALTER ROLE postgres WITH PASSWORD '${POSTGRES_PASSWORD}';

    -- ---------------------------------------------------------------
    -- 2. PostgREST roles (anon, authenticated, authenticator, service_role)
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

        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'service_role') THEN
            CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
        END IF;
    END
    \$\$;

    ALTER ROLE authenticator WITH PASSWORD '${POSTGRES_PASSWORD}';

    -- PostgREST switches from authenticator -> anon/authenticated/service_role via SET ROLE
    GRANT anon        TO authenticator;
    GRANT authenticated TO authenticator;
    GRANT service_role  TO authenticator;

    -- ---------------------------------------------------------------
    -- 3. GoTrue role (supabase_auth_admin)
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
    -- 4. Auth schema creation + ownership transfer to supabase_auth_admin
    -- ---------------------------------------------------------------
    CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION supabase_auth_admin;

    -- If schema already existed under a different owner, fix it
    ALTER SCHEMA auth OWNER TO supabase_auth_admin;

    -- ---------------------------------------------------------------
    -- 5. Auth enum types required by GoTrue v2.170.0
    --    All created in the auth schema, owned by supabase_auth_admin.
    --    Each check pg_type to stay idempotent.
    -- ---------------------------------------------------------------
    DO \$\$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_type t
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
            WHERE t.typname = 'factor_type' AND n.nspname = 'auth'
        ) THEN
            CREATE TYPE auth.factor_type AS ENUM ('totp', 'webauthn', 'phone');
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_type t
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
            WHERE t.typname = 'factor_status' AND n.nspname = 'auth'
        ) THEN
            CREATE TYPE auth.factor_status AS ENUM ('unverified', 'verified');
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_type t
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
            WHERE t.typname = 'aal_level' AND n.nspname = 'auth'
        ) THEN
            CREATE TYPE auth.aal_level AS ENUM ('aal1', 'aal2', 'aal3');
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_type t
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
            WHERE t.typname = 'code_challenge_method' AND n.nspname = 'auth'
        ) THEN
            CREATE TYPE auth.code_challenge_method AS ENUM ('s256', 'plain');
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_type t
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
            WHERE t.typname = 'one_time_token_type' AND n.nspname = 'auth'
        ) THEN
            CREATE TYPE auth.one_time_token_type AS ENUM (
                'confirmation_token',
                'reauthentication_token',
                'recovery_token',
                'email_change_token_new',
                'email_change_token_current',
                'phone_change_token'
            );
        END IF;
    END
    \$\$;

    -- ---------------------------------------------------------------
    -- 6. Schema permissions
    --    supabase_auth_admin: ALL on auth schema
    --    anon / authenticated: USAGE on public schema
    --    search_path: auth, public
    -- ---------------------------------------------------------------
    GRANT ALL ON SCHEMA auth   TO supabase_auth_admin;
    GRANT USAGE ON SCHEMA auth TO authenticated;
    GRANT USAGE ON SCHEMA auth TO anon;
    GRANT USAGE ON SCHEMA auth TO service_role;

    GRANT USAGE ON SCHEMA public TO anon;
    GRANT USAGE ON SCHEMA public TO authenticated;
    GRANT USAGE ON SCHEMA public TO service_role;

    ALTER ROLE supabase_auth_admin SET search_path TO auth, public;

    -- ---------------------------------------------------------------
    -- 7. Migration record sync
    --    If both public.schema_migrations and auth.schema_migrations
    --    exist, copy any records from public that are missing in auth
    --    so GoTrue does not re-run applied migrations.
    -- ---------------------------------------------------------------
    DO \$\$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'schema_migrations'
        ) AND EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'auth' AND table_name = 'schema_migrations'
        ) THEN
            INSERT INTO auth.schema_migrations (version)
            SELECT version FROM public.schema_migrations
            ON CONFLICT DO NOTHING;
        END IF;
    END
    \$\$;
EOSQL
