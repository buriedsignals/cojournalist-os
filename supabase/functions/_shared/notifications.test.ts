/**
 * Unit tests for the shared notification helpers. Pure-function coverage only —
 * no network. Run:
 *
 *   deno test --allow-env supabase/functions/_shared/notifications.test.ts
 */

import { assert, assertEquals, assertStringIncludes } from "https://deno.land/std@0.224.0/assert/mod.ts";
import {
  buildBaseHtml,
  buildProfileUrl,
  escapeHtml,
  groupFactsBySource,
  markdownToHtml,
  renderArticleCards,
} from "./notifications.ts";
import { EMAIL_STRINGS, getString, SUPPORTED_LANGUAGES } from "./email_translations.ts";

// Helper: render each scout type's full email HTML against a fixed payload.
// Used by per-type snapshot assertions below.
function renderPageScoutHtml(lang = "en"): string {
  const criteriaLabel = getString("criteria", lang);
  const monitoringLabel = getString("monitoring_url", lang);
  const cueText = getString("page_scout_cue", lang);
  return buildBaseHtml({
    headerTitle: getString("scout_alert", lang),
    headerSubtitle: "Test Scout",
    headerGradient: "#1a1a2e",
    accentColor: "#2563eb",
    contextLabel: getString("page_scout", lang),
    summary: "Found one new fact matching your criteria.",
    articles: [{
      title: "Evidence page",
      url: "https://example.com/page",
      summary: "",
      source: "",
    }],
    articlesSectionTitle: getString("see_what_matched", lang),
    extraContent: `<div>${escapeHtml(monitoringLabel)}: https://example.com</div>
<div>${escapeHtml(criteriaLabel)}: climate action</div>
<div>${escapeHtml(cueText)}</div>`,
    language: lang,
  });
}

function renderBeatScoutHtml(lang = "en"): string {
  return buildBaseHtml({
    headerTitle: getString("beat_scout", lang),
    headerSubtitle: "My Beat",
    headerGradient: ["#7c3aed", "#6d28d9"],
    accentColor: "#7c3aed",
    contextLabel: "ZURICH, CH",
    summary: "- Fact A\n- Fact B\n- Fact C",
    articles: [
      { title: "Source 1", url: "https://a.example/1", summary: "" },
      { title: "Source 2", url: "https://b.example/2", summary: "" },
    ],
    articlesSectionTitle: getString("top_stories", lang),
    extraContent: `<div>${escapeHtml(getString("pulse_scout_cue", lang))}</div>`,
    language: lang,
  });
}

function renderCivicScoutHtml(lang = "en"): string {
  return buildBaseHtml({
    headerTitle: getString("civic_scout", lang),
    headerSubtitle: "Oakland Council",
    headerGradient: ["#d97706", "#b45309"],
    accentColor: "#d97706",
    contextLabel: getString("civic_scout", lang),
    summary:
      "- **Commit to a 30% reduction** ([Oakland minutes](https://oakland.example/m.pdf))",
    articles: [],
    articlesSectionTitle: "",
    extraContent: `<div>${escapeHtml(getString("civic_scout_cue", lang))}</div>`,
    language: lang,
  });
}

function renderSocialScoutHtml(lang = "en"): string {
  return buildBaseHtml({
    headerTitle: getString("social_scout", lang),
    headerSubtitle: "Mayor watch",
    headerGradient: ["#e11d48", "#be123c"],
    accentColor: "#e11d48",
    contextLabel: "@somehandle on X",
    summary: "2 new posts:\n- post one\n- post two",
    articles: [
      { title: "@somehandle", url: "https://twitter.com/somehandle/status/1", summary: "post one" },
    ],
    articlesSectionTitle: getString("new_posts", lang),
    extraContent: `<div>${escapeHtml(getString("social_scout_cue", lang))}</div>`,
    language: lang,
  });
}

// ---------------------------------------------------------------------------
// email_translations
// ---------------------------------------------------------------------------

Deno.test("getString returns the English value for a known key", () => {
  assertEquals(getString("page_scout", "en"), "Page Scout");
});

Deno.test("getString falls back to English for an unknown language", () => {
  assertEquals(getString("beat_scout", "xx"), "Beat Scout");
});

Deno.test("getString returns the key itself when key is unknown", () => {
  assertEquals(getString("no_such_key_ever", "en"), "no_such_key_ever");
});

Deno.test("getString interpolates {name} placeholders", () => {
  const out = getString("and_more", "en", { count: 7 });
  assert(out.includes("7"));
  assert(!out.includes("{count}"));
});

Deno.test("getString leaves unfilled placeholders in place", () => {
  // `and_more` uses {count}; if we omit the param the token stays verbatim.
  const out = getString("and_more", "en", { other: 3 });
  assert(out.includes("{count}"));
});

Deno.test("every supported language carries the full key set", () => {
  const enKeys = Object.keys(EMAIL_STRINGS.en).sort();
  for (const lang of SUPPORTED_LANGUAGES) {
    const langKeys = Object.keys(EMAIL_STRINGS[lang]).sort();
    assertEquals(
      langKeys,
      enKeys,
      `Language '${lang}' is missing or has extra keys vs English`,
    );
  }
});

Deno.test("Smart Scout wording has been renamed to Beat Scout in every locale", () => {
  for (const lang of SUPPORTED_LANGUAGES) {
    const v = EMAIL_STRINGS[lang].beat_scout;
    assertEquals(v, "Beat Scout", `locale '${lang}' should use Beat Scout`);
  }
});

// ---------------------------------------------------------------------------
// escapeHtml
// ---------------------------------------------------------------------------

Deno.test("escapeHtml neutralizes every HTML-sensitive char", () => {
  assertEquals(
    escapeHtml(`<script>alert("xss & 'oops'")</script>`),
    "&lt;script&gt;alert(&quot;xss &amp; &#39;oops&#39;&quot;)&lt;/script&gt;",
  );
});

Deno.test("escapeHtml tolerates null/undefined", () => {
  assertEquals(escapeHtml(null), "");
  assertEquals(escapeHtml(undefined), "");
});

// ---------------------------------------------------------------------------
// markdownToHtml
// ---------------------------------------------------------------------------

Deno.test("markdownToHtml converts headers, bold, bullets and links", () => {
  const out = markdownToHtml(
    "## Title\n\n- **bold** item with [source](https://example.com)\n- plain item",
    "#ff0000",
  );
  assertStringIncludes(out, "<h2");
  assertStringIncludes(out, "<ul");
  assertStringIncludes(out, "<strong>bold</strong>");
  assertStringIncludes(out, 'href="https://example.com"');
  assertStringIncludes(out, "plain item");
});

Deno.test("markdownToHtml escapes HTML embedded in the source", () => {
  const out = markdownToHtml("<script>alert(1)</script>\n\nnormal");
  assert(!out.includes("<script>"), "raw script tag leaked into output");
  assertStringIncludes(out, "&lt;script&gt;");
});

Deno.test("markdownToHtml preserves bold inside link text", () => {
  const out = markdownToHtml("[**click**](https://example.com)");
  // inline markdown extraction uses the link text literally; the important
  // thing is the href lands verbatim.
  assertStringIncludes(out, 'href="https://example.com"');
});

// ---------------------------------------------------------------------------
// groupFactsBySource
// ---------------------------------------------------------------------------

Deno.test("groupFactsBySource dedups by source_url and caps to 5 by default", () => {
  const facts = [
    { source_url: "https://a.com", source_title: "A", source_domain: "a.com", statement: "s1" },
    { source_url: "https://a.com", source_title: "A", source_domain: "a.com", statement: "s2" },
    { source_url: "https://b.com", source_title: "B", source_domain: "b.com", statement: "s3" },
    { source_url: "https://c.com", source_title: "C", source_domain: "c.com", statement: "s4" },
    { source_url: "https://d.com", source_title: "D", source_domain: "d.com", statement: "s5" },
    { source_url: "https://e.com", source_title: "E", source_domain: "e.com", statement: "s6" },
    { source_url: "https://f.com", source_title: "F", source_domain: "f.com", statement: "s7" },
  ];
  const out = groupFactsBySource(facts);
  assertEquals(out.length, 5);
  assertEquals(out[0].url, "https://a.com");
  // Two statements for A => bulleted summary.
  assert(out[0].summary?.startsWith("\u2022"));
  assertStringIncludes(out[0].summary ?? "", "s1");
  assertStringIncludes(out[0].summary ?? "", "s2");
});

Deno.test("groupFactsBySource preserves single-statement plain summaries", () => {
  const out = groupFactsBySource([
    { source_url: "https://x.com", source_title: "X", statement: "only one" },
  ]);
  assertEquals(out[0].summary, "only one");
});

Deno.test("groupFactsBySource keeps URL-less facts as separate entries", () => {
  const out = groupFactsBySource([
    { source_url: null, source_title: "no1", statement: "one" },
    { source_url: null, source_title: "no2", statement: "two" },
  ]);
  assertEquals(out.length, 2);
});

// ---------------------------------------------------------------------------
// renderArticleCards
// ---------------------------------------------------------------------------

Deno.test("renderArticleCards caps at the requested limit", () => {
  const articles = Array.from({ length: 8 }, (_, i) => ({
    title: `t${i}`,
    url: `https://t${i}.com`,
    summary: "hi",
  }));
  const html = renderArticleCards(articles, "#123456", 3);
  const count = html.match(/<a href=/g)?.length ?? 0;
  assertEquals(count, 3);
});

Deno.test("renderArticleCards escapes title HTML", () => {
  // Parity with legacy notification_service._render_article_cards: titles are
  // HTML-escaped. URLs are escaped for attribute-breaking chars too, but
  // `javascript:` is not stripped (matches Python version).
  const html = renderArticleCards(
    [{
      title: '<img onerror=x>',
      url: 'https://example.com/"><script>',
      summary: '',
    }],
    "#000",
  );
  assert(!html.includes("<img onerror"));
  assertStringIncludes(html, "&lt;img");
  assert(!html.includes('"><script>'), "attribute-break must be escaped");
});

// ---------------------------------------------------------------------------
// buildBaseHtml — per-scout-type snapshot smoke
// ---------------------------------------------------------------------------

Deno.test("buildBaseHtml renders tuple gradient + accent + disclaimer", () => {
  const html = buildBaseHtml({
    headerTitle: "Beat Scout",
    headerSubtitle: "My Scout",
    headerGradient: ["#7c3aed", "#6d28d9"],
    accentColor: "#7c3aed",
    contextLabel: "OSLO",
    summary: "New facts",
    articles: [{ title: "A", url: "https://a.com", summary: "x" }],
    articlesSectionTitle: "Top Stories",
    language: "en",
  });
  assertStringIncludes(html, "linear-gradient(135deg, #7c3aed, #6d28d9)");
  assertStringIncludes(html, "Beat Scout");
  assertStringIncludes(html, "OSLO");
  assertStringIncludes(html, "Top Stories");
  assertStringIncludes(html, EMAIL_STRINGS.en.email_disclaimer);
});

Deno.test("buildBaseHtml accepts solid-color gradient fallback", () => {
  const html = buildBaseHtml({
    headerTitle: "Scout Alert!",
    headerSubtitle: "Page",
    headerGradient: "#1a1a2e",
    accentColor: "#2563eb",
    contextLabel: "PAGE SCOUT",
    summary: "changes detected",
    articles: [],
    articlesSectionTitle: "",
    language: "en",
  });
  assertStringIncludes(html, "background: #1a1a2e");
  // No articles → no section heading wrapped in <h3>
  assert(!html.includes("<h3 style=\"margin: 0 0 16px 0"));
});

Deno.test("buildBaseHtml localizes the disclaimer for the chosen language", () => {
  const html = buildBaseHtml({
    headerTitle: "Alerte",
    headerSubtitle: "Ma veille",
    headerGradient: "#1a1a2e",
    accentColor: "#2563eb",
    contextLabel: "PAGE",
    summary: "test",
    articles: [],
    articlesSectionTitle: "",
    language: "fr",
  });
  assertStringIncludes(html, EMAIL_STRINGS.fr.email_disclaimer);
});

// ---------------------------------------------------------------------------
// buildProfileUrl
// ---------------------------------------------------------------------------

Deno.test("buildProfileUrl maps known platforms and strips leading @", () => {
  assertEquals(
    buildProfileUrl("instagram", "@someone"),
    "https://instagram.com/someone",
  );
  assertEquals(buildProfileUrl("x", "handle"), "https://twitter.com/handle");
  assertEquals(
    buildProfileUrl("twitter", "handle"),
    "https://twitter.com/handle",
  );
  assertEquals(
    buildProfileUrl("facebook", "page"),
    "https://facebook.com/page",
  );
  assertEquals(buildProfileUrl("tiktok", "user"), "https://tiktok.com/@user");
});

Deno.test("buildProfileUrl falls back to a {platform}.com host for unknown platforms", () => {
  assertEquals(
    buildProfileUrl("unknown", "@me"),
    "https://unknown.com/me",
  );
});

// ---------------------------------------------------------------------------
// Per-scout-type template snapshots — validate colors, context, copy.
// ---------------------------------------------------------------------------

Deno.test("Page Scout: dark header + blue accent + disclaimer", () => {
  const html = renderPageScoutHtml("en");
  assertStringIncludes(html, "background: #1a1a2e");
  assertStringIncludes(html, "#2563eb");
  assertStringIncludes(html, "Scout Alert!");
  assertStringIncludes(html, "Monitoring URL");
  assertStringIncludes(html, EMAIL_STRINGS.en.page_scout_cue);
  assertStringIncludes(html, EMAIL_STRINGS.en.email_disclaimer);
});

Deno.test("Beat Scout: purple gradient + Top Stories section", () => {
  const html = renderBeatScoutHtml("en");
  assertStringIncludes(html, "linear-gradient(135deg, #7c3aed, #6d28d9)");
  assertStringIncludes(html, "Beat Scout");
  assertStringIncludes(html, "Top Stories");
  assertStringIncludes(html, "ZURICH, CH");
  assertStringIncludes(html, EMAIL_STRINGS.en.pulse_scout_cue);
  assertStringIncludes(html, 'href="https://a.example/1"');
  assertStringIncludes(html, 'href="https://b.example/2"');
});

Deno.test("Civic Scout: amber gradient + markdown promises list", () => {
  const html = renderCivicScoutHtml("en");
  assertStringIncludes(html, "linear-gradient(135deg, #d97706, #b45309)");
  assertStringIncludes(html, "Civic Scout");
  assertStringIncludes(html, "<strong>Commit to a 30% reduction</strong>");
  assertStringIncludes(html, 'href="https://oakland.example/m.pdf"');
  assertStringIncludes(html, EMAIL_STRINGS.en.civic_scout_cue);
});

Deno.test("Social Scout: rose gradient + new-posts section + handle context", () => {
  const html = renderSocialScoutHtml("en");
  assertStringIncludes(html, "linear-gradient(135deg, #e11d48, #be123c)");
  assertStringIncludes(html, "Social Scout Update");
  assertStringIncludes(html, "New Posts");
  assertStringIncludes(html, "@somehandle on X");
  assertStringIncludes(html, EMAIL_STRINGS.en.social_scout_cue);
});

// ---------------------------------------------------------------------------
// Localization — render each scout type in a non-English locale and confirm
// the locale's disclaimer lands in the output.
// ---------------------------------------------------------------------------

Deno.test("Page Scout localizes to Norwegian", () => {
  const html = renderPageScoutHtml("no");
  assertStringIncludes(html, EMAIL_STRINGS.no.scout_alert);
  assertStringIncludes(html, EMAIL_STRINGS.no.email_disclaimer);
});

Deno.test("Beat Scout localizes to German", () => {
  const html = renderBeatScoutHtml("de");
  assertStringIncludes(html, EMAIL_STRINGS.de.beat_scout);
  assertStringIncludes(html, EMAIL_STRINGS.de.top_stories);
  assertStringIncludes(html, EMAIL_STRINGS.de.email_disclaimer);
});

Deno.test("Civic Scout localizes to French", () => {
  const html = renderCivicScoutHtml("fr");
  assertStringIncludes(html, EMAIL_STRINGS.fr.civic_scout);
  assertStringIncludes(html, EMAIL_STRINGS.fr.email_disclaimer);
});

Deno.test("Social Scout localizes to Spanish", () => {
  const html = renderSocialScoutHtml("es");
  assertStringIncludes(html, EMAIL_STRINGS.es.social_scout);
  assertStringIncludes(html, EMAIL_STRINGS.es.new_posts);
  assertStringIncludes(html, EMAIL_STRINGS.es.email_disclaimer);
});

Deno.test("every scout type renders without errors in every supported language", () => {
  for (const lang of SUPPORTED_LANGUAGES) {
    for (
      const [renderName, render] of Object.entries({
        page: renderPageScoutHtml,
        beat: renderBeatScoutHtml,
        civic: renderCivicScoutHtml,
        social: renderSocialScoutHtml,
      })
    ) {
      const html = render(lang);
      assert(
        html.length > 0,
        `empty render for ${renderName}/${lang}`,
      );
      assertStringIncludes(
        html,
        EMAIL_STRINGS[lang].email_disclaimer,
        `${renderName}/${lang} missing disclaimer`,
      );
    }
  }
});

// ---------------------------------------------------------------------------
// Template structure invariants.
// ---------------------------------------------------------------------------

Deno.test("base template has DOCTYPE and body wrapper", () => {
  const html = renderBeatScoutHtml();
  assertStringIncludes(html, "<!DOCTYPE html>");
  assertStringIncludes(html, "<body");
  assertStringIncludes(html, 'max-width: 600px');
});

Deno.test("base template closes all opened major tags", () => {
  const html = renderBeatScoutHtml();
  const opens = (re: RegExp) => (html.match(re) ?? []).length;
  // Rough balance check — not a parser, just catches obvious leaks.
  assertEquals(opens(/<body/g), opens(/<\/body>/g));
  assertEquals(opens(/<html/g), opens(/<\/html>/g));
});

Deno.test("Social Scout drops removed-posts section when none provided", () => {
  const html = renderSocialScoutHtml();
  assert(!html.includes("Removed Posts"));
});

Deno.test("renderArticleCards truncates summary over 150 chars", () => {
  const long = "x".repeat(200);
  const html = renderArticleCards(
    [{ title: "t", url: "https://t", summary: long }],
    "#000",
  );
  assertStringIncludes(html, "...");
  assert(!html.includes("x".repeat(160)), "not truncated");
});

Deno.test("markdownToHtml handles empty string", () => {
  assertEquals(markdownToHtml(""), "");
});

Deno.test("markdownToHtml wraps bare text in a paragraph", () => {
  const html = markdownToHtml("just one line");
  assertStringIncludes(html, "<p");
  assertStringIncludes(html, "just one line");
});

Deno.test("getString preserves Unicode without mangling", () => {
  // German disclaimer contains ä (\u00e4) in 'enthält'.
  assertStringIncludes(getString("email_disclaimer", "de"), "\u00e4");
  // Finnish disclaimer contains ä in 'sähköposti'.
  assertStringIncludes(getString("email_disclaimer", "fi"), "\u00e4");
});

Deno.test("base template inlines all styles (no external <link> or <style>)", () => {
  const html = renderBeatScoutHtml();
  // Inline style attrs on key elements — these emails have to render in Gmail
  // / Outlook which strip <style> blocks.
  assert(!html.includes("<link"));
  assert(!html.includes("<style"));
  assertStringIncludes(html, 'style="');
});
