/**
 * Auth extraction for Edge Functions.
 *
 * - requireUser(req): extracts JWT, verifies via Supabase Auth, returns the
 *   authenticated user. Throws AuthError on missing/invalid token.
 * - requireServiceKey(req): validates the X-Service-Key header against the
 *   INTERNAL_SERVICE_KEY env var for function-to-function and cron-triggered
 *   calls.
 */

import { AuthError } from "./errors.ts";
import { getServiceClient, getUserClient, SupabaseClient } from "./supabase.ts";

export interface AuthedUser {
  id: string;
  email?: string;
  muckrockSubject?: string;
  /** Raw bearer token. Empty string for API-key auth (no JWT to forward). */
  token: string;
  /** Auth path used: "session" (Supabase JWT) or "api_key" (cj_… token). */
  authMethod?: "session" | "api_key";
}

export async function requireUser(req: Request): Promise<AuthedUser> {
  const header = req.headers.get("authorization") ?? req.headers.get("Authorization");
  if (!header || !header.toLowerCase().startsWith("bearer ")) {
    throw new AuthError("missing bearer token");
  }
  const token = header.slice(7).trim();
  if (!token) throw new AuthError("empty bearer token");

  const client = getUserClient(token);
  const { data, error } = await client.auth.getUser();
  if (error || !data.user) {
    throw new AuthError(error?.message ?? "invalid token");
  }

  const meta = (data.user.user_metadata ?? {}) as Record<string, unknown>;
  return {
    id: data.user.id,
    email: data.user.email ?? undefined,
    muckrockSubject: typeof meta.muckrock_subject === "string" ? meta.muckrock_subject : undefined,
    token,
    authMethod: "session",
  };
}

/** Like requireUser, but also accepts `Authorization: Bearer cj_<key>`
 *  agent API keys validated via the validate_api_key RPC. Use this on
 *  read-only public routes that agents (CLI, MCP, third-party) need. */
export async function requireUserOrApiKey(req: Request): Promise<AuthedUser> {
  const header = req.headers.get("authorization") ?? req.headers.get("Authorization");
  if (!header || !header.toLowerCase().startsWith("bearer ")) {
    throw new AuthError("missing bearer token");
  }
  const token = header.slice(7).trim();
  if (!token) throw new AuthError("empty bearer token");

  if (token.startsWith("cj_")) {
    const svc = getServiceClient();
    const { data: userId, error } = await svc.rpc("validate_api_key", { p_key: token });
    if (error) throw new AuthError(`api key validation failed: ${error.message}`);
    if (!userId || typeof userId !== "string") {
      throw new AuthError("invalid api key");
    }
    return { id: userId, token: "", authMethod: "api_key" };
  }

  // Fall through to session-JWT path.
  return requireUser(req);
}

/** Returns a Supabase client scoped to the caller. For session auth this is
 *  the user-JWT client (RLS-enforced). For API-key auth there's no JWT, so
 *  we fall back to the service client — callers MUST add an explicit
 *  `.eq("user_id", user.id)` (or equivalent) on every query. The
 *  `needsExplicitScope` flag flips true on that path so the caller knows. */
export function getCallerClient(
  user: AuthedUser,
): { db: SupabaseClient; needsExplicitScope: boolean } {
  if (user.authMethod === "api_key") {
    return { db: getServiceClient(), needsExplicitScope: true };
  }
  return { db: getUserClient(user.token), needsExplicitScope: false };
}

export function requireServiceKey(req: Request): void {
  const expectedInternal = Deno.env.get("INTERNAL_SERVICE_KEY");
  const expectedServiceRole = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

  // Accept either X-Service-Key = INTERNAL_SERVICE_KEY (the cron/dispatcher
  // path) or Authorization: Bearer SUPABASE_SERVICE_ROLE_KEY (tooling and
  // benchmarks that don't have the internal key).
  const providedInternal = req.headers.get("x-service-key") ??
    req.headers.get("X-Service-Key");
  if (expectedInternal && providedInternal === expectedInternal) return;

  const authHeader = req.headers.get("authorization") ??
    req.headers.get("Authorization") ?? "";
  if (
    expectedServiceRole && authHeader === `Bearer ${expectedServiceRole}`
  ) {
    return;
  }

  if (!expectedInternal && !expectedServiceRole) {
    throw new AuthError(
      "server misconfigured: neither INTERNAL_SERVICE_KEY nor SUPABASE_SERVICE_ROLE_KEY set",
    );
  }
  throw new AuthError("invalid service key");
}
