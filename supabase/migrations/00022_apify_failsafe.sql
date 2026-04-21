-- 00022_apify_failsafe.sql
-- Reconcile apify_run_queue rows that never received a webhook callback.
-- Invokes the apify-reconcile Edge Function every 10 minutes.

SELECT cron.schedule(
  'apify-reconcile',
  '*/10 * * * *',
  $cmd$
    SELECT net.http_post(
      url := (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'project_url') || '/functions/v1/apify-reconcile',
      headers := jsonb_build_object(
        'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role_key'),
        'Content-Type',  'application/json'
      ),
      body := '{}'::jsonb
    )
    WHERE EXISTS (SELECT 1 FROM vault.decrypted_secrets WHERE name = 'project_url')
      AND EXISTS (SELECT 1 FROM vault.decrypted_secrets WHERE name = 'service_role_key');
  $cmd$
);

-- Local fallback: mark runs stuck in 'running' for > 2 hours as timeout.
-- This runs even without vault secrets so local dev catches orphans.
CREATE OR REPLACE FUNCTION apify_mark_timeouts()
RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
  UPDATE apify_run_queue
  SET status = 'timeout',
      last_error = 'no callback within 2h',
      completed_at = NOW()
  WHERE status IN ('pending', 'running')
    AND started_at IS NOT NULL
    AND started_at < NOW() - INTERVAL '2 hours';
$$;

SELECT cron.schedule(
  'apify-mark-timeouts',
  '*/15 * * * *',
  'SELECT apify_mark_timeouts()'
);
