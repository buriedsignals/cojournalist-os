/**
 * MCP (Model Context Protocol) JSON-RPC 2.0 dispatcher + tool handlers.
 *
 * Wired into mcp-server/index.ts on `POST /`. Validates the caller's bearer
 * token (Supabase user JWT or `cj_<api_key>`), then forwards each tool call
 * to the sibling EF that owns the resource. This keeps auth, RLS, validation,
 * and audit paths in one place (the resource EFs) and lets the MCP server
 * stay a thin protocol adapter.
 *
 * Implements MCP 2024-11-05:
 *   - `initialize`        → capabilities handshake
 *   - `tools/list`        → enumerate tools + JSON Schema inputs
 *   - `tools/call`        → dispatch to the named handler
 *   - `notifications/initialized` → no-op (MCP spec: client finished init)
 *   - Anything else       → JSON-RPC method-not-found error
 *
 * Tool naming follows `verb_noun` to match the public-facing skill doc at
 * https://www.cojournalist.ai/skill.md (e.g. `list_scouts`, `create_scout`).
 * When adding a tool, update the skill doc in the same PR — the skill is
 * the advertised contract.
 */

import { requireUserOrApiKey, AuthedUser } from "../_shared/auth.ts";
import { logEvent } from "../_shared/log.ts";

const PROTOCOL_VERSION = "2024-11-05";
const SERVER_NAME = "cojournalist";
const SERVER_VERSION = "0.3.0";

// ---------------------------------------------------------------------------
// Forwarder
// ---------------------------------------------------------------------------

function efUrl(fn: string, path = ""): string {
  const base = (Deno.env.get("SUPABASE_URL") ?? "").replace(/\/$/, "");
  return `${base}/functions/v1/${fn}${path}`;
}

async function forward(
  token: string,
  method: string,
  fn: string,
  path: string,
  init: {
    query?: Record<string, string>;
    body?: unknown;
    accept?: string;
  } = {},
): Promise<unknown> {
  const url = new URL(efUrl(fn, path));
  for (const [k, v] of Object.entries(init.query ?? {})) {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  }
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };
  const anon = Deno.env.get("SUPABASE_ANON_KEY");
  if (anon) headers["apikey"] = anon;
  let body: BodyInit | undefined;
  if (init.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.body);
  }
  if (init.accept) headers["Accept"] = init.accept;

  const res = await fetch(url.toString(), { method, headers, body });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`${fn} ${method} ${path} → ${res.status} ${text.slice(0, 400)}`);
  }
  if (init.accept === "text/markdown") return text;
  return text ? JSON.parse(text) : null;
}

function q(args: Record<string, unknown>, keys: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const k of keys) {
    const v = args[k];
    if (v === undefined || v === null || v === "") continue;
    out[k] = typeof v === "boolean" ? String(v) : String(v);
  }
  return out;
}

// ---------------------------------------------------------------------------
// Tools
// ---------------------------------------------------------------------------

interface ToolDef {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  handler: (user: AuthedUser, token: string, args: Record<string, unknown>) => Promise<unknown>;
}

const TOOLS: ToolDef[] = [
  // ---------- Scouts ----------
  {
    name: "list_scouts",
    description: "List all scouts owned by the caller (id, name, type, schedule, is_active).",
    inputSchema: {
      type: "object",
      properties: {
        limit: { type: "integer", minimum: 1, maximum: 200 },
        offset: { type: "integer", minimum: 0 },
        type: { type: "string", enum: ["web", "pulse", "social", "civic"] },
      },
    },
    handler: (_u, token, args) =>
      forward(token, "GET", "scouts", "", { query: q(args, ["limit", "offset", "type"]) }),
  },
  {
    name: "create_scout",
    description:
      "Create a new scout. Required: name, type (web|pulse|social|civic). For web, pass url. For pulse, pass location and/or criteria+topic. Scheduling: pass `schedule_cron` OR `regularity` + `time` (+ `day_number` for weekly/monthly).",
    inputSchema: {
      type: "object",
      required: ["name", "type"],
      properties: {
        name: { type: "string", minLength: 1, maxLength: 200 },
        type: { type: "string", enum: ["web", "pulse", "social", "civic"] },
        criteria: { type: "string", maxLength: 4000 },
        topic: { type: "string", maxLength: 200 },
        url: { type: "string", format: "uri" },
        location: {
          type: "object",
          additionalProperties: true,
          description: "GeocodedLocation: { displayName, latitude, longitude, ... }",
        },
        regularity: { type: "string", enum: ["daily", "weekly", "monthly"] },
        schedule_cron: { type: "string", maxLength: 200 },
        day_number: { type: "integer", minimum: 0, maximum: 31 },
        time: { type: "string", pattern: "^\\d{1,2}:\\d{2}$" },
        provider: { type: "string" },
        project_id: { type: "string", format: "uuid" },
        priority_sources: { type: "array", items: { type: "string" } },
      },
    },
    handler: (_u, token, args) => forward(token, "POST", "scouts", "", { body: args }),
  },
  {
    name: "get_scout",
    description: "Fetch a single scout by id.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: { id: { type: "string", format: "uuid" } },
    },
    handler: (_u, token, args) => forward(token, "GET", "scouts", `/${String(args.id)}`),
  },
  {
    name: "update_scout",
    description:
      "Patch an existing scout (name, schedule, criteria, is_active). All fields optional; only sent keys change.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: {
        id: { type: "string", format: "uuid" },
        name: { type: "string", minLength: 1, maxLength: 200 },
        criteria: { type: "string" },
        topic: { type: "string" },
        url: { type: "string", format: "uri" },
        regularity: { type: "string", enum: ["daily", "weekly", "monthly"] },
        schedule_cron: { type: "string" },
        day_number: { type: "integer", minimum: 0, maximum: 31 },
        time: { type: "string", pattern: "^\\d{1,2}:\\d{2}$" },
        is_active: { type: "boolean" },
        project_id: { type: "string", format: "uuid" },
      },
    },
    handler: (_u, token, args) => {
      const { id, ...patch } = args;
      return forward(token, "PATCH", "scouts", `/${String(id)}`, { body: patch });
    },
  },
  {
    name: "run_scout",
    description: "Trigger an on-demand scout run. Spends credits. Returns 202 + run_id.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: { id: { type: "string", format: "uuid" } },
    },
    handler: (_u, token, args) =>
      forward(token, "POST", "scouts", `/${String(args.id)}/run`, { body: {} }),
  },
  {
    name: "pause_scout",
    description: "Pause a scout: set is_active=false and unschedule its cron job.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: { id: { type: "string", format: "uuid" } },
    },
    handler: (_u, token, args) =>
      forward(token, "POST", "scouts", `/${String(args.id)}/pause`, { body: {} }),
  },
  {
    name: "resume_scout",
    description: "Resume a paused scout: set is_active=true and re-schedule its cron job.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: { id: { type: "string", format: "uuid" } },
    },
    handler: (_u, token, args) =>
      forward(token, "POST", "scouts", `/${String(args.id)}/resume`, { body: {} }),
  },
  {
    name: "delete_scout",
    description: "Delete a scout and unschedule its cron job.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: { id: { type: "string", format: "uuid" } },
    },
    handler: (_u, token, args) => forward(token, "DELETE", "scouts", `/${String(args.id)}`),
  },

  // ---------- Units ----------
  {
    name: "list_units",
    description:
      "List information units owned by the caller. Pass `verified=false` for the editorial inbox (needs-review queue). Pass `used_in_article=false` to exclude already-used units.",
    inputSchema: {
      type: "object",
      properties: {
        project_id: { type: "string", format: "uuid" },
        limit: { type: "integer", minimum: 1, maximum: 200 },
        offset: { type: "integer", minimum: 0 },
        verified: { type: "boolean" },
        used_in_article: { type: "boolean" },
      },
    },
    handler: (_u, token, args) =>
      forward(token, "GET", "units", "", {
        query: q(args, ["project_id", "limit", "offset", "verified", "used_in_article"]),
      }),
  },
  {
    name: "search_units",
    description: "Semantic search over the caller's information units.",
    inputSchema: {
      type: "object",
      required: ["query_text"],
      properties: {
        query_text: { type: "string", minLength: 1, maxLength: 4000 },
        project_id: { type: "string", format: "uuid" },
        limit: { type: "integer", minimum: 1, maximum: 100 },
      },
    },
    handler: (_u, token, args) => forward(token, "POST", "units", "/search", { body: args }),
  },
  {
    name: "get_unit",
    description: "Fetch a single information unit by id.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: { id: { type: "string", format: "uuid" } },
    },
    handler: (_u, token, args) => forward(token, "GET", "units", `/${String(args.id)}`),
  },
  {
    name: "verify_unit",
    description:
      "Verify a unit (accept it for editorial use). Sets verified=true, optional verification_notes and verified_by.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: {
        id: { type: "string", format: "uuid" },
        verification_notes: { type: "string", maxLength: 4000 },
        verified_by: { type: "string", maxLength: 200 },
      },
    },
    handler: (_u, token, args) => {
      const { id, ...rest } = args;
      return forward(token, "PATCH", "units", `/${String(id)}`, {
        body: { verified: true, ...rest },
      });
    },
  },
  {
    name: "reject_unit",
    description:
      "Reject a unit (not wanted editorially). Sets verified=false and records the reason in verification_notes.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: {
        id: { type: "string", format: "uuid" },
        verification_notes: { type: "string", maxLength: 4000, description: "Reason for rejection" },
        verified_by: { type: "string", maxLength: 200 },
      },
    },
    handler: (_u, token, args) => {
      const { id, ...rest } = args;
      return forward(token, "PATCH", "units", `/${String(id)}`, {
        body: { verified: false, ...rest },
      });
    },
  },
  {
    name: "mark_unit_used",
    description:
      "Flag a unit as used in a published article so it leaves the inbox. Optionally record the URL and timestamp.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: {
        id: { type: "string", format: "uuid" },
        used_in_url: { type: "string", format: "uri" },
        used_at: { type: "string", format: "date-time" },
      },
    },
    handler: (_u, token, args) => {
      const { id, ...rest } = args;
      return forward(token, "PATCH", "units", `/${String(id)}`, {
        body: { used_in_article: true, ...rest },
      });
    },
  },
  {
    name: "delete_unit",
    description: "Delete an information unit by id.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: { id: { type: "string", format: "uuid" } },
    },
    handler: (_u, token, args) => forward(token, "DELETE", "units", `/${String(args.id)}`),
  },

  // ---------- Projects ----------
  {
    name: "list_projects",
    description: "List investigation projects owned by the caller.",
    inputSchema: {
      type: "object",
      properties: {
        limit: { type: "integer", minimum: 1, maximum: 200 },
        offset: { type: "integer", minimum: 0 },
      },
    },
    handler: (_u, token, args) =>
      forward(token, "GET", "projects", "", { query: q(args, ["limit", "offset"]) }),
  },
  {
    name: "create_project",
    description: "Create a new investigation project (a workspace for grouping scouts + units).",
    inputSchema: {
      type: "object",
      required: ["name"],
      properties: {
        name: { type: "string", minLength: 1, maxLength: 120 },
        description: { type: "string", maxLength: 2000 },
        visibility: { type: "string", enum: ["private", "team"], default: "private" },
        tags: { type: "array", items: { type: "string" }, maxItems: 30 },
      },
    },
    handler: (_u, token, args) => forward(token, "POST", "projects", "", { body: args }),
  },
  {
    name: "get_project",
    description: "Fetch a single project by id.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: { id: { type: "string", format: "uuid" } },
    },
    handler: (_u, token, args) => forward(token, "GET", "projects", `/${String(args.id)}`),
  },
  {
    name: "update_project",
    description: "Patch a project — name, description, visibility, or tags.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: {
        id: { type: "string", format: "uuid" },
        name: { type: "string", minLength: 1, maxLength: 120 },
        description: { type: "string", maxLength: 2000 },
        visibility: { type: "string", enum: ["private", "team"] },
        tags: { type: "array", items: { type: "string" }, maxItems: 30 },
      },
    },
    handler: (_u, token, args) => {
      const { id, ...patch } = args;
      return forward(token, "PATCH", "projects", `/${String(id)}`, { body: patch });
    },
  },
  {
    name: "delete_project",
    description: "Delete a project by id.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: { id: { type: "string", format: "uuid" } },
    },
    handler: (_u, token, args) => forward(token, "DELETE", "projects", `/${String(args.id)}`),
  },

  // ---------- Ingest ----------
  {
    name: "ingest_content",
    description:
      "Ingest a URL or raw text into the knowledge base. Creates a raw_capture row and extracts atomic information_units via Gemini.",
    inputSchema: {
      type: "object",
      required: ["kind"],
      properties: {
        kind: { type: "string", enum: ["url", "text"] },
        url: { type: "string", format: "uri", description: "Required when kind=url" },
        text: { type: "string", description: "Required when kind=text" },
        title: { type: "string" },
        criteria: { type: "string", description: "Optional extraction criteria" },
        notes: { type: "string" },
        project_id: { type: "string", format: "uuid" },
      },
    },
    handler: (_u, token, args) => forward(token, "POST", "ingest", "", { body: args }),
  },

  // ---------- Export ----------
  {
    name: "export_project_to_claude",
    description:
      "Export a project's verified, unused information units as a markdown brief suitable for piping to an LLM.",
    inputSchema: {
      type: "object",
      properties: {
        project_id: { type: "string", format: "uuid" },
        limit: { type: "integer", minimum: 1, maximum: 500 },
      },
    },
    handler: (_u, token, args) =>
      forward(token, "GET", "export-claude", "", {
        query: q(args, ["project_id", "limit"]),
        accept: "text/markdown",
      }),
  },

  // ---------- Reflections ----------
  {
    name: "list_reflections",
    description: "List editorial reflections (agent-written synthesized summaries) owned by the caller.",
    inputSchema: {
      type: "object",
      properties: {
        limit: { type: "integer", minimum: 1, maximum: 200 },
        offset: { type: "integer", minimum: 0 },
      },
    },
    handler: (_u, token, args) =>
      forward(token, "GET", "reflections", "", { query: q(args, ["limit", "offset"]) }),
  },
  {
    name: "create_reflection",
    description:
      "Create a reflection (durable editorial note) over scouts, units, or entities. Embedded at write time for semantic search.",
    inputSchema: {
      type: "object",
      required: ["scope_description", "content"],
      properties: {
        scope_description: { type: "string", minLength: 1 },
        content: { type: "string", minLength: 1 },
        unit_ids: { type: "array", items: { type: "string", format: "uuid" } },
        entity_ids: { type: "array", items: { type: "string", format: "uuid" } },
        scout_ids: { type: "array", items: { type: "string", format: "uuid" } },
      },
    },
    handler: (_u, token, args) => forward(token, "POST", "reflections", "", { body: args }),
  },
  {
    name: "search_reflections",
    description: "Semantic search over the caller's reflections.",
    inputSchema: {
      type: "object",
      required: ["query_text"],
      properties: {
        query_text: { type: "string", minLength: 1, maxLength: 4000 },
        limit: { type: "integer", minimum: 1, maximum: 100 },
      },
    },
    handler: (_u, token, args) =>
      forward(token, "POST", "reflections", "/search", { body: args }),
  },

  // ---------- Entities ----------
  {
    name: "search_entities",
    description:
      "Find canonical entities (people, orgs, places, policies) across the knowledge base. Returns entity rows with type + canonical_name.",
    inputSchema: {
      type: "object",
      properties: {
        search: { type: "string", description: "Substring match on canonical_name" },
        type: { type: "string", enum: ["person", "org", "place", "policy"] },
        limit: { type: "integer", minimum: 1, maximum: 200 },
        offset: { type: "integer", minimum: 0 },
      },
    },
    handler: (_u, token, args) =>
      forward(token, "GET", "entities", "", { query: q(args, ["search", "type", "limit", "offset"]) }),
  },
  {
    name: "merge_entities",
    description:
      "Collapse duplicate entities into a single keeper. Use after `search_entities` surfaces near-duplicates.",
    inputSchema: {
      type: "object",
      required: ["keeper_id", "merge_ids"],
      properties: {
        keeper_id: { type: "string", format: "uuid" },
        merge_ids: {
          type: "array",
          items: { type: "string", format: "uuid" },
          minItems: 1,
        },
      },
    },
    handler: (_u, token, args) => forward(token, "POST", "entities", "/merge", { body: args }),
  },
];

const TOOL_BY_NAME = new Map(TOOLS.map((t) => [t.name, t]));

// ---------------------------------------------------------------------------
// JSON-RPC 2.0
// ---------------------------------------------------------------------------

interface JsonRpcRequest {
  jsonrpc: "2.0";
  id?: string | number | null;
  method: string;
  params?: Record<string, unknown>;
}

interface JsonRpcErrorBody {
  code: number;
  message: string;
  data?: unknown;
}

function rpcOk(id: unknown, result: unknown): Response {
  return new Response(JSON.stringify({ jsonrpc: "2.0", id: id ?? null, result }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function rpcErr(id: unknown, err: JsonRpcErrorBody, httpStatus = 200): Response {
  return new Response(JSON.stringify({ jsonrpc: "2.0", id: id ?? null, error: err }), {
    status: httpStatus,
    headers: { "Content-Type": "application/json" },
  });
}

async function readRpcBody(req: Request): Promise<JsonRpcRequest | null> {
  try {
    const body = (await req.json()) as JsonRpcRequest;
    if (body?.jsonrpc !== "2.0" || typeof body.method !== "string") return null;
    return body;
  } catch {
    return null;
  }
}

export async function handleRpc(req: Request): Promise<Response> {
  const body = await readRpcBody(req);
  if (!body) {
    return rpcErr(null, { code: -32700, message: "Parse error" }, 400);
  }

  // Unauthenticated methods — spec-mandated handshake.
  if (body.method === "initialize") {
    return rpcOk(body.id, {
      protocolVersion: PROTOCOL_VERSION,
      serverInfo: { name: SERVER_NAME, version: SERVER_VERSION },
      capabilities: { tools: { listChanged: false } },
    });
  }
  if (body.method === "notifications/initialized") {
    // JSON-RPC notification — no response. Deno.serve still needs a 202.
    return new Response(null, { status: 202 });
  }

  let user: AuthedUser;
  let token: string;
  try {
    user = await requireUserOrApiKey(req);
    const header = req.headers.get("authorization") ?? req.headers.get("Authorization") ?? "";
    token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
    if (!token) {
      return rpcErr(body.id, { code: -32001, message: "missing bearer token" });
    }
  } catch (e) {
    return rpcErr(body.id, {
      code: -32001,
      message: e instanceof Error ? e.message : "unauthorized",
    });
  }

  if (body.method === "tools/list") {
    return rpcOk(body.id, {
      tools: TOOLS.map((t) => ({
        name: t.name,
        description: t.description,
        inputSchema: t.inputSchema,
      })),
    });
  }

  if (body.method === "tools/call") {
    const params = body.params ?? {};
    const name = typeof params.name === "string" ? params.name : "";
    const args = (params.arguments as Record<string, unknown> | undefined) ?? {};
    const tool = TOOL_BY_NAME.get(name);
    if (!tool) {
      return rpcErr(body.id, { code: -32602, message: `unknown tool: ${name}` });
    }
    try {
      const result = await tool.handler(user, token, args);
      const text = typeof result === "string" ? result : JSON.stringify(result);
      return rpcOk(body.id, {
        content: [{ type: "text", text }],
        isError: false,
      });
    } catch (e) {
      logEvent({
        level: "error",
        fn: "mcp-server",
        event: "tool_call_failed",
        user_id: user.id,
        msg: `${name}: ${e instanceof Error ? e.message : String(e)}`,
      });
      return rpcOk(body.id, {
        content: [{ type: "text", text: e instanceof Error ? e.message : String(e) }],
        isError: true,
      });
    }
  }

  return rpcErr(body.id, { code: -32601, message: `Method not found: ${body.method}` });
}
