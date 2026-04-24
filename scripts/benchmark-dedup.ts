/**
 * Canonical dedup live benchmark.
 *
 * Creates a temporary user plus temp web, beat, civic, and social scouts and
 * verifies that:
 * - web + beat converge on one canonical unit
 * - civic creates a linked canonical promise unit
 * - social produces canonical units and occurrences
 *
 * Usage:
 *   set -a; source .env; set +a
 *   deno run --allow-env --allow-net --allow-read=. scripts/benchmark-dedup.ts
 *
 * Required env:
 *   SUPABASE_URL
 *   SUPABASE_ANON_KEY
 *   SUPABASE_SERVICE_ROLE_KEY
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import {
  createTestUser,
  SUPABASE_URL,
} from "../supabase/functions/_shared/_testing.ts";
import {
  normalizeUnitStatement,
  sha256Hex,
} from "../supabase/functions/_shared/unit_dedup.ts";

const SUPABASE_ANON_KEY = mustEnv("SUPABASE_ANON_KEY");
const SUPABASE_SERVICE_ROLE_KEY = mustEnv("SUPABASE_SERVICE_ROLE_KEY");

const service = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const SHARED_CRITERIA =
  "Extract concrete factual statements about official decisions, commitments, votes, deadlines, and named public bodies.";
const CIVIC_CRITERIA =
  "Extract scheduled meetings, cancellations, official council actions, commitments, deadlines, and named public bodies.";
const SHARED_DOC_URL =
  "https://council.seattle.gov/2025/02/11/council-passes-updated-guidance-for-crowd-management-sets-the-stage-for-end-of-federal-consent-decree/";
const SOCIAL_CANDIDATES = [
  { platform: "instagram", handle: "whitehouse" },
  { platform: "x", handle: "WhiteHouse" },
] as const;
const CIVIC_CANDIDATES = [
  {
    rootDomain: "seattle.legistar.com",
    listingUrl: "https://seattle.legistar.com/Calendar.aspx",
  },
  {
    rootDomain: "kingcounty.legistar.com",
    listingUrl: "https://kingcounty.legistar.com/Calendar.aspx",
  },
] as const;
const FUTURE_CRON = "0 0 1 1 *";

interface ScoutRow {
  id: string;
  name: string;
  type: string;
  platform?: string | null;
  profile_handle?: string | null;
}

interface SmokeSummary {
  fixtures: {
    civicRoot?: string;
    civicListingUrl?: string;
    sharedDocUrl?: string;
    socialPlatform?: string;
    socialHandle?: string;
  };
  scouts: Record<string, ScoutRow>;
  runs: Record<string, Record<string, unknown>>;
  checks: Record<string, unknown>;
}

function mustEnv(name: string): string {
  const value = Deno.env.get(name);
  if (!value) throw new Error(`Missing env var ${name}`);
  return value;
}

function log(step: string, detail?: unknown) {
  if (detail === undefined) {
    console.log(`[dedup] ${step}`);
    return;
  }
  console.log(`[dedup] ${step}: ${JSON.stringify(detail)}`);
}

async function sleep(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function fnFetch(
  path: string,
  init: {
    method?: string;
    token?: string;
    serviceRole?: boolean;
    body?: unknown;
  } = {},
): Promise<unknown> {
  const headers = new Headers({
    "Content-Type": "application/json",
    "apikey": init.serviceRole ? SUPABASE_SERVICE_ROLE_KEY : SUPABASE_ANON_KEY,
  });
  if (init.serviceRole) {
    headers.set("Authorization", `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`);
  } else if (init.token) {
    headers.set("Authorization", `Bearer ${init.token}`);
  }

  const res = await fetch(`${SUPABASE_URL}/functions/v1${path}`, {
    method: init.method ?? "GET",
    headers,
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
  const text = await res.text();
  let parsed: unknown = null;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = text;
  }
  if (!res.ok) {
    throw new Error(
      `Function ${path} ${res.status}: ${
        typeof parsed === "string" ? parsed : JSON.stringify(parsed)
      }`,
    );
  }
  return parsed;
}

async function chooseCivicFixture(token: string): Promise<{
  rootDomain: string;
  listingUrl: string;
}> {
  for (const candidate of CIVIC_CANDIDATES) {
    log("civic.test", candidate);
    const discover = await fnFetch("/civic/discover", {
      method: "POST",
      token,
      body: { root_domain: candidate.rootDomain },
    }) as {
      candidates?: Array<{ url?: string }>;
    };
    const discovered = new Set(
      (discover.candidates ?? [])
        .map((row) => typeof row.url === "string" ? row.url : "")
        .filter(Boolean),
    );
    discovered.add(candidate.listingUrl);
    for (const url of discovered) {
      const preview = await fnFetch("/civic/test", {
        method: "POST",
        token,
        body: { tracked_urls: [url], criteria: CIVIC_CRITERIA },
      }) as {
        valid?: boolean;
        sample_promises?: Array<{ promise_text?: string }>;
      };
      if (preview.valid && (preview.sample_promises?.length ?? 0) > 0) {
        return {
          rootDomain: candidate.rootDomain,
          listingUrl: url,
        };
      }
    }
  }
  throw new Error("Could not find a civic fixture that passes preview");
}

async function chooseSocialFixture(token: string): Promise<{
  platform: string;
  handle: string;
}> {
  for (const candidate of SOCIAL_CANDIDATES) {
    log("social.test", candidate);
    const preview = await fnFetch("/social-test", {
      method: "POST",
      token,
      body: candidate,
    }) as {
      valid?: boolean;
      post_ids?: string[];
    };
    if (preview.valid && (preview.post_ids?.length ?? 0) > 0) {
      return { ...candidate };
    }
  }
  throw new Error("Could not find a social fixture with preview posts");
}

async function createWebScout(token: string, sharedDocUrl: string) {
  return await fnFetch("/scouts", {
    method: "POST",
    token,
    body: {
      name: `Smoke Web ${crypto.randomUUID().slice(0, 8)}`,
      type: "web",
      url: sharedDocUrl,
      criteria: SHARED_CRITERIA,
      provider: "firecrawl_plain",
      regularity: "daily",
      schedule_cron: FUTURE_CRON,
    },
  }) as ScoutRow;
}

async function createBeatScout(token: string, sharedDocUrl: string) {
  return await fnFetch("/scouts", {
    method: "POST",
    token,
    body: {
      name: `Smoke Beat ${crypto.randomUUID().slice(0, 8)}`,
      type: "beat",
      criteria: SHARED_CRITERIA,
      priority_sources: [sharedDocUrl],
      regularity: "daily",
      schedule_cron: FUTURE_CRON,
    },
  }) as ScoutRow;
}

async function createCivicScout(
  token: string,
  rootDomain: string,
  listingUrl: string,
) {
  const created = await fnFetch("/scouts/from-template", {
    method: "POST",
    token,
    body: {
      template_slug: "city-council-minutes",
      name: `Smoke Civic ${crypto.randomUUID().slice(0, 8)}`,
      fields: {
        root_domain: rootDomain,
        tracked_urls: [listingUrl],
        criteria: CIVIC_CRITERIA,
      },
    },
  }) as ScoutRow;
  await fnFetch(`/scouts/${created.id}/resume`, {
    method: "POST",
    token,
  });
  return created;
}

async function createSocialScout(
  userId: string,
  platform: string,
  handle: string,
): Promise<{ scout: ScoutRow; via: string }> {
  const inserted = await service.from("scouts")
    .insert({
      user_id: userId,
      name: `Smoke Social ${crypto.randomUUID().slice(0, 8)}`,
      type: "social",
      criteria: null,
      platform,
      profile_handle: handle.replace(/^@/, ""),
      regularity: "daily",
      schedule_cron: FUTURE_CRON,
      is_active: true,
      preferred_language: "en",
    })
    .select("id, name, type, platform, profile_handle")
    .single();
  if (inserted.error || !inserted.data) {
    throw new Error(`Failed to insert social scout: ${inserted.error?.message}`);
  }
  return { scout: inserted.data as ScoutRow, via: "service_insert" };
}

async function triggerRun(token: string, scoutId: string): Promise<string> {
  const result = await fnFetch(`/scouts/${scoutId}/run`, {
    method: "POST",
    token,
  }) as { run_id?: string };
  if (!result.run_id) throw new Error(`Missing run_id for scout ${scoutId}`);
  return result.run_id;
}

async function waitForRun(
  runId: string,
  timeoutMs = 8 * 60_000,
  intervalMs = 5_000,
): Promise<Record<string, unknown>> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const { data, error } = await service.from("scout_runs")
      .select("*")
      .eq("id", runId)
      .maybeSingle();
    if (error) throw new Error(error.message);
    if (data && data.status !== "running") return data as Record<string, unknown>;
    await sleep(intervalMs);
  }
  throw new Error(`Timed out waiting for scout_run ${runId}`);
}

async function drainCivicQueue(
  scoutId: string,
  timeoutMs = 8 * 60_000,
): Promise<Record<string, unknown>> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const { data, error } = await service.from("civic_extraction_queue")
      .select("id, status, source_url, updated_at, last_error")
      .eq("scout_id", scoutId);
    if (error) throw new Error(error.message);
    const rows = data ?? [];
    const pending = rows.filter((row) =>
      row.status === "pending" || row.status === "processing"
    );
    if (rows.length > 0 && pending.length === 0) {
      return { queued: rows.length, rows };
    }
    await sleep(10_000);
  }
  throw new Error(`Timed out draining civic queue for scout ${scoutId}`);
}

async function waitForSocialQueue(
  scoutId: string,
  timeoutMs = 10 * 60_000,
  intervalMs = 10_000,
): Promise<Record<string, unknown>> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const { data, error } = await service.from("apify_run_queue")
      .select("*")
      .eq("scout_id", scoutId)
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();
    if (error) throw new Error(error.message);
    if (data && ["succeeded", "failed", "timeout"].includes(String(data.status))) {
      return data as Record<string, unknown>;
    }
    await sleep(intervalMs);
  }
  throw new Error(`Timed out waiting for social queue row for scout ${scoutId}`);
}

async function verifyWebBeatDedup(
  token: string,
  webScoutId: string,
  beatScoutId: string,
  sharedDocUrl: string,
): Promise<Record<string, unknown>> {
  const webUnits = await fnFetch(`/units?scout_id=${webScoutId}`, {
    token,
  }) as { items?: Array<Record<string, unknown>> };
  const beatUnits = await fnFetch(`/units?scout_id=${beatScoutId}`, {
    token,
  }) as { items?: Array<Record<string, unknown>> };

  const items = [...(webUnits.items ?? []), ...(beatUnits.items ?? [])];
  const normalized = sharedDocUrl.replace(/\/+$/, "");
  const candidate = items.find((item) => {
    const sources = Array.isArray(item.sources) ? item.sources : [];
    const scouts = Array.isArray(item.linked_scouts) ? item.linked_scouts : [];
    const hasSource = sources.some((source) => {
      const url = typeof source?.url === "string"
        ? source.url.replace(/\/+$/, "")
        : "";
      return url === normalized;
    });
    const scoutIds = new Set(
      scouts.map((s) => typeof s?.id === "string" ? s.id : "").filter(Boolean),
    );
    return hasSource && scoutIds.has(webScoutId) && scoutIds.has(beatScoutId);
  });

  if (!candidate) {
    throw new Error(
      "Did not find a canonical unit linked to both web and beat scouts for the shared document URL",
    );
  }

  return {
    unit_id: candidate.id,
    occurrence_count: candidate.occurrence_count,
    linked_scouts: candidate.linked_scouts,
    sources: candidate.sources,
  };
}

async function verifyScoutUnits(
  token: string,
  scoutId: string,
): Promise<Record<string, unknown>> {
  const units = await fnFetch(`/units?scout_id=${scoutId}`, {
    token,
  }) as { items?: Array<Record<string, unknown>> };
  const items = units.items ?? [];
  if (items.length === 0) {
    throw new Error(`Scout ${scoutId} completed without API-visible units`);
  }
  return {
    unit_count: items.length,
    sample: items[0],
  };
}

async function verifyCivicOutput(
  userId: string,
  civicScoutId: string,
): Promise<Record<string, unknown>> {
  const { data: promises, error } = await service.from("promises")
    .select("id, unit_id, promise_text, source_url, meeting_date, due_date")
    .eq("user_id", userId)
    .eq("scout_id", civicScoutId);
  if (error) throw new Error(error.message);
  if (!promises || promises.length === 0) {
    throw new Error("Civic run finished without persisted promises");
  }
  const linked = promises.filter((p) => p.unit_id);
  if (linked.length === 0) {
    throw new Error("Civic promises were created without linked canonical units");
  }
  return {
    promise_count: promises.length,
    linked_unit_count: linked.length,
    sample: promises[0],
  };
}

async function verifySocialOutput(
  userId: string,
  socialScoutId: string,
): Promise<Record<string, unknown>> {
  const { data: occurrences, error } = await service.from("unit_occurrences")
    .select("unit_id, scout_id, source_url, extracted_at")
    .eq("user_id", userId)
    .eq("scout_id", socialScoutId)
    .limit(5);
  if (error) throw new Error(error.message);
  if (!occurrences || occurrences.length === 0) {
    throw new Error("Social run completed without unit occurrences");
  }
  return {
    occurrence_count: occurrences.length,
    sample: occurrences[0],
  };
}

function makeEmbedding(seed = 1): number[] {
  const values = Array.from({ length: 1536 }, () => 0);
  values[0] = seed;
  return values;
}

async function upsertSyntheticUnit(input: {
  userId: string;
  statement: string;
  unitType: "fact" | "event" | "entity_update" | "promise";
  embedding: number[];
  sourceUrl: string;
  sourceDomain: string;
  sourceTitle: string;
  sourceType: "scout" | "manual_ingest" | "agent_ingest" | "civic_promise";
  scoutId: string | null;
  scoutType: string | null;
  scoutRunId?: string | null;
}): Promise<Record<string, unknown>> {
  const statementHash = await sha256Hex(
    normalizeUnitStatement(input.statement),
  );
  const { data, error } = await service.rpc("upsert_canonical_unit", {
    p_user_id: input.userId,
    p_statement: input.statement,
    p_type: input.unitType,
    p_entities: [],
    p_embedding: input.embedding,
    p_embedding_model: "gemini-embedding-2-preview",
    p_source_url: input.sourceUrl,
    p_normalized_source_url: input.sourceUrl,
    p_source_domain: input.sourceDomain,
    p_source_title: input.sourceTitle,
    p_context_excerpt: null,
    p_occurred_at: null,
    p_extracted_at: new Date().toISOString(),
    p_source_type: input.sourceType,
    p_content_sha256: null,
    p_statement_hash: statementHash,
    p_scout_id: input.scoutId,
    p_scout_type: input.scoutType,
    p_scout_run_id: input.scoutRunId ?? null,
    p_project_id: null,
    p_raw_capture_id: null,
    p_metadata: { benchmark: "dedup" },
  });
  if (error) throw new Error(error.message);
  const row = Array.isArray(data) ? data[0] : data;
  if (!row || typeof row !== "object") {
    throw new Error("Missing synthetic upsert result");
  }
  return row as Record<string, unknown>;
}

async function verifySocialSemanticBoundary(
  userId: string,
  beatScoutId: string,
  socialScoutId: string,
): Promise<Record<string, unknown>> {
  const embedding = makeEmbedding(1);
  const nonSocial = await upsertSyntheticUnit({
    userId,
    statement:
      "The city council approved the annual budget ordinance after a 6-3 vote.",
    unitType: "fact",
    embedding,
    sourceUrl: "https://example.test/non-social-budget",
    sourceDomain: "example.test",
    sourceTitle: "Non-social budget ordinance",
    sourceType: "scout",
    scoutId: beatScoutId,
    scoutType: "beat",
  });
  const social = await upsertSyntheticUnit({
    userId,
    statement:
      "City Hall just posted that the annual budget passed and thanked supporters.",
    unitType: "entity_update",
    embedding,
    sourceUrl: "https://x.com/example/status/social-budget-probe",
    sourceDomain: "x.com",
    sourceTitle: "social budget probe",
    sourceType: "scout",
    scoutId: socialScoutId,
    scoutType: "social",
  });

  const nonSocialUnitId = String(nonSocial.unit_id ?? "");
  const socialUnitId = String(social.unit_id ?? "");
  if (!nonSocialUnitId || !socialUnitId) {
    throw new Error("Synthetic social boundary probe returned missing unit ids");
  }
  if (nonSocialUnitId === socialUnitId) {
    throw new Error(
      "Social semantic boundary failed: synthetic social unit merged into non-social canonical unit",
    );
  }
  if (String(social.match_scope ?? "") !== "new") {
    throw new Error(
      `Social semantic boundary failed: expected social synthetic match_scope=new, got ${String(social.match_scope ?? "")}`,
    );
  }

  return {
    non_social_unit_id: nonSocialUnitId,
    non_social_match_scope: nonSocial.match_scope,
    social_unit_id: socialUnitId,
    social_match_scope: social.match_scope,
  };
}

async function main() {
  const summary: SmokeSummary = {
    fixtures: {},
    scouts: {},
    runs: {},
    checks: {},
  };

  const testUser = await createTestUser();
  log("temp.user.created", { id: testUser.id, email: testUser.email });

  try {
    const creditSeed = await service.from("credit_accounts").insert({
      user_id: testUser.id,
      tier: "free",
      monthly_cap: 100,
      balance: 100,
      update_on: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
        .slice(0, 10),
      entitlement_source: "dedup-benchmark",
    });
    if (creditSeed.error) throw new Error(creditSeed.error.message);
    log("temp.user.credits_seeded", { user_id: testUser.id, balance: 100 });

    const civic = await chooseCivicFixture(testUser.token);
    summary.fixtures.civicRoot = civic.rootDomain;
    summary.fixtures.civicListingUrl = civic.listingUrl;
    summary.fixtures.sharedDocUrl = SHARED_DOC_URL;
    log("fixture.civic", civic);

    const social = await chooseSocialFixture(testUser.token);
    summary.fixtures.socialPlatform = social.platform;
    summary.fixtures.socialHandle = social.handle;
    log("fixture.social", social);

    const webScout = await createWebScout(testUser.token, SHARED_DOC_URL);
    const beatScout = await createBeatScout(testUser.token, SHARED_DOC_URL);
    const civicScout = await createCivicScout(
      testUser.token,
      civic.rootDomain,
      civic.listingUrl,
    );
    const socialCreate = await createSocialScout(
      testUser.id,
      social.platform,
      social.handle,
    );

    summary.scouts.web = webScout;
    summary.scouts.beat = beatScout;
    summary.scouts.civic = civicScout;
    summary.scouts.social = socialCreate.scout;
    summary.checks.social_create_via = socialCreate.via;

    const webRunId = await triggerRun(testUser.token, webScout.id);
    const webRun = await waitForRun(webRunId, 2 * 60_000, 5_000).catch((error) => ({
      status: "timeout",
      error: error instanceof Error ? error.message : String(error),
      run_id: webRunId,
    }));
    summary.runs.web = webRun;
    log("run.web", webRun);

    const beatRunId = await triggerRun(testUser.token, beatScout.id);
    const beatRun = await waitForRun(beatRunId);
    summary.runs.beat = beatRun;
    log("run.beat", beatRun);

    const beatCheck = await verifyScoutUnits(testUser.token, beatScout.id);
    summary.checks.beat_output = beatCheck;
    log("check.beat_output", beatCheck);

    if (webRun.status === "success") {
      const webCheck = await verifyScoutUnits(testUser.token, webScout.id);
      summary.checks.web_output = webCheck;
      log("check.web_output", webCheck);

      const dedupCheck = await verifyWebBeatDedup(
        testUser.token,
        webScout.id,
        beatScout.id,
        SHARED_DOC_URL,
      );
      summary.checks.web_beat_dedup = dedupCheck;
      log("check.web_beat_dedup", dedupCheck);
    } else {
      throw new Error(`Web smoke blocked before dedup check: ${JSON.stringify(webRun)}`);
    }

    const civicRunId = await triggerRun(testUser.token, civicScout.id);
    const civicRun = await waitForRun(civicRunId);
    summary.runs.civic = civicRun;
    log("run.civic", civicRun);

    const civicQueue = await drainCivicQueue(civicScout.id);
    summary.checks.civic_queue = civicQueue;
    log("check.civic_queue", civicQueue);

    const civicCheck = await verifyCivicOutput(testUser.id, civicScout.id);
    summary.checks.civic_output = civicCheck;
    log("check.civic_output", civicCheck);

    const socialRunId = await triggerRun(testUser.token, socialCreate.scout.id);
    const socialQueue = await waitForSocialQueue(socialCreate.scout.id);
    const socialRun = await waitForRun(socialRunId, 2 * 60_000, 5_000).catch(
      async () => {
        const { data, error } = await service.from("scout_runs")
          .select("*")
          .eq("id", socialRunId)
          .maybeSingle();
        if (error) throw new Error(error.message);
        return (data ?? {}) as Record<string, unknown>;
      },
    );
    summary.runs.social = socialRun;
    summary.checks.social_queue = socialQueue;
    log("run.social", socialRun);
    log("check.social_queue", socialQueue);

    const socialCheck = await verifySocialOutput(testUser.id, socialCreate.scout.id);
    summary.checks.social_output = socialCheck;
    log("check.social_output", socialCheck);

    const socialBoundaryCheck = await verifySocialSemanticBoundary(
      testUser.id,
      beatScout.id,
      socialCreate.scout.id,
    );
    summary.checks.social_semantic_boundary = socialBoundaryCheck;
    log("check.social_semantic_boundary", socialBoundaryCheck);

    console.log(JSON.stringify({ ok: true, summary }, null, 2));
  } finally {
    try {
      await testUser.cleanup();
      log("temp.user.cleaned", { id: testUser.id });
    } catch (error) {
      log("temp.user.cleanup_failed", {
        id: testUser.id,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }
}

if (import.meta.main) {
  await main();
}
