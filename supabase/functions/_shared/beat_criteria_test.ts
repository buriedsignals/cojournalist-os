import {
  assertMatch,
  assertStringIncludes,
} from "https://deno.land/std@0.208.0/assert/mod.ts";
import { buildBeatCriteriaRule } from "./beat_criteria.ts";

Deno.test("buildBeatCriteriaRule tightens policy-oriented criteria", () => {
  const rule = buildBeatCriteriaRule("housing policy");
  assertStringIncludes(rule, "policy");
  assertStringIncludes(rule, "government decisions");
  assertStringIncludes(rule, "market statistics");
});

Deno.test("buildBeatCriteriaRule still tightens non-policy topic criteria", () => {
  const rule = buildBeatCriteriaRule("renewable energy");
  assertMatch(rule, /primary subject/i);
});
