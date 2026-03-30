-- 00006_cron_cleanup.sql
-- TTL cleanup via SECURITY DEFINER functions (bypass RLS) + staggered pg_cron schedules.
-- Each invocation deletes up to 10,000 rows. The cron job runs frequently enough
-- that this keeps up with normal accumulation. If a backlog builds (e.g., cron was
-- disabled), it drains over successive runs without blocking concurrent writes.

CREATE OR REPLACE FUNCTION cleanup_scout_runs()
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    DELETE FROM scout_runs WHERE id IN (
        SELECT id FROM scout_runs WHERE expires_at < NOW() LIMIT 10000
    );
END;
$$;

CREATE OR REPLACE FUNCTION cleanup_execution_records()
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    DELETE FROM execution_records WHERE id IN (
        SELECT id FROM execution_records WHERE expires_at < NOW() LIMIT 10000
    );
END;
$$;

CREATE OR REPLACE FUNCTION cleanup_information_units()
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    DELETE FROM information_units WHERE id IN (
        SELECT id FROM information_units WHERE expires_at < NOW() LIMIT 10000
    );
END;
$$;

CREATE OR REPLACE FUNCTION cleanup_seen_records()
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    DELETE FROM seen_records WHERE id IN (
        SELECT id FROM seen_records WHERE expires_at < NOW() LIMIT 10000
    );
END;
$$;

-- Staggered schedules to avoid lock contention
SELECT cron.schedule('cleanup-scout-runs',       '0 3 * * *', 'SELECT cleanup_scout_runs()');
SELECT cron.schedule('cleanup-execution-records', '5 3 * * *', 'SELECT cleanup_execution_records()');
SELECT cron.schedule('cleanup-information-units', '10 3 * * *', 'SELECT cleanup_information_units()');
SELECT cron.schedule('cleanup-seen-records',      '15 3 * * *', 'SELECT cleanup_seen_records()');

-- ============================================================
-- RPC wrappers for Edge Functions to manage cron jobs via PostgREST
-- Edge Functions cannot call cron.schedule() directly through PostgREST
-- because it lives in the cron schema. These SECURITY DEFINER wrappers
-- expose the functionality as normal RPC functions in the public schema.
-- ============================================================
CREATE OR REPLACE FUNCTION schedule_cron_job(job_name text, cron_expr text, command text)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, cron AS $$
BEGIN
    RETURN cron.schedule(job_name, cron_expr, command);
END;
$$;

CREATE OR REPLACE FUNCTION unschedule_cron_job(job_name text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, cron AS $$
BEGIN
    PERFORM cron.unschedule(job_name);
    RETURN TRUE;
END;
$$;
