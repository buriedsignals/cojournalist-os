import {
  assertEquals,
  assertExists,
  assertMatch,
} from "https://deno.land/std@0.208.0/assert/mod.ts";
import { createTestUser, functionUrl } from "../_shared/_testing.ts";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function headers(token: string): HeadersInit {
  return {
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

Deno.test("scouts: unauthenticated request returns 401", async () => {
  const res = await fetch(functionUrl("scouts"), { method: "GET" });
  await res.body?.cancel();
  assertEquals(res.status, 401);
});

Deno.test("scouts: create + get + list + patch + delete round-trip", async () => {
  const user = await createTestUser();
  try {
    // Create
    const createRes = await fetch(functionUrl("scouts"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({
        name: "Test Scout",
        type: "web",
        url: "https://example.com",
      }),
    });
    assertEquals(createRes.status, 201);
    const created = await createRes.json();
    assertExists(created.id);
    assertMatch(created.id, UUID_RE);
    assertEquals(created.name, "Test Scout");
    assertEquals(created.type, "web");
    assertEquals(created.url, "https://example.com");
    assertEquals(created.is_active, false); // no schedule_cron -> inactive
    assertEquals(created.last_run, null);

    // Get
    const getRes = await fetch(
      functionUrl("scouts", `/${created.id}`),
      { headers: headers(user.token) },
    );
    assertEquals(getRes.status, 200);
    const fetched = await getRes.json();
    assertEquals(fetched.id, created.id);
    assertEquals(fetched.name, "Test Scout");

    // List
    const listRes = await fetch(functionUrl("scouts"), {
      headers: headers(user.token),
    });
    assertEquals(listRes.status, 200);
    const listed = await listRes.json();
    assertEquals(listed.pagination.total, 1);
    assertEquals(listed.items.length, 1);
    assertEquals(listed.items[0].id, created.id);

    // Patch
    const patchRes = await fetch(
      functionUrl("scouts", `/${created.id}`),
      {
        method: "PATCH",
        headers: headers(user.token),
        body: JSON.stringify({ criteria: "housing evictions" }),
      },
    );
    assertEquals(patchRes.status, 200);
    const patched = await patchRes.json();
    assertEquals(patched.criteria, "housing evictions");

    // Delete
    const delRes = await fetch(
      functionUrl("scouts", `/${created.id}`),
      {
        method: "DELETE",
        headers: headers(user.token),
      },
    );
    await delRes.body?.cancel();
    assertEquals(delRes.status, 204);

    // Confirm gone
    const gone = await fetch(
      functionUrl("scouts", `/${created.id}`),
      { headers: headers(user.token) },
    );
    await gone.body?.cancel();
    assertEquals(gone.status, 404);
  } finally {
    await user.cleanup();
  }
});

Deno.test("scouts: POST /:id/run returns 202 with run_id UUID", async () => {
  const user = await createTestUser();
  try {
    const createRes = await fetch(functionUrl("scouts"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({
        name: "Runnable Scout",
        type: "web",
        url: "https://example.com",
      }),
    });
    assertEquals(createRes.status, 201);
    const created = await createRes.json();

    const runRes = await fetch(
      functionUrl("scouts", `/${created.id}/run`),
      {
        method: "POST",
        headers: headers(user.token),
      },
    );
    assertEquals(runRes.status, 202);
    const runBody = await runRes.json();
    assertEquals(runBody.scout_id, created.id);
    assertExists(runBody.run_id);
    assertMatch(runBody.run_id, UUID_RE);

    // Cleanup
    await fetch(functionUrl("scouts", `/${created.id}`), {
      method: "DELETE",
      headers: headers(user.token),
    }).then((r) => r.body?.cancel());
  } finally {
    await user.cleanup();
  }
});

Deno.test("scouts: 404 on unknown scout id", async () => {
  const user = await createTestUser();
  try {
    const missing = "00000000-0000-0000-0000-000000000000";
    const res = await fetch(functionUrl("scouts", `/${missing}`), {
      headers: headers(user.token),
    });
    await res.body?.cancel();
    assertEquals(res.status, 404);
  } finally {
    await user.cleanup();
  }
});

Deno.test("scouts: 400 on invalid scout type", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(functionUrl("scouts"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({
        name: "Bad Type Scout",
        type: "not-a-real-type",
        url: "https://example.com",
      }),
    });
    assertEquals(res.status, 400);
    await res.body?.cancel();
  } finally {
    await user.cleanup();
  }
});
