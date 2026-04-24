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

function envAny(...names: string[]): string | undefined {
  for (const name of names) {
    const value = Deno.env.get(name);
    if (value) return value;
  }
  return undefined;
}

function envRequired(...names: string[]): string {
  const value = envAny(...names);
  if (!value) {
    throw new Error(`Missing env var. Tried: ${names.join(", ")}`);
  }
  return value;
}

export function getSupabaseUrl(): string {
  return envRequired("SERVICE_SUPABASE_URL", "SUPABASE_URL", "API_URL");
}

export function getServiceRoleKey(): string {
  return envRequired(
    "SERVICE_SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SERVICE_ROLE_KEY",
  );
}

export function getAnonKey(): string {
  return envRequired("SUPABASE_ANON_KEY", "PUBLISHABLE_KEY", "ANON_KEY");
}

export function getServiceClient(): SupabaseClient {
  return createClient(
    getSupabaseUrl(),
    getServiceRoleKey(),
    {
      auth: { persistSession: false, autoRefreshToken: false },
    },
  );
}

export function getUserClient(bearerToken: string): SupabaseClient {
  return createClient(getSupabaseUrl(), getAnonKey(), {
    auth: { persistSession: false, autoRefreshToken: false },
    global: {
      headers: { Authorization: `Bearer ${bearerToken}` },
    },
  });
}

export type { SupabaseClient };
