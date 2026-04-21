/**
 * ingest Edge Function — manual content ingestion pipeline.
 *
 * Accepts a URL or raw text, fetches/stores the content as a raw_capture,
 * then extracts atomic information_units via Gemini with embeddings.
 *
 * Route:
 *   POST /ingest
 *     body: { kind: "url"|"text", url?, text?, title?, criteria?, notes?, project_id? }
 *     -> 201 { ingest_id, raw_capture_id, units: [{id, statement}] }
 *
 * Auth: requireUser. All inserts go through the user-scoped client so RLS
 * enforces ownership. Failures mark the ingests row status=error with the
 * truncated error message.
 */

import { z } from "https://esm.sh/zod@3";
import { handleCors } from "../_shared/cors.ts";
import { requireUser, AuthedUser } from "../_shared/auth.ts";
import { getUserClient, SupabaseClient } from "../_shared/supabase.ts";
import { jsonError, jsonFromError, jsonOk } from "../_shared/responses.ts";
import { ValidationError } from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";
import { firecrawlScrape } from "../_shared/firecrawl.ts";
import { geminiEmbed, geminiExtract } from "../_shared/gemini.ts";

const IngestSchema = z
  .object({
    kind: z.enum(["url", "text"]),
    url: z.string().url().optional(),
    text: z.string().optional(),
    title: z.string().max(500).optional(),
    criteria: z.string().max(4000).optional(),
    notes: z.string().max(8000).optional(),
    project_id: z.string().uuid().optional(),
  })
  .superRefine((val, ctx) => {
    if (val.kind === "url" && !val.url) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["url"],
        message: "url is required when kind=url",
      });
    }
    if (val.kind === "text") {
      if (!val.text || val.text.length < 50) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["text"],
          message: "text is required (min 50 chars) when kind=text",
        });
      }
    }
  });

type IngestInput = z.infer<typeof IngestSchema>;

const EXTRACTION_SCHEMA: Record<string, unknown> = {
  type: "object",
  properties: {
    units: {
      type: "array",
      items: {
        type: "object",
        properties: {
          statement: { type: "string" },
          type: { type: "string", enum: ["fact", "event", "entity_update"] },
          context_excerpt: { type: "string" },
          occurred_at: { type: "string", nullable: true },
        },
        required: ["statement", "type"],
      },
    },
  },
  required: ["units"],
};

interface ExtractedUnit {
  statement: string;
  type: "fact" | "event" | "entity_update";
  context_excerpt?: string;
  occurred_at?: string | null;
}

const RAW_CONTENT_MAX = 100_000;
const PROMPT_CONTENT_MAX = 12_000;

Deno.serve(async (req): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  let user: AuthedUser;
  try {
    user = await requireUser(req);
  } catch (e) {
    return jsonFromError(e);
  }

  const url = new URL(req.url);
  const path = url.pathname.replace(/^.*\/ingest/, "") || "/";

  if (path !== "/" || req.method !== "POST") {
    return jsonError("method not allowed", 405);
  }

  try {
    return await handleIngest(req, user);
  } catch (e) {
    logEvent({
      level: "error",
      fn: "ingest",
      event: "unhandled",
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonFromError(e);
  }
});

// ---------------------------------------------------------------------------

async function handleIngest(req: Request, user: AuthedUser): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    throw new ValidationError("invalid JSON body");
  }
  const parsed = IngestSchema.safeParse(body);
  if (!parsed.success) {
    throw new ValidationError(
      parsed.error.issues.map((i) => i.message).join("; "),
    );
  }
  const input = parsed.data;

  const db = getUserClient(user.token);

  // 1. Create ingests row (status=processing).
  const { data: ingest, error: insErr } = await db
    .from("ingests")
    .insert({
      user_id: user.id,
      kind: input.kind,
      source_url: input.kind === "url" ? input.url : null,
      title: input.title ?? null,
      criteria: input.criteria ?? null,
      notes: input.notes ?? null,
      project_id: input.project_id ?? null,
      status: "processing",
    })
    .select("*")
    .single();
  if (insErr) throw new Error(insErr.message);

  const ingestId = ingest.id as string;

  try {
    const result = await runPipeline(db, user, ingestId, input);

    await db
      .from("ingests")
      .update({ status: "success", completed_at: new Date().toISOString() })
      .eq("id", ingestId);

    logEvent({
      level: "info",
      fn: "ingest",
      event: "success",
      user_id: user.id,
      ingest_id: ingestId,
      raw_capture_id: result.raw_capture_id,
      unit_count: result.units.length,
    });

    return jsonOk(
      {
        ingest_id: ingestId,
        raw_capture_id: result.raw_capture_id,
        units: result.units,
      },
      201,
    );
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    await db
      .from("ingests")
      .update({
        status: "error",
        error_message: msg.slice(0, 2000),
        completed_at: new Date().toISOString(),
      })
      .eq("id", ingestId);

    logEvent({
      level: "error",
      fn: "ingest",
      event: "failed",
      user_id: user.id,
      ingest_id: ingestId,
      msg,
    });
    throw e;
  }
}

interface PipelineResult {
  raw_capture_id: string;
  units: Array<{ id: string; statement: string }>;
}

async function runPipeline(
  db: SupabaseClient,
  user: AuthedUser,
  ingestId: string,
  input: IngestInput,
): Promise<PipelineResult> {
  // 2. Fetch content.
  let content: string;
  let sourceUrl: string | null = null;
  let sourceTitle: string | null = input.title ?? null;

  if (input.kind === "url") {
    sourceUrl = input.url!;
    const scrape = await firecrawlScrape(sourceUrl);
    content = scrape.markdown ?? "";
    if (!sourceTitle && scrape.title) sourceTitle = scrape.title;
  } else {
    content = input.text!;
  }

  if (!content || !content.trim()) {
    throw new ValidationError("no content to ingest");
  }

  const truncated = content.slice(0, RAW_CONTENT_MAX);

  // 3. Hash + raw_capture insert.
  const contentHash = await sha256Hex(truncated);
  const sourceDomain = sourceUrl ? safeDomain(sourceUrl) : null;

  const { data: capture, error: capErr } = await db
    .from("raw_captures")
    .insert({
      user_id: user.id,
      ingest_id: ingestId,
      source_url: sourceUrl,
      source_domain: sourceDomain,
      content_md: truncated,
      content_sha256: contentHash,
      token_count: Math.ceil(truncated.length / 4),
      captured_at: new Date().toISOString(),
    })
    .select("id")
    .single();
  if (capErr) throw new Error(capErr.message);
  const rawCaptureId = capture.id as string;

  // 4. Extract units via Gemini.
  const promptText = truncated.slice(0, PROMPT_CONTENT_MAX);
  const prompt =
    "Extract up to 15 discrete factual statements from the following text. " +
    "For each, give a one-sentence `statement`, a `type` (fact|event|entity_update), " +
    "a `context_excerpt` (a short quoted snippet surrounding the statement), and " +
    "`occurred_at` as a date in ISO 8601 if one is stated (null otherwise). " +
    "Return JSON matching the provided schema.\n\nTEXT:\n" +
    promptText;

  const extraction = await geminiExtract<{ units: ExtractedUnit[] }>(
    prompt,
    EXTRACTION_SCHEMA,
  );
  const extracted = Array.isArray(extraction?.units) ? extraction.units : [];

  // 5. Embed + insert each unit.
  const inserted: Array<{ id: string; statement: string }> = [];
  for (const u of extracted) {
    if (!u || typeof u.statement !== "string" || !u.statement.trim()) continue;
    if (!["fact", "event", "entity_update"].includes(u.type)) continue;

    const embedding = await geminiEmbed(u.statement, "RETRIEVAL_DOCUMENT");

    const { data: unitRow, error: unitErr } = await db
      .from("information_units")
      .insert({
        user_id: user.id,
        statement: u.statement,
        type: u.type,
        context_excerpt: u.context_excerpt ?? null,
        occurred_at: normalizeDate(u.occurred_at),
        source_url: sourceUrl,
        source_title: sourceTitle,
        source_domain: sourceDomain,
        extracted_at: new Date().toISOString(),
        source_type: "manual_ingest",
        raw_capture_id: rawCaptureId,
        project_id: input.project_id ?? null,
        embedding,
        embedding_model: "gemini-embedding-2-preview",
        used_in_article: false,
      })
      .select("id, statement")
      .single();

    if (unitErr) throw new Error(unitErr.message);
    inserted.push({
      id: unitRow.id as string,
      statement: unitRow.statement as string,
    });
  }

  return { raw_capture_id: rawCaptureId, units: inserted };
}

// ---------------------------------------------------------------------------

async function sha256Hex(input: string): Promise<string> {
  const buf = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function safeDomain(raw: string): string | null {
  try {
    return new URL(raw).hostname;
  } catch {
    return null;
  }
}

function normalizeDate(v: string | null | undefined): string | null {
  if (!v) return null;
  const trimmed = v.trim();
  if (!trimmed) return null;
  // Accept full ISO 8601; store as YYYY-MM-DD for DATE column.
  const match = trimmed.match(/^(\d{4}-\d{2}-\d{2})/);
  if (match) return match[1];
  const d = new Date(trimmed);
  if (isNaN(d.getTime())) return null;
  return d.toISOString().slice(0, 10);
}
