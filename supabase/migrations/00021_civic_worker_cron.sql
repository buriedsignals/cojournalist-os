-- 00021_civic_worker_cron.sql
-- pg_cron schedules that drive civic queue draining.
-- Depend on vault secrets (project_url, service_role_key). If they're absent
-- the jobs are no-ops on local/dev; they activate automatically once the vault
-- is populated on the real Supabase project.

-- civic-extract-worker: drain one queue row every 2 minutes
SELECT cron.schedule(
  'civic-extract-worker',
  '*/2 * * * *',
  $cmd$
    SELECT net.http_post(
      url := (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'project_url') || '/functions/v1/civic-extract-worker',
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

-- civic_queue_failsafe: every 10 minutes, reset stuck rows
SELECT cron.schedule(
  'civic-queue-failsafe',
  '*/10 * * * *',
  'SELECT civic_queue_failsafe()'
);
