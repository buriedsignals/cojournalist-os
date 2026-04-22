# Migrations index

Zero-padded sequential. Never edit a shipped migration — add a new one.

| # | File | What it introduces |
|---|---|---|
| 00001 | `extensions.sql` | `vector` (pgvector 1536-dim), `pg_cron`, `pg_net`, `pg_trgm`. |
| 00002 | `tables.sql` | Core tables: `scouts`, `scout_runs`, `post_snapshots`, `seen_records`, `execution_records`, `information_units`, `promises`, `user_preferences`. |
| 00003 | `indexes.sql` | B-tree + HNSW indexes on the core tables. |
| 00004 | `rls.sql` | Enables RLS on core tables; policy `auth.uid() = user_id` per table. |
| 00005 | `triggers.sql` | `update_updated_at()` trigger on `scouts`, `user_preferences`, `promises`. |
| 00006 | `cron_cleanup.sql` | `cleanup_scout_runs`, `cleanup_execution_records`, `cleanup_information_units`, `cleanup_seen_records`; staggered pg_cron at 03:00–03:15 UTC. Also exposes `schedule_cron_job` / `unschedule_cron_job` wrappers. |
| 00007 | `priority_sources.sql` | `scouts.priority_sources TEXT[]`. |
| 00008 | `phase1_tables.sql` | Phase 1 expansion: `raw_captures`, `entities`, `unit_entities`, `reflections`, `projects`, `project_members`, `ingests`, `civic_extraction_queue`, `apify_run_queue`. |
| 00009 | `phase1_columns.sql` | Adds `project_id` + verification fields to `scouts` and `information_units`; `occurred_at`, `context_excerpt`, `source_type`, `raw_capture_id`, `embedding_model`. |
| 00010 | `phase1_indexes.sql` | Trigram GIN on `entities.canonical_name`; HNSW on `entities.embedding`, `reflections.embedding`; partial indexes on queues. |
| 00011 | `phase1_rls.sql` | RLS for all Phase 1 tables, incl. project-shared reads for `scouts` / `information_units` / `reflections`. |
| 00012 | `phase1_triggers.sql` | `update_updated_at` on `projects`, `entities`, `civic_extraction_queue`. |
| 00013 | `phase1_backfill.sql` | Creates a default "Inbox" project per user; attaches orphan scouts/units. |
| 00014 | `phase1_cleanup.sql` | `cleanup_raw_captures`, `cleanup_civic_queue`, `cleanup_apify_queue`; scheduled 03:20–03:30 UTC. |
| 00015 | `scout_scheduling_rpc.sql` | `schedule_scout(p_scout_id, p_cron_expr)`, `unschedule_scout`, `trigger_scout_run`. Reads vault secrets; pg_net-POSTs to `execute-scout` Edge Function. |
| 00016 | `semantic_search_rpc.sql` | `semantic_search_units(p_embedding, p_user_id, p_project_id?, p_limit?)`. |
| 00017 | `merge_entities_rpc.sql` | `merge_entities(p_user_id, p_keep_id, p_merge_ids[])` — union aliases, remap junction, recount mentions. |
| 00018 | `reflection_search_rpc.sql` | `semantic_search_reflections(...)`. |
| 00019 | `scout_rpcs.sql` | `check_unit_dedup`, `increment_scout_failures` (auto-pause at 3), `reset_scout_failures`. |
| 00020 | `civic_queue_rpc.sql` | `claim_civic_queue_item` (FOR UPDATE SKIP LOCKED), `civic_queue_failsafe` (resets stuck rows after 30m). |
| 00021 | `civic_worker_cron.sql` | Schedules `civic-extract-worker` cron (every 2m, HTTP POST) + `civic_queue_failsafe` (every 10m). |
| 00022 | `apify_failsafe.sql` | `apify_mark_timeouts` (> 2h → timeout), `apify-reconcile` cron (every 10m, HTTP POST), `apify-mark-timeouts` cron (every 15m). |
| 00023 | `scout_health_cron.sql` | `scout-health-monitor` cron (Monday 09:00 UTC, HTTP POST). |
| 00024 | `mcp_oauth.sql` | `mcp_oauth_clients`, `mcp_oauth_codes`; RLS; `cleanup_mcp_oauth_codes` cron at 03:20. |
| 00025 | `credits.sql` | Credits system: `orgs`, `org_members`, `credit_accounts` (polymorphic, user XOR org), `usage_records`. Adds `tier` + `active_org_id` to `user_preferences`. RPCs: `decrement_credits`, `topup_team_credits`, `reset_expired_credits`. RLS: read-own, no user writes. |
| 00026 | `credits_cron.sql` | `cleanup_usage_records` (03:20 UTC) + `reset_expired_credits` (00:10 UTC). |
| 00027 | `drop_notification_email.sql` | Drops `user_preferences.notification_email`. Emails are now fetched fresh from `auth.users` at send-time (no denormalized copy in `public.*`). |
| 00028 | `health_notification_opt_in.sql` | Adds `user_preferences.health_notifications_enabled` (default TRUE). `scout-health-monitor` filters by this flag. |
| 00029 | `civic_queue_scout_run_id.sql` | Adds `scout_run_id` to `civic_extraction_queue` + `apify_run_queue`; refreshes `claim_civic_queue_item` RPC to return it. Enables async workers to flip `scout_runs.notification_sent`. |
| 00030 | `units_hybrid_search.sql` | Hybrid keyword + vector search RPC for information_units / inbox. |
| 00031 | `promises_due_date_confidence.sql` | Adds `due_date` + `date_confidence` columns (+ index) to `promises`, previously computed by the extractor but dropped by the DB. Adds `append_processed_pdf_url_capped(scout_id, url, cap)` so the civic-extract-worker marks `scouts.processed_pdf_urls` only on successful extraction (fixing silent data loss when Firecrawl failed). |
| 00036 | `api_keys.sql` | `api_keys` table (sha256 hashes, `cj_xxxxxxxx` prefix shown in UI, owner-scoped RLS) + `validate_api_key(p_key text) RETURNS uuid` SECURITY DEFINER RPC that returns the owning `user_id` and stamps `last_used_at`. Backs the `Authorization: Bearer cj_<key>` agent path used by the `units` Edge Function. |

## Conventions

- **Never mutate a shipped migration.** Add a new one.
- **Every new table** should ship with its RLS policies (and usually its indexes) in the same batch. A migration that creates a table without RLS is a leak.
- **Every SECURITY DEFINER RPC** must `SET search_path = public` and `REVOKE EXECUTE FROM PUBLIC, anon, authenticated` on any mutating path.
- **Cron jobs** that invoke Edge Functions pull the URL + service role key from `vault.decrypted_secrets` — never hard-code.

## How to add a migration

```bash
cd supabase
# New file: 000NN_<concise_name>.sql  (next sequential number)
# Include all of: tables, indexes, RLS, triggers, RPCs, grants — for that change's scope.
supabase db reset                       # applies from scratch locally
# Test RPCs with psql or via Edge Function integration test.
supabase db push                        # applies to remote after review
```

Then update the matching system doc in `docs/supabase/` in the same PR.
