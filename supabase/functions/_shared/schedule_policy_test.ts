import { assertEquals } from "https://deno.land/std@0.208.0/assert/mod.ts";
import {
  cronIsNoMoreFrequentThanWeekly,
  schedulePolicyError,
} from "./schedule_policy.ts";

Deno.test("schedule policy accepts weekly and monthly beat schedules", () => {
  assertEquals(schedulePolicyError("beat", "weekly", "0 8 * * 1"), null);
  assertEquals(schedulePolicyError("beat", "monthly", "0 8 1 * *"), null);
  assertEquals(schedulePolicyError("beat", undefined, "@weekly"), null);
});

Deno.test("schedule policy rejects daily beat schedules", () => {
  assertEquals(
    schedulePolicyError("beat", "daily", "0 8 * * *"),
    "beat scouts support weekly or monthly schedules only",
  );
  assertEquals(
    schedulePolicyError("beat", undefined, "0 8 * * *"),
    "beat scouts support weekly or monthly schedules only",
  );
  assertEquals(cronIsNoMoreFrequentThanWeekly("@daily"), false);
});

Deno.test("schedule policy keeps non-beat scouts unchanged", () => {
  assertEquals(schedulePolicyError("web", "daily", "0 8 * * *"), null);
  assertEquals(schedulePolicyError("social", "daily", "0 8 * * *"), null);
});
