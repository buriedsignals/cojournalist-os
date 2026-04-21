/**
 * Standard JSON response shapes with CORS headers applied.
 *
 * All helpers accept the incoming `Request` (or origin string) so the
 * response echoes the caller's origin + Access-Control-Allow-Credentials=true.
 * This is required when the frontend sets `credentials: 'include'` — the
 * browser rejects responses whose Access-Control-Allow-Origin is `*` in
 * credentialed mode.
 *
 * Callers that don't pass a request fall back to the legacy wildcard
 * headers (safe for server-to-server calls where no browser enforces CORS).
 */

import { corsHeaders, makeCorsHeaders } from "./cors.ts";
import { ApiError } from "./errors.ts";

function buildJsonHeaders(origin: Request | string | null | undefined): Record<string, string> {
  const originStr =
    origin == null
      ? null
      : typeof origin === "string"
      ? origin
      : origin.headers.get("origin");
  const base = originStr == null ? corsHeaders : makeCorsHeaders(originStr);
  return {
    ...base,
    "Content-Type": "application/json; charset=utf-8",
    Vary: "Origin",
  };
}

export function jsonOk(
  body: unknown,
  status = 200,
  origin?: Request | string | null,
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: buildJsonHeaders(origin),
  });
}

export function jsonError(
  message: string,
  status = 400,
  code?: string,
  origin?: Request | string | null,
): Response {
  const body: Record<string, unknown> = { error: message };
  if (code) body.code = code;
  return new Response(JSON.stringify(body), {
    status,
    headers: buildJsonHeaders(origin),
  });
}

export interface Pagination {
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export function jsonPaginated<T>(
  items: T[],
  total: number,
  offset: number,
  limit: number,
  origin?: Request | string | null,
): Response {
  const body = {
    items,
    pagination: {
      total,
      offset,
      limit,
      has_more: offset + items.length < total,
    } satisfies Pagination,
  };
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: buildJsonHeaders(origin),
  });
}

/**
 * Convert any thrown exception into a proper JSON error response.
 * ApiError (and subclasses) carry status + code; anything else becomes 500.
 */
export function jsonFromError(
  err: unknown,
  origin?: Request | string | null,
): Response {
  if (err instanceof ApiError) {
    return jsonError(err.message, err.status, err.code, origin);
  }
  return jsonError(errorToMessage(err), 500, "internal_error", origin);
}

/**
 * Coerce any thrown value into a string message. Critically, plain objects
 * (like PostgrestError from supabase-js) have no sensible `.toString()` and
 * would otherwise serialise as "[object Object]" — masking the real failure
 * from the client. This drills into known shapes before falling back to JSON.
 */
function errorToMessage(err: unknown): string {
  if (err == null) return "unknown error";
  if (typeof err === "string") return err;
  if (err instanceof Error) return err.message;
  if (typeof err === "object") {
    const e = err as Record<string, unknown>;
    const parts: string[] = [];
    if (typeof e.message === "string" && e.message) parts.push(e.message);
    if (typeof e.details === "string" && e.details) parts.push(e.details);
    if (typeof e.hint === "string" && e.hint) parts.push(`(hint: ${e.hint})`);
    if (typeof e.code === "string" && e.code) parts.push(`[${e.code}]`);
    if (parts.length > 0) return parts.join(" ");
    try {
      return JSON.stringify(err);
    } catch {
      /* fall through */
    }
  }
  return String(err);
}
