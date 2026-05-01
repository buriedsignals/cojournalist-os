import { firecrawlScrape } from "./firecrawl.ts";
import { geminiExtract } from "./gemini.ts";

export const CIVIC_DENYLIST_EXTENSIONS = [
  ".css",
  ".js",
  ".png",
  ".jpg",
  ".jpeg",
  ".svg",
  ".gif",
  ".webp",
  ".avif",
  ".bmp",
  ".ico",
  ".mp3",
  ".mp4",
  ".mov",
  ".m4v",
  ".avi",
  ".webm",
  ".zip",
  ".tar",
  ".gz",
  ".rar",
  ".woff",
  ".woff2",
  ".ttf",
  ".eot",
  ".map",
] as const;

export const CIVIC_DENYLIST_PREFIXES = [
  "mailto:",
  "javascript:",
  "tel:",
  "#",
] as const;

export const CIVIC_MEETING_KEYWORDS: readonly string[] = [
  "protokoll",
  "vollprotokoll",
  "wortprotokoll",
  "beschlussprotokoll",
  "tagesordnung",
  "geschaeftsverzeichnis",
  "sitzung",
  "niederschrift",
  "verhandlung",
  "ratssitzung",
  "gemeinderat",
  "proces-verbal",
  "procès-verbal",
  "ordre-du-jour",
  "délibération",
  "compte-rendu",
  "compte rendu",
  "séance",
  "seance",
  "minutes",
  "agenda",
  "proceedings",
  "transcript",
  "meeting",
  "decision",
  "resolution",
  "motion",
  "verbale",
  "ordine-del-giorno",
  "delibera",
  "seduta",
  "acta",
  "orden del día",
  "orden-del-dia",
  "sesión",
  "sesion",
  "pleno",
  "deliberación",
  "ata",
  "ordem do dia",
  "deliberação",
  "sessão",
  "notulen",
  "vergadering",
  "raadsvergadering",
  "besluitenlijst",
  "protokół",
  "protokol",
  "porządek obrad",
  "sesja",
  "protocol",
  "session",
] as const;

export interface CivicLink {
  url: string;
  anchorText: string;
}

export interface CivicTrackedPage {
  pageUrl: string;
  rawHtml?: string | null;
}

const MEETING_URL_SCHEMA: Record<string, unknown> = {
  type: "object",
  properties: {
    meeting_urls: {
      type: "array",
      items: { type: "integer" },
    },
  },
  required: ["meeting_urls"],
};

export function extractCivicLinksFromHtml(
  html: string,
  pageUrl: string,
): CivicLink[] {
  if (!html.trim()) return [];
  const allLinks: CivicLink[] = [];
  const seenUrls = new Set<string>();
  const pageParsed = new URL(pageUrl);
  const pageDomain = pageParsed.hostname.toLowerCase();
  const pageNoFragment = pageUrl.split("#")[0].replace(/\/+$/, "");
  const rawLinks = html.matchAll(/<a[^>]+href="([^"]+)"[^>]*>(.*?)<\/a>/gims);

  for (const match of rawLinks) {
    const rawHref = (match[1] ?? "").trim();
    const rawAnchor = (match[2] ?? "").replace(/<[^>]+>/g, "").trim();
    if (!rawHref) continue;
    if (CIVIC_DENYLIST_PREFIXES.some((prefix) => rawHref.startsWith(prefix))) {
      continue;
    }
    if (hasDeniedCivicAssetExtension(rawHref)) continue;

    let absolute: URL;
    try {
      absolute = new URL(rawHref, pageUrl);
    } catch {
      continue;
    }
    if (!["http:", "https:"].includes(absolute.protocol)) continue;
    if (absolute.hostname.toLowerCase() !== pageDomain) continue;

    const hrefNoFragment = absolute.toString().split("#")[0].replace(
      /\/+$/,
      "",
    );
    if (hrefNoFragment === pageNoFragment) continue;
    if (seenUrls.has(hrefNoFragment)) continue;
    seenUrls.add(hrefNoFragment);
    allLinks.push({ url: hrefNoFragment, anchorText: rawAnchor });
  }

  return allLinks;
}

export function extractCivicLinksFromPages(
  pages: CivicTrackedPage[],
): CivicLink[] {
  const merged: CivicLink[] = [];
  const seen = new Set<string>();
  for (const page of pages) {
    const rawHtml = page.rawHtml ?? "";
    if (!rawHtml.trim()) continue;
    const links = extractCivicLinksFromHtml(rawHtml, page.pageUrl);
    for (const link of links) {
      if (seen.has(link.url)) continue;
      seen.add(link.url);
      merged.push(link);
    }
  }
  return merged;
}

export async function discoverCivicDocumentsFromTrackedPages(
  trackedUrls: string[],
  opts: { maxDocs?: number } = {},
): Promise<{ documentUrls: string[]; scrapedPages: number }> {
  const pages: CivicTrackedPage[] = [];
  let scrapedPages = 0;
  for (const trackedUrl of trackedUrls) {
    if (!isCivicScrapableUrl(trackedUrl)) continue;
    try {
      const scraped = await firecrawlScrape(trackedUrl, {
        formats: ["rawHtml"],
        onlyMainContent: false,
        pdfMode: null,
      });
      pages.push({
        pageUrl: trackedUrl,
        rawHtml: scraped.rawHtml ?? "",
      });
      if ((scraped.rawHtml ?? "").trim()) scrapedPages += 1;
    } catch {
      continue;
    }
  }

  const links = extractCivicLinksFromPages(pages);
  const documentUrls = await classifyCivicMeetingUrls(links);
  const maxDocs = Math.max(1, opts.maxDocs ?? 5);
  return {
    documentUrls: documentUrls.slice(0, maxDocs),
    scrapedPages,
  };
}

export async function classifyCivicMeetingUrls(
  links: CivicLink[],
): Promise<string[]> {
  const scrapableLinks = links.filter((link) => isCivicScrapableUrl(link.url));
  if (scrapableLinks.length === 0) return [];

  const keywordMatches = scrapableLinks
    .filter((link) =>
      hasMeetingKeyword(`${link.url} ${link.anchorText}`.toLowerCase())
    )
    .map((link) => link.url);

  if (keywordMatches.length > 0) {
    const pdfMatches = keywordMatches.filter((url) => isPdfUrl(url));
    const htmlMatches = keywordMatches
      .filter((url) => !isPdfUrl(url))
      .filter((url) => urlPathDepth(url) > 2);
    return [...pdfMatches, ...htmlMatches].sort(compareCivicUrls);
  }

  const numbered = scrapableLinks.slice(0, 2000).map((link, index) => {
    const parsed = new URL(link.url);
    const displayPath = parsed.search
      ? `${parsed.pathname}${parsed.search}`
      : parsed.pathname;
    const anchorDisplay = link.anchorText ? ` — ${link.anchorText}` : "";
    return `${index}. ${displayPath}${anchorDisplay}`;
  }).join("\n");
  const baseDomain = new URL(scrapableLinks[0].url).hostname;
  const prompt =
    "You are a civic data assistant. Below is a numbered list of links " +
    `from the website ${baseDomain}. Each line shows: index, URL path, and anchor text.\n\n` +
    "Identify which links point to meeting minutes, council protocols, agendas, or official proceedings documents.\n\n" +
    "Return ONLY a JSON object with a 'meeting_urls' key containing an array of integer indices.\n" +
    'Example: {"meeting_urls": [0, 3, 7]}\n' +
    'If none are meeting documents, return: {"meeting_urls": []}\n\n' +
    `Links:\n${numbered}`;

  try {
    const extraction = await geminiExtract<{ meeting_urls: number[] }>(
      prompt,
      MEETING_URL_SCHEMA,
    );
    const seen = new Set<number>();
    const classified =
      (Array.isArray(extraction.meeting_urls) ? extraction.meeting_urls : [])
        .filter((idx): idx is number =>
          Number.isInteger(idx) && idx >= 0 && idx < scrapableLinks.length
        )
        .filter((idx) => {
          if (seen.has(idx)) return false;
          seen.add(idx);
          return true;
        })
        .map((idx) => scrapableLinks[idx].url)
        .sort(compareCivicUrls);
    return classified;
  } catch {
    return [];
  }
}

export function filterCivicDiscoveryCandidates<T extends { url: string }>(
  candidates: T[],
): T[] {
  return candidates.filter((candidate) => {
    try {
      const parsed = new URL(candidate.url);
      const path = parsed.pathname.toLowerCase();
      if (hasDeniedCivicAssetExtension(candidate.url)) return false;
      if (path.endsWith(".pdf")) return false;
      if (path.startsWith("/pdf/")) return false;
      return true;
    } catch {
      return false;
    }
  });
}

function hasMeetingKeyword(text: string): boolean {
  return CIVIC_MEETING_KEYWORDS.some((keyword) => text.includes(keyword));
}

export function isCivicScrapableUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol)) return false;
    return !hasDeniedCivicAssetExtension(url);
  } catch {
    return false;
  }
}

function hasDeniedCivicAssetExtension(urlOrHref: string): boolean {
  const withoutQuery = urlOrHref.split(/[?#]/)[0].toLowerCase();
  return CIVIC_DENYLIST_EXTENSIONS.some((ext) => withoutQuery.endsWith(ext));
}

function isPdfUrl(url: string): boolean {
  try {
    return new URL(url).pathname.toLowerCase().endsWith(".pdf");
  } catch {
    return url.split(/[?#]/)[0].toLowerCase().endsWith(".pdf");
  }
}

function urlPathDepth(url: string): number {
  try {
    return new URL(url).pathname.split("/").filter(Boolean).length;
  } catch {
    return 0;
  }
}

function compareCivicUrls(a: string, b: string): number {
  const [dateA, priorityA] = civicSortKey(a);
  const [dateB, priorityB] = civicSortKey(b);
  if (dateA !== dateB) return dateB.localeCompare(dateA);
  return priorityB - priorityA;
}

function civicSortKey(url: string): [string, number] {
  const date = url.match(/(\d{4}-\d{2}-\d{2})/)?.[1] ?? "0000-00-00";
  const lower = url.toLowerCase();
  let priority = 1;
  if (lower.includes("vollprotokoll") || lower.includes("wortprotokoll")) {
    priority = 3;
  } else if (
    lower.includes("beschlussprotokoll") ||
    lower.includes("protocol") ||
    lower.includes("minutes") ||
    lower.includes("proces") ||
    lower.includes("verbale")
  ) priority = 2;
  if (isPdfUrl(lower)) priority += 10;
  return [date, priority];
}
