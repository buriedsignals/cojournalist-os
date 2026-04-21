-- 00015_scout_scheduling_rpc.sql
-- RPCs called by the scouts Edge Function to manage pg_cron jobs and trigger
-- on-demand runs. Each scout gets a cron job named scout-<uuid> that POSTs
-- to the execute-scout Edge Function with the service-role Bearer token.

-- Look up project-url / service-role-key from vault.decrypted_secrets.
-- Populate these once per Supabase project (Dashboard -> Settings -> Vault):
--   project_url        = https://<ref>.supabase.co           (local: http://127.0.0.1:54321)
--   service_role_key   = <service role JWT>

CREATE OR REPLACE FUNCTION schedule_scout(p_scout_id UUID, p_cron_expr TEXT)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  job_name TEXT := 'scout-' || p_scout_id::text;
  project_url TEXT;
  service_key TEXT;
  http_cmd TEXT;
BEGIN
  SELECT decrypted_secret INTO project_url FROM vault.decrypted_secrets WHERE name = 'project_url';
  SELECT decrypted_secret INTO service_key FROM vault.decrypted_secrets WHERE name = 'service_role_key';
  IF project_url IS NULL OR service_key IS NULL THEN
    RAISE EXCEPTION 'vault secrets project_url / service_role_key must be set before scheduling scouts';
  END IF;

  PERFORM cron.unschedule(job_name)
    WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = job_name);

  http_cmd := format(
    $fmt$SELECT net.http_post(
      url := %L || '/functions/v1/execute-scout',
      headers := jsonb_build_object(
        'Authorization', 'Bearer ' || %L,
        'Content-Type',  'application/json'
      ),
      body := jsonb_build_object('scout_id', %L::text)
    )$fmt$,
    project_url, service_key, p_scout_id
  );

  PERFORM cron.schedule(job_name, p_cron_expr, http_cmd);
END; $$;

CREATE OR REPLACE FUNCTION unschedule_scout(p_scout_id UUID)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  job_name TEXT := 'scout-' || p_scout_id::text;
BEGIN
  PERFORM cron.unschedule(job_name)
    WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = job_name);
END; $$;

-- Insert a scout_runs row in 'running' and fire an async HTTP POST to
-- execute-scout. Returns the run id so the caller can reply 202 Accepted
-- with an execution handle.
CREATE OR REPLACE FUNCTION trigger_scout_run(p_scout_id UUID, p_user_id UUID)
RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  run_id UUID;
  project_url TEXT;
  service_key TEXT;
BEGIN
  INSERT INTO scout_runs (scout_id, user_id, status, started_at)
  VALUES (p_scout_id, p_user_id, 'running', NOW())
  RETURNING id INTO run_id;

  SELECT decrypted_secret INTO project_url FROM vault.decrypted_secrets WHERE name = 'project_url';
  SELECT decrypted_secret INTO service_key FROM vault.decrypted_secrets WHERE name = 'service_role_key';

  -- Vault may be unconfigured in local/dev; callers can still use trigger_scout_run
  -- to record the run-row, and execute-scout will be reached another way.
  IF project_url IS NOT NULL AND service_key IS NOT NULL THEN
    PERFORM net.http_post(
      url := project_url || '/functions/v1/execute-scout',
      headers := jsonb_build_object(
        'Authorization', 'Bearer ' || service_key,
        'Content-Type',  'application/json'
      ),
      body := jsonb_build_object(
        'scout_id',   p_scout_id::text,
        'run_id',     run_id::text,
        'user_id',    p_user_id::text
      )
    );
  END IF;

  RETURN run_id;
END; $$;
