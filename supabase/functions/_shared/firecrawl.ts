/**
 * Firecrawl v2 API client. Minimal surface: single-page scrape and
 * change-tracking scrape (per-scout baseline).
 *
 * Docs: https://docs.firecrawl.dev/api-reference
 */

import { ApiError } from "./errors.ts";

const FIRECRAWL_BASE = "https://api.firecrawl.dev/v2";

function firecrawlApiKey(): string {
  const k = Deno.env.get("FIRECRAWL_API_KEY");
  if (!k) throw new ApiError("FIRECRAWL_API_KEY not configured", 500);
  return k;
}

export interface ScrapeResult {
  markdown: string;
  html?: string;
  title?: string;
  source_url: string;
  fetched_at: string;
}

export interface ScrapeOptions {
  formats?: Array<"markdown" | "html">;
  onlyMainContent?: boolean;
  /**
   * PDF parser mode. Defaults to "fast", which matches the dorfkoenig
   * reference benchmark (far more section markers, zero OCR hallucinations
   * on InDesign/embedded-text PDFs vs. the default "auto"/"ocr" modes).
   * Pass `null` to omit the parsers field entirely (e.g. for HTML-only callers
   * that want to avoid any PDF-specific behaviour).
   */
  pdfMode?: "fast" | "auto" | "ocr" | null;
  /** Firecrawl server-side timeout in ms. Default 120_000 for civic PDFs. */
  timeoutMs?: number;
  /** Client-side AbortController fuse in ms. Defaults to timeoutMs + 5000. */
  abortAfterMs?: number;
}

export async function firecrawlScrape(
  url: string,
  opts: ScrapeOptions = {},
): Promise<ScrapeResult> {
  const timeoutMs = opts.timeoutMs ?? 120_000;
  const abortAfterMs = opts.abortAfterMs ?? timeoutMs + 5_000;

  const body: Record<string, unknown> = {
    url,
    formats: opts.formats ?? ["markdown"],
    onlyMainContent: opts.onlyMainContent ?? true,
    timeout: timeoutMs,
  };
  const pdfMode = opts.pdfMode === undefined ? "fast" : opts.pdfMode;
  if (pdfMode !== null) {
    body.parsers = [{ type: "pdf", mode: pdfMode }];
  }

  const ac = new AbortController();
  const fuse = setTimeout(() => ac.abort(), abortAfterMs);
  let res: Response;
  try {
    res = await fetch(`${FIRECRAWL_BASE}/scrape`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${firecrawlApiKey()}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      signal: ac.signal,
    });
  } catch (e) {
    clearTimeout(fuse);
    if ((e as { name?: string }).name === "AbortError") {
      throw new ApiError(`firecrawl scrape aborted after ${abortAfterMs}ms`, 504);
    }
    throw e;
  }
  clearTimeout(fuse);
  if (!res.ok) {
    throw new ApiError(`firecrawl scrape failed: ${res.status} ${await res.text()}`, 502);
  }
  const bodyJson = await res.json();
  const d = bodyJson?.data ?? {};
  return {
    markdown: d.markdown ?? "",
    html: d.html,
    title: d.metadata?.title,
    source_url: url,
    fetched_at: new Date().toISOString(),
  };
}

export interface SearchHit {
  url: string;
  title?: string;
  description?: string;
  markdown?: string;
}

/**
 * Firecrawl v2 /search endpoint. Returns up to `limit` SERP-style hits.
 *
 * Docs: https://docs.firecrawl.dev/api-reference/endpoint/search
 */
export async function firecrawlSearch(
  query: string,
  opts: { limit?: number; scrape?: boolean; lang?: string; country?: string } = {},
): Promise<SearchHit[]> {
  const body: Record<string, unknown> = {
    query,
    limit: Math.min(Math.max(1, opts.limit ?? 10), 20),
  };
  if (opts.lang) body.lang = opts.lang;
  if (opts.country) body.country = opts.country;
  if (opts.scrape) {
    body.scrapeOptions = { formats: ["markdown"], onlyMainContent: true };
  }

  const res = await fetch(`${FIRECRAWL_BASE}/search`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${firecrawlApiKey()}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new ApiError(
      `firecrawl search failed: ${res.status} ${await res.text()}`,
      502,
    );
  }
  const j = await res.json();
  const hits = Array.isArray(j?.data)
    ? j.data
    : Array.isArray(j?.data?.web)
    ? j.data.web
    : [];
  return hits.map((h: Record<string, unknown>) => ({
    url: String(h.url ?? ""),
    title: typeof h.title === "string" ? h.title : undefined,
    description: typeof h.description === "string" ? h.description : undefined,
    markdown: typeof h.markdown === "string" ? h.markdown : undefined,
  })).filter((h: SearchHit) => h.url.length > 0);
}

/**
 * Firecrawl /map — enumerate links on a site without scraping each.
 *
 * Docs: https://docs.firecrawl.dev/api-reference/endpoint/map
 */
export async function firecrawlMap(
  url: string,
  opts: { limit?: number; includeSubdomains?: boolean } = {},
): Promise<string[]> {
  const res = await fetch(`${FIRECRAWL_BASE}/map`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${firecrawlApiKey()}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      url,
      limit: Math.min(Math.max(1, opts.limit ?? 200), 500),
      includeSubdomains: opts.includeSubdomains ?? true,
    }),
  });
  if (!res.ok) {
    throw new ApiError(
      `firecrawl map failed: ${res.status} ${await res.text()}`,
      502,
    );
  }
  const body = await res.json();
  const links = Array.isArray(body?.links)
    ? body.links
    : Array.isArray(body?.data?.links)
    ? body.data.links
    : [];
  return links
    .map((l: unknown) => typeof l === "string" ? l : (l as { url?: string }).url ?? "")
    .filter((s: string) => typeof s === "string" && s.length > 0);
}

export interface ChangeTrackingResult extends ScrapeResult {
  change_status: "new" | "same" | "changed" | "removed";
  visibility?: "visible" | "hidden";
  previous_scrape_at?: string;
}

/**
 * Firecrawl v2 changeTracking scrape.
 *
 * CRITICAL SHAPE (matches the production FastAPI implementation — see
 * cojournalist/backend/app/services/scout_service.py::_firecrawl_scrape):
 * the changeTracking config lives INSIDE the `formats` array as an object
 * `{ type: "changeTracking", tag }`. The older `changeTrackingOptions`
 * top-level key is rejected by the v2 API with HTTP 400 "Unrecognized key".
 *
 * The `tag` is per-scout and caps at 128 chars.
 */
/**
 * Double-probe: verify that Firecrawl's changeTracking actually stores a
 * baseline for this URL. Some sites are "ghost baseline" — Firecrawl returns
 * a `previousScrapeAt` timestamp but no stored content, so the next call
 * always reports `changeStatus="new"`. We detect this by doing two sequential
 * changeTracking scrapes with the same tag and inspecting the second result.
 *
 * Returns:
 *   "firecrawl"        — baseline verified (previousScrapeAt set + changeStatus
 *                        is same/changed). Future runs can trust changeTracking.
 *   "firecrawl_plain"  — baseline dropped or ghost. Future runs must use
 *                        plain scrape + SHA-256 hash dedup.
 *
 * Port of backend/app/services/scout_service.py::double_probe.
 */
export async function doubleProbe(
  url: string,
  tag: string,
): Promise<"firecrawl" | "firecrawl_plain"> {
  try {
    await firecrawlChangeTrackingScrape(url, tag);
  } catch {
    return "firecrawl_plain";
  }
  let result2: ChangeTrackingResult;
  try {
    result2 = await firecrawlChangeTrackingScrape(url, tag);
  } catch {
    return "firecrawl_plain";
  }
  const { previous_scrape_at: prev, change_status: status } = result2;
  if (prev && (status === "same" || status === "changed")) {
    return "firecrawl";
  }
  return "firecrawl_plain";
}

export async function firecrawlChangeTrackingScrape(
  url: string,
  tag: string,
): Promise<ChangeTrackingResult> {
  const safeTag = tag.length > 128 ? tag.slice(0, 128) : tag;
  const res = await fetch(`${FIRECRAWL_BASE}/scrape`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${firecrawlApiKey()}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      url,
      formats: ["markdown", { type: "changeTracking", tag: safeTag }],
      onlyMainContent: true,
    }),
  });
  if (!res.ok) {
    throw new ApiError(`firecrawl change-tracking failed: ${res.status} ${await res.text()}`, 502);
  }
  const body = await res.json();
  const d = body?.data ?? {};
  const ct = d.changeTracking ?? {};
  return {
    markdown: d.markdown ?? "",
    html: d.html,
    title: d.metadata?.title,
    source_url: url,
    fetched_at: new Date().toISOString(),
    change_status: (ct.changeStatus ?? "new") as ChangeTrackingResult["change_status"],
    visibility: ct.visibility,
    previous_scrape_at: ct.previousScrapeAt,
  };
}
