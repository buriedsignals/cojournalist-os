/**
 * Main Edge Function — entry point for supabase/edge-runtime.
 *
 * The edge-runtime `--main-service` flag points here. Individual function
 * directories (execute-scout, manage-schedule) are served automatically by
 * the runtime at /<function-name>. This main service handles the root path
 * and any unmatched routes with a health-check or 404 response.
 */

Deno.serve((_req: Request): Response => {
  const url = new URL(_req.url);

  // Root health check
  if (url.pathname === "/" || url.pathname === "") {
    return new Response(
      JSON.stringify({ status: "ok", service: "edge-functions" }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  }

  // Fallback for unknown routes (individual functions are handled by the runtime)
  return new Response(
    JSON.stringify({ error: "Function not found" }),
    { status: 404, headers: { "Content-Type": "application/json" } },
  );
});
