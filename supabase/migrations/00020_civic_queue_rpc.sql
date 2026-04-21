-- 00020_civic_queue_rpc.sql
-- SKIP LOCKED claim for civic_extraction_queue to guarantee exactly-once
-- processing under concurrent workers.

CREATE OR REPLACE FUNCTION claim_civic_queue_item()
RETURNS TABLE (
  id              UUID,
  user_id         UUID,
  scout_id        UUID,
  source_url      TEXT,
  doc_kind        TEXT,
  attempts        INT
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  claimed_id UUID;
BEGIN
  -- Atomically pick one pending (or stale processing) row, mark it processing.
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
  SELECT q.id, q.user_id, q.scout_id, q.source_url, q.doc_kind, q.attempts
  FROM civic_extraction_queue q
  WHERE q.id = claimed_id;
END; $$;

-- Reset stuck 'processing' rows after a grace period; caps attempts at 3.
CREATE OR REPLACE FUNCTION civic_queue_failsafe()
RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
  UPDATE civic_extraction_queue
  SET status = CASE
                 WHEN attempts >= 3 THEN 'failed'
                 ELSE 'pending'
               END,
      last_error = CASE
                     WHEN attempts >= 3 THEN 'max attempts exceeded'
                     ELSE last_error
                   END,
      updated_at = NOW()
  WHERE status = 'processing'
    AND updated_at < NOW() - INTERVAL '30 minutes';
$$;
