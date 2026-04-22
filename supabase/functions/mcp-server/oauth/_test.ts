/**
 * Remote MCP OAuth flow — end-to-end contract tests.
 *
 * Exercises the pieces an external browser-based MCP client (claude.ai,
 * ChatGPT Enterprise) hits:
 *
 *   1. /authorize  → 302 to the broker with mcp_callback + mcp_state
 *   2. /authorize-callback → HTML bounce page containing the same-origin
 *      commit URL and a JS shim that reads location.hash
 *   3. /authorize-callback-commit → validates tokens, mints code, 302s to
 *      the client's redirect_uri
 *
 * State-token round-trip is verified separately (see state.ts); here we
 * assert the handlers' HTTP behaviour + validation paths.
 */

import {
  assertEquals,
  assertStringIncludes,
} from "https://deno.land/std@0.224.0/assert/mod.ts";
import { authorize, commitCallback, renderCallbackPage } from "./authorize.ts";

function reqWithEnv(env: Record<string, string>, fn: () => Promise<Response>): Promise<Response> {
  const prev: Record<string, string | undefined> = {};
  for (const k of Object.keys(env)) {
    prev[k] = Deno.env.get(k) ?? undefined;
    Deno.env.set(k, env[k]);
  }
  return fn().finally(() => {
    for (const k of Object.keys(prev)) {
      const v = prev[k];
      if (v === undefined) Deno.env.delete(k);
      else Deno.env.set(k, v);
    }
  });
}

// ---------------------------------------------------------------------------
// renderCallbackPage
// ---------------------------------------------------------------------------

Deno.test("renderCallbackPage: returns HTML bounce with inline commit URL", async () => {
  const res = await reqWithEnv(
    {
      SUPABASE_URL: "http://127.0.0.1:54321",
      MCP_SERVER_BASE_URL: "http://127.0.0.1:54321/functions/v1/mcp-server",
    },
    () =>
      renderCallbackPage(
        new Request("http://x/authorize-callback?mcp_state=abc.def", { method: "GET" }),
      ),
  );
  assertEquals(res.status, 200);
  const ct = res.headers.get("content-type") ?? "";
  assertStringIncludes(ct, "text/html");
  const html = await res.text();
  assertStringIncludes(
    html,
    "http://127.0.0.1:54321/functions/v1/mcp-server/authorize-callback-commit",
  );
  // Sanity — the JS shim must read location.hash and POST access_token
  assertStringIncludes(html, "access_token");
  assertStringIncludes(html, "refresh_token");
  assertStringIncludes(html, "mcp_state");
  // And must strip tokens from URL history after submitting.
  assertStringIncludes(html, "history.replaceState");
});

Deno.test("renderCallbackPage: sets a strict CSP so the page is self-contained", async () => {
  const res = await reqWithEnv(
    { SUPABASE_URL: "http://127.0.0.1:54321" },
    () =>
      renderCallbackPage(
        new Request("http://x/authorize-callback", { method: "GET" }),
      ),
  );
  const csp = res.headers.get("content-security-policy") ?? "";
  assertStringIncludes(csp, "default-src 'none'");
  assertStringIncludes(csp, "form-action 'self'");
});

Deno.test("renderCallbackPage: broker error without mcp_state → oauthError 400", async () => {
  const res = await reqWithEnv(
    { SUPABASE_URL: "http://127.0.0.1:54321" },
    () =>
      renderCallbackPage(
        new Request("http://x/authorize-callback?error=access_denied", { method: "GET" }),
      ),
  );
  assertEquals(res.status, 400);
  const body = await res.json();
  assertEquals(body.error, "access_denied");
});

// ---------------------------------------------------------------------------
// authorize — input validation (client_id must be UUID)
// ---------------------------------------------------------------------------

Deno.test("authorize: non-UUID client_id → 400 before DB query", async () => {
  const res = await reqWithEnv(
    { MCP_STATE_SECRET: "s".repeat(32), SUPABASE_URL: "http://127.0.0.1:54321" },
    () =>
      authorize(
        new Request(
          "http://x/authorize?client_id=not-a-uuid&redirect_uri=https://a.b&response_type=code&code_challenge=x&code_challenge_method=S256",
          { method: "GET" },
        ),
      ),
  );
  // Must be 400 with an OAuth 2.0 `invalid_request` code, never a 500
  // — the DB query would type-cast-error on a non-UUID and surface as
  // a misleading "client lookup failed" if we let it through.
  assertEquals(res.status, 400);
  const err = await res.json();
  assertEquals(err.error, "invalid_request");
  assertStringIncludes(err.error_description ?? "", "UUID");
});

Deno.test("authorize: missing client_id → 400", async () => {
  const res = await reqWithEnv(
    { MCP_STATE_SECRET: "s".repeat(32), SUPABASE_URL: "http://127.0.0.1:54321" },
    () =>
      authorize(
        new Request(
          "http://x/authorize?redirect_uri=https://a.b&response_type=code&code_challenge=x&code_challenge_method=S256",
          { method: "GET" },
        ),
      ),
  );
  assertEquals(res.status, 400);
  const err = await res.json();
  assertStringIncludes(err.error_description ?? "", "client_id");
});

// ---------------------------------------------------------------------------
// commitCallback
// ---------------------------------------------------------------------------

Deno.test("commitCallback: missing access_token → invalid_request", async () => {
  const body = new URLSearchParams({ mcp_state: "x.y" });
  const res = await reqWithEnv(
    { MCP_STATE_SECRET: "s".repeat(32), SUPABASE_URL: "http://127.0.0.1:54321" },
    () =>
      commitCallback(
        new Request("http://x/authorize-callback-commit", {
          method: "POST",
          body: body.toString(),
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
        }),
      ),
  );
  assertEquals(res.status, 400);
  const err = await res.json();
  assertEquals(err.error, "invalid_request");
  assertStringIncludes(err.error_description ?? "", "access_token");
});

Deno.test("commitCallback: invalid mcp_state → invalid_request", async () => {
  const body = new URLSearchParams({
    access_token: "at",
    refresh_token: "rt",
    mcp_state: "not-a-valid-token",
  });
  const res = await reqWithEnv(
    { MCP_STATE_SECRET: "s".repeat(32), SUPABASE_URL: "http://127.0.0.1:54321" },
    () =>
      commitCallback(
        new Request("http://x/authorize-callback-commit", {
          method: "POST",
          body: body.toString(),
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
        }),
      ),
  );
  assertEquals(res.status, 400);
  const err = await res.json();
  assertStringIncludes(err.error_description ?? "", "mcp_state");
});

Deno.test("commitCallback: garbage JSON body → invalid_request", async () => {
  const res = await reqWithEnv(
    { MCP_STATE_SECRET: "s".repeat(32), SUPABASE_URL: "http://127.0.0.1:54321" },
    () =>
      commitCallback(
        new Request("http://x/authorize-callback-commit", {
          method: "POST",
          body: "{not json",
          headers: { "Content-Type": "application/json" },
        }),
      ),
  );
  assertEquals(res.status, 400);
});
