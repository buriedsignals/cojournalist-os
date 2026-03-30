/**
 * execute-scout Edge Function
 *
 * Replaces the scraper-lambda. Receives scout configuration from pg_cron
 * (via pg_net.http_post) and calls the appropriate FastAPI execute endpoint.
 *
 * Scout type routing:
 *   web   -> POST /api/scouts/execute
 *   pulse -> POST /api/pulse/execute
 *   social -> POST /api/social/execute
 *   civic -> POST /api/civic/execute
 */

const BACKEND_URL = Deno.env.get("BACKEND_URL") ?? "http://backend:8000";
const SERVICE_KEY = Deno.env.get("INTERNAL_SERVICE_KEY") ?? "";

/** Map scout type to FastAPI execute endpoint. */
const EXECUTE_ENDPOINTS: Record<string, string> = {
  web: "/api/scouts/execute",
  pulse: "/api/pulse/execute",
  social: "/api/social/execute",
  civic: "/api/civic/execute",
};

Deno.serve(async (req: Request): Promise<Response> => {
  // Only accept POST requests
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    // Verify the request has a valid Authorization header (exact match, not substring)
    const authHeader = req.headers.get("Authorization") ?? "";
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
    const expectedToken = `Bearer ${supabaseServiceKey}`;

    if (!supabaseServiceKey) {
      return new Response(
        JSON.stringify({ error: "Server misconfigured: missing service key" }),
        { status: 500, headers: { "Content-Type": "application/json" } },
      );
    }

    if (authHeader !== expectedToken) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    }

    const body = await req.json();
    const scoutType: string = body.scout_type ?? body.type ?? "";
    const endpoint = EXECUTE_ENDPOINTS[scoutType];

    if (!endpoint) {
      return new Response(
        JSON.stringify({ error: `Unknown scout type: ${scoutType}` }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    console.log(`Executing ${scoutType} scout: ${body.scout_id ?? body.scraper_name ?? "unknown"}`);

    // Forward the request to FastAPI
    const response = await fetch(`${BACKEND_URL}${endpoint}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Service-Key": SERVICE_KEY,
      },
      body: JSON.stringify(body),
    });

    const responseBody = await response.text();

    console.log(`Scout execution completed: ${response.status}`);

    return new Response(responseBody, {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Error executing scout:", error);
    return new Response(
      JSON.stringify({
        error: "Internal server error",
        detail: error instanceof Error ? error.message : String(error),
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      },
    );
  }
});
