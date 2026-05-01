import {
  assertEquals,
  assertRejects,
} from "https://deno.land/std@0.208.0/assert/mod.ts";

import { ApiError } from "./errors.ts";
import {
  isTransientFirecrawlError,
  scrapePrimaryPageResilient,
  type ScrapeResult,
} from "./firecrawl.ts";

function scrapeResult(
  markdown: string,
  rawHtml: string | null = "<html></html>",
): ScrapeResult {
  return {
    markdown,
    rawHtml: rawHtml ?? undefined,
    title: "Example",
    source_url: "https://example.com",
    fetched_at: "2026-05-01T00:00:00Z",
  };
}

Deno.test("scrapePrimaryPageResilient returns combined strategy on first success", async () => {
  const result = await scrapePrimaryPageResilient({
    url: "https://example.com",
    retryDelayMs: 0,
    deps: {
      scrape: async () => scrapeResult("body"),
    },
  });

  assertEquals(result.markdown, "body");
  assertEquals(result.scrape_strategy, "combined");
  assertEquals(result.scrape_attempts, 1);
});

Deno.test("scrapePrimaryPageResilient retries transient combined failures", async () => {
  let calls = 0;
  const result = await scrapePrimaryPageResilient({
    url: "https://example.com",
    retryDelayMs: 0,
    deps: {
      scrape: async () => {
        calls += 1;
        if (calls === 1) {
          throw new ApiError("firecrawl scrape failed: 500 upstream", 502);
        }
        return scrapeResult("body");
      },
    },
  });

  assertEquals(calls, 2);
  assertEquals(result.scrape_strategy, "combined_retry");
  assertEquals(result.scrape_attempts, 2);
  assertEquals(result.scrape_warning, "combined_500");
});

Deno.test("scrapePrimaryPageResilient splits markdown and rawHtml after transient combined failures", async () => {
  let scrapeCalls = 0;
  const result = await scrapePrimaryPageResilient({
    url: "https://example.com",
    retryDelayMs: 0,
    deps: {
      scrape: async (_url, opts) => {
        scrapeCalls += 1;
        if (scrapeCalls <= 2) {
          throw new ApiError("firecrawl scrape aborted after 30000ms", 504);
        }
        if (opts?.formats?.includes("markdown")) {
          return scrapeResult("markdown only", null);
        }
        return scrapeResult("", "<a href='/minutes'>Minutes</a>");
      },
    },
  });

  assertEquals(result.markdown, "markdown only");
  assertEquals(result.rawHtml, "<a href='/minutes'>Minutes</a>");
  assertEquals(result.scrape_strategy, "split");
  assertEquals(result.scrape_attempts, 4);
  assertEquals(
    result.scrape_warning,
    "combined_aborted,combined_retry_aborted",
  );
});

Deno.test("scrapePrimaryPageResilient allows markdown-only fallback when rawHtml fails", async () => {
  let scrapeCalls = 0;
  const result = await scrapePrimaryPageResilient({
    url: "https://example.com",
    retryDelayMs: 0,
    deps: {
      scrape: async (_url, opts) => {
        scrapeCalls += 1;
        if (scrapeCalls <= 2) {
          throw new ApiError("firecrawl scrape failed: 500 upstream", 502);
        }
        if (opts?.formats?.includes("markdown")) {
          return scrapeResult("markdown only", null);
        }
        throw new ApiError("firecrawl scrape failed: 500 raw html", 502);
      },
    },
  });

  assertEquals(result.markdown, "markdown only");
  assertEquals(result.rawHtml, null);
  assertEquals(result.scrape_strategy, "markdown_only_fallback");
  assertEquals(
    result.scrape_warning,
    "combined_500,combined_retry_500,raw_html_500",
  );
});

Deno.test("scrapePrimaryPageResilient does not retry unsupported file errors", async () => {
  let calls = 0;
  await assertRejects(
    () =>
      scrapePrimaryPageResilient({
        url: "https://example.com/bad.gif",
        retryDelayMs: 0,
        deps: {
          scrape: async () => {
            calls += 1;
            throw new ApiError(
              'firecrawl scrape failed: 500 {"code":"SCRAPE_UNSUPPORTED_FILE_ERROR"}',
              502,
            );
          },
        },
      }),
    ApiError,
  );

  assertEquals(calls, 1);
});

Deno.test("isTransientFirecrawlError classifies only retryable Firecrawl failures", () => {
  assertEquals(
    isTransientFirecrawlError(
      new ApiError("firecrawl scrape failed: 429 rate limit", 502),
    ),
    true,
  );
  assertEquals(
    isTransientFirecrawlError(
      new ApiError("firecrawl scrape failed: 500 upstream", 502),
    ),
    true,
  );
  assertEquals(
    isTransientFirecrawlError(
      new ApiError(
        'firecrawl scrape failed: 500 {"code":"SCRAPE_UNSUPPORTED_FILE_ERROR"}',
        502,
      ),
    ),
    false,
  );
});
