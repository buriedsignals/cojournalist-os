-- 00023_scout_health_cron.sql
-- Weekly scout-health-monitor: finds auto-paused (is_active=false due to
-- failures) scouts and emails the owner a digest.

SELECT cron.schedule(
  'scout-health-monitor',
  '0 9 * * 1',  -- Monday 09:00 UTC
  $cmd$
    SELECT net.http_post(
      url := (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'project_url') || '/functions/v1/scout-health-monitor',
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
