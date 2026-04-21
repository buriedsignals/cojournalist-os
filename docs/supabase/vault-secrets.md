# Vault secrets

`vault.decrypted_secrets` is a Supabase-managed encrypted key-value store. We use it **only** for values that `SECURITY DEFINER` RPCs or `pg_net.http_post` cron jobs need to read at runtime — things we can't ship as Edge Function env vars because they're consumed inside the DB.

## Stored secrets

| Name | Value | Consumer |
|---|---|---|
| `project_url` | `https://gfmdziplticfoakhrfpt.supabase.co` | pg_cron HTTP jobs; `schedule_scout` / `trigger_scout_run` RPCs |
| `service_role_key` | Service role JWT | Same — used as the `Authorization: Bearer <...>` header when pg_net posts to Edge Functions |

That's it. No other secrets live in the vault. Edge Functions read their own env vars directly (`Deno.env.get(...)`).

## Configure

Dashboard → **Settings → Vault → "New secret"**, or in SQL:

```sql
SELECT vault.create_secret('https://gfmdziplticfoakhrfpt.supabase.co', 'project_url');
SELECT vault.create_secret('<service_role_key>',                       'service_role_key');
```

Secrets live in Dashboard → Project Settings → Edge Functions → Secrets, and the paste-values for the vault go directly into the SQL editor.

## Who reads them

### `schedule_scout` / `trigger_scout_run` (00015)

```sql
SELECT net.http_post(
  url := (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'project_url') || '/functions/v1/execute-scout',
  headers := jsonb_build_object(
    'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role_key'),
    'Content-Type', 'application/json'
  ),
  body := jsonb_build_object('scout_id', p_scout_id)
);
```

### Cron HTTP jobs (00021, 00022, 00023)

Same shape, hard-coded path per job:
- `civic-extract-worker` → `/functions/v1/civic-extract-worker`
- `apify-reconcile` → `/functions/v1/apify-reconcile`
- `scout-health-monitor` → `/functions/v1/scout-health-monitor`
- `scout-<uuid>` → `/functions/v1/execute-scout`

## What happens when secrets are missing

The `SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = '...'` returns zero rows → the full `url` / `Authorization` header is NULL → `net.http_post` silently no-ops (returns NULL). This is intentional — local dev + preflight environments can run `supabase db reset` without vault config and nothing errors. The downside: a prod deploy that forgets to populate the vault looks fine in logs but never actually fires cron HTTP jobs.

**Verify after prod setup:**

```sql
SELECT name FROM vault.decrypted_secrets WHERE name IN ('project_url', 'service_role_key');
-- Expected: 2 rows. If 0 or 1, cron HTTP jobs are broken.

-- End-to-end smoke:
SELECT schedule_scout('00000000-0000-0000-0000-000000000000', '0 9 * * 1');
-- Expected: error about unknown scout (not "vault secrets must be set").
```

## Rotation

Rotating the service role key:

1. Dashboard → Settings → API → Generate new service_role key.
2. Update `vault.decrypted_secrets` entry `service_role_key` with the new value (SQL or Dashboard → Settings → Vault).
3. Update Edge Function env var `SUPABASE_SERVICE_ROLE_KEY` too (Dashboard → Edge Functions → Manage secrets).
4. Observe cron jobs + edge functions for errors during the first 15 min after rotation.

Don't rotate `INTERNAL_SERVICE_KEY` (Edge-Function-only env var) via the vault — it's a separate concern.

## Why not env vars?

Edge Function env vars are read by Deno code, not by pg_cron or PL/pgSQL. The RPCs + cron jobs that invoke Edge Functions run inside Postgres — they have no access to Edge Function env. The vault is the bridge.

## See also

- `docs/supabase/cron-jobs.md` — list of jobs that consume vault secrets
- `supabase/migrations/00015_scout_scheduling_rpc.sql` — `schedule_scout` internals
