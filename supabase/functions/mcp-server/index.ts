/**
 * mcp-server Edge Function — MCP (Model Context Protocol) JSON-RPC 2.0
 * server for coJournalist, with an embedded OAuth 2.1 authorization
 * server.
 *
 * PR 1+2 shipped the OAuth skeleton. PR 3 wires the JSON-RPC dispatcher
 * (rpc.ts) — 11 tools forwarded to the units/scouts/projects EFs.
 *
 * Routes (after Kong strips `/mcp-server/` from the path):
 *
 *   GET  /.well-known/oauth-authorization-server  -> RFC 8414 metadata
 *   POST /register                                -> RFC 7591 dynamic reg
 *   GET  /authorize                               -> login bootstrap
 *   GET  /authorize-callback                      -> broker return path
 *   POST /token                                   -> OAuth 2.1 token endpoint
 *   POST /                                        -> JSON-RPC (PR 3)
 *   *                                             -> 404 JSON
 *
 * This function sets `verify_jwt = false` in config.toml — the OAuth
 * endpoints are (by design) unauthenticated, and the future JSON-RPC
 * handler does its own token verification via `requireUser`.
 */

import { handleCors } from "../_shared/cors.ts";
import { logEvent } from "../_shared/log.ts";
import { metadataHandler } from "./oauth/metadata.ts";
import { registerHandler } from "./oauth/register.ts";
import { authorize, commitCallback, renderCallbackPage } from "./oauth/authorize.ts";
import { tokenHandler } from "./oauth/token.ts";
import { oauthError } from "./oauth/errors.ts";
import { handleRpc } from "./rpc.ts";

function stripPrefix(pathname: string): string {
  // Kong may keep the function name in the path ("/mcp-server/x") or strip
  // it ("/x"); handle both. Also collapse trailing slashes.
  const stripped = pathname.replace(/^\/+mcp-server(\/|$)/, "/").replace(/\/+$/, "");
  return stripped === "" ? "/" : stripped;
}

Deno.serve(async (req: Request): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  const url = new URL(req.url);
  const path = stripPrefix(url.pathname);

  try {
    // RFC 8414 metadata
    if (path === "/.well-known/oauth-authorization-server" && req.method === "GET") {
      return metadataHandler(req);
    }
    // RFC 7591 dynamic client registration
    if (path === "/register" && req.method === "POST") {
      return await registerHandler(req);
    }
    // OAuth authorization endpoint
    if (path === "/authorize" && req.method === "GET") {
      return await authorize(req);
    }
    if (path === "/authorize-callback" && req.method === "GET") {
      return await renderCallbackPage(req);
    }
    if (path === "/authorize-callback-commit" && req.method === "POST") {
      return await commitCallback(req);
    }
    // OAuth token endpoint
    if (path === "/token" && req.method === "POST") {
      return await tokenHandler(req);
    }

    // JSON-RPC body — MCP protocol surface.
    if (path === "/" && req.method === "POST") {
      return await handleRpc(req);
    }

    return oauthError("invalid_request", `no route for ${req.method} ${path}`, 404);
  } catch (e) {
    logEvent({
      level: "error",
      fn: "mcp-server",
      event: "unhandled",
      msg: e instanceof Error ? e.message : String(e),
    });
    return oauthError("server_error", "internal error", 500);
  }
});
