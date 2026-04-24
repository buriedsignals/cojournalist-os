/**
 * CORS headers and preflight handling for Edge Functions.
 */

const ALLOWED_METHODS = "GET, HEAD, POST, PATCH, DELETE, OPTIONS";
const ALLOWED_HEADERS =
  "authorization, content-type, x-service-key, x-client-info, apikey";
const MAX_AGE = "86400";

/**
 * Build CORS headers for a given request origin.
 */
export function makeCorsHeaders(origin: string | null): Record<string, string> {
  return {
    "Access-Control-Allow-Origin": origin || "http://localhost:5173",
    "Access-Control-Allow-Methods": ALLOWED_METHODS,
    "Access-Control-Allow-Headers": ALLOWED_HEADERS,
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Max-Age": MAX_AGE,
  };
}

/**
 * Legacy static CORS headers — kept for backward compatibility with
 * responses.ts spread pattern. Echoes "*" which works as long as the
 * frontend does NOT use credentials: 'include'.
 */
export const corsHeaders: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": ALLOWED_METHODS,
  "Access-Control-Allow-Headers": ALLOWED_HEADERS,
  "Access-Control-Max-Age": MAX_AGE,
};

/**
 * Short-circuit handler for OPTIONS preflight requests.
 * Returns a 204 response with CORS headers, or null if the request is not OPTIONS.
 */
export function handleCors(req: Request): Response | null {
  if (req.method === "OPTIONS") {
    const origin = req.headers.get("origin");
    return new Response(null, {
      status: 204,
      headers: makeCorsHeaders(origin),
    });
  }
  return null;
}
