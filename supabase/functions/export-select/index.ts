/**
 * export-select Edge Function — LLM auto-selection of information units.
 *
 * Picks the most relevant units from a candidate list based on a user prompt
 * (e.g. "the most important budget decisions for a city council article")
 * and returns the selected unit IDs + a one-paragraph rationale.
 *
 * Route:
 *   POST /export-select
 *     body: {
 *       units: [{
 *         unit_id, statement, entities[], source_title,
 *         created_at, date, unit_type, scout_type
 *       }],
 *       prompt: string,           // user-supplied "pick units that match X"
 *       location?: string | null,
 *       topic?: string | null
 *     }
 *     -> 200 {
 *          selected_unit_ids: string[],
 *          selection_summary: string  // one paragraph explaining the choice
 *        }
 *
 * Auth: requireUser. Uses the user-scoped client only for logging — the
 * Gemini call is server-side and doesn't read Postgres (the units list is
 * passed in by the caller, who has already RLS-filtered them).
 */

import { handleCors } from "../_shared/cors.ts";
import { AuthedUser, requireUser } from "../_shared/auth.ts";
import { jsonError, jsonFromError, jsonOk } from "../_shared/responses.ts";
import { ValidationError } from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";
import { geminiExtract } from "../_shared/gemini.ts";

interface UnitInput {
  unit_id: string;
  statement: string;
  entities: string[];
  source_title: string;
  created_at: string;
  date: string | null;
  unit_type: string;
  scout_type: string;
}

interface SelectResponse {
  selected_unit_ids: string[];
  selection_summary: string;
}

const SELECTION_SCHEMA = {
  type: "object",
  properties: {
    selected_unit_ids: {
      type: "array",
      items: { type: "string" },
    },
    selection_summary: { type: "string" },
  },
  required: ["selected_unit_ids", "selection_summary"],
};

Deno.serve(async (req): Promise<Response> => {
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

  let body: {
    units?: UnitInput[];
    prompt?: string;
    location?: string | null;
    topic?: string | null;
  };
  try {
    body = await req.json();
  } catch {
    return jsonError("invalid JSON body", 400);
  }

  const units = Array.isArray(body.units) ? body.units : [];
  const prompt = (body.prompt ?? "").trim();
  if (!prompt) {
    return jsonFromError(new ValidationError("prompt is required"));
  }
  if (units.length === 0) {
    return jsonOk({
      selected_unit_ids: [],
      selection_summary: "No candidate units provided.",
    } satisfies SelectResponse);
  }

  // Compact the units into a list the model can scan: id + 1-line statement
  // + optional date/source. Skip embeddings/context to keep the prompt tight.
  const lines = units.map((u, i) => {
    const date = u.date ?? "—";
    const source = u.source_title || "(unknown source)";
    const entities = u.entities?.length ? ` [${u.entities.slice(0, 4).join(", ")}]` : "";
    return `${i + 1}. id=${u.unit_id} | ${u.unit_type} | ${date} | ${source}${entities}\n   ${u.statement}`;
  }).join("\n");

  const scope: string[] = [];
  if (body.location) scope.push(`Location: ${body.location}`);
  if (body.topic) scope.push(`Topic: ${body.topic}`);
  const scopeText = scope.length ? `\n\nContext:\n${scope.join("\n")}` : "";

  const llmPrompt = `You are helping a journalist assemble a story. From the
list of facts below, pick the ones that best match this brief:

  "${prompt}"
${scopeText}

Candidate facts:
${lines}

Return JSON with:
- selected_unit_ids: an array of the unit_id strings (from above) that
  should be used. Pick the most relevant 5-15. If fewer than 5 are
  genuinely on-topic, return only those. If none match, return [].
- selection_summary: one paragraph (~50-80 words) explaining the through-
  line of the selected facts and why they support the brief. Refer to
  the facts collectively, not by id.
`;

  let parsed: SelectResponse;
  try {
    parsed = await geminiExtract<SelectResponse>(
      llmPrompt,
      SELECTION_SCHEMA,
      {
        systemInstruction:
          "You are a precise editorial assistant. Always return valid JSON matching the requested schema.",
      },
    );
    // Defensive: ensure shape matches even if model wandered off-schema.
    if (!Array.isArray(parsed?.selected_unit_ids)) parsed.selected_unit_ids = [];
    if (typeof parsed?.selection_summary !== "string") parsed.selection_summary = "";

    // Sanity: filter selected ids to ones that were actually in the input.
    const validIds = new Set(units.map((u) => u.unit_id));
    parsed.selected_unit_ids = parsed.selected_unit_ids.filter((id) =>
      validIds.has(id)
    );

    logEvent({
      level: "info",
      fn: "export-select",
      event: "selected",
      user_id: user.id,
      input_count: units.length,
      selected_count: parsed.selected_unit_ids.length,
    });

    return jsonOk(parsed);
  } catch (e) {
    logEvent({
      level: "error",
      fn: "export-select",
      event: "unhandled",
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonFromError(e);
  }
});

export type { SelectResponse };
