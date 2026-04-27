/**
 * projects Edge Function — CRUD for investigation projects.
 *
 * Routes:
 *   GET    /projects           list caller's projects (paginated)
 *   POST   /projects           create a project
 *   GET    /projects/:id       fetch a single project
 *   PATCH  /projects/:id       update name/description/visibility/tags
 *   DELETE /projects/:id       delete a project
 */

import { z } from "https://esm.sh/zod@3";
import { handleCors } from "../_shared/cors.ts";
import {
  AuthedUser,
  getCallerClient,
  requireUserOrApiKey,
} from "../_shared/auth.ts";
import {
  jsonError,
  jsonFromError,
  jsonOk,
  jsonPaginated,
} from "../_shared/responses.ts";
import {
  ConflictError,
  NotFoundError,
  ValidationError,
} from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";

const CreateSchema = z.object({
  name: z.string().min(1).max(120),
  description: z.string().max(2000).optional(),
  visibility: z.enum(["private", "team"]).default("private"),
  tags: z.array(z.string().max(50)).max(30).optional(),
});

const UpdateSchema = z.object({
  name: z.string().min(1).max(120).optional(),
  description: z.string().max(2000).nullable().optional(),
  visibility: z.enum(["private", "team"]).optional(),
  tags: z.array(z.string().max(50)).max(30).optional(),
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
  // Trim the "/projects" prefix Kong leaves on the path. "/projects" -> "",
  // "/projects/<id>" -> "/<id>".
  const path = url.pathname.replace(/^.*\/projects/, "") || "/";
  const idMatch = path.match(/^\/([0-9a-f-]{36})$/i);
  const isRead = req.method === "GET" || req.method === "HEAD";

  try {
    if (path === "/" && isRead) {
      return await listProjects(req, user);
    }
    if (path === "/" && req.method === "POST") {
      return await createProject(req, user);
    }
    if (idMatch && isRead) {
      return await getProject(user, idMatch[1]);
    }
    if (idMatch && req.method === "PATCH") {
      return await updateProject(req, user, idMatch[1]);
    }
    if (idMatch && req.method === "DELETE") {
      return await deleteProject(user, idMatch[1]);
    }
    return jsonError("method not allowed", 405);
  } catch (e) {
    logEvent({
      level: "error",
      fn: "projects",
      event: "unhandled",
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonFromError(e);
  }
});

// ---------------------------------------------------------------------------

async function listProjects(req: Request, user: AuthedUser): Promise<Response> {
  const url = new URL(req.url);
  const offset = Math.max(
    0,
    parseInt(url.searchParams.get("offset") ?? "0", 10),
  );
  const limit = Math.min(
    100,
    Math.max(1, parseInt(url.searchParams.get("limit") ?? "50", 10)),
  );

  const { db } = getCallerClient(user);
  const { data, count, error } = await db
    .from("projects")
    .select("*", { count: "exact" })
    .eq("user_id", user.id)
    .order("created_at", { ascending: false })
    .range(offset, offset + limit - 1);

  if (error) throw new Error(error.message);
  return jsonPaginated(data ?? [], count ?? 0, offset, limit);
}

async function createProject(
  req: Request,
  user: AuthedUser,
): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    throw new ValidationError("invalid JSON body");
  }
  const parsed = CreateSchema.safeParse(body);
  if (!parsed.success) {
    throw new ValidationError(
      parsed.error.issues.map((i) => i.message).join("; "),
    );
  }

  const { db } = getCallerClient(user);
  const { data, error } = await db
    .from("projects")
    .insert({ ...parsed.data, user_id: user.id })
    .select("*")
    .single();

  if (error) {
    if (error.code === "23505") {
      throw new ConflictError("project name already exists");
    }
    throw new Error(error.message);
  }

  logEvent({
    level: "info",
    fn: "projects",
    event: "created",
    user_id: user.id,
    project_id: data.id,
  });
  return jsonOk(data, 201);
}

async function getProject(user: AuthedUser, id: string): Promise<Response> {
  const { db } = getCallerClient(user);
  const { data, error } = await db.from("projects").select("*").eq("id", id).eq(
    "user_id",
    user.id,
  ).maybeSingle();
  if (error) throw new Error(error.message);
  if (!data) throw new NotFoundError("project");
  return jsonOk(data);
}

async function updateProject(
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
    throw new ValidationError(
      parsed.error.issues.map((i) => i.message).join("; "),
    );
  }
  if (Object.keys(parsed.data).length === 0) {
    throw new ValidationError("no updatable fields provided");
  }

  const { db } = getCallerClient(user);
  const { data, error } = await db
    .from("projects")
    .update(parsed.data)
    .eq("id", id)
    .eq("user_id", user.id)
    .select("*")
    .maybeSingle();

  if (error) {
    if (error.code === "23505") {
      throw new ConflictError("project name already exists");
    }
    throw new Error(error.message);
  }
  if (!data) throw new NotFoundError("project");
  return jsonOk(data);
}

async function deleteProject(user: AuthedUser, id: string): Promise<Response> {
  const { db } = getCallerClient(user);
  const { error, count } = await db
    .from("projects")
    .delete({ count: "exact" })
    .eq("id", id)
    .eq("user_id", user.id);
  if (error) throw new Error(error.message);
  if (!count) throw new NotFoundError("project");
  return new Response(null, {
    status: 204,
    headers: { "Access-Control-Allow-Origin": "*" },
  });
}
