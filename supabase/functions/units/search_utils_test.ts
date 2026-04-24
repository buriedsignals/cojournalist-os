import {
  assertEquals,
} from "https://deno.land/std@0.208.0/assert/mod.ts";
import {
  buildSearchMatchInfo,
  filterPreciseSearchResults,
  isPreciseSearchQuery,
  matchingKeywordFields,
  unitHasKeywordHit,
} from "./search_utils.ts";

Deno.test("isPreciseSearchQuery treats single proper-name token as precise", () => {
  assertEquals(isPreciseSearchQuery("Sourias"), true);
  assertEquals(isPreciseSearchQuery("221"), true);
  assertEquals(isPreciseSearchQuery("housing affordability"), false);
});

Deno.test("unitHasKeywordHit matches scout names and statements", () => {
  assertEquals(
    unitHasKeywordHit("Sourias", {
      statement: "Councilmember Sourias introduced the motion.",
      scout_name: "City Hall",
    }),
    true,
  );
  assertEquals(
    unitHasKeywordHit("Sourias", {
      statement: "Police investigate two homicide incidents.",
      scout_name: "Crime desk",
    }),
    false,
  );
});

Deno.test("matchingKeywordFields identifies statement, source, and scout hits", () => {
  assertEquals(
    matchingKeywordFields("Sourias 221", {
      statement: "Councilmember Sourias introduced the motion.",
      source: { title: "Agenda item 221", domain: "city.gov" },
      scout_name: "City Hall",
    }),
    ["statement", "source"],
  );
});

Deno.test("filterPreciseSearchResults drops semantic neighbors without keyword hit", () => {
  const filtered = filterPreciseSearchResults("Sourias", [
    { statement: "Police investigate two homicide incidents." },
    { statement: "Councilmember Sourias introduced the motion." },
  ]);
  assertEquals(filtered.length, 1);
  assertEquals(filtered[0].statement, "Councilmember Sourias introduced the motion.");
});

Deno.test("buildSearchMatchInfo marks direct keyword hits", () => {
  const match = buildSearchMatchInfo(
    "Sourias",
    { statement: "Councilmember Sourias introduced the motion." },
    0.81,
  );
  assertEquals(match.category, "direct");
  assertEquals(match.below_interest_threshold, false);
});

Deno.test("buildSearchMatchInfo marks strong semantic-only hits as related", () => {
  const match = buildSearchMatchInfo(
    "housing reform",
    { statement: "Council expands zoning affordability incentives." },
    0.78,
  );
  assertEquals(match.category, "related");
  assertEquals(match.below_interest_threshold, false);
});

Deno.test("buildSearchMatchInfo marks weak semantic-only hits as loose", () => {
  const match = buildSearchMatchInfo(
    "housing reform",
    { statement: "School board discusses lunch staffing." },
    0.77,
  );
  assertEquals(match.category, "loose");
  assertEquals(match.below_interest_threshold, true);
});
