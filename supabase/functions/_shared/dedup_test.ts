import { assertEquals } from "https://deno.land/std@0.224.0/assert/assert_equals.ts";
import { cosineSimilarity, isWithinRunDuplicate } from "./dedup.ts";

Deno.test("cosineSimilarity: identical vectors → 1", () => {
  assertEquals(cosineSimilarity([1, 0, 0], [1, 0, 0]), 1);
});

Deno.test("cosineSimilarity: orthogonal vectors → 0", () => {
  assertEquals(cosineSimilarity([1, 0, 0], [0, 1, 0]), 0);
});

Deno.test("cosineSimilarity: mismatched length → 0", () => {
  assertEquals(cosineSimilarity([1, 2], [1, 2, 3]), 0);
});

Deno.test("cosineSimilarity: zero vector → 0", () => {
  assertEquals(cosineSimilarity([0, 0], [1, 0]), 0);
});

Deno.test("isWithinRunDuplicate: no duplicates in empty kept set", () => {
  assertEquals(isWithinRunDuplicate([1, 0, 0], []), false);
});

Deno.test("isWithinRunDuplicate: identical match caught", () => {
  assertEquals(isWithinRunDuplicate([1, 0, 0], [[1, 0, 0]]), true);
});

Deno.test("isWithinRunDuplicate: below threshold (0.75) allowed", () => {
  // ~0.7 similarity between these — below the 0.75 default
  const a = [1, 0, 0];
  const b = [0.7, 0.7142, 0];
  assertEquals(isWithinRunDuplicate(a, [b]), false);
});

Deno.test("isWithinRunDuplicate: at threshold caught", () => {
  const a = [1, 0, 0];
  const b = [0.8, 0.6, 0];
  // cosine ~= 0.8 → above 0.75 threshold
  assertEquals(isWithinRunDuplicate(a, [b]), true);
});

Deno.test("isWithinRunDuplicate: custom threshold", () => {
  const a = [1, 0, 0];
  const b = [0.9, 0.44, 0];
  // cosine ~ 0.9 → passes default 0.75 but not 0.95
  assertEquals(isWithinRunDuplicate(a, [b], 0.95), false);
  assertEquals(isWithinRunDuplicate(a, [b], 0.75), true);
});
