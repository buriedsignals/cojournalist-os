-- 00026_credits_cron.sql
-- Cron jobs for credit + usage maintenance.
-- Staggered relative to the 03:xx cleanup jobs in 00006 to avoid lock contention.

-- Prune expired audit rows (90-day TTL on usage_records.expires_at).
-- Batched LIMIT keeps individual invocations short even with a backlog.
CREATE OR REPLACE FUNCTION cleanup_usage_records()
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    DELETE FROM usage_records WHERE id IN (
        SELECT id FROM usage_records WHERE expires_at < NOW() LIMIT 10000
    );
END;
$$;

-- Reset balance to monthly_cap where the MuckRock entitlement update_on has passed.
-- reset_expired_credits() is defined in 00025 and handles the actual update.
-- This wrapper exists so the cron job can call a predictable name.

SELECT cron.schedule('cleanup-usage-records', '20 3 * * *', 'SELECT cleanup_usage_records()');
SELECT cron.schedule('reset-expired-credits', '10 0 * * *', 'SELECT reset_expired_credits()');
