/**
 * Test helpers for Deno.test() runs against local supabase (127.0.0.1:54321).
 *
 * Usage:
 *   import { createTestUser, functionUrl } from "../_shared/_testing.ts";
 *   const { id, token, cleanup } = await createTestUser();
 *   try { ... } finally { await cleanup(); }
 *
 * Requires env vars (see .env.test.local — supabase status prints them):
 *   SUPABASE_URL              e.g. http://127.0.0.1:54321
 *   SUPABASE_ANON_KEY         anon publishable key
 *   SUPABASE_SERVICE_ROLE_KEY service-role secret key
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

function env(name: string, fallback?: string): string {
  const v = Deno.env.get(name) ?? fallback;
  if (!v) throw new Error(`Missing env var ${name} for tests`);
  return v;
}

export const SUPABASE_URL = env("SUPABASE_URL", "http://127.0.0.1:54321");

export function functionUrl(name: string, path = ""): string {
  return `${SUPABASE_URL}/functions/v1/${name}${path}`;
}

export interface TestUser {
  id: string;
  email: string;
  token: string;
  cleanup: () => Promise<void>;
}

export async function createTestUser(): Promise<TestUser> {
  const service = createClient(
    SUPABASE_URL,
    env("SUPABASE_SERVICE_ROLE_KEY"),
    { auth: { persistSession: false, autoRefreshToken: false } },
  );
  const email = `test-${crypto.randomUUID()}@example.test`;
  const password = "test-pw-" + crypto.randomUUID();

  const { data: created, error: createErr } = await service.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
  });
  if (createErr || !created.user) {
    throw new Error(`failed to create test user: ${createErr?.message}`);
  }

  const anon = createClient(SUPABASE_URL, env("SUPABASE_ANON_KEY"), {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data: session, error: signErr } = await anon.auth.signInWithPassword({
    email,
    password,
  });
  if (signErr || !session.session) {
    throw new Error(`failed to sign in test user: ${signErr?.message}`);
  }

  const id = created.user.id;
  return {
    id,
    email,
    token: session.session.access_token,
    cleanup: async () => {
      await service.auth.admin.deleteUser(id);
    },
  };
}
