-- ============================================================
-- Add scout_run_id linkage to async processing queues so the workers can flip
-- scout_runs.notification_sent after a successful per-row extraction.
--
-- Nullable + on-delete set null because older queue rows (pre-migration) have
-- no run linkage and we don't backfill.
-- ============================================================

ALTER TABLE civic_extraction_queue
    ADD COLUMN IF NOT EXISTS scout_run_id UUID REFERENCES scout_runs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_civic_extraction_queue_scout_run_id
    ON civic_extraction_queue (scout_run_id)
    WHERE scout_run_id IS NOT NULL;

ALTER TABLE apify_run_queue
    ADD COLUMN IF NOT EXISTS scout_run_id UUID REFERENCES scout_runs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_apify_run_queue_scout_run_id
    ON apify_run_queue (scout_run_id)
    WHERE scout_run_id IS NOT NULL;

-- Refresh claim_civic_queue_item so it surfaces the new column to workers.
-- DROP + CREATE (not CREATE OR REPLACE) because changing RETURNS TABLE is a
-- signature change Postgres rejects via OR REPLACE.
DROP FUNCTION IF EXISTS claim_civic_queue_item();

CREATE FUNCTION claim_civic_queue_item()
RETURNS TABLE (
  id              UUID,
  user_id         UUID,
  scout_id        UUID,
  scout_run_id    UUID,
  source_url      TEXT,
  doc_kind        TEXT,
  attempts        INT
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  claimed_id UUID;
BEGIN
  WITH candidate AS (
    SELECT q.id
    FROM civic_extraction_queue q
    WHERE (q.status = 'pending')
       OR (q.status = 'processing' AND q.updated_at < NOW() - INTERVAL '30 minutes')
    ORDER BY q.created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
  )
  UPDATE civic_extraction_queue q
  SET status = 'processing',
      attempts = q.attempts + 1,
      updated_at = NOW()
  FROM candidate
  WHERE q.id = candidate.id
  RETURNING q.id INTO claimed_id;

  IF claimed_id IS NULL THEN
    RETURN;
  END IF;

  RETURN QUERY
  SELECT q.id, q.user_id, q.scout_id, q.scout_run_id, q.source_url, q.doc_kind, q.attempts
  FROM civic_extraction_queue q
  WHERE q.id = claimed_id;
END; $$;
