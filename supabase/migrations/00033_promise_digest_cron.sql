-- 00033_promise_digest_cron.sql
-- Schedules the daily civic-promise digest at 08:00 UTC. Mirrors the legacy
-- aws/lambdas/promise-checker-lambda (EventBridge `0 8 * * ? *`). Calls the
-- promise-digest Edge Function which groups promises due today by user,
-- sends one email per user, and flips promises.status='notified'.
--
-- Depends on vault.decrypted_secrets (project_url, service_role_key). Until
-- those are populated, this job is a no-op (matches the pattern established
-- in 00021_civic_worker_cron.sql + 00022_apify_failsafe.sql).

SELECT cron.schedule(
  'promise-digest',
  '0 8 * * *',
  $cmd$
    SELECT net.http_post(
      url := (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'project_url') || '/functions/v1/promise-digest',
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
