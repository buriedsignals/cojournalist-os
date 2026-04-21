# Social / Apify pipeline

Social Scouts kick off an async Apify actor run; the actor's webhook fires back into Supabase when done. This doc covers the run queue, the webhook handler, reconciliation, and the timeout failsafe.

## Tables

### `apify_run_queue` (00008)

Tracks one Apify actor run per social scout execution.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id`, `scout_id` | FKs | |
| `apify_run_id` | TEXT | Populated after actor starts |
| `platform` | TEXT | `instagram` / `x` / `facebook` / `tiktok` |
| `handle` | TEXT | Profile handle |
| `status` | TEXT CHECK IN ('pending','running','succeeded','failed','timeout') | |
| `attempts` | INT DEFAULT 0 | |
| `started_at` | TIMESTAMPTZ | |
| `completed_at` | TIMESTAMPTZ | |
| `last_error` | TEXT | |
| `created_at` | TIMESTAMPTZ | |

Partial index: `idx_apify_queue_pending(status, started_at) WHERE status IN ('pending','running')`.

### `post_snapshots` (00002)

Social media post baseline per scout. Used for diffing on each run.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `scout_id` | UUID → `scouts(id)` ON DELETE CASCADE — UNIQUE | |
| `user_id` | UUID → `auth.users(id)` | |
| `platform` | TEXT | |
| `handle` | TEXT | |
| `posts` | JSONB | Array of post objects (platform-specific shape) |
| `post_count` | INT | |
| `updated_at` | TIMESTAMPTZ | |

One row per scout, replaced on each successful run.

## RPCs

### `apify_mark_timeouts() RETURNS VOID`

Called every 15 minutes by pg_cron. Marks any `pending`/`running` row with `started_at < NOW() - INTERVAL '2 hours'` as `timeout`.

## RLS

```sql
-- 00011:
CREATE POLICY apq_user   ON apify_run_queue FOR ALL USING (auth.uid() = user_id);
-- 00004:
CREATE POLICY posts_user ON post_snapshots  FOR ALL USING (auth.uid() = user_id);
```

Edge Functions operate with service-role.

## Cron jobs

| Job | Schedule | Command |
|---|---|---|
| `apify-reconcile` | `*/10 * * * *` | HTTP POST → `apify-reconcile` Edge Function |
| `apify-mark-timeouts` | `*/15 * * * *` | `SELECT apify_mark_timeouts()` |
| `cleanup-apify-queue` | `30 3 * * *` | `SELECT cleanup_apify_queue()` — delete terminal rows > 7d |

## Edge Functions

### `social-kickoff`
Starts an Apify actor run for a scout.

1. Service-role auth.
2. Load scout, require `platform` + `profile_handle`.
3. **`decrementOrThrow` for `social_monitoring_<platform>`** — 2 credits for most platforms, 15 for Facebook. On P0002 → 402.
4. Insert `apify_run_queue` row (status=`pending`).
5. If `APIFY_API_TOKEN` missing (local dev): mark row, return 202.
6. Call Apify API to start actor run with webhook URL pointing to `apify-callback`. Store `apify_run_id` and flip status to `running`.
7. Return 202 with `queue_id`.

Actor IDs:
- `instagram` → `apify/instagram-scraper`
- `x` → `apidojo/tweet-scraper`
- `facebook` → `apify/facebook-posts-scraper`

### `apify-callback`
Receives Apify's webhook when an actor run finishes. Authed via `x-internal-key` header matching `INTERNAL_SERVICE_KEY` env.

```
apify-callback body → { eventType, resource: { actId, defaultDatasetId, ... } }
  → find apify_run_queue row by apify_run_id
  → fetch posts from Apify dataset (via apify-reconcile internals)
  → diff against post_snapshots
  → for new posts: geminiExtract → information_units
  → post_snapshots UPDATE posts + post_count
  → apify_run_queue UPDATE status=succeeded | failed, completed_at
```

### `apify-reconcile`
Cron-driven sweep for runs the callback missed (webhook lost, cold-start etc.).

```
SELECT rows WHERE status = 'running' AND started_at < NOW() - INTERVAL '10 minutes'
FOR EACH:
  GET Apify runs API → check status
  IF terminal: process like apify-callback would have
  ELSE: leave; apify_mark_timeouts will catch > 2h
```

Runs every 10 minutes.

## Data flow

```
Scout cron → execute-scout → social-kickoff
                              ├─ decrement_credits (platform-dependent)
                              ├─ apify_run_queue INSERT pending
                              └─ Apify actor start → apify_run_id, status=running
                                                                │
                Apify actor runs for up to 2h                  │
                                                                │
                             ┌─────────── 1. normal path ─────┤
                             │                                 │
                 Apify webhook fires                           │
                  → apify-callback (x-internal-key header)     │
                  → fetch dataset, diff vs post_snapshots      │
                  → information_units INSERT (new posts only)  │
                  → post_snapshots UPDATE                      │
                  → apify_run_queue UPDATE succeeded           │
                                                                │
                             └─────────── 2. webhook miss ──── │
                                                                │
           apify-reconcile (every 10m)                          │
             → GET Apify runs API → reconcile terminal runs ────┘
                                                                │
           apify_mark_timeouts (every 15m)                      │
             → mark >2h stuck rows as timeout ──────────────────┘

cleanup_apify_queue (03:30 UTC)
  → delete terminal rows > 7 days old
```

## Invariants

1. **Credits are deducted at kickoff**, not at callback. Refund logic on callback-fail is intentionally absent — matches source behaviour.
2. **One apify_run_queue row per scout run** — not per post. Post diffs happen inside the callback against `post_snapshots`.
3. **`post_snapshots.scout_id` is UNIQUE** — always upsert, never append.
4. **Runs self-heal within ~2h 15min.** Webhook → callback is the fast path; reconcile every 10m catches missed webhooks; timeout at >2h is the hard cap.
5. **Apify credits and coJournalist credits are separate systems.** The Apify bill is platform-cost; coJournalist credits monetise that.

## Operations

### Inspect queue

```sql
SELECT platform, handle, status, attempts, started_at, completed_at, last_error
  FROM apify_run_queue
 WHERE user_id = '<uuid>'
 ORDER BY started_at DESC NULLS FIRST
 LIMIT 50;
```

### Manually retry a timeout

```sql
UPDATE apify_run_queue
   SET status = 'pending', attempts = 0, last_error = NULL
 WHERE id = '<queue_uuid>';
-- Then the next scout-run will pick it up via social-kickoff again.
```

### Check webhook config on Apify

Apify actor "Webhooks" tab should point at:
```
https://<project-ref>.functions.supabase.co/apify-callback
  header: x-internal-key: $INTERNAL_SERVICE_KEY
  events: ACTOR.RUN.SUCCEEDED, ACTOR.RUN.FAILED, ACTOR.RUN.TIMED_OUT
```

## See also

- `docs/features/social.md` — feature behaviour, per-platform nuances
- `docs/supabase/scouts-runs.md` — upstream scheduling
- `supabase/migrations/00022_apify_failsafe.sql`
