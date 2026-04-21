/**
 * Tests for scout-beat-execute Edge Function.
 *
 * Requires local supabase stack (see supabase status). Live-API tests are
 * gated on FIRECRAWL_API_KEY + GEMINI_API_KEY + INTERNAL_SERVICE_KEY.
 */

import {
  assertEquals,
  assertExists,
} from "https://deno.land/std@0.208.0/assert/mod.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { createTestUser, functionUrl, SUPABASE_URL } from "../_shared/_testing.ts";

const SERVICE_KEY = Deno.env.get("INTERNAL_SERVICE_KEY") ?? "";
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const FIRECRAWL_KEY = Deno.env.get("FIRECRAWL_API_KEY") ?? "";
const GEMINI_KEY = Deno.env.get("GEMINI_API_KEY") ?? "";
const liveKeys = Boolean(SERVICE_KEY && FIRECRAWL_KEY && GEMINI_KEY);

function svcHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Service-Key": SERVICE_KEY,
  };
}

function adminDb() {
  return createClient(SUPABASE_URL, SERVICE_ROLE_KEY, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

Deno.test("scout-beat-execute: unauthenticated returns 401", async () => {
  const res = await fetch(functionUrl("scout-beat-execute"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scout_id: "00000000-0000-0000-0000-000000000000",
    }),
  });
  await res.body?.cancel();
  assertEquals(res.status, 401);
});

Deno.test("scout-beat-execute: 400 when scout has no priority_sources", async () => {
  if (!SERVICE_KEY) {
    console.warn("skipping: INTERNAL_SERVICE_KEY not set");
    return;
  }
  const user = await createTestUser();
  const db = adminDb();
  try {
    const { data: scout, error } = await db
      .from("scouts")
      .insert({
        user_id: user.id,
        name: "Beat Test (no sources)",
        type: "pulse",
        criteria: "housing policy",
        priority_sources: [],
      })
      .select("id")
      .single();
    if (error) throw new Error(error.message);

    const res = await fetch(functionUrl("scout-beat-execute"), {
      method: "POST",
      headers: svcHeaders(),
      body: JSON.stringify({ scout_id: scout.id }),
    });
    assertEquals(res.status, 400);
    await res.body?.cancel();

    await db.from("scouts").delete().eq("id", scout.id);
  } finally {
    await user.cleanup();
  }
});

Deno.test("scout-beat-execute: 404 when scout missing", async () => {
  if (!SERVICE_KEY) {
    console.warn("skipping: INTERNAL_SERVICE_KEY not set");
    return;
  }
  const res = await fetch(functionUrl("scout-beat-execute"), {
    method: "POST",
    headers: svcHeaders(),
    body: JSON.stringify({
      scout_id: "00000000-0000-0000-0000-000000000000",
    }),
  });
  assertEquals(res.status, 404);
  await res.body?.cancel();
});

Deno.test({
  name: "scout-beat-execute: happy path scrapes + extracts (live firecrawl+gemini)",
  ignore: !liveKeys,
  fn: async () => {
    const user = await createTestUser();
    const db = adminDb();
    try {
      const { data: scout, error } = await db
        .from("scouts")
        .insert({
          user_id: user.id,
          name: "Beat Test (live)",
          type: "pulse",
          criteria: "any newsworthy development",
          priority_sources: [
            "https://example.com",
            "https://www.iana.org/help/example-domains",
          ],
        })
        .select("id")
        .single();
      if (error) throw new Error(error.message);

      const res = await fetch(functionUrl("scout-beat-execute"), {
        method: "POST",
        headers: svcHeaders(),
        body: JSON.stringify({ scout_id: scout.id }),
      });
      assertEquals(res.status, 200);
      const body = await res.json();
      assertEquals(body.status, "ok");
      assertExists(body.run_id);
      // sources_scraped could be <2 if one fails; just assert it's a number.
      assertEquals(typeof body.sources_scraped, "number");

      await db.from("scouts").delete().eq("id", scout.id);
    } finally {
      await user.cleanup();
    }
  },
});
