# Civic extraction pipeline

Civic Scouts monitor council meeting portals for new agenda/minutes documents, extract promise-shaped statements, and track them through fulfilment states. This doc covers the queue, the worker, the SKIP-LOCKED claim pattern, and the failsafe cron.

## Tables

### `promises` (00002, extended in 00031)

Persistent tracker for extracted promises. As of 00038, every promise also links to a canonical `information_units` row (`promises.unit_id`) so civic promises dedup against page/beat/social/manual facts instead of living in a separate universe.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `scout_id` | UUID → `scouts(id)` ON DELETE SET NULL | |
| `user_id` | UUID → `auth.users(id)` | |
| `unit_id` | UUID → `information_units(id)` ON DELETE SET NULL | Canonical promise unit |
| `promise_text` | TEXT | The promise itself |
| `source_url` | TEXT | PDF/HTML URL where the promise was made |
| `meeting_date` | DATE | Date of the council meeting (mapped from `source_date` in the backend Pydantic `Promise`) |
| `due_date` | DATE | When the promise is expected to be fulfilled (00031) — indexed |
| `date_confidence` | TEXT CHECK IN ('high','medium','low') | Confidence in `due_date` (00031) |
| `status` | TEXT CHECK IN ('new','in_progress','fulfilled','broken','notified') DEFAULT 'new' | |
| `created_at`, `updated_at` | TIMESTAMPTZ | `updated_at` via trigger |

### `civic_extraction_queue` (00008)

Work queue for async PDF/HTML extraction. Workers claim rows via SKIP LOCKED.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id`, `scout_id` | FKs | |
| `source_url` | TEXT | PDF/meeting document URL |
| `doc_kind` | TEXT CHECK IN ('pdf','html') | |
| `status` | TEXT CHECK IN ('pending','processing','done','failed') DEFAULT 'pending' | |
| `attempts` | INT DEFAULT 0 | Capped at 3 by failsafe |
| `raw_capture_id` | UUID → `raw_captures(id)` | Populated post-processing |
| `error_message` | TEXT | Last failure |
| `claimed_at` | TIMESTAMPTZ | Set when status→processing |
| `completed_at` | TIMESTAMPTZ | |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

Partial index: `idx_civic_queue_work(status, created_at) WHERE status IN ('pending','processing')` — the hot read path for workers.

## RPCs

### `claim_civic_queue_item() RETURNS TABLE(id UUID, user_id UUID, scout_id UUID, source_url TEXT, doc_kind TEXT, attempts INT)`

Atomic claim. Uses `FOR UPDATE SKIP LOCKED` so concurrent workers never grab the same row.

```sql
-- Shape (00020):
WITH claimed AS (
  SELECT id FROM civic_extraction_queue
   WHERE status = 'pending'
      OR (status = 'processing' AND claimed_at < NOW() - INTERVAL '30 minutes')
   ORDER BY created_at
   LIMIT 1
   FOR UPDATE SKIP LOCKED
)
UPDATE civic_extraction_queue q
   SET status = 'processing',
       claimed_at = NOW(),
       attempts = attempts + 1,
       updated_at = NOW()
  FROM claimed
 WHERE q.id = claimed.id
 RETURNING q.id, q.user_id, q.scout_id, q.source_url, q.doc_kind, q.attempts;
```

Returns zero or one row. Callers treat empty as "nothing to do".

### `civic_queue_failsafe() RETURNS VOID`

Reset stuck `processing` rows. Called every 10 minutes by pg_cron.

```sql
-- Shape:
UPDATE civic_extraction_queue
   SET status = CASE WHEN attempts >= 3 THEN 'failed' ELSE 'pending' END,
       claimed_at = NULL,
       updated_at = NOW()
 WHERE status = 'processing'
   AND claimed_at < NOW() - INTERVAL '30 minutes';
```

## RLS

```sql
-- 00011:
CREATE POLICY civq_user ON civic_extraction_queue FOR ALL USING (auth.uid() = user_id);
```

Workers use service-role and bypass RLS.

## Cron jobs

| Job | Schedule | Command | Purpose |
|---|---|---|---|
| `civic-extract-worker` | `*/2 * * * *` | HTTP POST → `civic-extract-worker` Edge Function | Drain one queue item every 2 minutes |
| `civic-queue-failsafe` | `*/10 * * * *` | `SELECT civic_queue_failsafe()` | Reset stuck rows after 30m |
| `cleanup-civic-queue` | `25 3 * * *` | `SELECT cleanup_civic_queue()` | Delete terminal rows > 7d old |

`civic-extract-worker` reads vault secrets (`project_url`, `service_role_key`) and calls the Edge Function via `pg_net.http_post`. Conditional — if vault secrets aren't set (e.g. local dev), the cron job no-ops.

## Edge Functions

### `civic-execute`
Kicks off a scout run. For each `tracked_urls` entry, does a change-tracked Firecrawl scrape. If the tracked listing page changed, parses `rawHtml`, extracts same-domain links, runs the shared civic keyword/LLM classifier, and enqueues the resolved meeting-document URLs. Discovery intentionally prefers listing pages such as `/urversammlung/protokoll` and rejects dead `/pdf/...` index candidates. `civic-execute` enqueues each URL that is **not already in `scouts.processed_pdf_urls`** AND **not already in `civic_extraction_queue` for this scout with status in (pending, processing, done)**. `civic-execute` does **not** append to `scouts.processed_pdf_urls` — that's the worker's job, after a successful extraction. Refreshes `scouts.baseline_established_at`.

### `civic-extract-worker`
Worker loop. Called every 2 minutes by pg_cron (and on-demand by the manage-schedule Edge Function). Firecrawl is called with `parsers: [{ type: "pdf", mode: "fast" }]` (avoids OCR hallucinations on embedded-text PDFs) and up to a 125 s client fuse.

```
LOOP
  SELECT * FROM claim_civic_queue_item() -> { id, source_url, doc_kind, ... }
  BREAK IF no row

  TRY
    firecrawlScrape(source_url, { pdfMode: 'fast', timeoutMs: 120_000 })
    raw_captures INSERT (expires_at = now() + 30 days)
    geminiExtract(PROMISE_SCHEMA, content)   # JSON-schema'd list of promises
                                             # fields: promise_text, context,
                                             # meeting_date, due_date, date_confidence
    FOR EACH promise:
      upsert_canonical_unit(type='promise', source_type='civic_promise')
      promises UPSERT by unit_id status='new' (with due_date + date_confidence)
    civic_extraction_queue UPDATE status=done, raw_capture_id, completed_at
    append_processed_pdf_url_capped(scout_id, source_url, 100)  # 00031
  CATCH:
    civic_extraction_queue UPDATE status=pending, error_message
    (next claim will increment attempts; at 3, failsafe marks failed)
END LOOP
```

`raw_captures.expires_at` is set to `now() + 30 days` on every insert. Without this, the `cleanup_raw_captures` cron (scheduled in `00014`) is a no-op — `expires_at` was previously never populated, so nothing was ever deleted. The 30-day TTL honours the "scrape → extract → discard" posture: long enough to re-extract promises on a bug-fix deploy, short enough that civic PDFs' extracted markdown isn't permanently stored.

### `civic-test`
Dev tooling. Resolves downstream meeting documents from the selected listing page, then previews promise extraction without scheduling.

## Data flow

```
civic-execute (scheduled per-scout)
  → firecrawlChangeTrackingScrape(tracked_urls[i], tag=scout_id)
  → parse rawHtml for same-domain links
  → classify meeting-document links (keyword stage, LLM fallback)
  → INSERT civic_extraction_queue (status=pending)    ◄──┐
                                                        │
civic-extract-worker (every 2m)                         │
  → claim_civic_queue_item()  (SKIP LOCKED)             │
  → firecrawl / pdf parse                               │
  → raw_captures + information_units/unit_occurrences UPSERT + promises UPSERT │
  → civic_extraction_queue UPDATE status=done           │
                                                        │
civic_queue_failsafe (every 10m)                        │
  → reset stuck 'processing' rows > 30m → 'pending' ────┘
  → cap attempts at 3 → status='failed'

cleanup_civic_queue (03:25 UTC)
  → delete rows in ('done','failed') > 7 days old
```

## Invariants

1. **Workers never double-process a row.** `FOR UPDATE SKIP LOCKED` is the guarantee.
2. **Stuck rows self-heal within 40 minutes.** Failsafe runs every 10m, grace is 30m.
3. **Max 3 attempts per URL.** Beyond that it's `failed` and needs manual intervention.
4. **`scouts.processed_pdf_urls` is a ring buffer, cap 100, appended only after successful extraction.** Prevents re-enqueueing pages already successfully processed, without an unbounded array. Failing scrapes stay out of the set so the queue retry path can actually retry them (3 attempts capped by `civic_queue_failsafe`). `append_processed_pdf_url_capped(scout_id, url, cap)` (migration 00031) is the idempotent helper.
5. **Only newly created canonical promise units trigger the immediate civic alert.** Rediscoveries from Civic/Page/Beat attach provenance and update the tracker but do not create a second inbox card or a second alert.

## Operations

### See the queue backlog

```sql
SELECT status, COUNT(*), MIN(created_at) AS oldest
  FROM civic_extraction_queue
 GROUP BY status
 ORDER BY status;
```

### Manually retry a failed row

```sql
UPDATE civic_extraction_queue
   SET status = 'pending', attempts = 0, error_message = NULL, updated_at = NOW()
 WHERE id = '<queue_uuid>';
```

### Force-process a specific scout

```
POST /functions/v1/civic-execute  { "scout_id": "<uuid>" }
```

## See also

- `docs/features/civic.md` — feature-level behaviour, promise extraction
- `docs/supabase/scouts-runs.md` — upstream scheduling + change detection
- `supabase/migrations/00020_civic_queue_rpc.sql`, `00021_civic_worker_cron.sql`
