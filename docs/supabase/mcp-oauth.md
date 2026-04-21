# MCP OAuth

Model Context Protocol clients (Claude Code, Codex, Gemini CLI, Goose) authenticate to the coJournalist MCP server via OAuth 2.0 with PKCE. This doc covers the RFC 7591 Dynamic Client Registration + Authorization Code flow, the two tables that persist state, and the cleanup cron.

Migration: `supabase/migrations/00024_mcp_oauth.sql`.

## Tables

### `mcp_oauth_clients`

Registered MCP clients. Public-client / PKCE flow supported (no `client_secret_hash`).

| Column | Type | Notes |
|---|---|---|
| `client_id` | UUID PK | Opaque identifier issued at registration |
| `client_secret_hash` | TEXT | NULL for `token_endpoint_auth_method='none'` (PKCE) |
| `redirect_uris` | TEXT[] NOT NULL | Exact-match validation at `/authorize` |
| `token_endpoint_auth_method` | TEXT CHECK IN ('none','client_secret_post','client_secret_basic') | |
| `client_name`, `client_uri`, `tos_uri`, `policy_uri` | TEXT | Metadata |
| `scope` | TEXT | Space-delimited default scope |
| `user_id` | UUID → `auth.users(id)` | Who registered this client (for dashboard visibility) |
| `registered_at` | TIMESTAMPTZ | |
| `last_used_at` | TIMESTAMPTZ | Updated on successful code exchange |

Index: `mcp_oauth_clients_user_id_idx(user_id)`.

### `mcp_oauth_codes`

One-shot authorization codes. Wraps a Supabase JWT for the client to exchange at `/token`.

| Column | Type | Notes |
|---|---|---|
| `code` | TEXT PK | Opaque, URL-safe, 48+ chars |
| `client_id` | UUID → `mcp_oauth_clients(client_id)` | |
| `user_id` | UUID → `auth.users(id)` | Who approved the grant |
| `supabase_access_token` | TEXT NOT NULL | The JWT issued upstream by Supabase Auth, handed back unchanged at `/token` |
| `code_challenge` | TEXT | PKCE S256 challenge |
| `code_challenge_method` | TEXT CHECK IN ('S256') | Only S256 accepted |
| `redirect_uri` | TEXT NOT NULL | Must match registered redirect_uris[] |
| `scopes` | TEXT[] | |
| `expires_at` | TIMESTAMPTZ NOT NULL | 10 minutes from creation |
| `used_at` | TIMESTAMPTZ | Flipped on successful exchange (idempotency guard) |
| `created_at` | TIMESTAMPTZ | |

Index: `mcp_oauth_codes_expires_at_idx(expires_at)`.

## RPC

### `cleanup_mcp_oauth_codes() RETURNS VOID`

Daily. Deletes codes where `(used_at IS NOT NULL AND used_at < NOW() - INTERVAL '5 minutes') OR expires_at < NOW()`.

## RLS

```sql
-- 00024:
CREATE POLICY clients_owner_select ON mcp_oauth_clients FOR SELECT USING (auth.uid() = user_id);
-- mcp_oauth_codes: no user-facing policies; service_role only
```

Clients can't SELECT each other's registrations. Codes are never exposed to any role via RLS — only the Edge Function (service-role) reads them.

## Cron

| Job | Schedule | Command |
|---|---|---|
| `cleanup-mcp-oauth-codes` | `20 3 * * *` | `SELECT cleanup_mcp_oauth_codes()` |

## Edge Function

### `mcp-server`

Single Edge Function implements the full OAuth 2.0 flow:

| Route | Method | Purpose |
|---|---|---|
| `/.well-known/oauth-authorization-server` | GET | RFC 8414 metadata document |
| `/.well-known/oauth-protected-resource` | GET | RFC 9728 resource metadata |
| `/register` | POST | RFC 7591 Dynamic Client Registration. Issues a new `client_id`; saves redirect_uris + scopes. |
| `/authorize` | GET | Opens a grant-approval page; after user approval, stores a row in `mcp_oauth_codes` and 302s to `redirect_uri?code=...&state=...`. |
| `/token` | POST | Exchanges `code` + `code_verifier` (PKCE) for the wrapped `supabase_access_token`. Returns `{ access_token, token_type: 'bearer', expires_in, scope }`. One-shot — marks `used_at`. |

### Actual MCP endpoints (not part of OAuth)

The same `mcp-server` Edge Function also serves MCP protocol endpoints at `/mcp/*` — these are authenticated via the Bearer token from `/token`.

## Data flow

```
1. Register (once per client)
   Client → POST /register { client_name, redirect_uris, scope, token_endpoint_auth_method='none' }
         ← { client_id: '<uuid>' }

2. Authorize
   User in Claude Code → open /authorize?client_id=X&redirect_uri=Y&response_type=code
                        &code_challenge=Z&code_challenge_method=S256&scope=...&state=...
   Approval page → click "Allow"
                → mcp_oauth_codes INSERT { code, supabase_access_token, code_challenge, expires_at=+10m }
                → 302 to redirect_uri?code=<code>&state=<state>

3. Exchange
   Client → POST /token { grant_type='authorization_code', code, code_verifier, client_id, redirect_uri }
         → validate code_verifier → S256 hash == stored code_challenge
         → check expires_at, used_at
         → mcp_oauth_codes UPDATE used_at = NOW()
         ← { access_token: <supabase JWT>, token_type: 'bearer', expires_in: 3600, scope }

4. MCP traffic
   Client → GET /mcp/... with Authorization: Bearer <supabase JWT>
   mcp-server → requireUser(jwt) → user-scoped client → tool calls
```

## Invariants

1. **PKCE is enforced.** `code_challenge_method` must be `S256`; plain method is rejected.
2. **Codes are one-shot and short-lived** (10 min expiry; `used_at` = lockout). Reuse returns invalid_grant.
3. **`supabase_access_token` is handed back verbatim** — no JWT re-signing. The MCP client receives the same token a browser would, with the same claims and expiry.
4. **`redirect_uri` must exact-match** a value in `mcp_oauth_clients.redirect_uris[]`. No wildcards.
5. **Codes are never readable via RLS** — no policy grants SELECT to any authenticated role. Only the Edge Function (service-role) touches the table.

## Operations

### See registered clients for a user

```sql
SELECT client_id, client_name, redirect_uris, scope, registered_at, last_used_at
  FROM mcp_oauth_clients
 WHERE user_id = '<uuid>'
 ORDER BY registered_at DESC;
```

### Revoke a client

```sql
DELETE FROM mcp_oauth_clients WHERE client_id = '<uuid>';
-- Any outstanding codes also disappear (FK CASCADE from the codes table).
```

### Investigate stuck codes

```sql
SELECT code, client_id, user_id, expires_at, used_at, created_at
  FROM mcp_oauth_codes
 WHERE used_at IS NULL AND expires_at > NOW()
 ORDER BY created_at DESC
 LIMIT 20;
```

## See also

- `supabase/migrations/00024_mcp_oauth.sql`
- `docs/muckrock/plans-and-entitlements.md` — MCP clients still consume user credits for tool calls
