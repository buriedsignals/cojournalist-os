# TTL & retention

What data expires and when. Backed by `expires_at TIMESTAMPTZ` columns + staggered cleanup cron jobs.

## Summary

| Table | Retention | Driver | Cleanup job | Migration |
|---|---|---|---|---|
| `scout_runs` | 90 days | `expires_at` | `cleanup-scout-runs` (03:00 UTC) | 00006 |
| `execution_records` | 90 days | `expires_at` | `cleanup-execution-records` (03:05) | 00006 |
| `information_units` | 90 days | `expires_at` | `cleanup-information-units` (03:10) | 00006 |
| `seen_records` | 90 days | `expires_at` | `cleanup-seen-records` (03:15) | 00006 |
| `raw_captures` | 30 days (civic) | `expires_at` | `cleanup-raw-captures` (03:20) | 00014 — civic-extract-worker sets `expires_at = now() + 30 days` on insert; pre-existing `expires_at IS NULL` rows persist until backfilled or manually deleted |
| `civic_extraction_queue` | 7 days (terminal) | status + `updated_at` | `cleanup-civic-queue` (03:25) | 00014 |
| `apify_run_queue` | 7 days (terminal) | status + `completed_at` | `cleanup-apify-queue` (03:30) | 00014 |
| `mcp_oauth_codes` | 5 min (used) / 10 min (unused) | `used_at` / `expires_at` | `cleanup-mcp-oauth-codes` (03:20) | 00024 |
| `usage_records` | 90 days | `expires_at` | `cleanup-usage-records` (03:20) | 00026 |
| Everything else | Forever | — | — | — |

## What's permanent

- `auth.users` — user identity, never deleted automatically.
- `user_preferences`, `orgs`, `org_members`, `credit_accounts` — identity + entitlements.
- `scouts`, `projects`, `project_members`, `ingests` — user-owned configuration.
- `entities`, `unit_entities`, `reflections` — the knowledge graph. Users invest effort here; we don't time it out.
- `promises` — civic tracker is long-lived by design.
- `post_snapshots` — per-scout baseline, one row per scout, overwritten not appended.
- `mcp_oauth_clients` — user-registered.

## Why 90 days?

90 days is the default TTL for most time-series data:
- Matches the source DynamoDB layout (`TIME#`, `USAGE#` TTL was 90d).
- Long enough for monthly reporting + investigation retrospectives.
- Short enough that a single scout run doesn't hold storage forever.

Users can verify/export an `information_unit` before it expires; verified units are still subject to TTL by default — if we change that, add a `verified_until` or toggle the expiry trigger. Currently not implemented.

## Why 7 days for queues?

`civic_extraction_queue` and `apify_run_queue` are worker queues. Once terminal (`done`/`failed`/`succeeded`/`timeout`), rows have no operational value. 7 days is a debugging window — long enough to investigate a bad run, short enough that the queues stay lean.

## Why 5 minutes for used OAuth codes?

`mcp_oauth_codes.used_at` gets set on successful token exchange. Keeping the row for 5 minutes is an audit buffer — if a client complains that their code was rejected, we can check `used_at` and distinguish "already used" from "never existed". After 5 min, delete.

Unused codes expire at `expires_at` (10 min from creation); cleanup removes them too.

## Cleanup implementation

All `cleanup_*` RPCs use a LIMIT batch pattern to keep each cron invocation short:

```sql
CREATE OR REPLACE FUNCTION cleanup_information_units() RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    DELETE FROM information_units WHERE id IN (
        SELECT id FROM information_units WHERE expires_at < NOW() LIMIT 10000
    );
END;
$$;
```

If a backlog accumulates (e.g. cron was disabled for a week), successive daily runs drain it 10,000 rows at a time without blocking writes.

## Running cleanup manually

```sql
-- One table:
SELECT cleanup_information_units();

-- All TTL cleanups in order:
SELECT cleanup_scout_runs();
SELECT cleanup_execution_records();
SELECT cleanup_information_units();
SELECT cleanup_seen_records();
SELECT cleanup_raw_captures();
SELECT cleanup_civic_queue();
SELECT cleanup_apify_queue();
SELECT cleanup_mcp_oauth_codes();
SELECT cleanup_usage_records();
```

Monitor row counts before/after:

```sql
SELECT relname, n_live_tup, n_dead_tup
  FROM pg_stat_user_tables
 WHERE relname IN (
   'scout_runs','execution_records','information_units','seen_records',
   'raw_captures','civic_extraction_queue','apify_run_queue',
   'mcp_oauth_codes','usage_records'
 )
 ORDER BY relname;
```

## Changing retention

To extend TTL on a table, update the `expires_at` default in a new migration:

```sql
ALTER TABLE information_units ALTER COLUMN expires_at SET DEFAULT (NOW() + INTERVAL '180 days');
```

**This only applies to new rows.** Existing rows keep their earlier `expires_at`. To retroactively extend, update them:

```sql
UPDATE information_units SET expires_at = GREATEST(expires_at, NOW() + INTERVAL '90 days');
```

Adjust `LIMIT 10000` inside the cleanup RPC if you need to burn down a backlog faster.

## See also

- `docs/supabase/cron-jobs.md` — scheduled cleanup order
- `docs/supabase/rpc-reference.md` — cleanup function signatures
- `docs/architecture/records-and-deduplication.md` — legacy DDB TTL design for reference
