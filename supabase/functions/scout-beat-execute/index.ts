/**
 * scout-beat-execute Edge Function — Beat Scout (type='pulse') runner.
 *
 * Scrapes up to 20 priority sources in parallel (concurrency 5), aggregates
 * markdown, persists raw_captures per source, and extracts atomic information
 * units via Gemini structured output. Used for Beat Scouts (topic/criteria
 * monitoring of a fixed list of reliable sources) in the v2 pipeline.
 *
 * Route:
 *   POST /scout-beat-execute
 *     body: { scout_id: uuid, run_id?: uuid }
 *     -> 200 { status: "ok", sources_scraped: N, articles_count: M, run_id }
 *
 * Auth: service-role only (X-Service-Key header). Invoked by pg_cron and the
 * scouts router's run dispatcher — not from user browsers.
 *
 * Errors:
 *   - 404 if scout missing
 *   - 400 if scout has no priority_sources or missing criteria
 *   - 500/502 on all firecrawl/gemini failures; failed runs mark scout_runs
 *     status='error' and call increment_scout_failures (auto-pause at 3).
 */

import { z } from "https://esm.sh/zod@3";
import { handleCors } from "../_shared/cors.ts";
import { requireServiceKey } from "../_shared/auth.ts";
import { getServiceClient, SupabaseClient } from "../_shared/supabase.ts";
import { jsonError, jsonFromError, jsonOk } from "../_shared/responses.ts";
import { NotFoundError, ValidationError } from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";
import { firecrawlScrape, ScrapeResult } from "../_shared/firecrawl.ts";
import { isWithinRunDuplicate } from "../_shared/dedup.ts";
import { geminiEmbed } from "../_shared/gemini.ts";
import {
  aiFilterResults,
  applyDateFilter,
  capUndatedResults,
  clusterFilter,
  countryTld,
  dedupeByEmbedding,
  generatePulseSummary,
  generateQueries,
  getRecencyConfig,
  isLikelyTourismContent,
  PulseCategory,
  PulseHit,
  PulseScope,
  PulseSourceMode,
  runSearches,
} from "../_shared/pulse_pipeline.ts";
import {
  CREDIT_COSTS,
  decrementOrThrow,
  InsufficientCreditsError,
  insufficientCreditsResponse,
  refundCredits,
} from "../_shared/credits.ts";
import { Article, sendBeatAlert } from "../_shared/notifications.ts";
import { incrementAndMaybeNotify } from "../_shared/scout_failures.ts";
import {
  extractAtomicUnits,
  publishedDateFromScrape,
} from "../_shared/atomic_extract.ts";

const InputSchema = z.object({
  scout_id: z.string().uuid(),
  run_id: z.string().uuid().optional(),
});

const MAX_SOURCES = 20;
const CONCURRENCY = 5;

Deno.serve(async (req: Request): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  if (req.method !== "POST") {
    return jsonError("method not allowed", 405);
  }

  try {
    requireServiceKey(req);
  } catch (e) {
    return jsonFromError(e);
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return jsonError("invalid JSON body", 400);
  }
  const parsed = InputSchema.safeParse(body);
  if (!parsed.success) {
    return jsonError(
      parsed.error.issues.map((i) => i.message).join("; "),
      400,
    );
  }
  const { scout_id, run_id } = parsed.data;

  try {
    return await execute(scout_id, run_id);
  } catch (e) {
    logEvent({
      level: "error",
      fn: "scout-beat-execute",
      event: "unhandled",
      scout_id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonFromError(e);
  }
});

// ---------------------------------------------------------------------------

async function execute(scoutId: string, runIdIn?: string): Promise<Response> {
  const db = getServiceClient();

  // 1. Load scout
  const { data: scout, error: scoutErr } = await db
    .from("scouts")
    .select("*")
    .eq("id", scoutId)
    .maybeSingle();
  if (scoutErr) throw new Error(scoutErr.message);
  if (!scout) throw new NotFoundError("scout");

  if (!scout.criteria || !String(scout.criteria).trim()) {
    throw new ValidationError("beat scout requires criteria");
  }

  // Explicit priority_sources shortcut: user pasted URLs directly. Scrape those
  // unchanged — skips the 8-stage discovery pipeline, keeps behavior predictable.
  const manualSourcesRaw: string[] = Array.isArray(scout.priority_sources)
    ? scout.priority_sources
    : [];
  const manualSources = manualSourcesRaw
    .filter((s): s is string => typeof s === "string" && s.trim().length > 0)
    .slice(0, MAX_SOURCES);

  // 2. Decrement credits before running the discovery pipeline.
  try {
    await decrementOrThrow(db, {
      userId: scout.user_id,
      cost: CREDIT_COSTS.pulse,
      scoutId: scout.id,
      scoutType: "pulse",
      operation: "pulse",
    });
  } catch (e) {
    if (e instanceof InsufficientCreditsError) {
      return insufficientCreditsResponse(e.required, e.current);
    }
    throw e;
  }

  // 3. Resolve / create scout_runs row
  const runId = await resolveRun(db, scout, runIdIn);

  try {
    // --- Stage 0: prepare pipeline inputs ---
    const locationObj = extractLocationObj(scout.location);
    const cityName = locationObj.city ?? null;
    const countryName = locationObj.country ?? null;
    const countryCode = locationObj.countryCode ?? null;
    const topic = (scout.topic as string | null)?.trim() ?? null;
    const criteria = (scout.criteria as string).trim();
    const sourceMode: PulseSourceMode =
      (scout.source_mode as string | null) === "niche" ? "niche" : "reliable";
    const hasLocation = Boolean(cityName || countryName);
    const hasCriteria = Boolean(criteria || topic);
    const scope: PulseScope = hasCriteria && hasLocation
      ? "combined"
      : hasCriteria
      ? "topic"
      : "location";
    const preferredLanguage = (scout.preferred_language as string | null) ?? "en";

    // --- Resolve final source list ---
    // Two branches, chosen by the user's setup:
    //  (A) priority_sources non-empty → direct scrape (legacy opt-in path)
    //  (B) empty → full 8-stage pulse pipeline (query gen → search → dedup → AI filter)
    let finalUrls: string[];
    let newsPulseHits: PulseHit[] = [];
    let govPulseHits: PulseHit[] = [];

    if (manualSources.length > 0) {
      finalUrls = manualSources;
    } else {
      // Full pipeline branch — news + optional parallel government fan-out.
      newsPulseHits = await runPulsePipeline({
        scope,
        sourceMode,
        category: "news",
        city: cityName,
        country: countryName,
        countryCode,
        criteria: criteria || topic,
        preferredLanguage,
      });
      if (hasLocation && hasCriteria) {
        govPulseHits = await runPulsePipeline({
          scope: "combined",
          sourceMode,
          category: "government",
          city: cityName,
          country: countryName,
          countryCode,
          criteria: criteria || topic,
          preferredLanguage,
        });
      }
      finalUrls = [
        ...newsPulseHits.map((h) => h.url),
        ...govPulseHits.map((h) => h.url),
      ].filter((u, i, arr) => u && arr.indexOf(u) === i).slice(0, MAX_SOURCES);
    }

    if (finalUrls.length === 0) {
      // Empty pipeline outcome (no discovered URLs) — record a no-op success
      // and refund the pre-charge (matches legacy source behaviour).
      await db
        .from("scout_runs")
        .update({
          status: "success",
          scraper_status: true,
          criteria_status: false,
          articles_count: 0,
          completed_at: new Date().toISOString(),
        })
        .eq("id", runId);
      await refundCredits(db, {
        userId: scout.user_id as string,
        cost: CREDIT_COSTS.pulse,
        scoutId,
        scoutType: "pulse",
        operation: "pulse",
      });
      return jsonOk({
        status: "ok",
        run_id: runId,
        sources_scraped: 0,
        sources_failed: 0,
        articles_count: 0,
        note: "pulse pipeline produced zero sources for this query",
      });
    }

    // --- Stage 2 continuation: parallel full-markdown scrapes (concurrency 5) ---
    const scraped = await mapLimit(finalUrls, CONCURRENCY, (url) =>
      firecrawlScrape(url),
    );

    const succeeded: ScrapeResult[] = [];
    const failures: Array<{ url: string; error: string }> = [];
    scraped.forEach((r, i) => {
      if (r.status === "fulfilled") {
        const v = r.value;
        if (v.markdown && v.markdown.trim().length > 0) {
          succeeded.push(v);
        } else {
          failures.push({ url: finalUrls[i], error: "empty markdown" });
        }
      } else {
        failures.push({
          url: finalUrls[i],
          error: r.reason instanceof Error
            ? r.reason.message
            : String(r.reason),
        });
      }
    });

    if (succeeded.length === 0) {
      throw new Error(
        `all ${finalUrls.length} sources failed: ${
          failures
            .map((f) => `${f.url} (${f.error})`)
            .slice(0, 3)
            .join("; ")
        }`,
      );
    }

    // Keep a lookup so per-URL gov vs news partitioning survives the scrape step.
    const govUrlSet = new Set(govPulseHits.map((h) => h.url));

    // 5. Persist raw_captures for each successful scrape.
    const rawCaptureIds: string[] = [];
    for (const s of succeeded) {
      const md = s.markdown ?? "";
      const hash = await sha256Hex(md);
      const { data: cap, error: capErr } = await db
        .from("raw_captures")
        .insert({
          user_id: scout.user_id,
          scout_id: scout.id,
          scout_run_id: runId,
          source_url: s.source_url,
          source_domain: safeDomain(s.source_url),
          content_md: md.slice(0, 200_000),
          content_sha256: hash,
          token_count: Math.ceil(md.length / 4),
          captured_at: s.fetched_at,
        })
        .select("id")
        .single();
      if (capErr) throw new Error(capErr.message);
      rawCaptureIds.push(cap.id as string);
    }

    // 6 + 7. Per-article extraction with forced target language.
    //
    // We extract 1-3 units per successfully scraped source (prod shape) and
    // attribute each unit to its own source URL. Fixes three audit regressions:
    //   - language: system prompt forces preferred_language, article-by-article
    //   - source_diversity: each unit carries its real source, not primary's
    //   - undated_ratio: Firecrawl metadata publishedTime feeds occurred_at
    //     as a fallback when the LLM can't extract one
    let insertedCount = 0;
    const insertedStatements: string[] = [];
    const newsStatements: string[] = [];
    const govStatements: string[] = [];
    const runEmbeddings: number[][] = [];

    for (let i = 0; i < succeeded.length; i++) {
      const src = succeeded[i];
      const captureId = rawCaptureIds[i];
      const scrapePublishedDate = publishedDateFromScrape(src);

      let extracted;
      try {
        extracted = await extractAtomicUnits({
          title: src.title ?? null,
          content: src.markdown ?? "",
          sourceUrl: src.source_url,
          publishedDate: scrapePublishedDate,
          language: preferredLanguage,
          criteria: scout.criteria as string | null,
          maxUnits: 3,
          contentLimit: 3000,
        });
      } catch (e) {
        logEvent({
          level: "warn",
          fn: "scout-beat-execute",
          event: "extract_failed",
          scout_id: scoutId,
          source_url: src.source_url,
          msg: e instanceof Error ? e.message : String(e),
        });
        continue;
      }

      for (const u of extracted) {
        let embedding: number[];
        try {
          embedding = await geminiEmbed(u.statement, "RETRIEVAL_DOCUMENT");
        } catch (e) {
          logEvent({
            level: "warn",
            fn: "scout-beat-execute",
            event: "embed_failed",
            scout_id: scoutId,
            msg: e instanceof Error ? e.message : String(e),
          });
          continue;
        }

        // Within-run paraphrase guard first — avoids an RPC round-trip for
        // pairs that would both insert otherwise.
        if (isWithinRunDuplicate(embedding, runEmbeddings)) continue;

        const { data: dupRes, error: dupErr } = await db.rpc("check_unit_dedup", {
          p_embedding: embedding,
          p_scout_id: scoutId,
        });
        if (dupErr) {
          logEvent({
            level: "warn",
            fn: "scout-beat-execute",
            event: "dedup_check_failed",
            scout_id: scoutId,
            msg: dupErr.message,
          });
        }
        if (dupRes === true) continue;
        runEmbeddings.push(embedding);

        // occurred_at priority: LLM-extracted → Firecrawl metadata → null.
        const occurredAt = normalizeDate(u.occurred_at) ?? scrapePublishedDate;

        const { error: unitErr } = await db.from("information_units").insert({
          user_id: scout.user_id,
          scout_id: scout.id,
          scout_type: "pulse",
          statement: u.statement,
          type: u.type,
          context_excerpt: u.context_excerpt ?? null,
          occurred_at: occurredAt,
          source_type: "scout",
          source_url: src.source_url,
          source_domain: safeDomain(src.source_url),
          source_title: src.title ?? null,
          extracted_at: new Date().toISOString(),
          raw_capture_id: captureId,
          embedding,
          embedding_model: "gemini-embedding-2-preview",
          used_in_article: false,
        });
        if (unitErr) {
          logEvent({
            level: "warn",
            fn: "scout-beat-execute",
            event: "unit_insert_failed",
            scout_id: scoutId,
            msg: unitErr.message,
          });
          continue;
        }
        insertedCount += 1;
        if (insertedStatements.length < 10) {
          insertedStatements.push(u.statement);
        }
        if (govUrlSet.has(src.source_url)) {
          if (govStatements.length < 5) govStatements.push(u.statement);
        } else {
          if (newsStatements.length < 5) newsStatements.push(u.statement);
        }
      }
    }

    // 9. Mark run success + reset failures.
    await db
      .from("scout_runs")
      .update({
        status: "success",
        scraper_status: true,
        criteria_status: true,
        articles_count: insertedCount,
        completed_at: new Date().toISOString(),
      })
      .eq("id", runId);

    const { error: resetErr } = await db.rpc("reset_scout_failures", {
      p_scout_id: scoutId,
    });
    if (resetErr) {
      logEvent({
        level: "warn",
        fn: "scout-beat-execute",
        event: "reset_failures_failed",
        scout_id: scoutId,
        msg: resetErr.message,
      });
    }

    logEvent({
      level: "info",
      fn: "scout-beat-execute",
      event: "success",
      scout_id: scoutId,
      run_id: runId,
      sources_scraped: succeeded.length,
      articles_count: insertedCount,
    });

    // Notify user when new, non-duplicate units landed. Build separate article
    // cards for news vs government (legacy behaviour), with LLM-composed
    // summaries per section rather than raw statement bullets.
    if (insertedCount > 0 && insertedStatements.length > 0) {
      try {
        const newsScrapes = succeeded.filter((s) => !govUrlSet.has(s.source_url));
        const govScrapes = succeeded.filter((s) => govUrlSet.has(s.source_url));
        const newsArticles: Article[] = newsScrapes.slice(0, 5).map((s) => ({
          title: s.title ?? s.source_url,
          url: s.source_url,
          summary: "",
          source: safeDomain(s.source_url) ?? "",
        }));
        const govArticles: Article[] = govScrapes.slice(0, 5).map((s) => ({
          title: s.title ?? s.source_url,
          url: s.source_url,
          summary: "",
          source: safeDomain(s.source_url) ?? "",
        }));

        // Prefer LLM-composed summaries when pipeline produced hits; fall back
        // to bulleted statement list for the manual-priority-sources path.
        const emailLang = (preferredLanguage ?? "en").toLowerCase();
        const summary = newsPulseHits.length > 0
          ? await generatePulseSummary(newsPulseHits, {
            city: cityName,
            language: emailLang,
            category: "news",
          })
          : newsStatements.slice(0, 5).map((s) => `- ${s}`).join("\n");
        const govSummary = govPulseHits.length > 0
          ? await generatePulseSummary(govPulseHits, {
            city: cityName,
            language: emailLang,
            category: "government",
          })
          : govStatements.slice(0, 5).map((s) => `- ${s}`).join("\n");

        const locationLabel = extractLocationLabel(scout.location);
        await sendBeatAlert(db, {
          userId: scout.user_id as string,
          scoutId: scout.id as string,
          runId,
          scoutName: (scout.name as string | null) ?? "Beat Scout",
          location: locationLabel,
          topic,
          summary: summary || insertedStatements.slice(0, 5).map((s) => `- ${s}`).join("\n"),
          articles: newsArticles.length > 0 ? newsArticles : newsScrapes
            .concat(govScrapes)
            .slice(0, 5)
            .map((s) => ({
              title: s.title ?? s.source_url,
              url: s.source_url,
              summary: "",
              source: safeDomain(s.source_url) ?? "",
            })),
          govArticles: govArticles.length > 0 ? govArticles : undefined,
          govSummary: govSummary || undefined,
        });
      } catch (e) {
        logEvent({
          level: "warn",
          fn: "scout-beat-execute",
          event: "notify_failed",
          scout_id: scoutId,
          run_id: runId,
          msg: e instanceof Error ? e.message : String(e),
        });
      }
    }

    return jsonOk({
      status: "ok",
      run_id: runId,
      sources_scraped: succeeded.length,
      sources_failed: failures.length,
      articles_count: insertedCount,
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    await db
      .from("scout_runs")
      .update({
        status: "error",
        error_message: msg.slice(0, 2000),
        completed_at: new Date().toISOString(),
      })
      .eq("id", runId);

    await incrementAndMaybeNotify(db, {
      scoutId,
      userId: scout.user_id as string,
      scoutName: (scout.name as string | null) ?? "Beat Scout",
      scoutType: "pulse",
      language: scout.preferred_language as string | null,
    });
    // Refund the 7-credit pre-charge — the run produced no billable output.
    await refundCredits(db, {
      userId: scout.user_id as string,
      cost: CREDIT_COSTS.pulse,
      scoutId,
      scoutType: "pulse",
      operation: "pulse",
    });
    throw e;
  }
}

// ---------------------------------------------------------------------------

async function resolveRun(
  db: SupabaseClient,
  scout: Record<string, unknown>,
  runIdIn: string | undefined,
): Promise<string> {
  if (runIdIn) {
    const { data, error } = await db
      .from("scout_runs")
      .select("id")
      .eq("id", runIdIn)
      .maybeSingle();
    if (error) throw new Error(error.message);
    if (data?.id) {
      await db
        .from("scout_runs")
        .update({ status: "running", started_at: new Date().toISOString() })
        .eq("id", runIdIn);
      return runIdIn;
    }
    // fall through: invalid run_id, create a new row
  }
  const { data, error } = await db
    .from("scout_runs")
    .insert({
      scout_id: scout.id as string,
      user_id: scout.user_id as string,
      status: "running",
    })
    .select("id")
    .single();
  if (error) throw new Error(error.message);
  return data.id as string;
}

/**
 * Run `fn` against `items` with at most `limit` concurrent in-flight tasks.
 * Returns PromiseSettledResult<R>[] in the same order as `items`.
 */
async function mapLimit<T, R>(
  items: T[],
  limit: number,
  fn: (t: T) => Promise<R>,
): Promise<PromiseSettledResult<R>[]> {
  const results = new Array<PromiseSettledResult<R>>(items.length);
  let cursor = 0;
  const workers: Promise<void>[] = [];
  const nWorkers = Math.min(limit, items.length);
  for (let w = 0; w < nWorkers; w++) {
    workers.push(
      (async () => {
        while (true) {
          const idx = cursor++;
          if (idx >= items.length) return;
          try {
            const value = await fn(items[idx]);
            results[idx] = { status: "fulfilled", value };
          } catch (reason) {
            results[idx] = { status: "rejected", reason };
          }
        }
      })(),
    );
  }
  await Promise.all(workers);
  return results;
}

async function sha256Hex(input: string): Promise<string> {
  const buf = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function safeDomain(raw: string | null | undefined): string | null {
  if (!raw) return null;
  try {
    return new URL(raw).hostname;
  } catch {
    return null;
  }
}

function extractLocationLabel(v: unknown): string | null {
  if (!v) return null;
  if (typeof v === "string") return v || null;
  if (typeof v === "object") {
    const rec = v as Record<string, unknown>;
    const candidates = [rec.displayName, rec.display_name, rec.label, rec.city];
    for (const c of candidates) {
      if (typeof c === "string" && c.trim()) return c;
    }
  }
  return null;
}

function normalizeDate(v: string | null | undefined): string | null {
  if (!v) return null;
  const trimmed = v.trim();
  if (!trimmed) return null;
  const match = trimmed.match(/^(\d{4}-\d{2}-\d{2})/);
  if (match) return match[1];
  const d = new Date(trimmed);
  if (isNaN(d.getTime())) return null;
  return d.toISOString().slice(0, 10);
}

/**
 * Parse scout.location into city/country/countryCode. Handles both the string
 * form (legacy "City, Country") and the structured jsonb form written by the
 * MapTiler geocoder in the Location Scout modal.
 */
interface LocationShape {
  city: string | null;
  country: string | null;
  countryCode: string | null;
}
function extractLocationObj(v: unknown): LocationShape {
  if (!v) return { city: null, country: null, countryCode: null };
  if (typeof v === "string") {
    const parts = v.split(",").map((s) => s.trim());
    return { city: parts[0] || null, country: parts[1] || null, countryCode: null };
  }
  if (typeof v === "object") {
    const rec = v as Record<string, unknown>;
    const city = pickString(rec.city, rec.displayName, rec.display_name, rec.label);
    const country = pickString(rec.country, rec.country_name);
    const countryCode = pickString(rec.country_code, rec.countryCode);
    return { city, country, countryCode: countryCode?.toUpperCase() ?? null };
  }
  return { city: null, country: null, countryCode: null };
}
function pickString(...candidates: unknown[]): string | null {
  for (const c of candidates) {
    if (typeof c === "string" && c.trim()) return c.trim();
  }
  return null;
}

/**
 * Thread the 8-stage pulse pipeline for a single category (news OR government).
 * Mirrors legacy pulse_orchestrator.search_news stages 1-8. Returns final
 * AI-filtered hits ready for atomic extraction.
 */
interface RunPipelineOpts {
  scope: PulseScope;
  sourceMode: PulseSourceMode;
  category: PulseCategory;
  city: string | null;
  country: string | null;
  countryCode: string | null;
  criteria: string | null;
  preferredLanguage: string;
}
async function runPulsePipeline(opts: RunPipelineOpts): Promise<PulseHit[]> {
  const plan = await generateQueries({
    city: opts.city,
    country: opts.country,
    countryCode: opts.countryCode,
    criteria: opts.criteria,
    category: opts.category,
  });
  if (plan.queries.length === 0 && plan.discovery_queries.length === 0) {
    return [];
  }
  const rawHits = await runSearches({
    plan,
    lang: opts.preferredLanguage,
    country: opts.countryCode ?? undefined,
  });
  if (rawHits.length === 0) return [];

  // Stages 3+4: date filter + undated cap.
  const recency = getRecencyConfig(opts.scope, opts.category, opts.sourceMode);
  const { dated, undated } = applyDateFilter(rawHits, recency);
  const capped = capUndatedResults(undated, recency);
  let hits = [...dated, ...capped];
  if (hits.length === 0) return [];

  // Stage 5: tourism pre-filter (niche + location + news only).
  if (
    opts.category === "news" &&
    opts.sourceMode === "niche" &&
    (opts.city || opts.country)
  ) {
    hits = hits.filter((h) => !isLikelyTourismContent(h));
  }
  if (hits.length === 0) return [];

  // Stage 6: embedding dedup + rarity + local-language bonus.
  // Scope-aware threshold: narrower searches need higher thresholds.
  const threshold = opts.scope === "combined"
    ? 0.85
    : opts.scope === "location"
    ? 0.82
    : 0.80;
  const tld = countryTld(opts.countryCode ?? null);
  hits = await dedupeByEmbedding(hits, {
    threshold,
    primaryLanguage: plan.primary_language,
    localTlds: tld ? [tld] : undefined,
  });

  // Stage 7: cluster filter (niche mode only).
  if (opts.category === "news" && opts.sourceMode === "niche") {
    hits = clusterFilter(hits);
  }
  if (hits.length === 0) return [];

  // Stage 8: AI relevance filter.
  const maxResults = opts.sourceMode === "reliable" ? 8 : 6;
  hits = await aiFilterResults(hits, {
    cityName: opts.city,
    countryName: opts.country,
    localLanguage: plan.primary_language,
    category: opts.category,
    sourceMode: opts.sourceMode,
    criteria: opts.criteria,
    maxResults,
  });
  return hits;
}
