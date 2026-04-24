import {
  assertEquals,
} from "https://deno.land/std@0.208.0/assert/mod.ts";
import type { SupabaseClient } from "./supabase.ts";
import {
  ensureWebBaseline,
  maybeInitializeMissingWebBaselineRun,
} from "./web_scout_baseline.ts";

function createFakeSvc() {
  const inserts: Array<{ table: string; payload: unknown }> = [];
  const updates: Array<{
    table: string;
    payload: unknown;
    column: string;
    value: unknown;
  }> = [];
  const rpcs: Array<{ name: string; args: unknown }> = [];

  const svc = {
    from(table: string) {
      return {
        insert(payload: unknown) {
          inserts.push({ table, payload });
          return Promise.resolve({ error: null });
        },
        update(payload: unknown) {
          return {
            eq(column: string, value: unknown) {
              updates.push({ table, payload, column, value });
              return Promise.resolve({ error: null });
            },
          };
        },
      };
    },
    rpc(name: string, args: unknown) {
      rpcs.push({ name, args });
      return Promise.resolve({ error: null });
    },
  };

  return {
    svc,
    inserts,
    updates,
    rpcs,
  };
}

Deno.test("ensureWebBaseline stores only baseline state for firecrawl_plain scouts", async () => {
  const { svc, inserts, updates, rpcs } = createFakeSvc();

  const changed = await ensureWebBaseline(
    svc as unknown as SupabaseClient,
    {
      id: "scout-1",
      user_id: "user-1",
      url: "https://example.com",
      provider: "firecrawl_plain",
      baseline_established_at: null,
    },
    {
      doubleProbe: async () => "firecrawl_plain",
      firecrawlScrape: async () => ({
        markdown: "Initial baseline body",
        source_url: "https://example.com",
        fetched_at: "2026-04-24T00:00:00Z",
      }),
      now: () => "2026-04-24T00:00:00Z",
    },
  );

  assertEquals(changed, true);
  assertEquals(inserts.map((entry) => entry.table), ["raw_captures"]);
  assertEquals(updates.map((entry) => entry.table), ["scouts"]);
  assertEquals(rpcs.length, 0);
});

Deno.test("ensureWebBaseline no-ops when the scout already has a baseline", async () => {
  const { svc, inserts, updates } = createFakeSvc();

  const changed = await ensureWebBaseline(
    svc as unknown as SupabaseClient,
    {
      id: "scout-1",
      user_id: "user-1",
      url: "https://example.com",
      provider: "firecrawl",
      baseline_established_at: "2026-04-20T00:00:00Z",
    },
  );

  assertEquals(changed, false);
  assertEquals(inserts.length, 0);
  assertEquals(updates.length, 0);
});

Deno.test("maybeInitializeMissingWebBaselineRun short-circuits first run to baseline-only", async () => {
  const { svc, inserts, updates, rpcs } = createFakeSvc();

  const result = await maybeInitializeMissingWebBaselineRun(
    svc as unknown as SupabaseClient,
    {
      id: "scout-1",
      user_id: "user-1",
      url: "https://example.com",
      provider: "firecrawl",
      baseline_established_at: null,
      name: "Planning Board",
    },
    "run-1",
    {
      doubleProbe: async () => "firecrawl",
      firecrawlScrape: async () => ({
        markdown: "",
        source_url: "https://example.com",
        fetched_at: "2026-04-24T00:00:00Z",
      }),
      now: () => "2026-04-24T00:00:00Z",
    },
  );

  assertEquals(result?.articles_count, 0);
  assertEquals(result?.merged_existing_count, 0);
  assertEquals(result?.criteria_ran, false);
  assertEquals(result?.baseline_initialized, true);
  assertEquals(inserts.length, 0);
  assertEquals(updates.map((entry) => entry.table), ["scouts", "scout_runs"]);
  assertEquals(rpcs.map((entry) => entry.name), ["reset_scout_failures"]);
});
