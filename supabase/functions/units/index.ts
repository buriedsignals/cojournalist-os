/**
 * units Edge Function — information units (atomic facts extracted from scout
 * results) with verification + usage tracking and semantic search.
 *
 * Routes:
 *   GET    /units              list caller's units (filter + paginate)
 *   POST   /units/search       semantic search over caller's units
 *   GET    /units/:id          fetch a single unit
 *   PATCH  /units/:id          update verification/usage fields
 *
 * Auth: requireUser for every route. User-scoped client for reads/updates;
 * service-role client is used only to invoke the SECURITY DEFINER
 * semantic_search_units RPC (we pass user.id explicitly so RLS would over-
 * filter the call).
 *
 * Column note: the schema column is `type`, exposed as `unit_type` via
 * shapeUnitResponse.
 */

import { z } from "https://esm.sh/zod@3";
import { handleCors } from "../_shared/cors.ts";
import { AuthedUser, getCallerClient, requireUserOrApiKey } from "../_shared/auth.ts";
import { getServiceClient } from "../_shared/supabase.ts";
import {
  jsonError,
  jsonFromError,
  jsonOk,
  jsonPaginated,
} from "../_shared/responses.ts";
import { NotFoundError, ValidationError } from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";
import { shapeUnitResponse } from "../_shared/db.ts";
import { geminiEmbed } from "../_shared/gemini.ts";

const SearchSchema = z.object({
  query_text: z.string().min(1).max(4000),
  project_id: z.string().uuid().optional(),
  limit: z.number().int().min(1).max(100).optional(),
});

const UpdateSchema = z.object({
  verified: z.boolean().optional(),
  verification_notes: z.string().max(4000).nullable().optional(),
  verified_by: z.string().max(200).nullable().optional(),
  used_in_article: z.boolean().optional(),
  used_at: z.string().datetime().nullable().optional(),
  used_in_url: z.string().url().nullable().optional(),
});

Deno.serve(async (req): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  let user: AuthedUser;
  try {
    user = await requireUserOrApiKey(req);
  } catch (e) {
    return jsonFromError(e);
  }

  const url = new URL(req.url);
  // Trim the "/units" prefix Kong leaves on the path. "/units" -> "",
  // "/units/<id>" -> "/<id>", "/units/search" -> "/search".
  const path = url.pathname.replace(/^.*\/units/, "") || "/";
  const idMatch = path.match(/^\/([0-9a-f-]{36})$/i);

  try {
    if (path === "/" && req.method === "GET") {
      return await listUnits(req, user);
    }
    if (path === "/search" && req.method === "POST") {
      return await searchUnits(req, user);
    }
    if (idMatch && req.method === "GET") {
      return await getUnit(user, idMatch[1]);
    }
    if (idMatch && req.method === "PATCH") {
      return await updateUnit(req, user, idMatch[1]);
    }
    if (idMatch && req.method === "DELETE") {
      return await deleteUnit(user, idMatch[1]);
    }
    return jsonError("method not allowed", 405);
  } catch (e) {
    logEvent({
      level: "error",
      fn: "units",
      event: "unhandled",
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonFromError(e);
  }
});

// ---------------------------------------------------------------------------

function parseBool(v: string | null): boolean | null {
  if (v === null) return null;
  const s = v.toLowerCase();
  if (s === "true" || s === "1") return true;
  if (s === "false" || s === "0") return false;
  return null;
}

async function listUnits(req: Request, user: AuthedUser): Promise<Response> {
  const url = new URL(req.url);
  const offset = Math.max(0, parseInt(url.searchParams.get("offset") ?? "0", 10));
  const limit = Math.min(
    100,
    Math.max(1, parseInt(url.searchParams.get("limit") ?? "50", 10)),
  );

  const projectId = url.searchParams.get("project_id");
  const scoutId = url.searchParams.get("scout_id");
  const verified = parseBool(url.searchParams.get("verified"));
  const used = parseBool(url.searchParams.get("used"));
  const from = url.searchParams.get("from");
  const to = url.searchParams.get("to");

  const { db, needsExplicitScope } = getCallerClient(user);
  let q = db
    .from("information_units")
    .select("*", { count: "exact" })
    .order("extracted_at", { ascending: false });

  if (needsExplicitScope) q = q.eq("user_id", user.id);
  if (projectId) q = q.eq("project_id", projectId);
  if (scoutId) q = q.eq("scout_id", scoutId);
  if (verified !== null) q = q.eq("verified", verified);
  if (used !== null) q = q.eq("used_in_article", used);
  if (from) q = q.gte("extracted_at", from);
  if (to) q = q.lte("extracted_at", to);

  const { data, count, error } = await q.range(offset, offset + limit - 1);
  if (error) throw new Error(error.message);

  const shaped = await Promise.all(
    (data ?? []).map((row) => shapeUnitResponse(db, row)),
  );
  return jsonPaginated(shaped, count ?? 0, offset, limit);
}

async function searchUnits(req: Request, user: AuthedUser): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    throw new ValidationError("invalid JSON body");
  }
  const parsed = SearchSchema.safeParse(body);
  if (!parsed.success) {
    throw new ValidationError(parsed.error.issues.map((i) => i.message).join("; "));
  }

  const { query_text, project_id, limit } = parsed.data;
  const effectiveLimit = limit ?? 20;

  // Short-circuit: if the user has no units at all, skip the embedding call.
  const { db: userDb, needsExplicitScope } = getCallerClient(user);
  let countQ = userDb
    .from("information_units")
    .select("id", { count: "exact", head: true });
  if (needsExplicitScope) countQ = countQ.eq("user_id", user.id);
  const { count: unitCount, error: countErr } = await countQ;
  if (countErr) throw new Error(countErr.message);
  if (!unitCount) {
    return jsonOk({ items: [] });
  }

  // Hybrid search (migration 00028): FTS + vector merged via RRF. If embedding
  // generation fails we still run the RPC with p_embedding = null so keyword
  // matches (e.g. a street name in context_excerpt) still surface.
  let embedding: number[] | null = null;
  try {
    embedding = await geminiEmbed(query_text, "RETRIEVAL_QUERY");
  } catch (e) {
    logEvent({
      level: "warn",
      fn: "units",
      event: "embed_failed_fts_fallback",
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
  }

  const svc = getServiceClient();
  const { data, error } = await svc.rpc("semantic_search_units", {
    p_embedding: embedding,
    p_user_id: user.id,
    p_project_id: project_id ?? null,
    p_limit: effectiveLimit,
    p_query_text: query_text,
  });
  if (error) throw new Error(error.message);

  // The RPC returns a minimal projection (id, statement, context_excerpt,
  // unit_type, occurred_at, extracted_at, project_id, similarity). We rehydrate
  // each hit via shapeUnitResponse so agents get the full envelope, and we
  // preserve the similarity score.
  const items = await Promise.all(
    (data ?? []).map(async (row: Record<string, unknown>) => {
      let fetchQ = userDb
        .from("information_units")
        .select("*")
        .eq("id", row.id as string);
      if (needsExplicitScope) fetchQ = fetchQ.eq("user_id", user.id);
      const { data: full, error: fetchErr } = await fetchQ.maybeSingle();
      if (fetchErr) throw new Error(fetchErr.message);
      if (!full) {
        // Row filtered by RLS (shouldn't happen since the RPC already scoped
        // to user_id) — fall back to the projection + similarity.
        return { ...row };
      }
      const shaped = await shapeUnitResponse(userDb, full);
      return { ...shaped, similarity: row.similarity ?? null };
    }),
  );

  return jsonOk({ items });
}

async function getUnit(user: AuthedUser, id: string): Promise<Response> {
  const { db, needsExplicitScope } = getCallerClient(user);
  let q = db.from("information_units").select("*").eq("id", id);
  if (needsExplicitScope) q = q.eq("user_id", user.id);
  const { data, error } = await q.maybeSingle();
  if (error) throw new Error(error.message);
  if (!data) throw new NotFoundError("unit");
  return jsonOk(await shapeUnitResponse(db, data));
}

async function updateUnit(
  req: Request,
  user: AuthedUser,
  id: string,
): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    throw new ValidationError("invalid JSON body");
  }
  const parsed = UpdateSchema.safeParse(body);
  if (!parsed.success) {
    throw new ValidationError(parsed.error.issues.map((i) => i.message).join("; "));
  }
  if (Object.keys(parsed.data).length === 0) {
    throw new ValidationError("no updatable fields provided");
  }

  // Stamp verified_at automatically when verified flips true and no client-
  // supplied timestamp is needed. (verified_at isn't on the allowed input
  // list, so we derive it here.)
  const patch: Record<string, unknown> = { ...parsed.data };
  if (parsed.data.verified === true) {
    patch.verified_at = new Date().toISOString();
  } else if (parsed.data.verified === false) {
    patch.verified_at = null;
  }

  const { db, needsExplicitScope } = getCallerClient(user);
  let updQ = db.from("information_units").update(patch).eq("id", id);
  if (needsExplicitScope) updQ = updQ.eq("user_id", user.id);
  const { data, error } = await updQ.select("*").maybeSingle();

  if (error) throw new Error(error.message);
  if (!data) throw new NotFoundError("unit");

  logEvent({
    level: "info",
    fn: "units",
    event: "updated",
    user_id: user.id,
    unit_id: id,
  });
  return jsonOk(await shapeUnitResponse(db, data));
}

async function deleteUnit(user: AuthedUser, id: string): Promise<Response> {
  const { db, needsExplicitScope } = getCallerClient(user);
  let q = db.from("information_units").delete({ count: "exact" }).eq("id", id);
  if (needsExplicitScope) q = q.eq("user_id", user.id);
  const { error, count } = await q;
  if (error) throw new Error(error.message);
  if (!count) throw new NotFoundError("unit");

  logEvent({
    level: "info",
    fn: "units",
    event: "deleted",
    user_id: user.id,
    unit_id: id,
  });
  return new Response(null, {
    status: 204,
    headers: { "Access-Control-Allow-Origin": "*" },
  });
}
