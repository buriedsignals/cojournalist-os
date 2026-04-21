/**
 * civic-test Edge Function — synchronous preview of what a civic scout would
 * extract, used by the UI's Add Civic Scout flow. Nothing is persisted.
 *
 * Route:
 *   POST /civic-test
 *     body: { tracked_urls: string[] (1..2), criteria?: string }
 *     -> 200 { results: [{ url, title?, promises_count?, promises?, error? }] }
 *
 * For each URL (max 2): firecrawlScrape, then Gemini-extract up to 10
 * promises. Per-URL failures (scrape or extract) are reported in the result
 * entry rather than surfacing as a 500.
 */

import { z } from "https://esm.sh/zod@3";
import { handleCors } from "../_shared/cors.ts";
import { requireUser, AuthedUser } from "../_shared/auth.ts";
import { jsonError, jsonFromError, jsonOk } from "../_shared/responses.ts";
import { ValidationError } from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";
import { firecrawlScrape } from "../_shared/firecrawl.ts";
import { geminiExtract } from "../_shared/gemini.ts";

const InputSchema = z.object({
  tracked_urls: z.array(z.string().url()).min(1).max(2),
  criteria: z.string().max(4000).optional(),
});

const MARKDOWN_MAX = 15_000;
const PROMISES_PREVIEW_CAP = 10;

const EXTRACTION_SCHEMA: Record<string, unknown> = {
  type: "object",
  properties: {
    promises: {
      type: "array",
      items: {
        type: "object",
        properties: {
          promise_text: { type: "string" },
          context: { type: "string" },
          meeting_date: { type: "string", nullable: true },
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
  meeting_date?: string | null;
}

interface UrlResult {
  url: string;
  title?: string;
  promises_count?: number;
  promises?: ExtractedPromise[];
  error?: string;
}

Deno.serve(async (req: Request): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  if (req.method !== "POST") {
    return jsonError("method not allowed", 405);
  }

  let user: AuthedUser;
  try {
    user = await requireUser(req);
  } catch (e) {
    return jsonFromError(e);
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
      new ValidationError(
        parsed.error.issues.map((i) => i.message).join("; "),
      ),
    );
  }
  const { tracked_urls, criteria } = parsed.data;

  try {
    const results: UrlResult[] = [];
    for (const url of tracked_urls) {
      results.push(await previewUrl(url, criteria));
    }

    logEvent({
      level: "info",
      fn: "civic-test",
      event: "preview",
      user_id: user.id,
      urls: tracked_urls.length,
    });

    return jsonOk({ results });
  } catch (e) {
    logEvent({
      level: "error",
      fn: "civic-test",
      event: "unhandled",
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonFromError(e);
  }
});

// ---------------------------------------------------------------------------

async function previewUrl(
  url: string,
  criteria: string | undefined,
): Promise<UrlResult> {
  let scraped;
  try {
    scraped = await firecrawlScrape(url);
  } catch (e) {
    return {
      url,
      error: `scrape failed: ${e instanceof Error ? e.message : String(e)}`,
    };
  }

  const markdown = scraped.markdown ?? "";
  if (!markdown.trim()) {
    return {
      url,
      title: scraped.title,
      promises_count: 0,
      promises: [],
    };
  }

  const prompt =
    `Extract commitments, promises, and votes from this council document. ` +
    `If a criteria is given, only include matching items. ` +
    `${criteria ? "Criteria: " + criteria : ""}` +
    `\n\n---\n\n${markdown.slice(0, MARKDOWN_MAX)}`;

  let extraction: { promises: ExtractedPromise[] };
  try {
    extraction = await geminiExtract<{ promises: ExtractedPromise[] }>(
      prompt,
      EXTRACTION_SCHEMA,
    );
  } catch (_e) {
    return { url, title: scraped.title, error: "extract failed" };
  }

  const all = Array.isArray(extraction?.promises) ? extraction.promises : [];
  const filtered = all.filter(
    (p) => p && typeof p.promise_text === "string" && p.promise_text.trim(),
  );
  const preview = filtered.slice(0, PROMISES_PREVIEW_CAP);

  return {
    url,
    title: scraped.title,
    promises_count: filtered.length,
    promises: preview,
  };
}
