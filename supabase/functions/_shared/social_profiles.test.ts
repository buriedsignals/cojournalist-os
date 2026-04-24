import { assertEquals } from "https://deno.land/std@0.208.0/assert/mod.ts";

import {
  buildSocialProfileUrl,
  classifyProfileProbeStatus,
  looksLikeMissingProfileError,
  normalizeSocialHandle,
} from "./social_profiles.ts";

Deno.test("normalizeSocialHandle preserves a bare Instagram handle", () => {
  assertEquals(
    normalizeSocialHandle("instagram", "buriedsignals"),
    "buriedsignals",
  );
});

Deno.test("normalizeSocialHandle strips social profile URLs", () => {
  assertEquals(
    normalizeSocialHandle(
      "instagram",
      "https://www.instagram.com/buriedsignals/",
    ),
    "buriedsignals",
  );
  assertEquals(
    normalizeSocialHandle("x", "https://twitter.com/buriedsignals"),
    "buriedsignals",
  );
  assertEquals(
    normalizeSocialHandle("tiktok", "https://www.tiktok.com/@buriedsignals"),
    "buriedsignals",
  );
});

Deno.test("buildSocialProfileUrl builds canonical URLs from handles", () => {
  assertEquals(
    buildSocialProfileUrl("instagram", "buriedsignals"),
    "https://www.instagram.com/buriedsignals/",
  );
  assertEquals(
    buildSocialProfileUrl("x", "@buriedsignals"),
    "https://x.com/buriedsignals",
  );
});

Deno.test("classifyProfileProbeStatus keeps anti-bot responses inconclusive", () => {
  assertEquals(classifyProfileProbeStatus(200), "exists");
  assertEquals(classifyProfileProbeStatus(302), "exists");
  assertEquals(classifyProfileProbeStatus(404), "missing");
  assertEquals(classifyProfileProbeStatus(403), "uncertain");
  assertEquals(classifyProfileProbeStatus(429), "uncertain");
});

Deno.test("looksLikeMissingProfileError matches not-found/private failures", () => {
  assertEquals(looksLikeMissingProfileError("Profile not found"), true);
  assertEquals(
    looksLikeMissingProfileError("username does not exist on Instagram"),
    true,
  );
  assertEquals(
    looksLikeMissingProfileError("Apify actor timed out after 120 seconds"),
    false,
  );
});
