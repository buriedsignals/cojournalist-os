# Supabase — system documentation

This is the **source of truth** for what lives in Supabase (project `cojournalist-prod`, ref `gfmdziplticfoakhrfpt`). Every file in this directory maps to one system and explains *what the migrations actually created* plus *why it's shaped that way*.

If you change a migration, RPC, RLS policy, Edge Function, or cron job, update the matching doc in the same PR. A schema change without a doc change is a bug.

## Index

### Architecture

- [**Architecture overview**](./architecture-overview.md) — how the pieces fit. Auth, Edge Functions, RPCs, pg_cron, vault secrets.
- [**Migrations index**](./migrations.md) — one-liner per migration file (00001–00026) with what it introduces.

### Systems

Each system doc covers: tables, indexes, triggers, RPCs, RLS, cron jobs, Edge Functions, data flow.

- [**Auth & users**](./auth-users.md) — `auth.users` seeding, `user_preferences`, tier + active_org pointer.
- [**Credits & entitlements**](./credits-entitlements.md) — `orgs`, `org_members`, `credit_accounts`, `usage_records`, `decrement_credits` / `topup_team_credits` / `reset_expired_credits`, MuckRock webhook.
- [**Scouts & runs**](./scouts-runs.md) — `scouts`, `scout_runs`, `execution_records`, scheduling (`schedule_scout` / `trigger_scout_run`), failure auto-pause, the four scout-execute Edge Functions.
- [**Information units & entities**](./units-entities.md) — `information_units`, `entities`, `unit_entities`, `reflections`, embedding columns, `semantic_search_units`, `merge_entities`, dedup.
- [**Projects & ingest**](./projects-ingest.md) — `projects`, `project_members`, `ingests`, `raw_captures`, default Inbox backfill, team-shared reads.
- [**Civic extraction pipeline**](./civic-pipeline.md) — `civic_extraction_queue`, `claim_civic_queue_item`, civic-extract-worker cron, failsafe.
- [**Social / Apify pipeline**](./social-apify.md) — `apify_run_queue`, `post_snapshots`, apify-callback/reconcile, timeouts.
- [**MCP OAuth**](./mcp-oauth.md) — `mcp_oauth_clients`, `mcp_oauth_codes`, RFC 7591 flow.

### Operations

- [**pg_cron jobs**](./cron-jobs.md) — every scheduled job in one place.
- [**RLS policies reference**](./rls-reference.md) — every policy, table by table.
- [**RPC reference**](./rpc-reference.md) — every function, signature, permissions, callers.
- [**Edge Functions reference**](./edge-functions.md) — every function, method/path, auth model, dependencies.
- [**Vault secrets**](./vault-secrets.md) — what's stored in `vault.decrypted_secrets` and why.
- [**TTL & retention**](./retention.md) — which tables expire what, when cron runs.

## Conventions

- **RPCs use `SECURITY DEFINER` + `SET search_path = public`.** Always. EXECUTE is revoked from `anon`/`authenticated` on the mutating ones — only service_role (and the RPC itself through Edge Functions) can call them.
- **RLS is the second line of defence.** Edge Functions use service_role and bypass RLS; PostgREST / browser clients hit RLS. Write policies are owner-only (`auth.uid() = user_id`). Read policies sometimes open up via `project_members` for team-shared projects.
- **Cron jobs** run between 00:00–03:30 UTC for cleanup; every 2/10/15 min for workers and reconciliation. Staggered to avoid lock contention.
- **TTL columns** (`expires_at`) are the default mechanism for data retention; cleanup RPCs use `LIMIT 10000` per invocation so a backlog drains over several cron runs without blocking writes.
- **Polymorphic credit ownership** (user XOR org) is enforced by a table-level CHECK; never relax it — `decrement_credits` assumes exactly one owner row per user and per org.
- **Vault secrets** are read inside SECURITY DEFINER RPCs (`schedule_scout`, `trigger_scout_run`) — never logged, never exposed to clients.

## Related docs (not Supabase-specific)

- `docs/v2-migration-runbook.md` — operational cutover plan
- `docs/auth-db-migration.md` — MuckRock OIDC → Supabase Auth design
- `docs/muckrock/plans-and-entitlements.md` — tier definitions, credit costs; implementation lives in `credits-entitlements.md`
- `docs/architecture/records-and-deduplication.md` — legacy DDB layout for context
