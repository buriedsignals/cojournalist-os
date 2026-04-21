/**
 * Supabase client factories.
 *
 * - getServiceClient(): service-role client for admin ops (RPC, scheduled tasks,
 *   merges). Bypasses RLS. Use sparingly.
 * - getUserClient(bearerToken): user-scoped client that carries the caller's
 *   JWT; RLS is enforced.
 */

import {
  createClient,
  SupabaseClient,
} from "https://esm.sh/@supabase/supabase-js@2";

function env(name: string): string {
  const v = Deno.env.get(name);
  if (!v) throw new Error(`Missing env var: ${name}`);
  return v;
}

export function getServiceClient(): SupabaseClient {
  return createClient(env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY"), {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

export function getUserClient(bearerToken: string): SupabaseClient {
  return createClient(env("SUPABASE_URL"), env("SUPABASE_ANON_KEY"), {
    auth: { persistSession: false, autoRefreshToken: false },
    global: {
      headers: { Authorization: `Bearer ${bearerToken}` },
    },
  });
}

export type { SupabaseClient };
