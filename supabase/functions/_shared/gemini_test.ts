import {
  assertEquals,
  assertRejects,
} from "https://deno.land/std@0.224.0/assert/mod.ts";
import {
  formatGeminiEmbedText,
  geminiEmbed,
} from "./gemini.ts";

Deno.test("formatGeminiEmbedText prefixes retrieval query text", () => {
  assertEquals(
    formatGeminiEmbedText("housing policy", "RETRIEVAL_QUERY"),
    "task: search result | query: housing policy",
  );
});

Deno.test("formatGeminiEmbedText prefixes retrieval document text with title", () => {
  assertEquals(
    formatGeminiEmbedText("body", "RETRIEVAL_DOCUMENT", "Council Minutes"),
    "title: Council Minutes | text: body",
  );
  assertEquals(
    formatGeminiEmbedText("body", "RETRIEVAL_DOCUMENT", null),
    "title: none | text: body",
  );
});

Deno.test("geminiEmbed sends prefixed text without taskType", async () => {
  const originalFetch = globalThis.fetch;
  const originalKey = Deno.env.get("GEMINI_API_KEY");
  Deno.env.set("GEMINI_API_KEY", "test-key");

  let capturedBody = "";
  globalThis.fetch = (async (_input: RequestInfo | URL, init?: RequestInit) => {
    capturedBody = String(init?.body ?? "");
    return new Response(
      JSON.stringify({
        embedding: { values: new Array(1536).fill(0).map((_v, i) => (i === 0 ? 1 : 0)) },
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    );
  }) as typeof fetch;

  try {
    const result = await geminiEmbed("body", "RETRIEVAL_DOCUMENT", {
      title: "Weekly digest",
    });
    assertEquals(result.length, 1536);
    const payload = JSON.parse(capturedBody);
    assertEquals(payload.content.parts[0].text, "title: Weekly digest | text: body");
    assertEquals("taskType" in payload, false);
  } finally {
    globalThis.fetch = originalFetch;
    if (originalKey === undefined) Deno.env.delete("GEMINI_API_KEY");
    else Deno.env.set("GEMINI_API_KEY", originalKey);
  }
});

Deno.test("geminiEmbed rejects malformed embedding responses", async () => {
  const originalFetch = globalThis.fetch;
  const originalKey = Deno.env.get("GEMINI_API_KEY");
  Deno.env.set("GEMINI_API_KEY", "test-key");

  globalThis.fetch = (async () =>
    new Response(
      JSON.stringify({ embedding: { values: [1, 2, 3] } }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    )) as typeof fetch;

  try {
    await assertRejects(
      () => geminiEmbed("body", "RETRIEVAL_QUERY"),
      Error,
      "unexpected embedding shape",
    );
  } finally {
    globalThis.fetch = originalFetch;
    if (originalKey === undefined) Deno.env.delete("GEMINI_API_KEY");
    else Deno.env.set("GEMINI_API_KEY", originalKey);
  }
});
