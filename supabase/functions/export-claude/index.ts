/**
 * export-claude Edge Function — Markdown export of verified, unused units.
 *
 * Route:
 *   GET /export-claude?project_id=<uuid>&limit=<int>
 *
 * Returns a plain-text markdown document suitable for piping into Claude or
 * another LLM as grounding context. Filters information_units to rows that
 * are verified AND have not yet been used in a published article.
 */

import { handleCors, corsHeaders } from "../_shared/cors.ts";
import { AuthedUser, requireUser } from "../_shared/auth.ts";
import { getUserClient } from "../_shared/supabase.ts";
import { jsonFromError } from "../_shared/responses.ts";
import { logEvent } from "../_shared/log.ts";

interface UnitRow {
  id?: string;
  statement: string;
  type: string | null;
  occurred_at?: string | null;
  event_date?: string | null;
  source_title?: string | null;
  source_domain?: string | null;
  source_url?: string | null;
  context_excerpt?: string | null;
}

Deno.serve(async (req): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  if (req.method !== "GET") {
    return new Response("method not allowed", {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  let user: AuthedUser;
  try {
    user = await requireUser(req);
  } catch (e) {
    return jsonFromError(e);
  }

  try {
    const url = new URL(req.url);
    const projectId = url.searchParams.get("project_id");
    const rawLimit = parseInt(url.searchParams.get("limit") ?? "50", 10);
    const limit = Math.min(200, Math.max(1, isNaN(rawLimit) ? 50 : rawLimit));

    const db = getUserClient(user.token);
    let query = db
      .from("information_units")
      .select("*")
      .eq("verified", true)
      .eq("used_in_article", false)
      .order("extracted_at", { ascending: false })
      .limit(limit);

    if (projectId) {
      query = query.eq("project_id", projectId);
    }

    const { data, error } = await query;
    if (error) throw new Error(error.message);

    const rows = (data ?? []) as UnitRow[];
    const body = rows.length === 0
      ? "# No unused verified units\n"
      : rows.map(formatUnit).join("\n");

    logEvent({
      level: "info",
      fn: "export-claude",
      event: "exported",
      user_id: user.id,
      count: rows.length,
    });

    return new Response(body, {
      status: 200,
      headers: {
        ...corsHeaders,
        "Content-Type": "text/markdown; charset=utf-8",
      },
    });
  } catch (e) {
    logEvent({
      level: "error",
      fn: "export-claude",
      event: "unhandled",
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonFromError(e);
  }
});

function formatUnit(u: UnitRow): string {
  const occurred = u.occurred_at ?? u.event_date ?? "unknown";
  const sourceLabel = u.source_title ?? u.source_domain ?? u.source_url ?? "source";
  const sourceUrl = u.source_url ?? "";
  const context = u.context_excerpt ?? "—";
  return [
    `## ${u.statement}`,
    "",
    `- **Type:** ${u.type ?? "unknown"}`,
    `- **Occurred:** ${occurred}`,
    `- **Source:** [${sourceLabel}](${sourceUrl})`,
    `- **Context:** ${context}`,
    "",
    "---",
    "",
  ].join("\n");
}
