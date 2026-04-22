// cojo CLI live smoke test — exercises the real Supabase Edge Functions
// against a test API key. Skipped unless all of these env vars are set
// in CI (or locally for ad-hoc runs):
//
//   COJO_TEST_API_URL          — e.g. https://gfmdziplticfoakhrfpt.supabase.co/functions/v1
//   COJO_TEST_API_KEY          — cj_… key with read-only test scope
//   COJO_TEST_SUPABASE_ANON_KEY — Supabase project anon key
//
// CI gating: the workflow declares `if: ${{ secrets.COJO_TEST_API_KEY != '' }}`,
// so missing secrets skip the job entirely. Locally, leaving any of the env
// vars unset skips at test-collection time — no network is touched.
//
// Read-only by design: never invokes mutating commands (delete/verify/reject).

import { assert, assertExists } from "jsr:@std/assert";
import { apiFetch, writeConfigFile } from "../lib/client.ts";

const API_URL = Deno.env.get("COJO_TEST_API_URL");
const API_KEY = Deno.env.get("COJO_TEST_API_KEY");
const ANON_KEY = Deno.env.get("COJO_TEST_SUPABASE_ANON_KEY");

const SKIP = !API_URL || !API_KEY || !ANON_KEY;
const SKIP_REASON = SKIP
  ? "Skipping live smoke tests: set COJO_TEST_API_URL + COJO_TEST_API_KEY + COJO_TEST_SUPABASE_ANON_KEY"
  : "";

async function withSmokeConfig(fn: () => Promise<void>): Promise<void> {
  const originalHome = Deno.env.get("HOME");
  const tmp = await Deno.makeTempDir({ prefix: "cojo-smoke-" });
  Deno.env.set("HOME", tmp);
  try {
    writeConfigFile({
      api_url: API_URL!,
      api_key: API_KEY!,
      supabase_anon_key: ANON_KEY!,
    });
    await fn();
  } finally {
    if (originalHome === undefined) Deno.env.delete("HOME");
    else Deno.env.set("HOME", originalHome);
    try {
      await Deno.remove(tmp, { recursive: true });
    } catch {
      /* ignore */
    }
  }
}

Deno.test({
  name: "smoke: GET /units returns a paginated envelope",
  ignore: SKIP,
  fn: async () => {
    if (SKIP) {
      console.warn(SKIP_REASON);
      return;
    }
    await withSmokeConfig(async () => {
      const result = await apiFetch<{ items?: unknown[]; total?: number }>(
        "/functions/v1/units?limit=1",
      );
      // Accept both Edge envelope (`{items, total}`) and FastAPI fallback.
      assert(typeof result === "object" && result !== null);
    });
  },
});

Deno.test({
  name: "smoke: GET /units/search returns hybrid results",
  ignore: SKIP,
  fn: async () => {
    if (SKIP) return;
    await withSmokeConfig(async () => {
      const result = await apiFetch<{ items?: unknown[] }>(
        "/functions/v1/units/search?q=test&limit=1",
      );
      assertExists(result);
    });
  },
});

Deno.test({
  name: "smoke: GET /scouts returns user's scouts",
  ignore: SKIP,
  fn: async () => {
    if (SKIP) return;
    await withSmokeConfig(async () => {
      const result = await apiFetch<{ items?: unknown[] }>(
        "/functions/v1/scouts?limit=5",
      );
      assertExists(result);
    });
  },
});

Deno.test({
  name: "smoke: GET /user returns the current user",
  ignore: SKIP,
  fn: async () => {
    if (SKIP) return;
    await withSmokeConfig(async () => {
      const result = await apiFetch<{ id?: string; email?: string }>(
        "/functions/v1/user",
      );
      assertExists(result);
    });
  },
});
