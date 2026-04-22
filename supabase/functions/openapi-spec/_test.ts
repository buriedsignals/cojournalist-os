/**
 * openapi-spec tests.
 *
 * Two layers:
 *
 *   Structural (offline, runs without Supabase) — imports spec.json and asserts
 *   every path + tool the product publicly commits to is present. Breaks
 *   immediately when someone drops a route or renames a field.
 *
 *   HTTP (online, requires `supabase start`) — verifies the EF actually serves
 *   the spec as application/json with the correct openapi version.
 */

import {
  assertEquals,
  assertExists,
  assertStringIncludes,
} from "https://deno.land/std@0.208.0/assert/mod.ts";
import spec from "./spec.json" with { type: "json" };
import { functionUrl } from "../_shared/_testing.ts";

type SpecDoc = {
  openapi: string;
  info: { title: string; version: string };
  paths: Record<string, Record<string, unknown>>;
  components: {
    schemas: Record<string, unknown>;
    securitySchemes: Record<string, unknown>;
  };
};

const doc = spec as unknown as SpecDoc;

// ---------------------------------------------------------------------------
// Offline structural assertions — catch drift the moment a route disappears.
// ---------------------------------------------------------------------------

const REQUIRED_PATHS: Array<[string, string[]]> = [
  ["/scouts", ["get", "post"]],
  ["/scouts/{id}", ["get", "patch", "delete"]],
  ["/scouts/{id}/run", ["post"]],
  ["/scouts/{id}/pause", ["post"]],
  ["/scouts/{id}/resume", ["post"]],
  ["/scouts/from-template", ["post"]],
  ["/units", ["get"]],
  ["/units/search", ["post"]],
  ["/units/{id}", ["get", "patch", "delete"]],
  ["/projects", ["get", "post"]],
  ["/projects/{id}", ["get", "patch", "delete"]],
  ["/entities", ["get", "post"]],
  ["/entities/merge", ["post"]],
  ["/reflections", ["get", "post"]],
  ["/reflections/search", ["post"]],
  ["/reflections/{id}", ["get", "delete"]],
  ["/ingest", ["post"]],
  ["/export-claude", ["get"]],
  ["/user/me", ["get"]],
  ["/user/preferences", ["get", "patch"]],
  ["/api-keys", ["get", "post"]],
  ["/api-keys/{id}", ["delete"]],
  ["/mcp-server", ["post"]],
  ["/openapi-spec", ["get"]],
];

Deno.test("spec.json — OpenAPI 3.1.0 header + version present", () => {
  assertEquals(doc.openapi, "3.1.0");
  assertExists(doc.info?.version);
  assertEquals(doc.info.title, "coJournalist API");
});

Deno.test("spec.json — every advertised path + method is declared", () => {
  for (const [path, methods] of REQUIRED_PATHS) {
    const node = doc.paths[path];
    if (!node) throw new Error(`missing path: ${path}`);
    for (const m of methods) {
      if (!node[m]) {
        throw new Error(`missing method on ${path}: ${m}`);
      }
    }
  }
});

Deno.test("spec.json — security schemes bearer + apikey both declared", () => {
  assertExists(doc.components.securitySchemes.bearerAuth);
  assertExists(doc.components.securitySchemes.anonKey);
});

Deno.test("spec.json — verification workflow exposed via Unit + UnitUpdate", () => {
  const unit = doc.components.schemas.Unit as { properties: Record<string, unknown> };
  for (
    const field of [
      "verified",
      "verified_by",
      "verification_notes",
      "used_in_article",
      "used_in_url",
      "used_at",
    ]
  ) {
    if (!unit.properties[field]) throw new Error(`Unit schema missing ${field}`);
  }
  const patch = doc.components.schemas.UnitUpdate as { properties: Record<string, unknown> };
  for (
    const field of [
      "verified",
      "verified_by",
      "verification_notes",
      "used_in_article",
      "used_in_url",
      "used_at",
    ]
  ) {
    if (!patch.properties[field]) throw new Error(`UnitUpdate schema missing ${field}`);
  }
});

Deno.test("spec.json — Scout schema enumerates the 4 scout types", () => {
  const scoutType = doc.components.schemas.ScoutType as { enum: string[] };
  assertEquals([...scoutType.enum].sort(), ["civic", "pulse", "social", "web"]);
});

Deno.test("spec.json — inbox filter parameters present on GET /units", () => {
  const get = doc.paths["/units"].get as { parameters: Array<{ name: string }> };
  const names = get.parameters.map((p) => p.name);
  for (const expected of ["verified", "used_in_article", "project_id", "since"]) {
    if (!names.includes(expected)) throw new Error(`GET /units missing parameter: ${expected}`);
  }
});

// ---------------------------------------------------------------------------
// Online HTTP assertion — kept for integration coverage. Skipped unless the
// local Supabase stack is reachable (tests depend on `_shared/_testing.ts`).
// ---------------------------------------------------------------------------

Deno.test({
  name: "openapi-spec HTTP: GET returns 200 application/json with openapi 3.1.0",
  ignore: !Deno.env.get("SUPABASE_URL"),
  fn: async () => {
    const res = await fetch(functionUrl("openapi-spec"), { method: "GET" });
    assertEquals(res.status, 200);
    const ct = res.headers.get("content-type") ?? "";
    assertStringIncludes(ct, "application/json");
    const body = await res.json();
    assertEquals(body.openapi, "3.1.0");
    assertExists(body.paths["/projects"]);
    assertExists(body.paths["/scouts/{id}/run"]);
  },
});
