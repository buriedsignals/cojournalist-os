import { assertEquals } from "https://deno.land/std@0.224.0/assert/assert_equals.ts";
import { assert } from "https://deno.land/std@0.224.0/assert/assert.ts";
import { compressContext, estimateTokens } from "./taco_compress.ts";

Deno.test("compressContext: empty string returns empty", () => {
  const { text, stats } = compressContext("");
  assertEquals(text, "");
  assertEquals(stats.originalChars, 0);
  assertEquals(stats.reductionPct, 0);
});

Deno.test("compressContext: plain article text passes through", () => {
  const input = "The city council of Zurich voted 8-3 to approve the new transit plan on Tuesday.\n\nMayor Anna Müller praised the decision.";
  const { text, stats } = compressContext(input);
  assertEquals(text, input);
  assertEquals(stats.reductionPct, 0);
});

Deno.test("compressContext: strips cookie consent banners", () => {
  const input = `# Local News

This article is about the mayor's decision.

We use cookies to improve your experience. Accept all cookies. Manage preferences.
Cookie policy: Read our cookie policy for more information.

The mayor announced the new policy today.`;
  const { text, stats } = compressContext(input);
  assert(!text.includes("cookie"), "cookie banner should be stripped");
  assert(text.includes("mayor"), "article content should be preserved");
  assert(stats.reductionPct > 0, "should show reduction");
  assert(stats.rulesApplied.includes("cookie_consent"));
});

Deno.test("compressContext: strips social sharing blocks", () => {
  const input = `Important news story here.

Share on Facebook
Share on Twitter
Share on LinkedIn
Share on WhatsApp

The investigation revealed new findings.`;
  const { text, stats } = compressContext(input);
  assert(!text.includes("Share on Facebook"), "social sharing should be stripped");
  assert(text.includes("investigation"), "article content should be preserved");
  assert(stats.rulesApplied.includes("social_sharing"));
});

Deno.test("compressContext: strips footer boilerplate", () => {
  const input = `Article content about local politics.

© 2025 Local News Corp. All rights reserved.
Terms of Service | Privacy Policy | Cookie Policy | Sitemap`;
  const { text, stats } = compressContext(input);
  assert(!text.includes("All rights reserved"), "copyright should be stripped");
  assert(text.includes("local politics"), "article content should be preserved");
  assert(stats.rulesApplied.includes("footer_boilerplate"));
});

Deno.test("compressContext: strips ad markers", () => {
  const input = `Breaking: new development in city hall.

Advertisement

Subscribe now to continue reading this article.
Already a subscriber? Sign in.

The council met yesterday.`;
  const { text, stats } = compressContext(input);
  assert(!text.includes("Advertisement"), "ad marker should be stripped");
  assert(!text.includes("Subscribe now"), "subscription prompt should be stripped");
  assert(text.includes("council met"), "article content should be preserved");
});

Deno.test("compressContext: strips related articles headers", () => {
  const input = `Main article about the budget vote.

## Related Articles

Some link to another article.

## You may also like

Another recommendation.`;
  const { text, stats } = compressContext(input);
  assert(!text.includes("Related Articles"), "related section should be stripped");
  assert(!text.includes("You may also like"), "recommendations should be stripped");
  assert(text.includes("budget vote"), "main content should be preserved");
});

Deno.test("compressContext: normalizes excessive whitespace", () => {
  const input = "Paragraph one.\n\n\n\n\n\n\nParagraph two.";
  const { text } = compressContext(input);
  assert(!text.includes("\n\n\n"), "should collapse excessive newlines");
  assert(text.includes("Paragraph one."), "content preserved");
  assert(text.includes("Paragraph two."), "content preserved");
});

Deno.test("compressContext: strips German-language boilerplate", () => {
  const input = `Nachrichten aus der Gemeinde.

Teilen auf Facebook
Teilen auf Twitter

Alle Rechte vorbehalten.
Datenschutzerklärung | Impressum | AGB`;
  const { text, stats } = compressContext(input);
  assert(!text.includes("Alle Rechte vorbehalten"), "German copyright stripped");
  assert(text.includes("Gemeinde"), "German content preserved");
});

Deno.test("compressContext: combined noise strips yield measurable reduction", () => {
  const noise = `[Home](/) | [About](/about) | [Contact](/contact) | [Search](/search) | [Login](/login)
[News](/news) | [Sports](/sports) | [Culture](/culture) | [Politics](/politics)

# Main Headline

The city council approved the $50M infrastructure plan on Monday.

Mayor Johnson cited "urgent need for road repairs" during the press conference.

## Comments

Leave a comment
Reply
Reply
Reply

Share on Facebook
Share on Twitter
Share on LinkedIn

© 2025 City Gazette. All rights reserved.
Terms of Service | Privacy Policy`;

  const { text, stats } = compressContext(noise);
  assert(stats.reductionPct >= 10, `expected >=10% reduction, got ${stats.reductionPct}%`);
  assert(text.includes("$50M infrastructure"), "key fact preserved");
  assert(text.includes("Mayor Johnson"), "key entity preserved");
});

Deno.test("compressContext: paywall prompts stripped", () => {
  const input = `First paragraph of the article.

This article is for subscribers only. Subscribe to continue reading.
Already a subscriber? Sign in.

Second paragraph with the actual news.`;
  const { text, stats } = compressContext(input);
  assert(!text.includes("subscribers only"), "paywall prompt should be stripped");
  assert(text.includes("actual news"), "article content should be preserved");
  assert(stats.rulesApplied.includes("paywall_prompts"));
});

Deno.test("estimateTokens: approximates correctly", () => {
  assertEquals(estimateTokens(""), 0);
  assertEquals(estimateTokens("abcd"), 1);
  assertEquals(estimateTokens("a".repeat(100)), 25);
});
