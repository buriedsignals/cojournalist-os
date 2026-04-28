-- Allow self-host maintenance tooling to seed the signup allowlist through the
-- Supabase REST API with a service-role key. Keep anon/authenticated locked out.

DO $$
BEGIN
  IF to_regclass('public.signup_email_allowlist') IS NOT NULL
     AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    EXECUTE 'GRANT SELECT, INSERT, UPDATE ON public.signup_email_allowlist TO service_role';
    IF to_regclass('public.signup_email_allowlist_id_seq') IS NOT NULL THEN
      EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE public.signup_email_allowlist_id_seq TO service_role';
    END IF;
  END IF;
END;
$$;
