/**
 * /authorize (GET) and /authorize-callback (GET).
 *
 * /authorize:
 *   Entry point for an MCP client initiating login. We validate the client,
 *   sign a stateful blob that encodes the full OAuth flow, and 302 the
 *   browser to the MuckRock login broker (FastAPI pre-cutover; Supabase
 *   native OIDC post-cutover).
 *
 * /authorize-callback:
 *   The broker redirects back here with `{access_token, refresh_token,
 *   mcp_state}`. We verify the HMAC, resolve the user from the Supabase
 *   access token, mint a single-use MCP `code`, store it alongside the
 *   Supabase tokens, and 302 back to the MCP client's `redirect_uri`
 *   with the original `state`.
 *
 * Broker mode is expected to pass the tokens via query string (we control
 * it, no hash dance). TODO after auth-DB cutover: swap the 302 target to
 * `${SUPABASE_URL}/auth/v1/authorize?provider=muckrock&redirect_to=...`,
 * which means tokens come back in the URL fragment and this callback needs
 * to emit a tiny HTML page that reads `location.hash`, POSTs to a sibling
 * endpoint, and THEN redirects. See Plan 03 Risk #1.
 */

import { getServiceClient } from "../../_shared/supabase.ts";
import { logEvent } from "../../_shared/log.ts";
import { base64urlEncode, signState, verifyState } from "./state.ts";
import { baseUrl } from "./metadata.ts";
import { oauthError } from "./errors.ts";

function randUrlSafe(bytes: number): string {
  const buf = new Uint8Array(bytes);
  crypto.getRandomValues(buf);
  return base64urlEncode(buf);
}

function brokerBaseUrl(): string {
  // Pre-cutover default. Override with MCP_BROKER_URL for dev.
  return Deno.env.get("MCP_BROKER_URL") ?? "https://cojournalist.ai/api/auth/login";
}

/**
 * GET /authorize
 *
 * Params (query): client_id, redirect_uri, response_type=code, state,
 *                 code_challenge, code_challenge_method=S256, scope
 */
export async function authorize(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const params = url.searchParams;

  const clientId = params.get("client_id");
  const redirectUri = params.get("redirect_uri");
  const responseType = params.get("response_type");
  const state = params.get("state") ?? "";
  const codeChallenge = params.get("code_challenge");
  const codeChallengeMethod = params.get("code_challenge_method") ?? "S256";

  if (!clientId) return oauthError("invalid_request", "client_id required", 400);
  if (!redirectUri) return oauthError("invalid_request", "redirect_uri required", 400);
  if (responseType !== "code") {
    return oauthError("unsupported_response_type", "response_type must be 'code'", 400);
  }
  if (!codeChallenge) {
    return oauthError("invalid_request", "code_challenge required (PKCE)", 400);
  }
  if (codeChallengeMethod !== "S256") {
    return oauthError("invalid_request", "code_challenge_method must be S256", 400);
  }

  const db = getServiceClient();
  const { data: client, error } = await db
    .from("mcp_oauth_clients")
    .select("client_id, redirect_uris")
    .eq("client_id", clientId)
    .maybeSingle();
  if (error) {
    logEvent({ level: "error", fn: "mcp-server.authorize", event: "client_lookup_failed", msg: error.message });
    return oauthError("server_error", "client lookup failed", 500);
  }
  if (!client) {
    return oauthError("invalid_request", "unknown client_id", 400);
  }
  const allowed = Array.isArray(client.redirect_uris) ? client.redirect_uris as string[] : [];
  if (!allowed.includes(redirectUri)) {
    return oauthError("invalid_request", "redirect_uri not registered for this client", 400);
  }

  const mcpState = await signState({
    client_id: clientId,
    redirect_uri: redirectUri,
    state,
    code_challenge: codeChallenge,
    nonce: randUrlSafe(16),
  });

  const callback = `${baseUrl()}/authorize-callback`;
  // TODO(post-auth-cutover): replace brokerBaseUrl() with
  //   `${SUPABASE_URL}/auth/v1/authorize?provider=muckrock&redirect_to=${callback}#mcp_state=${mcpState}`
  // and render an HTML page in /authorize-callback that reads
  // location.hash client-side. Until then the FastAPI broker echoes the
  // tokens + mcp_state back as query parameters (no fragment needed).
  const target = new URL(brokerBaseUrl());
  target.searchParams.set("next", callback);
  target.searchParams.set("mcp_state", mcpState);

  logEvent({
    level: "info",
    fn: "mcp-server.authorize",
    event: "redirect_to_broker",
    client_id: clientId,
  });

  return new Response(null, {
    status: 302,
    headers: { Location: target.toString() },
  });
}

/**
 * GET /authorize-callback
 *
 * Expected query params (pre-cutover, from FastAPI broker):
 *   access_token, refresh_token, mcp_state
 *
 * Optional: error / error_description — forwarded to the MCP client.
 */
export async function callback(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const params = url.searchParams;

  const brokerError = params.get("error");
  if (brokerError) {
    // Try to forward error back to client if we still have a valid state.
    const maybeState = params.get("mcp_state");
    if (maybeState) {
      try {
        const payload = await verifyState(maybeState);
        const target = new URL(payload.redirect_uri);
        target.searchParams.set("error", brokerError);
        const desc = params.get("error_description");
        if (desc) target.searchParams.set("error_description", desc);
        if (payload.state) target.searchParams.set("state", payload.state);
        return new Response(null, { status: 302, headers: { Location: target.toString() } });
      } catch {
        // fall through to user-facing error
      }
    }
    return oauthError("access_denied", brokerError, 400);
  }

  const accessToken = params.get("access_token");
  const refreshToken = params.get("refresh_token");
  const mcpState = params.get("mcp_state");

  if (!accessToken || !refreshToken || !mcpState) {
    return oauthError(
      "invalid_request",
      "missing access_token, refresh_token, or mcp_state",
      400,
    );
  }

  let payload;
  try {
    payload = await verifyState(mcpState);
  } catch (e) {
    logEvent({
      level: "warn",
      fn: "mcp-server.callback",
      event: "bad_state",
      msg: e instanceof Error ? e.message : String(e),
    });
    return oauthError("invalid_request", "invalid mcp_state", 400);
  }

  // Resolve user id from the Supabase access token.
  const db = getServiceClient();
  const { data: userData, error: userErr } = await db.auth.getUser(accessToken);
  if (userErr || !userData.user) {
    logEvent({
      level: "warn",
      fn: "mcp-server.callback",
      event: "bad_access_token",
      msg: userErr?.message,
    });
    return oauthError("invalid_request", "access_token did not resolve to a user", 400);
  }
  const userId = userData.user.id;

  const code = randUrlSafe(32);
  const { error: insertErr } = await db.from("mcp_oauth_codes").insert({
    code,
    client_id: payload.client_id,
    user_id: userId,
    supabase_access_token: accessToken,
    supabase_refresh_token: refreshToken,
    code_challenge: payload.code_challenge,
    code_challenge_method: "S256",
    redirect_uri: payload.redirect_uri,
    scopes: [],
  });
  if (insertErr) {
    logEvent({
      level: "error",
      fn: "mcp-server.callback",
      event: "code_insert_failed",
      msg: insertErr.message,
    });
    return oauthError("server_error", "failed to mint authorization code", 500);
  }

  const target = new URL(payload.redirect_uri);
  target.searchParams.set("code", code);
  if (payload.state) target.searchParams.set("state", payload.state);

  logEvent({
    level: "info",
    fn: "mcp-server.callback",
    event: "code_issued",
    client_id: payload.client_id,
    user_id: userId,
  });

  return new Response(null, {
    status: 302,
    headers: { Location: target.toString() },
  });
}
