# pg_cron jobs

All scheduled work in one place. Jobs are staggered intentionally — avoid lock contention and resource spikes.

Schedule encoding: standard 5-field cron (`minute hour day-of-month month day-of-week`), UTC timezone.

## Jobs

| Job | Schedule | Kind | Command | Migration |
|---|---|---|---|---|
| `cleanup-scout-runs` | `0 3 * * *` | SQL | `SELECT cleanup_scout_runs()` | 00006 |
| `cleanup-execution-records` | `5 3 * * *` | SQL | `SELECT cleanup_execution_records()` | 00006 |
| `cleanup-information-units` | `10 3 * * *` | SQL | `SELECT cleanup_information_units()` | 00006 |
| `cleanup-seen-records` | `15 3 * * *` | SQL | `SELECT cleanup_seen_records()` | 00006 |
| `cleanup-raw-captures` | `20 3 * * *` | SQL | `SELECT cleanup_raw_captures()` | 00014 |
| `cleanup-civic-queue` | `25 3 * * *` | SQL | `SELECT cleanup_civic_queue()` | 00014 |
| `cleanup-apify-queue` | `30 3 * * *` | SQL | `SELECT cleanup_apify_queue()` | 00014 |
| `cleanup-mcp-oauth-codes` | `20 3 * * *` | SQL | `SELECT cleanup_mcp_oauth_codes()` | 00024 |
| `cleanup-usage-records` | `20 3 * * *` | SQL | `SELECT cleanup_usage_records()` | 00026 |
| `reset-expired-credits` | `10 0 * * *` | SQL | `SELECT reset_expired_credits()` | 00026 |
| `civic-extract-worker` | `*/2 * * * *` | HTTP POST | → `civic-extract-worker` Edge Function | 00021 |
| `civic-queue-failsafe` | `*/10 * * * *` | SQL | `SELECT civic_queue_failsafe()` | 00021 |
| `apify-reconcile` | `*/10 * * * *` | HTTP POST | → `apify-reconcile` Edge Function | 00022 |
| `apify-mark-timeouts` | `*/15 * * * *` | SQL | `SELECT apify_mark_timeouts()` | 00022 |
| `scout-health-monitor` | `0 9 * * 1` | HTTP POST | → `scout-health-monitor` Edge Function | 00023 |
| `scout-<uuid>` | Per scout | HTTP POST | → `execute-scout` Edge Function | 00015 (dynamic via `schedule_scout` RPC) |

## Grouping by purpose

### TTL cleanup (03:00–03:30 UTC, staggered)
All nine `cleanup-*` jobs run during the 30-minute cleanup window. Each cleanup RPC processes at most 10,000 rows per invocation (via `LIMIT 10000` inside the function), so if a backlog accumulates it drains over successive runs without blocking concurrent writes.

### Credits (00:10 UTC daily)
`reset-expired-credits` runs once daily just after midnight. It's the fallback for MuckRock entitlement resets — normally the webhook drives the reset, but this catches orgs where the webhook was lost.

### Worker drain loops (every 2–15 min)
- `civic-extract-worker` — drains one civic queue item every 2 minutes.
- `apify-reconcile` — reconciles lost Apify webhooks every 10 minutes.
- `civic-queue-failsafe` — resets stuck civic rows every 10 minutes (30m grace).
- `apify-mark-timeouts` — marks > 2h stuck Apify rows as timeout every 15 minutes.

### Scheduled scouts (per-scout)
`scout-<uuid>` jobs are dynamic — created by `schedule_scout(scout_id, cron_expr)` RPC when a user activates a scout, removed by `unschedule_scout`. Each HTTP-POSTs to `execute-scout` via `pg_net`. The schedule is whatever the scout's `schedule_cron` column holds.

### Weekly digest
`scout-health-monitor` runs Monday 09:00 UTC — emails users whose scouts auto-paused in the past week.

## How HTTP-POST cron jobs work

SQL cron jobs are trivial. HTTP-POST jobs (`civic-extract-worker`, `apify-reconcile`, `scout-health-monitor`, `scout-<uuid>`) are wired through `pg_net` and read Edge Function credentials from `vault.decrypted_secrets`:

```sql
SELECT net.http_post(
  url := (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'project_url') || '/functions/v1/<function>',
  headers := jsonb_build_object(
    'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role_key'),
    'Content-Type', 'application/json'
  ),
  body := '{}'::jsonb
);
```

**Safety**: if vault secrets aren't populated (local dev), the select returns no rows → no POST fires → cron job no-ops rather than erroring.

## Inspecting cron activity

```sql
-- All configured jobs
SELECT jobid, jobname, schedule, command, active FROM cron.job ORDER BY jobname;

-- Recent runs (cron tracks last ~30 days)
SELECT j.jobname, r.status, r.return_message, r.start_time, r.end_time
  FROM cron.job_run_details r
  JOIN cron.job j USING (jobid)
 WHERE r.start_time > NOW() - INTERVAL '24 hours'
 ORDER BY r.start_time DESC
 LIMIT 50;

-- Active scheduled scouts
SELECT jobname, schedule FROM cron.job WHERE jobname LIKE 'scout-%';
```

## Adding a cron job

Inside a new migration:

```sql
-- SQL-only job:
SELECT cron.schedule('my-job', '*/5 * * * *', 'SELECT my_function()');

-- HTTP-POST job:
SELECT cron.schedule(
  'my-http-job',
  '*/10 * * * *',
  $$
  SELECT net.http_post(
    url := (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'project_url') || '/functions/v1/my-edge-fn',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role_key'),
      'Content-Type', 'application/json'
    ),
    body := '{}'::jsonb
  )
  $$
);
```

Pick a minute offset that doesn't collide with existing jobs in the same hour (see table above). For cleanup jobs, spread within 03:00–03:59.

## See also

- Per-system docs link their own cron jobs (`credits-entitlements.md`, `civic-pipeline.md`, `social-apify.md`, `scouts-runs.md`, `mcp-oauth.md`).
- `docs/supabase/retention.md` — which tables the cleanup jobs touch and why.
- `supabase/migrations/00006_cron_cleanup.sql`, `00014_phase1_cleanup.sql`, `00021_civic_worker_cron.sql`, `00022_apify_failsafe.sql`, `00023_scout_health_cron.sql`, `00026_credits_cron.sql`.
