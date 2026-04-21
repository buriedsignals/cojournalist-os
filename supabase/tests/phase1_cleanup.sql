BEGIN;
SELECT plan(3);

SELECT is(
  (SELECT COUNT(*)::int FROM cron.job WHERE jobname = 'cleanup-raw-captures'), 1,
  'cleanup-raw-captures cron job must be scheduled');
SELECT is(
  (SELECT COUNT(*)::int FROM cron.job WHERE jobname = 'cleanup-civic-queue'), 1,
  'cleanup-civic-queue cron job must be scheduled');
SELECT is(
  (SELECT COUNT(*)::int FROM cron.job WHERE jobname = 'cleanup-apify-queue'), 1,
  'cleanup-apify-queue cron job must be scheduled');

SELECT * FROM finish();
ROLLBACK;
