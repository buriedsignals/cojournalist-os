-- 00001_extensions.sql
-- Enable required PostgreSQL extensions for coJournalist.
-- vector: pgvector for embedding storage and similarity search
-- pg_cron: scheduled job execution (replaces EventBridge)
-- pg_net: HTTP requests from within PostgreSQL (used by pg_cron to trigger Edge Functions)

CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_cron" WITH SCHEMA pg_catalog;
CREATE EXTENSION IF NOT EXISTS "pg_net";

-- Required grants for pg_cron on self-hosted Postgres (not needed on Supabase Cloud,
-- but harmless to include). Allows the postgres role to manage cron jobs.
GRANT USAGE ON SCHEMA cron TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA cron TO postgres;
