import {
  assert,
  assertEquals,
} from "https://deno.land/std@0.208.0/assert/mod.ts";
import {
  buildBeatLocationMatcher,
  parseBeatLocation,
} from "./beat_location.ts";

Deno.test("parseBeatLocation keeps country-only selections as country scope", () => {
  const parsed = parseBeatLocation({
    displayName: "United Kingdom",
    country: "GB",
    locationType: "country",
  });

  assertEquals(parsed.city, null);
  assertEquals(parsed.country, "United Kingdom");
  assertEquals(parsed.countryCode, "GB");
});

Deno.test("parseBeatLocation keeps city selections intact", () => {
  const parsed = parseBeatLocation({
    displayName: "London, United Kingdom",
    city: "London",
    country: "GB",
    locationType: "city",
  });

  assertEquals(parsed.city, "London");
  assertEquals(parsed.countryCode, "GB");
});

Deno.test("buildBeatLocationMatcher accepts UK coverage and rejects Montreal drift", () => {
  const matcher = buildBeatLocationMatcher({
    city: null,
    country: "United Kingdom",
    countryCode: "GB",
  });

  assert(matcher);
  assert(
    matcher(
      "Government’s Local Power Plan will support renewable energy projects across England, Scotland and Wales.",
    ),
  );
  assert(
    !matcher(
      "Montreal is expanding social housing supply across Quebec as Canada revises affordability policy.",
    ),
  );
});
