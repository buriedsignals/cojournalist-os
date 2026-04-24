/**
 * scout-templates Edge Function — static catalog of pre-built scout templates
 * that users or agents can instantiate via POST /scouts/from-template.
 *
 * Routes:
 *   GET /scout-templates           list all templates ({ templates: [...] })
 *   GET /scout-templates/:slug     single template by slug (404 if unknown)
 *
 * Auth: requireUser (JWT). Catalog is identical for every caller; auth is
 * required so clients standardise on Bearer.
 */

import { handleCors } from "../_shared/cors.ts";
import { requireUser, AuthedUser } from "../_shared/auth.ts";
import { jsonError, jsonFromError, jsonOk } from "../_shared/responses.ts";
import { NotFoundError } from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";
import templates from "./templates.json" with { type: "json" };

interface Template {
  slug: string;
  name: string;
  type: string;
  description: string;
  defaults: Record<string, unknown>;
  fields: Array<{
    key: string;
    label: string;
    required?: boolean;
    multiline?: boolean;
  }>;
  example_fill?: Record<string, unknown>;
}

const TEMPLATES = templates as Template[];

Deno.serve(async (req): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  let user: AuthedUser;
  try {
    user = await requireUser(req);
  } catch (e) {
    return jsonFromError(e);
  }

  const url = new URL(req.url);
  // Trim the "/scout-templates" prefix Kong leaves on the path.
  const path = url.pathname.replace(/^.*\/scout-templates/, "") || "/";
  const slugMatch = path.match(/^\/([a-z0-9][a-z0-9-]*)$/i);
  const isRead = req.method === "GET" || req.method === "HEAD";

  try {
    if (path === "/" && isRead) {
      return jsonOk({ templates: TEMPLATES });
    }
    if (slugMatch && isRead) {
      const slug = slugMatch[1];
      const tpl = TEMPLATES.find((t) => t.slug === slug);
      if (!tpl) throw new NotFoundError("template");
      return jsonOk(tpl);
    }
    return jsonError("method not allowed", 405);
  } catch (e) {
    logEvent({
      level: "error",
      fn: "scout-templates",
      event: "unhandled",
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonFromError(e);
  }
});
