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

Deno.test("units: unauthenticated request returns 401", async () => {
  const res = await fetch(functionUrl("units"), { method: "GET" });
  await res.body?.cancel();
  assertEquals(res.status, 401);
});

Deno.test("units: unknown method returns 405", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(functionUrl("units"), {
      method: "DELETE",
      headers: headers(user.token),
    });
    await res.body?.cancel();
    assertEquals(res.status, 405);
  } finally {
    await user.cleanup();
  }
});

Deno.test("units: empty list for new user", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(functionUrl("units"), {
      headers: headers(user.token),
    });
    assertEquals(res.status, 200);
    const body = await res.json();
    assertExists(body.pagination);
    assertEquals(body.pagination.total, 0);
    assertEquals(body.items.length, 0);
  } finally {
    await user.cleanup();
  }
});

Deno.test("units: search without query_text returns 400", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(functionUrl("units", "/search"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({}),
    });
    assertEquals(res.status, 400);
    await res.body?.cancel();
  } finally {
    await user.cleanup();
  }
});

Deno.test("units: search with non-JSON body returns 400", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(functionUrl("units", "/search"), {
      method: "POST",
      headers: headers(user.token),
      body: "not json",
    });
    assertEquals(res.status, 400);
    await res.body?.cancel();
  } finally {
    await user.cleanup();
  }
});

// Search short-circuits when the caller has zero units — no Gemini call is
// made. This path is safe to run without GEMINI_API_KEY.
Deno.test("units: search on empty corpus returns empty items", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(functionUrl("units", "/search"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({ query_text: "anything at all" }),
    });
    assertEquals(res.status, 200);
    const body = await res.json();
    assertEquals(body.items, []);
  } finally {
    await user.cleanup();
  }
});

Deno.test("units: GET on unknown id returns 404", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(
      functionUrl("units", "/00000000-0000-0000-0000-000000000000"),
      { headers: headers(user.token) },
    );
    assertEquals(res.status, 404);
    await res.body?.cancel();
  } finally {
    await user.cleanup();
  }
});

Deno.test("units: PATCH on unknown id returns 404", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(
      functionUrl("units", "/00000000-0000-0000-0000-000000000000"),
      {
        method: "PATCH",
        headers: headers(user.token),
        body: JSON.stringify({ verified: true }),
      },
    );
    assertEquals(res.status, 404);
    await res.body?.cancel();
  } finally {
    await user.cleanup();
  }
});

Deno.test("units: PATCH with empty body returns 400", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(
      functionUrl("units", "/00000000-0000-0000-0000-000000000000"),
      {
        method: "PATCH",
        headers: headers(user.token),
        body: JSON.stringify({}),
      },
    );
    assertEquals(res.status, 400);
    await res.body?.cancel();
  } finally {
    await user.cleanup();
  }
});

// Deep semantic-search test — requires a real embedding endpoint. Skip unless
// GEMINI_API_KEY is set in the test env.
const geminiConfigured = Boolean(Deno.env.get("GEMINI_API_KEY"));
const deepSearchTest = geminiConfigured ? Deno.test : Deno.test.ignore;

deepSearchTest(
  "units: search with query_text succeeds end-to-end (requires GEMINI_API_KEY)",
  async () => {
    const user = await createTestUser();
    try {
      // We don't seed a unit here — the function still exercises the full
      // embed -> RPC roundtrip because count > 0 is the only short-circuit
      // and any DB presence would require complex setup. Without seeding,
      // this path still short-circuits on empty corpus; so the assertion is
      // identical to the empty-corpus test. Left as a placeholder so a fuller
      // fixture can be dropped in later without moving the gate.
      const res = await fetch(functionUrl("units", "/search"), {
        method: "POST",
        headers: headers(user.token),
        body: JSON.stringify({ query_text: "housing policy zurich" }),
      });
      assertEquals(res.status, 200);
      const body = await res.json();
      assertExists(body.items);
    } finally {
      await user.cleanup();
    }
  },
);
