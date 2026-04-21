/**
 * entities Edge Function — canonical entity store + merge.
 *
 * Routes:
 *   GET    /entities            list entities (paginated). Query params:
 *                               type?, search?, offset, limit.
 *   GET    /entities/:id        single entity with mentions[] from unit_entities.
 *   POST   /entities            create entity.
 *   POST   /entities/merge      merge one or more entities into a keeper via
 *                               the merge_entities RPC (service-role).
 */

import { z } from "https://esm.sh/zod@3";
import { handleCors } from "../_shared/cors.ts";
import { requireUser, AuthedUser } from "../_shared/auth.ts";
import { getServiceClient, getUserClient } from "../_shared/supabase.ts";
import {
  jsonError,
  jsonFromError,
  jsonOk,
  jsonPaginated,
} from "../_shared/responses.ts";
import { ConflictError, NotFoundError, ValidationError } from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";

const ENTITY_TYPES = [
  "person",
  "org",
  "place",
  "policy",
  "event",
  "document",
  "other",
] as const;

const CreateSchema = z.object({
  canonical_name: z.string().min(1).max(500),
  type: z.enum(ENTITY_TYPES),
  aliases: z.array(z.string().max(500)).max(100).optional(),
  metadata: z.record(z.unknown()).optional(),
});

const MergeSchema = z.object({
  keep_id: z.string().uuid(),
  merge_ids: z.array(z.string().uuid()).min(1),
});

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
  // Trim the "/entities" prefix Kong leaves on the path. "/entities" -> "",
  // "/entities/<id>" -> "/<id>", "/entities/merge" -> "/merge".
  const path = url.pathname.replace(/^.*\/entities/, "") || "/";
  const idMatch = path.match(/^\/([0-9a-f-]{36})$/i);

  try {
    if (path === "/" && req.method === "GET") {
      return await listEntities(req, user);
    }
    if (path === "/" && req.method === "POST") {
      return await createEntity(req, user);
    }
    if (path === "/merge" && req.method === "POST") {
      return await mergeEntities(req, user);
    }
    if (idMatch && req.method === "GET") {
      return await getEntity(user, idMatch[1]);
    }
    return jsonError("method not allowed", 405);
  } catch (e) {
    logEvent({
      level: "error",
      fn: "entities",
      event: "unhandled",
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonFromError(e);
  }
});

// ---------------------------------------------------------------------------

async function listEntities(req: Request, user: AuthedUser): Promise<Response> {
  const url = new URL(req.url);
  const offset = Math.max(0, parseInt(url.searchParams.get("offset") ?? "0", 10));
  const limit = Math.min(100, Math.max(1, parseInt(url.searchParams.get("limit") ?? "50", 10)));
  const type = url.searchParams.get("type");
  const search = url.searchParams.get("search");

  const db = getUserClient(user.token);
  let q = db
    .from("entities")
    .select("*", { count: "exact" })
    .order("mention_count", { ascending: false })
    .order("canonical_name", { ascending: true })
    .range(offset, offset + limit - 1);

  if (type) {
    if (!ENTITY_TYPES.includes(type as typeof ENTITY_TYPES[number])) {
      throw new ValidationError(`invalid type: ${type}`);
    }
    q = q.eq("type", type);
  }
  if (search) {
    // canonical_name ILIKE '%search%' OR aliases && ARRAY[search]
    const escaped = search.replace(/[%_\\]/g, (c) => `\\${c}`);
    q = q.or(`canonical_name.ilike.%${escaped}%,aliases.cs.{${search}}`);
  }

  const { data, count, error } = await q;
  if (error) throw new Error(error.message);
  return jsonPaginated(data ?? [], count ?? 0, offset, limit);
}

async function createEntity(req: Request, user: AuthedUser): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    throw new ValidationError("invalid JSON body");
  }
  const parsed = CreateSchema.safeParse(body);
  if (!parsed.success) {
    throw new ValidationError(parsed.error.issues.map((i) => i.message).join("; "));
  }

  const db = getUserClient(user.token);
  const { data, error } = await db
    .from("entities")
    .insert({
      user_id: user.id,
      canonical_name: parsed.data.canonical_name,
      type: parsed.data.type,
      aliases: parsed.data.aliases ?? [],
      metadata: parsed.data.metadata ?? {},
    })
    .select("*")
    .single();

  if (error) {
    if (error.code === "23505") {
      throw new ConflictError("entity with this canonical_name + type already exists");
    }
    throw new Error(error.message);
  }

  logEvent({
    level: "info",
    fn: "entities",
    event: "created",
    user_id: user.id,
    entity_id: data.id,
  });
  return jsonOk(data, 201);
}

async function getEntity(user: AuthedUser, id: string): Promise<Response> {
  const db = getUserClient(user.token);
  const { data: entity, error } = await db
    .from("entities")
    .select("*")
    .eq("id", id)
    .maybeSingle();
  if (error) throw new Error(error.message);
  if (!entity) throw new NotFoundError("entity");

  const { data: mentions, error: mentionsErr } = await db
    .from("unit_entities")
    .select("unit_id, mention_text, confidence, resolved_at")
    .eq("entity_id", id);
  if (mentionsErr) throw new Error(mentionsErr.message);

  return jsonOk({ ...entity, mentions: mentions ?? [] });
}

async function mergeEntities(req: Request, user: AuthedUser): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    throw new ValidationError("invalid JSON body");
  }
  const parsed = MergeSchema.safeParse(body);
  if (!parsed.success) {
    throw new ValidationError(parsed.error.issues.map((i) => i.message).join("; "));
  }

  const svc = getServiceClient();
  const { error } = await svc.rpc("merge_entities", {
    p_user_id: user.id,
    p_keep_id: parsed.data.keep_id,
    p_merge_ids: parsed.data.merge_ids,
  });
  if (error) {
    // Ownership violations raised by the RPC surface as plpgsql errors.
    const msg = error.message || "merge failed";
    if (msg.includes("not owned by caller")) {
      throw new NotFoundError("entity");
    }
    throw new Error(msg);
  }

  logEvent({
    level: "info",
    fn: "entities",
    event: "merged",
    user_id: user.id,
    keep_id: parsed.data.keep_id,
    merged: parsed.data.merge_ids.length,
  });
  return jsonOk({ merged: parsed.data.merge_ids.length });
}
