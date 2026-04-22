/**
 * api-keys Edge Function — CRUD for the caller's agent API keys.
 *
 * Routes (all session-auth via requireUser):
 *   POST   /api-keys {name}     create — returns the raw key ONCE
 *   GET    /api-keys             list — never includes the raw key or hash
 *   DELETE /api-keys/:id         revoke (RLS-scoped)
 *
 * Raw keys are sha256-hashed before insert. The first 11 chars (`cj_xxxxxxxx`)
 * are stored as `key_prefix` so the UI can show users which key is which
 * without exposing the secret.
 */

import { z } from "https://esm.sh/zod@3";
import { handleCors } from "../_shared/cors.ts";
import { AuthedUser, requireUser } from "../_shared/auth.ts";
import { getUserClient } from "../_shared/supabase.ts";
import { jsonError, jsonFromError, jsonOk } from "../_shared/responses.ts";
import { NotFoundError, ValidationError } from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";

const CreateSchema = z.object({
  name: z.string().min(1).max(100),
});

function generateKey(): string {
  // 24 url-safe random chars after the cj_ prefix → ~143 bits of entropy.
  const bytes = new Uint8Array(18);
  crypto.getRandomValues(bytes);
  const b64 = btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  return `cj_${b64}`;
}

async function sha256Hex(input: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

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
  const path = url.pathname.replace(/^.*\/api-keys/, "") || "/";
  const idMatch = path.match(/^\/([0-9a-f-]{36})$/i);

  try {
    if (path === "/" && req.method === "GET") return await listKeys(user);
    if (path === "/" && req.method === "POST") return await createKey(req, user);
    if (idMatch && req.method === "DELETE") return await revokeKey(user, idMatch[1]);
    return jsonError("method not allowed", 405);
  } catch (e) {
    logEvent({
      level: "error",
      fn: "api-keys",
      event: "unhandled",
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonFromError(e);
  }
});

async function listKeys(user: AuthedUser): Promise<Response> {
  const db = getUserClient(user.token);
  const { data, error } = await db
    .from("api_keys")
    .select("id, key_prefix, name, created_at, last_used_at")
    .order("created_at", { ascending: false });
  if (error) throw new Error(error.message);
  return jsonOk({
    keys: (data ?? []).map((row) => ({
      key_id: row.id,
      key_prefix: row.key_prefix,
      name: row.name,
      created_at: row.created_at,
      last_used_at: row.last_used_at,
    })),
    count: data?.length ?? 0,
  });
}

async function createKey(req: Request, user: AuthedUser): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    throw new ValidationError("invalid JSON body");
  }
  const parsed = CreateSchema.safeParse(body);
  if (!parsed.success) {
    throw new ValidationError(
      parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; "),
    );
  }

  const rawKey = generateKey();
  const keyHash = await sha256Hex(rawKey);
  const keyPrefix = rawKey.slice(0, 11);

  const db = getUserClient(user.token);
  const { data, error } = await db
    .from("api_keys")
    .insert({
      user_id: user.id,
      key_hash: keyHash,
      key_prefix: keyPrefix,
      name: parsed.data.name,
    })
    .select("id, key_prefix, name, created_at")
    .single();
  if (error) throw new Error(error.message);

  logEvent({
    level: "info",
    fn: "api-keys",
    event: "created",
    user_id: user.id,
    key_id: data.id,
  });

  return jsonOk(
    {
      key: rawKey,
      key_id: data.id,
      key_prefix: data.key_prefix,
      name: data.name,
      created_at: data.created_at,
    },
    201,
  );
}

async function revokeKey(user: AuthedUser, id: string): Promise<Response> {
  const db = getUserClient(user.token);
  const { error, count } = await db
    .from("api_keys")
    .delete({ count: "exact" })
    .eq("id", id);
  if (error) throw new Error(error.message);
  if (!count) throw new NotFoundError("api_key");

  logEvent({
    level: "info",
    fn: "api-keys",
    event: "revoked",
    user_id: user.id,
    key_id: id,
  });

  return new Response(null, {
    status: 204,
    headers: { "Access-Control-Allow-Origin": "*" },
  });
}
