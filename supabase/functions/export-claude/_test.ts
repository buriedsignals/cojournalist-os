import {
  assertEquals,
  assertStringIncludes,
} from "https://deno.land/std@0.208.0/assert/mod.ts";
import { createTestUser, functionUrl } from "../_shared/_testing.ts";

function headers(token: string): HeadersInit {
  return {
    "Authorization": `Bearer ${token}`,
  };
}

Deno.test("export-claude: unauthenticated request returns 401", async () => {
  const res = await fetch(functionUrl("export-claude"), { method: "GET" });
  await res.body?.cancel();
  assertEquals(res.status, 401);
});

Deno.test("export-claude: GET with no units returns 200 text/markdown", async () => {
  const user = await createTestUser();
  try {
    const res = await fetch(functionUrl("export-claude"), {
      headers: headers(user.token),
    });
    assertEquals(res.status, 200);
    const ct = res.headers.get("content-type") ?? "";
    assertStringIncludes(ct, "text/markdown");
    const body = await res.text();
    // Either the explicit header OR whitespace-only is acceptable per spec.
    if (body.trim().length > 0) {
      assertStringIncludes(body, "# No unused verified units");
    }
  } finally {
    await user.cleanup();
  }
});
