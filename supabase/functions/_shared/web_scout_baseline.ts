import type { SupabaseClient } from "./supabase.ts";
import { ValidationError } from "./errors.ts";
import { doubleProbe, firecrawlScrape } from "./firecrawl.ts";
import { logEvent } from "./log.ts";
import { deriveSourceDomain, sha256Hex } from "./unit_dedup.ts";

export interface WebBaselineScout {
  id: string;
  user_id: string;
  url?: string | null;
  provider?: string | null;
  baseline_established_at?: string | null;
  name?: string | null;
}

interface WebBaselineDeps {
  doubleProbe: typeof doubleProbe;
  firecrawlScrape: typeof firecrawlScrape;
  now: () => string;
}

const DEFAULT_DEPS: WebBaselineDeps = {
  doubleProbe,
  firecrawlScrape,
  now: () => new Date().toISOString(),
};

const RAW_CAPTURE_TTL_DAYS = 30;

function rawCaptureExpiresAt(nowIso: string): string {
  const start = Date.parse(nowIso);
  const base = Number.isNaN(start) ? Date.now() : start;
  return new Date(base + RAW_CAPTURE_TTL_DAYS * 24 * 60 * 60 * 1000)
    .toISOString();
}

async function stampBaseline(
  svc: SupabaseClient,
  scoutId: string,
  patch: Record<string, unknown>,
  deps: WebBaselineDeps,
): Promise<void> {
  const { error } = await svc
    .from("scouts")
    .update({
      baseline_established_at: deps.now(),
      ...patch,
    })
    .eq("id", scoutId);
  if (error) throw new Error(error.message);
}

export async function establishWebBaseline(
  svc: SupabaseClient,
  scout: WebBaselineScout,
  deps: WebBaselineDeps = DEFAULT_DEPS,
): Promise<"firecrawl" | "firecrawl_plain"> {
  if (!scout.url?.trim()) {
    throw new ValidationError("web scouts require a url before scheduling");
  }

  if (scout.provider === "firecrawl_plain") {
    const scrape = await deps.firecrawlScrape(scout.url);
    const markdown = scrape.markdown?.trim() ?? "";
    if (!markdown) {
      throw new ValidationError(
        "unable to establish page baseline from empty content",
      );
    }
    const { error } = await svc.from("raw_captures").insert({
      user_id: scout.user_id,
      scout_id: scout.id,
      source_url: scout.url,
      source_domain: deriveSourceDomain(scout.url),
      content_md: scrape.markdown,
      content_sha256: await sha256Hex(scrape.markdown),
      token_count: Math.ceil(scrape.markdown.length / 4),
      captured_at: deps.now(),
      expires_at: rawCaptureExpiresAt(deps.now()),
    });
    if (error) throw new Error(error.message);
    await stampBaseline(svc, scout.id, { provider: "firecrawl_plain" }, deps);
    return "firecrawl_plain";
  }

  const provider = await deps.doubleProbe(
    scout.url,
    `scout-${scout.id}`.slice(0, 128),
  );
  if (provider === "firecrawl") {
    await stampBaseline(svc, scout.id, { provider }, deps);
    return provider;
  }

  const scrape = await deps.firecrawlScrape(scout.url);
  const markdown = scrape.markdown?.trim() ?? "";
  if (!markdown) {
    throw new ValidationError(
      "unable to establish page baseline from empty content",
    );
  }
  const { error } = await svc.from("raw_captures").insert({
    user_id: scout.user_id,
    scout_id: scout.id,
    source_url: scout.url,
    source_domain: deriveSourceDomain(scout.url),
    content_md: scrape.markdown,
    content_sha256: await sha256Hex(scrape.markdown),
    token_count: Math.ceil(scrape.markdown.length / 4),
    captured_at: deps.now(),
    expires_at: rawCaptureExpiresAt(deps.now()),
  });
  if (error) throw new Error(error.message);
  await stampBaseline(svc, scout.id, { provider }, deps);
  return provider;
}

export async function ensureWebBaseline(
  svc: SupabaseClient,
  scout: WebBaselineScout,
  deps: WebBaselineDeps = DEFAULT_DEPS,
): Promise<boolean> {
  if (scout.baseline_established_at) return false;
  await establishWebBaseline(svc, scout, deps);
  return true;
}

export interface MissingBaselineRunResult {
  change_status: "same";
  articles_count: 0;
  merged_existing_count: 0;
  criteria_ran: false;
  baseline_initialized: true;
}

export async function maybeInitializeMissingWebBaselineRun(
  svc: SupabaseClient,
  scout: WebBaselineScout,
  runId: string,
  deps: WebBaselineDeps = DEFAULT_DEPS,
): Promise<MissingBaselineRunResult | null> {
  if (scout.baseline_established_at) return null;

  await establishWebBaseline(svc, scout, deps);

  const { error: runErr } = await svc
    .from("scout_runs")
    .update({
      status: "success",
      articles_count: 0,
      merged_existing_count: 0,
      completed_at: deps.now(),
      scraper_status: true,
      criteria_status: false,
    })
    .eq("id", runId);
  if (runErr) throw new Error(runErr.message);

  const { error: failureErr } = await svc.rpc("reset_scout_failures", {
    p_scout_id: scout.id,
  });
  if (failureErr) throw new Error(failureErr.message);

  logEvent({
    level: "info",
    fn: "web-scout-baseline",
    event: "initialized_on_run",
    scout_id: scout.id,
    run_id: runId,
    user_id: scout.user_id,
    msg: scout.name ?? "Page Scout",
  });

  return {
    change_status: "same",
    articles_count: 0,
    merged_existing_count: 0,
    criteria_ran: false,
    baseline_initialized: true,
  };
}
