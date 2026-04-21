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
import { getUserClient } from "./supabase.ts";

export interface AuthedUser {
  id: string;
  email?: string;
  muckrockSubject?: string;
  token: string;
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
  };
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
