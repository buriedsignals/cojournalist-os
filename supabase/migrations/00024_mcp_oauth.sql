-- 00024_mcp_oauth.sql
-- OAuth 2.1 authorization server tables for the MCP Edge Function.
--
-- `mcp_oauth_clients` holds dynamically registered clients (RFC 7591).
-- `mcp_oauth_codes` holds short-lived one-shot authorization codes bound to
-- the caller's Supabase access/refresh tokens. At /token we hand those
-- Supabase tokens straight back to the MCP client, so every downstream
-- `tools/call` reuses `requireUser` unchanged.
--
-- RLS:
--   clients: owner SELECT (users may list their own registrations for
--            debugging/revoke). All writes go via service_role from the
--            Edge Function.
--   codes:   service_role only — these wrap a short-lived Supabase JWT and
--            must never be exposed to a client.
--
-- Cleanup: `cleanup_mcp_oauth_codes()` SECURITY DEFINER runs via pg_cron
-- at 03:20 every day, deleting rows where the code has either been used
-- (>5 min ago) or expired.

-- ---------------------------------------------------------------------------
-- clients
-- ---------------------------------------------------------------------------

CREATE TABLE mcp_oauth_clients (
    client_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_secret_hash text,  -- NULL for public (PKCE-only) clients
    client_name text NOT NULL,
    redirect_uris text[] NOT NULL CHECK (array_length(redirect_uris, 1) >= 1),
    token_endpoint_auth_method text NOT NULL DEFAULT 'none'
        CHECK (token_endpoint_auth_method IN ('none', 'client_secret_post', 'client_secret_basic')),
    user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_used_at timestamptz
);

CREATE INDEX mcp_oauth_clients_user_id_idx ON mcp_oauth_clients(user_id);

-- ---------------------------------------------------------------------------
-- codes
-- ---------------------------------------------------------------------------

CREATE TABLE mcp_oauth_codes (
    code text PRIMARY KEY,  -- opaque 32-byte urlsafe
    client_id uuid NOT NULL REFERENCES mcp_oauth_clients(client_id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    supabase_access_token text NOT NULL,   -- handed back unchanged at /token
    supabase_refresh_token text NOT NULL,
    code_challenge text NOT NULL,
    code_challenge_method text NOT NULL DEFAULT 'S256'
        CHECK (code_challenge_method = 'S256'),
    redirect_uri text NOT NULL,
    scopes text[] NOT NULL DEFAULT ARRAY[]::text[],
    expires_at timestamptz NOT NULL DEFAULT (now() + interval '10 minutes'),
    used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX mcp_oauth_codes_expires_at_idx ON mcp_oauth_codes(expires_at);
CREATE INDEX mcp_oauth_codes_client_id_idx ON mcp_oauth_codes(client_id);

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

ALTER TABLE mcp_oauth_clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_oauth_codes   ENABLE ROW LEVEL SECURITY;

-- clients: owner SELECT only. Inserts/updates happen via service_role from
-- the Edge Function (bypasses RLS); no user-facing INSERT/UPDATE/DELETE policy.
CREATE POLICY clients_owner_select ON mcp_oauth_clients
    FOR SELECT
    USING (auth.uid() = user_id);

-- codes: no user-facing policy. Service role bypasses RLS; anon / authenticated
-- roles can never SELECT a code (which wraps a real Supabase access token).

-- ---------------------------------------------------------------------------
-- Cleanup function + cron
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION cleanup_mcp_oauth_codes()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    DELETE FROM mcp_oauth_codes
     WHERE (used_at IS NOT NULL AND used_at < now() - interval '5 minutes')
        OR expires_at < now();
END;
$$;

SELECT cron.schedule(
    'cleanup-mcp-oauth-codes',
    '20 3 * * *',
    'SELECT cleanup_mcp_oauth_codes()'
);
