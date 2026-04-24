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
 * 5 candidate INDEX pages likely to list meeting protocols. Discovery
 * explicitly prefers listing pages like `/urversammlung/protokoll` over
 * direct `/pdf/...` document URLs.
 *
 * `test` — for each tracked_url, scrape the listing page raw HTML, extract
 * downstream meeting-document links, classify them with the old civic
 * keyword/LLM flow, then preview promises from the resolved documents.
 * Mirrors the existing `civic-test` Edge Function at a different URL path
 * to match the frontend's `/civic/test` convention.
 *
 * Preview only — no persistence, no credit charge.
 */

import { z } from "https://esm.sh/zod@3";
import { handleCors } from "../_shared/cors.ts";
import { requireUser, AuthedUser } from "../_shared/auth.ts";
import { jsonError, jsonFromError, jsonOk } from "../_shared/responses.ts";
import { ValidationError } from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";
import { firecrawlMap } from "../_shared/firecrawl.ts";
import {
  filterCivicDiscoveryCandidates,
} from "../_shared/civic_links.ts";
import { previewCivicTrackedUrls } from "../_shared/civic_preview.ts";
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

const PROMISES_PREVIEW_CAP = 10;

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
    "You are a civic data assistant. Below is a list of URLs from a local " +
    "government website. Identify the best candidates — pages that serve as " +
    "an INDEX or LISTING where council meeting protocols, assembly minutes, " +
    "or official decision documents are published over time.\n\n" +
    "IMPORTANT: Prefer index/listing pages over individual documents. " +
    "A page like '/urversammlung/protokoll' that LISTS many protocol PDFs " +
    "is far more valuable than a single PDF file. Do NOT return individual " +
    "PDF or document URLs — return the pages that LINK TO them.\n\n" +
    "Prioritize:\n" +
    "- Pages that list/link to meeting protocol PDFs or minutes\n" +
    "- Assembly proceedings index pages\n" +
    "- Council news or decisions pages with recurring updates\n" +
    "- Archive pages with historical meeting documents\n\n" +
    "Return the top 5 most relevant INDEX pages. For each, provide:\n" +
    "- url: the exact URL from the list\n" +
    "- description: what it likely contains (1 sentence)\n" +
    "- confidence: 0.0 to 1.0\n\n" +
    "Return ONLY a JSON object with a 'candidates' array. Max 5 entries.\n\n" +
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

  const candidates = filterCivicDiscoveryCandidates((extraction.candidates ?? [])
    .filter((c) => c && typeof c.url === "string" && c.url.trim().length > 0)
    .slice(0, 5)
    .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0)));

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

  const preview = await previewCivicTrackedUrls(tracked_urls, criteria, {
    maxDocs: 5,
    maxPromisesPerDocument: PROMISES_PREVIEW_CAP,
  });
  const allPromises = preview.documents.flatMap((document) => document.promises)
    .slice(0, PROMISES_PREVIEW_CAP);
  const documentsFound = preview.documentsFound;

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
