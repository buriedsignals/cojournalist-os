-- 00036_api_keys.sql
-- API keys table + validation RPC. Lets agents call public Edge Function
-- routes (currently `units` for hybrid feed search) with a long-lived
-- `Authorization: Bearer cj_<random>` token instead of a Supabase session
-- JWT. Keys are stored as sha256 hashes; the raw key is shown to the user
-- only at creation time.

CREATE TABLE IF NOT EXISTS public.api_keys (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  key_hash      text NOT NULL UNIQUE,
  -- "cj_xxxxxxxx" — first 11 chars of the raw key, surfaced in the UI list
  -- so users can identify which key is which without storing the secret.
  key_prefix    text NOT NULL,
  name          text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  last_used_at  timestamptz
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON public.api_keys(user_id);

ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY api_keys_owner_all ON public.api_keys
  FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Validation RPC. SECURITY DEFINER so the unauthenticated EF call can look
-- up the row even before we know who the caller is. Returns the owning
-- user_id (or NULL if no match) and stamps last_used_at.
CREATE OR REPLACE FUNCTION public.validate_api_key(p_key text)
RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, extensions AS $$
DECLARE
  v_hash    text := encode(extensions.digest(p_key, 'sha256'), 'hex');
  v_user_id uuid;
BEGIN
  SELECT user_id INTO v_user_id FROM api_keys WHERE key_hash = v_hash;
  IF v_user_id IS NOT NULL THEN
    UPDATE api_keys SET last_used_at = now() WHERE key_hash = v_hash;
  END IF;
  RETURN v_user_id;
END;
$$;

REVOKE ALL ON FUNCTION public.validate_api_key(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.validate_api_key(text) TO anon, authenticated, service_role;
