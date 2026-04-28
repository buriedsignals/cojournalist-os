-- Signup allowlist for OSS/self-hosted deployments.
--
-- The before-user-created Auth hook calls
-- public.hook_restrict_signup_by_allowlist(event jsonb). If the allowlist table
-- is empty, signups are allowed so existing installs are not locked out by the
-- migration alone. Setup seeds the admin email and allowed domains.

CREATE TABLE IF NOT EXISTS public.signup_email_allowlist (
  id BIGSERIAL PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('email', 'domain')),
  value TEXT NOT NULL,
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (kind, value)
);

CREATE OR REPLACE FUNCTION public.update_signup_email_allowlist_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_signup_email_allowlist_updated_at
  ON public.signup_email_allowlist;

CREATE TRIGGER trg_signup_email_allowlist_updated_at
  BEFORE UPDATE ON public.signup_email_allowlist
  FOR EACH ROW
  EXECUTE PROCEDURE public.update_signup_email_allowlist_updated_at();

CREATE OR REPLACE FUNCTION public.hook_restrict_signup_by_allowlist(event jsonb)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
  email TEXT;
  email_domain TEXT;
  rule_count INTEGER;
  allowed_count INTEGER;
BEGIN
  SELECT count(*) INTO rule_count
  FROM public.signup_email_allowlist;

  IF rule_count = 0 THEN
    RETURN '{}'::jsonb;
  END IF;

  email := lower(coalesce(event->'user'->>'email', ''));
  email_domain := lower(split_part(email, '@', 2));

  IF email = '' OR email_domain = '' THEN
    RETURN jsonb_build_object(
      'error', jsonb_build_object(
        'http_code', 403,
        'message', 'Use an allowed newsroom email address to sign up.'
      )
    );
  END IF;

  SELECT count(*) INTO allowed_count
  FROM public.signup_email_allowlist
  WHERE (kind = 'email' AND value = email)
     OR (kind = 'domain' AND value = email_domain);

  IF allowed_count > 0 THEN
    RETURN '{}'::jsonb;
  END IF;

  RETURN jsonb_build_object(
    'error', jsonb_build_object(
      'http_code', 403,
      'message', 'This email domain is not allowed for this coJournalist instance.'
    )
  );
END;
$$;

GRANT USAGE ON SCHEMA public TO supabase_auth_admin;
GRANT SELECT ON public.signup_email_allowlist TO supabase_auth_admin;
GRANT EXECUTE
  ON FUNCTION public.hook_restrict_signup_by_allowlist(jsonb)
  TO supabase_auth_admin;

REVOKE ALL ON public.signup_email_allowlist FROM anon, authenticated, public;
REVOKE EXECUTE
  ON FUNCTION public.hook_restrict_signup_by_allowlist(jsonb)
  FROM anon, authenticated, public;

