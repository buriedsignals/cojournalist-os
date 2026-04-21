import {
  assertEquals,
  assertExists,
  assertStringIncludes,
} from "https://deno.land/std@0.208.0/assert/mod.ts";
import { functionUrl } from "../_shared/_testing.ts";

Deno.test("openapi-spec: GET returns 200 application/json with openapi 3.1.0", async () => {
  const res = await fetch(functionUrl("openapi-spec"), { method: "GET" });
  assertEquals(res.status, 200);
  const ct = res.headers.get("content-type") ?? "";
  assertStringIncludes(ct, "application/json");
  const spec = await res.json();
  assertEquals(spec.openapi, "3.1.0");
  assertExists(spec.paths["/projects"]);
});
