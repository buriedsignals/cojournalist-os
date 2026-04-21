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

Deno.test("projects: unauthenticated request returns 401", async () => {
  const res = await fetch(functionUrl("projects"), { method: "GET" });
  await res.body?.cancel();
  assertEquals(res.status, 401);
});

Deno.test("projects: create + get + list + patch + delete round-trip", async () => {
  const user = await createTestUser();
  try {
    // Create
    const createRes = await fetch(functionUrl("projects"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({ name: "Housing Beat", description: "Zurich housing" }),
    });
    assertEquals(createRes.status, 201);
    const created = await createRes.json();
    assertExists(created.id);
    assertEquals(created.name, "Housing Beat");
    assertEquals(created.visibility, "private");

    // Get
    const getRes = await fetch(functionUrl("projects", `/${created.id}`), {
      headers: headers(user.token),
    });
    assertEquals(getRes.status, 200);
    const fetched = await getRes.json();
    assertEquals(fetched.id, created.id);

    // List
    const listRes = await fetch(functionUrl("projects"), { headers: headers(user.token) });
    assertEquals(listRes.status, 200);
    const listed = await listRes.json();
    assertEquals(listed.pagination.total, 1);
    assertEquals(listed.items.length, 1);
    assertEquals(listed.items[0].id, created.id);

    // Patch
    const patchRes = await fetch(functionUrl("projects", `/${created.id}`), {
      method: "PATCH",
      headers: headers(user.token),
      body: JSON.stringify({ description: "Zurich affordable-housing beat" }),
    });
    assertEquals(patchRes.status, 200);
    const patched = await patchRes.json();
    assertEquals(patched.description, "Zurich affordable-housing beat");

    // Delete
    const delRes = await fetch(functionUrl("projects", `/${created.id}`), {
      method: "DELETE",
      headers: headers(user.token),
    });
    await delRes.body?.cancel();
    assertEquals(delRes.status, 204);

    // Confirm gone
    const gone = await fetch(functionUrl("projects", `/${created.id}`), {
      headers: headers(user.token),
    });
    await gone.body?.cancel();
    assertEquals(gone.status, 404);
  } finally {
    await user.cleanup();
  }
});

Deno.test("projects: duplicate name returns 409", async () => {
  const user = await createTestUser();
  try {
    const first = await fetch(functionUrl("projects"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({ name: "Dup" }),
    });
    assertEquals(first.status, 201);
    const firstBody = await first.json();

    const second = await fetch(functionUrl("projects"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({ name: "Dup" }),
    });
    assertEquals(second.status, 409);
    await second.body?.cancel();

    // Cleanup: delete the first to avoid leak (user.cleanup also cascades)
    await fetch(functionUrl("projects", `/${firstBody.id}`), {
      method: "DELETE",
      headers: headers(user.token),
    }).then((r) => r.body?.cancel());
  } finally {
    await user.cleanup();
  }
});

Deno.test("projects: invalid body returns 400", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(functionUrl("projects"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({ visibility: "wrong-value" }),
    });
    assertEquals(res.status, 400);
    await res.body?.cancel();
  } finally {
    await user.cleanup();
  }
});
