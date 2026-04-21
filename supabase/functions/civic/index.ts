/**
 * civic Edge Function — Civic Scout UI preview endpoints.
 *
 * Routes:
 *   POST /civic/discover
 *     body: { root_domain: string }
 *     -> 200 { candidates: [{ url, description, confidence }] (up to 5) }
 *
 *   POST /civic/test
 *     body: { tracked_urls: string[] (1..2), criteria?: string }
 *     -> 200 { valid: boolean, documents_found: number,
 *              sample_promises: [{ promise_text, context, source_url,
 *                                  source_date, due_date?, date_confidence,
 *                                  criteria_match }],
 *              error?: string }
 *
 * `discover` — Firecrawl /map on the root domain, then Gemini ranks up to
 * 5 candidate INDEX pages likely to list meeting protocols.
 *
 * `test` — for each tracked_url, Firecrawl scrape + Gemini-extract up to 10
 * promises. Mirrors the existing `civic-test` Edge Function at a different
 * URL path to match the frontend's `/civic/test` convention.
 *
 * Preview only — no persistence, no credit charge.
 */

import { z } from "https://esm.sh/zod@3";
import { handleCors } from "../_shared/cors.ts";
import { requireUser, AuthedUser } from "../_shared/auth.ts";
import { jsonError, jsonFromError, jsonOk } from "../_shared/responses.ts";
import { ValidationError } from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";
import { firecrawlMap, firecrawlScrape } from "../_shared/firecrawl.ts";
import { geminiExtract } from "../_shared/gemini.ts";

// ---------------------------------------------------------------------------
// Discover
// ---------------------------------------------------------------------------

const DiscoverSchema = z.object({
  root_domain: z.string().min(3).max(300),
});

const DISCOVER_SCHEMA: Record<string, unknown> = {
  type: "object",
  properties: {
    candidates: {
      type: "array",
      items: {
        type: "object",
        properties: {
          url: { type: "string" },
          description: { type: "string" },
          confidence: { type: "number" },
        },
        required: ["url", "description", "confidence"],
      },
    },
  },
  required: ["candidates"],
};

interface Candidate {
  url: string;
  description: string;
  confidence: number;
}

// ---------------------------------------------------------------------------
// Test
// ---------------------------------------------------------------------------

const TestSchema = z.object({
  tracked_urls: z.array(z.string().url()).min(1).max(2),
  criteria: z.string().max(4000).optional(),
});

const TEST_MARKDOWN_MAX = 15_000;
const PROMISES_PREVIEW_CAP = 10;

const TEST_EXTRACTION_SCHEMA: Record<string, unknown> = {
  type: "object",
  properties: {
    promises: {
      type: "array",
      items: {
        type: "object",
        properties: {
          promise_text: { type: "string" },
          context: { type: "string" },
          source_date: { type: "string", nullable: true },
          due_date: { type: "string", nullable: true },
          date_confidence: { type: "string" },
          criteria_match: { type: "boolean" },
        },
        required: ["promise_text"],
      },
    },
  },
  required: ["promises"],
};

interface ExtractedPromise {
  promise_text: string;
  context?: string;
  source_date?: string | null;
  due_date?: string | null;
  date_confidence?: string;
  criteria_match?: boolean;
}

// ---------------------------------------------------------------------------

Deno.serve(async (req: Request): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  let user: AuthedUser;
  try {
    user = await requireUser(req);
  } catch (e) {
    return jsonFromError(e);
  }

  const url = new URL(req.url);
  // Kong strips function slug; path starts with "/civic/..." for us.
  const path = url.pathname.replace(/^.*\/civic/, "") || "/";

  try {
    if (path === "/discover" && req.method === "POST") {
      return await discover(req, user);
    }
    if (path === "/test" && req.method === "POST") {
      return await test(req, user);
    }
    return jsonError("method not allowed", 405);
  } catch (e) {
    logEvent({
      level: "error",
      fn: "civic",
      event: "unhandled",
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonFromError(e);
  }
});

// ---------------------------------------------------------------------------

async function discover(req: Request, user: AuthedUser): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    throw new ValidationError("invalid JSON body");
  }
  const parsed = DiscoverSchema.safeParse(body);
  if (!parsed.success) {
    throw new ValidationError(
      parsed.error.issues.map((i) => i.message).join("; "),
    );
  }

  const raw = parsed.data.root_domain.trim();
  const target = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;

  let urls: string[] = [];
  try {
    urls = await firecrawlMap(target, { limit: 200, includeSubdomains: true });
  } catch (e) {
    logEvent({
      level: "warn",
      fn: "civic",
      event: "map_failed",
      user_id: user.id,
      target,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonOk({ candidates: [] });
  }

  if (urls.length === 0) {
    return jsonOk({ candidates: [] });
  }

  const list = urls.slice(0, 200).map((u, i) => `${i + 1}. ${u}`).join("\n");
  const prompt =
    "You are a civic data assistant. Below are URLs from a local government website. " +
    "Identify the best INDEX/LISTING pages that publish council meeting protocols, " +
    "assembly minutes, or official decisions over time. Prefer index pages that LINK TO " +
    "multiple PDFs or minutes — NOT individual documents.\n\n" +
    "Return up to 5 candidates. For each: url (exact), description (1 sentence), " +
    "confidence (0.0-1.0). Return JSON matching the provided schema.\n\n" +
    `URLs (${urls.length} total, showing first ${Math.min(urls.length, 200)}):\n${list}`;

  let extraction: { candidates: Candidate[] };
  try {
    extraction = await geminiExtract(prompt, DISCOVER_SCHEMA);
  } catch (e) {
    logEvent({
      level: "warn",
      fn: "civic",
      event: "rank_failed",
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonOk({ candidates: [] });
  }

  const candidates = (extraction.candidates ?? [])
    .filter((c) => c && typeof c.url === "string" && c.url.trim().length > 0)
    .slice(0, 5)
    .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0));

  logEvent({
    level: "info",
    fn: "civic",
    event: "discover",
    user_id: user.id,
    target,
    urls_mapped: urls.length,
    candidates: candidates.length,
  });

  return jsonOk({ candidates });
}

async function test(req: Request, user: AuthedUser): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    throw new ValidationError("invalid JSON body");
  }
  const parsed = TestSchema.safeParse(body);
  if (!parsed.success) {
    throw new ValidationError(
      parsed.error.issues.map((i) => i.message).join("; "),
    );
  }
  const { tracked_urls, criteria } = parsed.data;

  const allPromises: Array<{
    promise_text: string;
    context: string;
    source_url: string;
    source_date: string;
    due_date?: string;
    date_confidence: string;
    criteria_match: boolean;
  }> = [];
  let documentsFound = 0;

  for (const url of tracked_urls) {
    let scraped;
    try {
      scraped = await firecrawlScrape(url);
    } catch (e) {
      logEvent({
        level: "warn",
        fn: "civic",
        event: "test_scrape_failed",
        user_id: user.id,
        url,
        msg: e instanceof Error ? e.message : String(e),
      });
      continue;
    }

    const markdown = (scraped.markdown ?? "").slice(0, TEST_MARKDOWN_MAX);
    if (!markdown.trim()) continue;

    documentsFound += 1;

    const prompt =
      "Extract commitments, promises, votes, or decisions from this council document. " +
      (criteria ? `Focus on items that match: "${criteria}".\n` : "") +
      "For each: promise_text (the core commitment, one sentence), context (short " +
      "quoted snippet), source_date (ISO 8601 if mentioned; else null), due_date " +
      "(ISO 8601 if mentioned; else null), date_confidence ('high'|'medium'|'low'), " +
      "criteria_match (boolean — true if matches criteria or there is no criteria). " +
      "Return up to 10 items.\n\n---\n\n" +
      markdown;

    let extraction: { promises: ExtractedPromise[] };
    try {
      extraction = await geminiExtract(prompt, TEST_EXTRACTION_SCHEMA);
    } catch (e) {
      logEvent({
        level: "warn",
        fn: "civic",
        event: "test_extract_failed",
        user_id: user.id,
        url,
        msg: e instanceof Error ? e.message : String(e),
      });
      continue;
    }

    const promises = Array.isArray(extraction.promises) ? extraction.promises : [];
    for (const p of promises.slice(0, PROMISES_PREVIEW_CAP)) {
      if (!p || typeof p.promise_text !== "string" || !p.promise_text.trim()) continue;
      allPromises.push({
        promise_text: p.promise_text.trim(),
        context: p.context ?? "",
        source_url: url,
        source_date: p.source_date ?? "",
        due_date: p.due_date ?? undefined,
        date_confidence: p.date_confidence ?? "low",
        criteria_match: criteria ? !!p.criteria_match : true,
      });
    }
  }

  logEvent({
    level: "info",
    fn: "civic",
    event: "test",
    user_id: user.id,
    urls: tracked_urls.length,
    documents_found: documentsFound,
    promises: allPromises.length,
  });

  return jsonOk({
    valid: documentsFound > 0,
    documents_found: documentsFound,
    sample_promises: allPromises.slice(0, PROMISES_PREVIEW_CAP),
  });
}
