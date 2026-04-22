/**
 * Gemini API client: embeddings (1536-dim) and structured extraction.
 *
 * Docs: https://ai.google.dev/api/rest/v1beta
 */

import { ApiError } from "./errors.ts";

const GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta";
const EMBED_MODEL = "models/gemini-embedding-2-preview";
const EMBED_DIM = 1536;

function geminiApiKey(): string {
  const k = Deno.env.get("GEMINI_API_KEY");
  if (!k) throw new ApiError("GEMINI_API_KEY not configured", 500);
  return k;
}

export type GeminiTaskType =
  | "SEMANTIC_SIMILARITY"
  | "RETRIEVAL_DOCUMENT"
  | "RETRIEVAL_QUERY"
  | "CLASSIFICATION"
  | "CLUSTERING";

export async function geminiEmbed(
  text: string,
  taskType: GeminiTaskType = "SEMANTIC_SIMILARITY",
): Promise<number[]> {
  const res = await fetch(
    `${GEMINI_BASE}/${EMBED_MODEL}:embedContent?key=${geminiApiKey()}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: { parts: [{ text }] },
        taskType,
        outputDimensionality: EMBED_DIM,
      }),
    },
  );
  if (!res.ok) {
    throw new ApiError(`gemini embed failed: ${res.status} ${await res.text()}`, 502);
  }
  const body = await res.json();
  const values = body?.embedding?.values;
  if (!Array.isArray(values) || values.length !== EMBED_DIM) {
    throw new ApiError(`unexpected embedding shape (len ${values?.length})`, 502);
  }
  return values as number[];
}

/**
 * JSON-schema-constrained generation. Returns the parsed object.
 *
 * `opts.systemInstruction` maps to Gemini's `system_instruction` field —
 * used to enforce persistent rules (language, role, format) separately
 * from the per-call user prompt.
 */
export async function geminiExtract<T>(
  prompt: string,
  schema: Record<string, unknown>,
  opts?: { model?: string; systemInstruction?: string } | string,
): Promise<T> {
  // Accept legacy `(prompt, schema, model)` call shape for backwards compat.
  const o = typeof opts === "string" ? { model: opts } : (opts ?? {});
  const modelId = o.model ?? Deno.env.get("LLM_MODEL") ?? "gemini-2.5-flash-lite";
  const requestBody: Record<string, unknown> = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: {
      responseMimeType: "application/json",
      responseSchema: schema,
    },
  };
  if (o.systemInstruction) {
    requestBody.system_instruction = {
      parts: [{ text: o.systemInstruction }],
    };
  }
  const res = await fetch(
    `${GEMINI_BASE}/models/${modelId}:generateContent?key=${geminiApiKey()}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    },
  );
  if (!res.ok) {
    throw new ApiError(`gemini extract failed: ${res.status} ${await res.text()}`, 502);
  }
  const body = await res.json();
  const text = body?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (typeof text !== "string") {
    throw new ApiError("gemini response missing text part", 502);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError(`gemini returned non-JSON: ${text.slice(0, 200)}`, 502);
  }
}
