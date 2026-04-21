-- 00014_phase1_cleanup.sql
-- TTL cleanup functions + pg_cron schedules for Phase 1 queue-style tables.
-- Staggered 5 min apart to prevent lock contention. LIMIT 10000 rows per run.

-- Delete raw_captures past expires_at
CREATE OR REPLACE FUNCTION cleanup_raw_captures()
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    DELETE FROM raw_captures WHERE id IN (
        SELECT id FROM raw_captures
        WHERE expires_at IS NOT NULL AND expires_at < NOW()
        LIMIT 10000
    );
END; $$;

-- Delete done/failed civic queue entries after 7 days
CREATE OR REPLACE FUNCTION cleanup_civic_queue()
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    DELETE FROM civic_extraction_queue WHERE id IN (
        SELECT id FROM civic_extraction_queue
        WHERE status IN ('done','failed')
          AND updated_at < NOW() - INTERVAL '7 days'
        LIMIT 10000
    );
END; $$;

-- Delete succeeded/failed/timeout apify runs after 7 days
CREATE OR REPLACE FUNCTION cleanup_apify_queue()
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    DELETE FROM apify_run_queue WHERE id IN (
        SELECT id FROM apify_run_queue
        WHERE status IN ('succeeded','failed','timeout')
          AND completed_at IS NOT NULL
          AND completed_at < NOW() - INTERVAL '7 days'
        LIMIT 10000
    );
END; $$;

-- Schedule all three (staggered to avoid lock contention)
SELECT cron.schedule('cleanup-raw-captures', '20 3 * * *', 'SELECT cleanup_raw_captures()');
SELECT cron.schedule('cleanup-civic-queue',  '25 3 * * *', 'SELECT cleanup_civic_queue()');
SELECT cron.schedule('cleanup-apify-queue',  '30 3 * * *', 'SELECT cleanup_apify_queue()');
