-- migration-rollback.sql
-- Empty all v2 application tables so the migration can be re-run from scratch.
-- Keeps auth.users intact — those rows are pre-seeded and safe to leave.
--
-- Scope: everything seeded by scripts/migrate/main.ts phases 1-9, plus the
--        ephemeral captures/queues from normal operation. Does NOT touch
--        auth.*, cron.*, vault.* or extension/system schemas.
--
-- Usage:
--   psql "$DATABASE_URL" -f docs/migration-rollback.sql
-- Or via the dashboard SQL editor — run the whole block in one transaction.

BEGIN;

TRUNCATE
    usage_records,
    credit_accounts,
    org_members,
    orgs,
    unit_entities,
    entities,
    reflections,
    information_units,
    raw_captures,
    civic_extraction_queue,
    apify_run_queue,
    promises,
    post_snapshots,
    seen_records,
    execution_records,
    scout_runs,
    scouts,
    ingests,
    project_members,
    projects,
    user_preferences
RESTART IDENTITY CASCADE;

COMMIT;
