import {
  assertEquals,
  assertExists,
} from "https://deno.land/std@0.208.0/assert/mod.ts";
import { createTestUser, functionUrl } from "../_shared/_testing.ts";

function headers(token: string): HeadersInit {
  return {
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

Deno.test("user: unauthenticated /me returns 401", async () => {
  const res = await fetch(functionUrl("user", "/me"), { method: "GET" });
  await res.body?.cancel();
  assertEquals(res.status, 401);
});

Deno.test("user: GET /me returns id + email", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(functionUrl("user", "/me"), {
      headers: headers(user.token),
    });
    assertEquals(res.status, 200);
    const body = await res.json();
    assertEquals(body.id, user.id);
    assertEquals(body.email, user.email);
  } finally {
    await user.cleanup();
  }
});

Deno.test("user: GET /preferences returns {} when no row exists", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(functionUrl("user", "/preferences"), {
      headers: headers(user.token),
    });
    assertEquals(res.status, 200);
    const body = await res.json();
    assertEquals(body, {});
  } finally {
    await user.cleanup();
  }
});

Deno.test("user: PATCH /preferences upserts and returns the row", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(functionUrl("user", "/preferences"), {
      method: "PATCH",
      headers: headers(user.token),
      body: JSON.stringify({
        timezone: "Europe/Zurich",
        language: "en",
        theme: "dark",
      }),
    });
    assertEquals(res.status, 200);
    const body = await res.json();
    assertExists(body.user_id);
    assertEquals(body.user_id, user.id);
    assertEquals(body.timezone, "Europe/Zurich");
    assertEquals(body.preferred_language, "en");
    assertEquals(body.preferences?.theme, "dark");
  } finally {
    await user.cleanup();
  }
});

Deno.test("user: POST /onboarding-complete flips the flag", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(functionUrl("user", "/onboarding-complete"), {
      method: "POST",
      headers: headers(user.token),
    });
    assertEquals(res.status, 200);
    const body = await res.json();
    assertEquals(body.onboarding_completed, true);
  } finally {
    await user.cleanup();
  }
});
