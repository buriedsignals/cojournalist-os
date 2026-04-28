import { assertEquals } from "https://deno.land/std@0.224.0/assert/assert_equals.ts";
import { classifyCivicQueueFailure } from "./civic_queue_state.ts";

Deno.test("classifyCivicQueueFailure retries attempts one and two", () => {
  assertEquals(classifyCivicQueueFailure(1), {
    status: "pending",
    terminal: false,
  });
  assertEquals(classifyCivicQueueFailure(2), {
    status: "pending",
    terminal: false,
  });
});

Deno.test("classifyCivicQueueFailure marks attempt three terminal", () => {
  assertEquals(classifyCivicQueueFailure(3), {
    status: "failed",
    terminal: true,
  });
  assertEquals(classifyCivicQueueFailure(4), {
    status: "failed",
    terminal: true,
  });
});
