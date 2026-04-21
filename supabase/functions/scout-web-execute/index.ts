/**
 * scout-web-execute Edge Function — synchronous Page Scout pipeline.
 *
 * Called internally by execute-scout. Must complete within ~50s. Flow:
 *   1. Load scout.
 *   2. Create (or reuse) a scout_runs row with status='running'.
 *   3. Firecrawl change-tracking scrape using per-scout tag.
 *   4. If change_status === "same": mark run success, reset failures, return.
 *   5. Else: store raw_capture, optionally extract units via Gemini (when
 *      scout.criteria is set), dedup each unit via check_unit_dedup RPC,
 *      insert non-dupes into information_units, mark run success.
 *   6. On any throw: mark run error, increment_scout_failures, surface error.
 *
 * Auth: service-role Bearer only (internal call).
 */

import { z } from "https://esm.sh/zod@3";
import { handleCors } from "../_shared/cors.ts";
import { getServiceClient, SupabaseClient } from "../_shared/supabase.ts";
import { jsonError, jsonFromError, jsonOk } from "../_shared/responses.ts";
import {
  ApiError,
  AuthError,
  NotFoundError,
  ValidationError,
} from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";
import {
  type ChangeTrackingResult,
  firecrawlChangeTrackingScrape,
  firecrawlScrape,
} from "../_shared/firecrawl.ts";
import { geminiEmbed } from "../_shared/gemini.ts";
import { extractAtomicUnits } from "../_shared/atomic_extract.ts";
import { isWithinRunDuplicate } from "../_shared/dedup.ts";
import {
  CREDIT_COSTS,
  decrementOrThrow,
  InsufficientCreditsError,
  insufficientCreditsResponse,
  refundCredits,
} from "../_shared/credits.ts";
import { sendPageScoutAlert } from "../_shared/notifications.ts";
import { incrementAndMaybeNotify } from "../_shared/scout_failures.ts";

const InputSchema = z.object({
  scout_id: z.string().uuid(),
  run_id: z.string().uuid().optional(),
  user_id: z.string().uuid().optional(),
});

const PROMPT_CONTENT_MAX = 12_000;

Deno.serve(async (req: Request): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  if (req.method !== "POST") {
    return jsonError("method not allowed", 405);
  }

  // Service-role-only auth (exact match, not substring).
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const authHeader = req.headers.get("authorization") ??
    req.headers.get("Authorization") ?? "";
  if (!serviceKey || authHeader !== `Bearer ${serviceKey}`) {
    return jsonFromError(new AuthError("service-role key required"));
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return jsonFromError(new ValidationError("invalid JSON body"));
  }
  const parsed = InputSchema.safeParse(body);
  if (!parsed.success) {
    return jsonFromError(
      new ValidationError(parsed.error.issues.map((i) => i.message).join("; ")),
    );
  }

  const svc = getServiceClient();
  const { scout_id } = parsed.data;
  let { run_id } = parsed.data;

  // 1. Load scout.
  const { data: scout, error: scoutErr } = await svc
    .from("scouts")
    .select(
      "id, user_id, type, name, url, criteria, project_id, is_active, provider, preferred_language",
    )
    .eq("id", scout_id)
    .maybeSingle();
  if (scoutErr) return jsonFromError(new Error(scoutErr.message));
  if (!scout) return jsonFromError(new NotFoundError("scout"));
  if (!scout.url) {
    return jsonFromError(new ValidationError("scout has no url"));
  }

  // 2. Decrement credits before any billable work.
  try {
    await decrementOrThrow(svc, {
      userId: scout.user_id,
      cost: CREDIT_COSTS.website_extraction,
      scoutId: scout.id,
      scoutType: "web",
      operation: "website_extraction",
    });
  } catch (e) {
    if (e instanceof InsufficientCreditsError) {
      return insufficientCreditsResponse(e.required, e.current);
    }
    return jsonFromError(e);
  }

  // 3. Ensure scout_runs row exists.
  if (!run_id) {
    const { data: runRow, error: runErr } = await svc
      .from("scout_runs")
      .insert({
        scout_id: scout.id,
        user_id: scout.user_id,
        status: "running",
        started_at: new Date().toISOString(),
      })
      .select("id")
      .single();
    if (runErr) return jsonFromError(new Error(runErr.message));
    run_id = runRow.id as string;
  }

  try {
    const result = await runPipeline(svc, scout, run_id);

    await svc
      .from("scout_runs")
      .update({
        status: "success",
        articles_count: result.articles_count,
        completed_at: new Date().toISOString(),
        scraper_status: true,
        criteria_status: result.criteria_ran,
      })
      .eq("id", run_id);

    // Reset failure counter + (if changed) stamp baseline_established_at.
    await svc.rpc("reset_scout_failures", { p_scout_id: scout.id });
    if (result.change_status === "same" || result.change_status === "changed") {
      await svc
        .from("scouts")
        .update({ baseline_established_at: new Date().toISOString() })
        .eq("id", scout.id);
    }

    logEvent({
      level: "info",
      fn: "scout-web-execute",
      event: "success",
      scout_id: scout.id,
      run_id,
      change: result.change_status,
      articles_count: result.articles_count,
    });

    // Notify user when criteria ran and produced new, non-duplicate units.
    // Never throws — a mail failure must not flip the run into error.
    if (result.criteria_ran && result.articles_count > 0 && result.summary) {
      try {
        await sendPageScoutAlert(svc, {
          userId: scout.user_id,
          scoutId: scout.id,
          runId: run_id,
          scoutName: scout.name ?? "Page Scout",
          url: scout.url,
          criteria: scout.criteria ?? "",
          summary: result.summary,
          matchedUrl: result.matchedUrl ?? null,
          matchedTitle: result.matchedTitle ?? null,
        });
      } catch (e) {
        logEvent({
          level: "warn",
          fn: "scout-web-execute",
          event: "notify_failed",
          scout_id: scout.id,
          run_id,
          msg: e instanceof Error ? e.message : String(e),
        });
      }
    }

    return jsonOk({
      status: "ok",
      change: result.change_status,
      articles_count: result.articles_count,
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    try {
      await svc
        .from("scout_runs")
        .update({
          status: "error",
          error_message: msg.slice(0, 2000),
          completed_at: new Date().toISOString(),
        })
        .eq("id", run_id);
      await incrementAndMaybeNotify(svc, {
        scoutId: scout.id as string,
        userId: scout.user_id as string,
        scoutName: (scout.name as string | null) ?? "Page Scout",
        scoutType: "web",
        language: scout.preferred_language as string | null,
      });
      // Refund the pre-run charge on failure — users shouldn't pay for
      // scheduled scrapes that never produced billable output.
      await refundCredits(svc, {
        userId: scout.user_id as string,
        cost: CREDIT_COSTS.website_extraction,
        scoutId: scout.id as string,
        scoutType: "web",
        operation: "website_extraction",
      });
    } catch (cleanupErr) {
      logEvent({
        level: "error",
        fn: "scout-web-execute",
        event: "cleanup_failed",
        scout_id: scout.id,
        run_id,
        msg: cleanupErr instanceof Error ? cleanupErr.message : String(cleanupErr),
      });
    }
    logEvent({
      level: "error",
      fn: "scout-web-execute",
      event: "failed",
      scout_id: scout.id,
      run_id,
      msg,
    });
    return jsonFromError(e);
  }
});

// ---------------------------------------------------------------------------

interface ScoutRow {
  id: string;
  user_id: string;
  type: string;
  name: string | null;
  url: string;
  criteria: string | null;
  project_id: string | null;
  is_active: boolean;
  provider: "firecrawl" | "firecrawl_plain" | null;
  preferred_language: string | null;
}

interface PipelineResult {
  change_status: "new" | "same" | "changed" | "removed";
  articles_count: number;
  criteria_ran: boolean;
  summary?: string;
  matchedUrl?: string | null;
  matchedTitle?: string | null;
}

async function runPipeline(
  svc: SupabaseClient,
  scout: ScoutRow,
  runId: string,
): Promise<PipelineResult> {
  // 3. Scrape via the provider recorded for this scout (mirrors prod
  //    scout_service.execute branching):
  //      - "firecrawl_plain": plain scrape + SHA-256 hash compare to prior
  //        raw_captures row. Used when double-probe flagged the URL as
  //        ghost-baseline.
  //      - "firecrawl" or null: changeTracking scrape with per-scout tag.
  //        On Firecrawl failure, fall back to plain + hash so a transient
  //        error doesn't look like "new content" every run.
  const tag = `scout-${scout.id}`.slice(0, 128);

  let markdown: string;
  let changeStatus: ChangeTrackingResult["change_status"];
  let scrapeTitle: string | null = null;

  if (scout.provider === "firecrawl_plain") {
    const plain = await firecrawlScrape(scout.url);
    markdown = plain.markdown ?? "";
    scrapeTitle = plain.title ?? null;
    changeStatus = await hashChangeStatus(svc, scout.id, markdown);
  } else {
    try {
      const ct = await firecrawlChangeTrackingScrape(scout.url, tag);
      markdown = ct.markdown ?? "";
      scrapeTitle = ct.title ?? null;
      changeStatus = ct.change_status;
    } catch (e) {
      logEvent({
        level: "warn",
        fn: "scout-web-execute",
        event: "change_tracking_fallback",
        scout_id: scout.id,
        msg: e instanceof Error ? e.message : String(e),
      });
      const plain = await firecrawlScrape(scout.url);
      markdown = plain.markdown ?? "";
      scrapeTitle = plain.title ?? null;
      changeStatus = await hashChangeStatus(svc, scout.id, markdown);
    }
  }

  if (changeStatus === "same") {
    return { change_status: "same", articles_count: 0, criteria_ran: false };
  }

  if (!markdown.trim()) {
    throw new ApiError("firecrawl returned empty markdown", 502);
  }
  // Keep the legacy local name for the rest of the pipeline below.
  const scrape = {
    markdown,
    change_status: changeStatus,
    title: scrapeTitle,
  };

  // 4. Insert raw_capture for the scraped content.
  const contentHash = await sha256Hex(markdown);
  const sourceDomain = safeDomain(scout.url);

  const { data: capture, error: capErr } = await svc
    .from("raw_captures")
    .insert({
      user_id: scout.user_id,
      scout_id: scout.id,
      scout_run_id: runId,
      source_url: scout.url,
      source_domain: sourceDomain,
      content_md: markdown,
      content_sha256: contentHash,
      token_count: Math.ceil(markdown.length / 4),
      captured_at: new Date().toISOString(),
    })
    .select("id")
    .single();
  if (capErr) throw new Error(capErr.message);
  const rawCaptureId = capture.id as string;

  // 5. If criteria set, extract units and insert non-dupes.
  if (!scout.criteria || !scout.criteria.trim()) {
    return { change_status: scrape.change_status, articles_count: 0, criteria_ran: false };
  }

  // Shared per-article extraction — prod shape. Forces preferred_language,
  // passes the criteria separately so Gemini treats it as filter data, and
  // applies 5W1H completeness rules. Max 8 units for web scouts (matches
  // atomic_unit_service.MAX_UNITS_WEB_SCOUT).
  const extracted = await extractAtomicUnits({
    title: scrape.title ?? null,
    content: markdown,
    sourceUrl: scout.url,
    publishedDate: null,
    language: (scout as { preferred_language?: string | null }).preferred_language ?? "en",
    criteria: scout.criteria,
    maxUnits: 8,
    contentLimit: PROMPT_CONTENT_MAX,
  });

  let inserted = 0;
  const insertedStatements: string[] = [];
  const runEmbeddings: number[][] = [];
  for (const u of extracted) {
    if (!u || typeof u.statement !== "string" || !u.statement.trim()) continue;
    if (!["fact", "event", "entity_update"].includes(u.type)) continue;

    const embedding = await geminiEmbed(u.statement, "RETRIEVAL_DOCUMENT");

    // Within-run paraphrase guard: drop units that are near-duplicates of an
    // already-kept unit in *this* extraction batch. check_unit_dedup only
    // covers cross-run history so paraphrase pairs would otherwise co-land.
    if (isWithinRunDuplicate(embedding, runEmbeddings)) continue;

    const { data: isDupe, error: dupErr } = await svc.rpc("check_unit_dedup", {
      p_embedding: embedding,
      p_scout_id: scout.id,
    });
    if (dupErr) throw new Error(dupErr.message);
    if (isDupe) continue;
    runEmbeddings.push(embedding);

    const { error: insErr } = await svc.from("information_units").insert({
      user_id: scout.user_id,
      scout_id: scout.id,
      scout_type: "web",
      statement: u.statement,
      type: u.type,
      context_excerpt: u.context_excerpt ?? null,
      occurred_at: normalizeDate(u.occurred_at),
      source_url: scout.url,
      source_title: scrape.title ?? null,
      source_domain: sourceDomain,
      extracted_at: new Date().toISOString(),
      source_type: "scout",
      raw_capture_id: rawCaptureId,
      embedding,
      embedding_model: "gemini-embedding-2-preview",
      project_id: scout.project_id ?? null,
      used_in_article: false,
    });
    if (insErr) throw new Error(insErr.message);
    inserted += 1;
    if (insertedStatements.length < 3) insertedStatements.push(u.statement);
  }

  // Build a short summary for the notification email from the first few
  // statements (bulleted if 2+). Matches legacy summary shape.
  const summary = insertedStatements.length === 1
    ? insertedStatements[0]
    : insertedStatements.map((s) => `- ${s}`).join("\n");

  return {
    change_status: scrape.change_status,
    articles_count: inserted,
    criteria_ran: true,
    summary: summary || undefined,
    matchedUrl: inserted > 0 ? scout.url : null,
    matchedTitle: inserted > 0 ? (scrape.title ?? null) : null,
  };
}

// ---------------------------------------------------------------------------

async function sha256Hex(input: string): Promise<string> {
  const buf = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Compute SHA-256 of the newly scraped markdown and compare against the
 * most recent raw_captures row for this scout. Port of prod
 * ExecutionDeduplicationService.get_latest_content_hash + hash-based
 * change detection. Used only on the firecrawl_plain path.
 */
async function hashChangeStatus(
  svc: SupabaseClient,
  scoutId: string,
  markdown: string,
): Promise<"new" | "same" | "changed"> {
  if (!markdown.trim()) return "new";
  const hash = await sha256Hex(markdown);
  const { data, error } = await svc
    .from("raw_captures")
    .select("content_sha256")
    .eq("scout_id", scoutId)
    .order("captured_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error || !data) return "new";
  if (data.content_sha256 === hash) return "same";
  return "changed";
}

function safeDomain(raw: string): string | null {
  try {
    return new URL(raw).hostname;
  } catch {
    return null;
  }
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
