# Scouts & runs

Scouts are user-owned monitors that execute on a pg_cron schedule. This doc covers the scout tables, scheduling RPCs, run tracking, failure auto-pause, and the four scout-execute Edge Functions.

## Scout types

| Type | UI name | What it does | Primary Edge Function | Cron cost |
|---|---|---|---|---|
| `web` | Page Scout | Firecrawl change-tracked diff of a URL; optional Gemini extraction when `criteria` is set | `scout-web-execute` | 1 |
| `pulse` | Beat / Location Scout | **Manual path** (`priority_sources` non-empty): parallel scrape of up to 20 URLs → Gemini per-article extraction. **Discovery path** (empty): full 8-stage pipeline (LLM query gen → Firecrawl search → date filter → undated cap → tourism pre-filter → embedding dedup w/ language bonus → cluster filter → AI relevance filter) + optional parallel government category fan-out. | `scout-beat-execute` (+ `_shared/pulse_pipeline.ts`) | 7 (refunded on empty pipeline or error) |
| `social` | Social Scout | Apify actor run → webhook-delivered posts → unit extraction | `social-kickoff` (+ `apify-callback`) | 2/15 by platform |
| `civic` | Civic Scout (weekly/monthly only) | Firecrawl change-tracking per tracked URL → discover meeting PDFs → enqueue for worker extraction (cap 2/run) | `civic-execute` (+ `civic-extract-worker`) | 10 (refunded on no-op or error) |

Costs: `supabase/functions/_shared/credits.ts` (`CREDIT_COSTS`).

## Tables

### `scouts`

One row per user-configured monitor. Type-discriminated: many columns only apply to a subset of types.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID → `auth.users(id)` ON DELETE CASCADE | |
| `project_id` | UUID → `projects(id)` | Set to default "Inbox" if not specified (backfill 00013) |
| `name` | TEXT NOT NULL | UNIQUE (user_id, name) |
| `type` | TEXT CHECK IN ('web','pulse','social','civic') | |
| `criteria` | TEXT | Prompt-style filter; web requires it to extract, civic/beat use it for relevance |
| `preferred_language` | TEXT DEFAULT 'en' | |
| `regularity` | TEXT CHECK IN ('daily','weekly','monthly') | |
| `schedule_cron` | TEXT | e.g. `0 9 * * *`; NOT NULL when `is_active=TRUE` |
| `schedule_timezone` | TEXT DEFAULT 'UTC' | |
| `topic` | TEXT | free-text topic (pulse) |
| `url` | TEXT | web |
| `provider` | TEXT CHECK IN ('firecrawl','firecrawl_plain') | web |
| `source_mode` | TEXT CHECK IN ('reliable','niche') | pulse |
| `excluded_domains` | TEXT[] | pulse |
| `priority_sources` | TEXT[] | pulse (added 00007); required for beat scout |
| `platform` | TEXT CHECK IN ('instagram','x','facebook') | social |
| `profile_handle` | TEXT | social |
| `monitor_mode` | TEXT CHECK IN ('summarize','criteria') | social |
| `track_removals` | BOOLEAN DEFAULT FALSE | social |
| `root_domain` | TEXT | civic |
| `tracked_urls` | TEXT[] | civic |
| `processed_pdf_urls` | TEXT[] | civic — ring-buffer capped at 100 to suppress repeat enqueues |
| `location` | JSONB | `GeocodedLocation`, pulse |
| `config` | JSONB DEFAULT `'{}'` | overflow for rare flags |
| `is_active` | BOOLEAN DEFAULT TRUE | Flips to FALSE at 3 consecutive failures |
| `consecutive_failures` | INT DEFAULT 0 | Managed by `increment_scout_failures` / `reset_scout_failures` |
| `baseline_established_at` | TIMESTAMPTZ | Web/civic: stamp of last successful change-tracking run |
| `created_at`, `updated_at` | TIMESTAMPTZ | `updated_at` via trigger |

Indexes: `idx_scouts_user(user_id)`, `idx_scouts_type(user_id, type)`, `idx_scouts_active(user_id) WHERE is_active`, `idx_scouts_project(project_id)`.

### `scout_runs`

One row per scheduled or manual execution.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `scout_id` | UUID → `scouts(id)` ON DELETE CASCADE | |
| `user_id` | UUID → `auth.users(id)` | |
| `status` | TEXT CHECK IN ('running','success','error','skipped') | |
| `started_at` | TIMESTAMPTZ | |
| `completed_at` | TIMESTAMPTZ | |
| `articles_count` | INT | How many units/captures produced |
| `error_message` | TEXT | First 2000 chars of the thrown error |
| `scraper_status` | BOOLEAN | Web: did the fetch succeed |
| `criteria_status` | BOOLEAN | Web/beat: did criteria extraction run |
| `expires_at` | TIMESTAMPTZ DEFAULT (NOW() + 90d) | TTL |

Indexes: `idx_runs_scout(scout_id, started_at DESC)`, `idx_runs_expires(expires_at) WHERE NOT NULL`.

### `execution_records`

Summary cards shown in the UI; embedded for dedup.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `scout_id` | UUID → `scouts(id)` ON DELETE CASCADE | |
| `user_id` | UUID → `auth.users(id)` | |
| `scout_type` | TEXT | |
| `summary_text` | TEXT | 1-sentence AI-generated summary |
| `embedding` | `vector(1536)` | Gemini embedding of `summary_text` |
| `content_hash` | TEXT | SHA-256 of the extracted content |
| `is_duplicate` | BOOLEAN | Set by `check_unit_dedup` logic |
| `completed_at` | TIMESTAMPTZ | |
| `expires_at` | TIMESTAMPTZ DEFAULT (NOW() + 90d) | TTL |

Index: `idx_exec_embedding` HNSW over `embedding` (vector_cosine_ops).

### `raw_captures` (00008)

Source of truth for scraped content. Used by web/civic/pulse extraction and verification.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id`, `scout_id`, `scout_run_id`, `ingest_id` | FKs | |
| `content_md` | TEXT | Markdown body |
| `content_sha256` | TEXT | For dedup |
| `token_count` | INT | Rough Gemini token estimate |
| `captured_at` | TIMESTAMPTZ DESC | |
| `expires_at` | TIMESTAMPTZ | Optional TTL; cleanup_raw_captures prunes |

## Scheduling — RPCs

### `schedule_scout(p_scout_id UUID, p_cron_expr TEXT) RETURNS VOID`

Atomically creates a `pg_cron` job named `scout-<uuid>` that HTTP-POSTs to the `execute-scout` Edge Function. Reads `vault.decrypted_secrets` for `project_url` + `service_role_key`. Idempotent: unschedules an existing job of the same name first.

### `unschedule_scout(p_scout_id UUID) RETURNS VOID`

Removes `scout-<uuid>` from pg_cron.

### `trigger_scout_run(p_scout_id UUID, p_user_id UUID) RETURNS UUID`

Idempotent manual-run entry point. Inserts a `scout_runs` row with status=`running`, fires async HTTP POST to `execute-scout`, returns the run_id. Used by the `scouts/run` Edge Function on user click and by the cron jobs themselves.

## Failure handling — RPCs

### `increment_scout_failures(p_scout_id UUID, p_threshold INT DEFAULT 3) RETURNS (consecutive_failures INT, is_active BOOLEAN)`

Called on exception in every scout-execute function. Increments the counter; flips `is_active=FALSE` at threshold to auto-pause the scout. The Monday `scout-health-monitor` cron job aggregates auto-paused scouts into a digest email.

### `reset_scout_failures(p_scout_id UUID) RETURNS VOID`

Called on success. Clears the counter.

## RLS

```sql
-- 00004:
CREATE POLICY scouts_user ON scouts FOR ALL USING (auth.uid() = user_id);
CREATE POLICY runs_user   ON scout_runs FOR ALL USING (auth.uid() = user_id);
CREATE POLICY exec_user   ON execution_records FOR ALL USING (auth.uid() = user_id);
```

Note: 00011 expands `scouts_read` (SELECT) to also allow reads when the scout's `project_id` is shared with the caller via `project_members`. Writes remain owner-only.

Service-role bypasses RLS — which is how `scout-*-execute` Edge Functions operate.

## Cron jobs

| Job | Schedule | Target | Purpose |
|---|---|---|---|
| `scout-<uuid>` | From `scouts.schedule_cron` | `execute-scout` Edge Function | Per-scout scheduled run |
| `scout-health-monitor` | `0 9 * * 1` (Monday 09:00 UTC) | `scout-health-monitor` Edge Function | Weekly digest of auto-paused scouts |
| `cleanup-scout-runs` | `0 3 * * *` | `cleanup_scout_runs()` | Prune expired runs |
| `cleanup-execution-records` | `5 3 * * *` | `cleanup_execution_records()` | Prune expired exec records |

## Edge Functions

### `execute-scout`
Thin dispatcher that loads the scout and routes to the appropriate type-specific function (`scout-web-execute`, `scout-beat-execute`, `social-kickoff`, `civic-execute`).

### `scout-web-execute`
1. Service-role auth.
2. Load scout, ensure it has a `url`.
3. **`decrementOrThrow` for `website_extraction`** (1 credit). On P0002 → 402.
4. Ensure `scout_runs` row exists.
5. `firecrawlChangeTrackingScrape(url, tag=scout_id)`.
6. If `change_status === 'same'`: mark run success, reset failures, stamp baseline, return.
7. Else: store `raw_captures` row. If `scout.criteria` set: `geminiExtract(EXTRACTION_SCHEMA)` → for each unit call `check_unit_dedup` (cosine ≥ 0.85 over 90d) → insert non-dupes into `information_units`.
8. On throw: mark run error, `increment_scout_failures`, return error.

### `scout-beat-execute`
1. Service-key auth.
2. Load scout, require `priority_sources` + `criteria`.
3. **`decrementOrThrow` for `pulse`** (7 credits).
4. Parallel `firecrawlScrape` (concurrency 5, cap 20 sources, 40k-char aggregate cap).
5. Store per-source `raw_captures`.
6. `geminiExtract` against aggregated markdown.
7. Dedup + insert units, mark run, reset/increment failures.

### `social-kickoff`
1. Service-role auth.
2. Load scout, require `platform` + `profile_handle`.
3. **`decrementOrThrow` for platform-specific key** (2 or 15).
4. Insert `apify_run_queue` row (status=`pending`), call Apify API to start actor run, update row to `running` with `apify_run_id`. Webhook URL points to `apify-callback`.
5. Later: `apify-callback` receives the run result, processes posts via `apify-reconcile`.

### `civic-execute`
1. Service-key auth.
2. Load scout, require `tracked_urls`. Reject `regularity=daily` (weekly/monthly only).
3. **`decrementOrThrow` for `civic`** (10 credits).
4. Ensure `scout_runs` row.
5. For each tracked URL (until `MAX_DOCS_PER_RUN=2` is hit): `firecrawlChangeTrackingScrape`. On change, parse markdown for PDF + meeting document links (multilingual keyword list in `civic-execute/index.ts:MEETING_KEYWORDS`). Insert non-duplicate URLs into `civic_extraction_queue` (pending). `scout.processed_pdf_urls` is touched by the worker on successful extraction only.
6. If no rows were queued OR the run errors, refund the 10 credits via `refund_credits`. Matches legacy no-charge-on-no-op semantics.
7. `civic-extract-worker` cron drains the queue async.

## Data flow — full scout run

```
pg_cron(scout-<uuid>) at schedule_cron
  → HTTP POST /functions/v1/execute-scout   (vault service_role_key)
  → execute-scout loads scout, routes by type
  → scout-web-execute (or beat/social/civic)
    ├─ decrement_credits RPC  (atomic: usage_records INSERT same tx)
    │   ├─ success (balance N-1) → continue
    │   └─ P0002 insufficient → 402 JSON, no run row
    ├─ scout_runs UPSERT status=running
    ├─ <type-specific work>
    ├─ scout_runs UPDATE status=success|error, completed_at
    └─ reset_scout_failures() | increment_scout_failures()
  → execution_records INSERT (embedded summary)
  → information_units INSERT (for web/beat/civic; social goes via callback)
```

## Invariants

1. **One pg_cron job per active scout**, named `scout-<uuid>`. Disabling a scout unschedules it.
2. **Credits decrement before billable work.** The RPC + CHECK constraint guarantee no negative balance even under concurrent runs.
3. **Consecutive failures auto-pause at 3.** The weekly digest surfaces them to the user.
4. **Baseline is per-scout.** Web/civic Firecrawl change-tracking uses `tag = scout_id` so each scout has its own diff state.
5. **Scout deletion cascades** to scout_runs, execution_records, information_units, promises, raw_captures, civic_extraction_queue, apify_run_queue, seen_records, post_snapshots. No orphaned data.

## Operations

### Manually re-run a scout

```
POST /functions/v1/scouts/run  { "scout_id": "<uuid>" }
```
Or from SQL: `SELECT trigger_scout_run('<scout_uuid>', '<user_uuid>');`

### Unpause a scout that auto-paused

```sql
UPDATE scouts SET is_active=TRUE, consecutive_failures=0 WHERE id = '<uuid>';
-- Then re-schedule:
SELECT schedule_scout('<uuid>', (SELECT schedule_cron FROM scouts WHERE id='<uuid>'));
```

### See active cron jobs

```sql
SELECT jobname, schedule, command FROM cron.job WHERE jobname LIKE 'scout-%';
```

## See also

- `docs/features/web-scouts.md`, `pulse.md`, `social.md`, `civic.md` — feature-level behaviour
- `docs/supabase/civic-pipeline.md` — queue/worker flow
- `docs/supabase/social-apify.md` — async Apify lifecycle
- `docs/supabase/credits-entitlements.md` — `decrement_credits` contract
