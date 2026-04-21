/**
 * OAuth 2.1 / MCP error response helpers.
 *
 * All OAuth endpoints return `{error, error_description}` per RFC 6749 §5.2
 * rather than the generic `{error: msg}` from `_shared/responses.ts`.
 */

import { corsHeaders } from "../../_shared/cors.ts";

export type OAuthErrorCode =
  | "invalid_request"
  | "invalid_client"
  | "invalid_grant"
  | "unauthorized_client"
  | "unsupported_grant_type"
  | "unsupported_response_type"
  | "invalid_scope"
  | "server_error"
  | "access_denied"
  | "invalid_redirect_uri"
  | "invalid_client_metadata";

const jsonHeaders: Record<string, string> = {
  ...corsHeaders,
  "Content-Type": "application/json; charset=utf-8",
  // OAuth endpoints must not be cached by shared caches.
  "Cache-Control": "no-store",
  "Pragma": "no-cache",
};

export function oauthError(
  code: OAuthErrorCode,
  description: string,
  status = 400,
  extra?: Record<string, string>,
): Response {
  const body: Record<string, string> = {
    error: code,
    error_description: description,
  };
  const headers = { ...jsonHeaders };
  if (status === 401) {
    headers["WWW-Authenticate"] = `Bearer error="${code}", error_description="${description.replace(/"/g, "'")}"`;
  }
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...headers, ...(extra ?? {}) },
  });
}

export function oauthJson(body: unknown, status = 200, extraHeaders?: Record<string, string>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...jsonHeaders, ...(extraHeaders ?? {}) },
  });
}
