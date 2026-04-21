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

Deno.test("entities: unauthenticated request returns 401", async () => {
  const res = await fetch(functionUrl("entities"), { method: "GET" });
  await res.body?.cancel();
  assertEquals(res.status, 401);
});

Deno.test("entities: create + list + get round-trip", async () => {
  const user = await createTestUser();
  try {
    // Create
    const createRes = await fetch(functionUrl("entities"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({
        canonical_name: "Jane Doe",
        type: "person",
        aliases: ["J. Doe"],
        metadata: { role: "subject" },
      }),
    });
    assertEquals(createRes.status, 201);
    const created = await createRes.json();
    assertExists(created.id);
    assertEquals(created.canonical_name, "Jane Doe");
    assertEquals(created.type, "person");
    assertEquals(created.aliases, ["J. Doe"]);

    // List
    const listRes = await fetch(functionUrl("entities"), {
      headers: headers(user.token),
    });
    assertEquals(listRes.status, 200);
    const listed = await listRes.json();
    assertEquals(listed.pagination.total, 1);
    assertEquals(listed.items.length, 1);
    assertEquals(listed.items[0].id, created.id);

    // Get (with empty mentions)
    const getRes = await fetch(functionUrl("entities", `/${created.id}`), {
      headers: headers(user.token),
    });
    assertEquals(getRes.status, 200);
    const fetched = await getRes.json();
    assertEquals(fetched.id, created.id);
    assertEquals(fetched.mentions, []);
  } finally {
    await user.cleanup();
  }
});

Deno.test("entities: duplicate (canonical_name, type) returns 409", async () => {
  const user = await createTestUser();
  try {
    const first = await fetch(functionUrl("entities"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({ canonical_name: "Acme Corp", type: "org" }),
    });
    assertEquals(first.status, 201);
    await first.body?.cancel();

    const second = await fetch(functionUrl("entities"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({ canonical_name: "Acme Corp", type: "org" }),
    });
    assertEquals(second.status, 409);
    await second.body?.cancel();
  } finally {
    await user.cleanup();
  }
});

Deno.test("entities: merge collapses sources into keeper", async () => {
  const user = await createTestUser();
  try {
    async function mkEntity(name: string): Promise<string> {
      const r = await fetch(functionUrl("entities"), {
        method: "POST",
        headers: headers(user.token),
        body: JSON.stringify({ canonical_name: name, type: "person" }),
      });
      assertEquals(r.status, 201);
      const body = await r.json();
      return body.id as string;
    }

    const a = await mkEntity("Alpha");
    const b = await mkEntity("Beta");
    const c = await mkEntity("Gamma");

    // Merge B + C into A
    const mergeRes = await fetch(functionUrl("entities", "/merge"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({ keep_id: a, merge_ids: [b, c] }),
    });
    assertEquals(mergeRes.status, 200);
    const mergeBody = await mergeRes.json();
    assertEquals(mergeBody.merged, 2);

    // List — only A remains
    const listRes = await fetch(functionUrl("entities"), {
      headers: headers(user.token),
    });
    assertEquals(listRes.status, 200);
    const listed = await listRes.json();
    assertEquals(listed.pagination.total, 1);
    assertEquals(listed.items.length, 1);
    assertEquals(listed.items[0].id, a);

    // B and C return 404
    for (const gone of [b, c]) {
      const r = await fetch(functionUrl("entities", `/${gone}`), {
        headers: headers(user.token),
      });
      await r.body?.cancel();
      assertEquals(r.status, 404);
    }
  } finally {
    await user.cleanup();
  }
});

Deno.test("entities: merge with missing body fields returns 400", async () => {
  const user = await createTestUser();
  try {
    // Missing merge_ids entirely
    const res1 = await fetch(functionUrl("entities", "/merge"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({ keep_id: "00000000-0000-0000-0000-000000000000" }),
    });
    assertEquals(res1.status, 400);
    await res1.body?.cancel();

    // Empty merge_ids array
    const res2 = await fetch(functionUrl("entities", "/merge"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({
        keep_id: "00000000-0000-0000-0000-000000000000",
        merge_ids: [],
      }),
    });
    assertEquals(res2.status, 400);
    await res2.body?.cancel();

    // Missing keep_id
    const res3 = await fetch(functionUrl("entities", "/merge"), {
      method: "POST",
      headers: headers(user.token),
      body: JSON.stringify({
        merge_ids: ["00000000-0000-0000-0000-000000000001"],
      }),
    });
    assertEquals(res3.status, 400);
    await res3.body?.cancel();
  } finally {
    await user.cleanup();
  }
});
