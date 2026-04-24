import {
  assertEquals,
  assertExists,
} from "https://deno.land/std@0.208.0/assert/mod.ts";

import {
  classifyCivicMeetingUrls,
  extractCivicLinksFromHtml,
  extractCivicLinksFromPages,
  filterCivicDiscoveryCandidates,
} from "./civic_links.ts";

Deno.test("extractCivicLinksFromHtml extracts same-domain document links and strips fragments", () => {
  const html = `
    <html>
      <body>
        <a href="/urversammlung/protokoll">Protokolle</a>
        <a href="/pdf/protokoll/2025/vollprotokoll_2025-03-19.pdf#page=1">Vollprotokoll</a>
        <a href="mailto:info@example.org">Mail</a>
        <a href="https://external.example.org/minutes">External</a>
      </body>
    </html>
  `;

  const links = extractCivicLinksFromHtml(
    html,
    "https://gemeinde.zermatt.ch",
  );

  assertEquals(links, [
    {
      url: "https://gemeinde.zermatt.ch/urversammlung/protokoll",
      anchorText: "Protokolle",
    },
    {
      url: "https://gemeinde.zermatt.ch/pdf/protokoll/2025/vollprotokoll_2025-03-19.pdf",
      anchorText: "Vollprotokoll",
    },
  ]);
});

Deno.test("extractCivicLinksFromPages de-duplicates links across tracked pages", () => {
  const pages = [
    {
      pageUrl: "https://gemeinde.zermatt.ch/urversammlung/protokoll",
      rawHtml:
        '<a href="/pdf/protokoll/2025/vollprotokoll_2025-03-19.pdf">Vollprotokoll</a>',
    },
    {
      pageUrl: "https://gemeinde.zermatt.ch/urversammlung/protokoll?page=2",
      rawHtml:
        '<a href="/pdf/protokoll/2025/vollprotokoll_2025-03-19.pdf">Duplicate</a>',
    },
  ];

  const links = extractCivicLinksFromPages(pages);

  assertEquals(links.length, 1);
  assertEquals(
    links[0].url,
    "https://gemeinde.zermatt.ch/pdf/protokoll/2025/vollprotokoll_2025-03-19.pdf",
  );
});

Deno.test("filterCivicDiscoveryCandidates rejects dead /pdf listing paths but keeps listing pages", () => {
  const filtered = filterCivicDiscoveryCandidates([
    { url: "https://gemeinde.zermatt.ch/pdf/protokoll", confidence: 0.95 },
    {
      url: "https://gemeinde.zermatt.ch/urversammlung/protokoll",
      confidence: 0.9,
    },
  ]);

  assertEquals(filtered, [
    {
      url: "https://gemeinde.zermatt.ch/urversammlung/protokoll",
      confidence: 0.9,
    },
  ]);
});

Deno.test("classifyCivicMeetingUrls uses keyword stage for pdf minutes links", async () => {
  const urls = await classifyCivicMeetingUrls([
    {
      url: "https://gemeinde.zermatt.ch/pdf/protokoll/2025/vollprotokoll_2025-03-19.pdf",
      anchorText: "Vollprotokoll 19.03.2025",
    },
    {
      url: "https://gemeinde.zermatt.ch/pdf/protokoll/2024/beschlussprotokoll_2024-12-11.pdf",
      anchorText: "Beschlussprotokoll 11.12.2024",
    },
  ]);

  assertEquals(urls.length, 2);
  assertExists(urls[0].match(/2025-03-19/));
  assertExists(urls[1].match(/2024-12-11/));
});
