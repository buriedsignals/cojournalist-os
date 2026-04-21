BEGIN;
SELECT plan(50);

-- ---------------------------------------------------------------------------
-- Table existence
-- ---------------------------------------------------------------------------
SELECT has_table('public', 'mcp_oauth_clients', 'mcp_oauth_clients table must exist');
SELECT has_table('public', 'mcp_oauth_codes',   'mcp_oauth_codes table must exist');

-- ---------------------------------------------------------------------------
-- mcp_oauth_clients columns
-- ---------------------------------------------------------------------------
SELECT has_column('public', 'mcp_oauth_clients', 'client_id', 'clients.client_id exists');
SELECT col_type_is('public', 'mcp_oauth_clients', 'client_id', 'uuid', 'clients.client_id is uuid');
SELECT col_is_pk('public', 'mcp_oauth_clients', 'client_id', 'clients.client_id is PK');

SELECT has_column('public', 'mcp_oauth_clients', 'client_secret_hash', 'clients.client_secret_hash exists');
SELECT col_type_is('public', 'mcp_oauth_clients', 'client_secret_hash', 'text', 'client_secret_hash is text');
SELECT col_is_null('public', 'mcp_oauth_clients', 'client_secret_hash', 'client_secret_hash may be null for public clients');

SELECT has_column('public', 'mcp_oauth_clients', 'client_name', 'clients.client_name exists');
SELECT col_not_null('public', 'mcp_oauth_clients', 'client_name', 'clients.client_name NOT NULL');

SELECT has_column('public', 'mcp_oauth_clients', 'redirect_uris', 'clients.redirect_uris exists');
SELECT col_type_is('public', 'mcp_oauth_clients', 'redirect_uris', 'text[]', 'redirect_uris is text[]');
SELECT col_not_null('public', 'mcp_oauth_clients', 'redirect_uris', 'clients.redirect_uris NOT NULL');

SELECT has_column('public', 'mcp_oauth_clients', 'token_endpoint_auth_method', 'clients.token_endpoint_auth_method exists');
SELECT col_not_null('public', 'mcp_oauth_clients', 'token_endpoint_auth_method', 'token_endpoint_auth_method NOT NULL');

SELECT has_column('public', 'mcp_oauth_clients', 'user_id', 'clients.user_id exists');
SELECT has_column('public', 'mcp_oauth_clients', 'created_at', 'clients.created_at exists');
SELECT col_type_is('public', 'mcp_oauth_clients', 'created_at', 'timestamp with time zone', 'created_at is timestamptz');
SELECT has_column('public', 'mcp_oauth_clients', 'last_used_at', 'clients.last_used_at exists');
SELECT col_type_is('public', 'mcp_oauth_clients', 'last_used_at', 'timestamp with time zone', 'last_used_at is timestamptz');

-- ---------------------------------------------------------------------------
-- mcp_oauth_codes columns
-- ---------------------------------------------------------------------------
SELECT has_column('public', 'mcp_oauth_codes', 'code', 'codes.code exists');
SELECT col_is_pk('public', 'mcp_oauth_codes', 'code', 'codes.code is PK');
SELECT col_type_is('public', 'mcp_oauth_codes', 'code', 'text', 'codes.code is text');

SELECT has_column('public', 'mcp_oauth_codes', 'client_id', 'codes.client_id exists');
SELECT col_not_null('public', 'mcp_oauth_codes', 'client_id', 'codes.client_id NOT NULL');

SELECT has_column('public', 'mcp_oauth_codes', 'user_id', 'codes.user_id exists');
SELECT col_not_null('public', 'mcp_oauth_codes', 'user_id', 'codes.user_id NOT NULL');

SELECT col_not_null('public', 'mcp_oauth_codes', 'supabase_access_token', 'codes.supabase_access_token NOT NULL');
SELECT col_not_null('public', 'mcp_oauth_codes', 'supabase_refresh_token', 'codes.supabase_refresh_token NOT NULL');
SELECT col_not_null('public', 'mcp_oauth_codes', 'code_challenge', 'codes.code_challenge NOT NULL');
SELECT col_not_null('public', 'mcp_oauth_codes', 'code_challenge_method', 'codes.code_challenge_method NOT NULL');
SELECT col_not_null('public', 'mcp_oauth_codes', 'redirect_uri', 'codes.redirect_uri NOT NULL');

SELECT col_type_is('public', 'mcp_oauth_codes', 'expires_at', 'timestamp with time zone', 'codes.expires_at is timestamptz');
SELECT col_not_null('public', 'mcp_oauth_codes', 'expires_at', 'codes.expires_at NOT NULL');
SELECT col_type_is('public', 'mcp_oauth_codes', 'used_at',    'timestamp with time zone', 'codes.used_at is timestamptz');
SELECT col_type_is('public', 'mcp_oauth_codes', 'created_at', 'timestamp with time zone', 'codes.created_at is timestamptz');

-- ---------------------------------------------------------------------------
-- CHECK constraints
-- ---------------------------------------------------------------------------

-- token_endpoint_auth_method only accepts the three whitelisted values.
PREPARE bad_auth_method AS
  INSERT INTO mcp_oauth_clients (client_name, redirect_uris, token_endpoint_auth_method)
  VALUES ('bad', ARRAY['https://a/cb'], 'bogus');
SELECT throws_ok(
    'bad_auth_method',
    '23514',
    NULL,
    'token_endpoint_auth_method CHECK rejects invalid value'
);

-- redirect_uris must have >=1 element.
PREPARE empty_redirects AS
  INSERT INTO mcp_oauth_clients (client_name, redirect_uris)
  VALUES ('empty', ARRAY[]::text[]);
SELECT throws_ok(
    'empty_redirects',
    '23514',
    NULL,
    'redirect_uris CHECK rejects empty array'
);

-- code_challenge_method must be S256.
-- Need a valid client first to avoid FK error masking the CHECK failure.
INSERT INTO mcp_oauth_clients (client_id, client_name, redirect_uris)
VALUES ('00000000-0000-0000-0000-0000000000a1', 'fixture', ARRAY['https://x.test/cb']);

-- Use a real auth.users row so FK succeeds. auth.users may be empty in test DB;
-- guard by inserting one if needed.
DO $$
DECLARE _u uuid;
BEGIN
    SELECT id INTO _u FROM auth.users LIMIT 1;
    IF _u IS NULL THEN
        INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password,
                                email_confirmed_at, created_at, updated_at)
        VALUES ('00000000-0000-0000-0000-0000000000b1', '00000000-0000-0000-0000-000000000000',
                'authenticated', 'authenticated',
                'mcp-test@example.test', '', now(), now(), now());
    END IF;
END$$;

PREPARE bad_challenge_method AS
  INSERT INTO mcp_oauth_codes (code, client_id, user_id, supabase_access_token,
                               supabase_refresh_token, code_challenge,
                               code_challenge_method, redirect_uri)
  VALUES ('test-code-bad-method', '00000000-0000-0000-0000-0000000000a1',
          (SELECT id FROM auth.users ORDER BY created_at LIMIT 1),
          'at', 'rt', 'challenge', 'plain', 'https://x.test/cb');
SELECT throws_ok(
    'bad_challenge_method',
    '23514',
    NULL,
    'code_challenge_method CHECK rejects non-S256'
);

-- ---------------------------------------------------------------------------
-- RLS enabled
-- ---------------------------------------------------------------------------
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE relname = 'mcp_oauth_clients'),
          'RLS enabled on mcp_oauth_clients');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE relname = 'mcp_oauth_codes'),
          'RLS enabled on mcp_oauth_codes');

-- Anon SELECT on mcp_oauth_codes must return 0 rows (RLS denies, no policy).
-- Seed a row as service role, then switch to anon and try to read it.
INSERT INTO mcp_oauth_codes (code, client_id, user_id, supabase_access_token,
                             supabase_refresh_token, code_challenge, redirect_uri)
VALUES ('test-anon-deny', '00000000-0000-0000-0000-0000000000a1',
        (SELECT id FROM auth.users ORDER BY created_at LIMIT 1),
        'at', 'rt', 'challenge', 'https://x.test/cb');

SET LOCAL ROLE anon;
SELECT is(
    (SELECT count(*)::int FROM mcp_oauth_codes WHERE code = 'test-anon-deny'),
    0,
    'anon cannot SELECT mcp_oauth_codes rows'
);
RESET ROLE;

-- ---------------------------------------------------------------------------
-- cleanup_mcp_oauth_codes() deletes expired / old-used rows, keeps fresh ones
-- ---------------------------------------------------------------------------

-- Fresh row, should be kept.
INSERT INTO mcp_oauth_codes (code, client_id, user_id, supabase_access_token,
                             supabase_refresh_token, code_challenge, redirect_uri,
                             expires_at, used_at)
VALUES ('fresh-unused', '00000000-0000-0000-0000-0000000000a1',
        (SELECT id FROM auth.users ORDER BY created_at LIMIT 1),
        'at', 'rt', 'challenge', 'https://x.test/cb',
        now() + interval '10 minutes', NULL);

-- Expired.
INSERT INTO mcp_oauth_codes (code, client_id, user_id, supabase_access_token,
                             supabase_refresh_token, code_challenge, redirect_uri,
                             expires_at, used_at)
VALUES ('expired-unused', '00000000-0000-0000-0000-0000000000a1',
        (SELECT id FROM auth.users ORDER BY created_at LIMIT 1),
        'at', 'rt', 'challenge', 'https://x.test/cb',
        now() - interval '1 minute', NULL);

-- Used >5min ago.
INSERT INTO mcp_oauth_codes (code, client_id, user_id, supabase_access_token,
                             supabase_refresh_token, code_challenge, redirect_uri,
                             expires_at, used_at)
VALUES ('old-used', '00000000-0000-0000-0000-0000000000a1',
        (SELECT id FROM auth.users ORDER BY created_at LIMIT 1),
        'at', 'rt', 'challenge', 'https://x.test/cb',
        now() + interval '1 hour', now() - interval '10 minutes');

-- Used recently (<5 min ago) — still should be kept, single-use guard rail.
INSERT INTO mcp_oauth_codes (code, client_id, user_id, supabase_access_token,
                             supabase_refresh_token, code_challenge, redirect_uri,
                             expires_at, used_at)
VALUES ('recent-used', '00000000-0000-0000-0000-0000000000a1',
        (SELECT id FROM auth.users ORDER BY created_at LIMIT 1),
        'at', 'rt', 'challenge', 'https://x.test/cb',
        now() + interval '1 hour', now() - interval '1 minute');

SELECT lives_ok(
    'SELECT cleanup_mcp_oauth_codes()',
    'cleanup_mcp_oauth_codes() runs without error'
);

SELECT is((SELECT count(*)::int FROM mcp_oauth_codes WHERE code = 'fresh-unused'),
          1, 'fresh unused row is retained');
SELECT is((SELECT count(*)::int FROM mcp_oauth_codes WHERE code = 'expired-unused'),
          0, 'expired row is deleted');
SELECT is((SELECT count(*)::int FROM mcp_oauth_codes WHERE code = 'old-used'),
          0, 'used >5min ago row is deleted');
SELECT is((SELECT count(*)::int FROM mcp_oauth_codes WHERE code = 'recent-used'),
          1, 'recently used row is retained (5-min single-use window)');

-- ---------------------------------------------------------------------------
-- Foreign key cascade: deleting a client cascades to its codes
-- ---------------------------------------------------------------------------
INSERT INTO mcp_oauth_clients (client_id, client_name, redirect_uris)
VALUES ('00000000-0000-0000-0000-0000000000a2', 'cascade-fixture', ARRAY['https://x.test/cb']);

INSERT INTO mcp_oauth_codes (code, client_id, user_id, supabase_access_token,
                             supabase_refresh_token, code_challenge, redirect_uri)
VALUES ('cascade-code', '00000000-0000-0000-0000-0000000000a2',
        (SELECT id FROM auth.users ORDER BY created_at LIMIT 1),
        'at', 'rt', 'challenge', 'https://x.test/cb');

DELETE FROM mcp_oauth_clients WHERE client_id = '00000000-0000-0000-0000-0000000000a2';

SELECT is((SELECT count(*)::int FROM mcp_oauth_codes WHERE code = 'cascade-code'),
          0, 'deleting client cascades-deletes its codes');

-- ---------------------------------------------------------------------------
-- cleanup function presence + cron job registered
-- ---------------------------------------------------------------------------
SELECT has_function(
    'public', 'cleanup_mcp_oauth_codes', ARRAY[]::text[],
    'cleanup_mcp_oauth_codes() function exists'
);
SELECT is(
    (SELECT count(*)::int FROM cron.job WHERE jobname = 'cleanup-mcp-oauth-codes'),
    1,
    'cleanup cron job scheduled'
);

SELECT * FROM finish();
ROLLBACK;
